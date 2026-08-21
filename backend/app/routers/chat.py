import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import User, PendingAction, Order, Ticket, Escalation, ChatSession, ChatMessage
from app.auth.deps import get_current_user
from app.schemas.chat import ChatRequest, ConfirmRequest, CreateSessionRequest
from app.agent.orchestration import AgentService
from app.config import SNAPSHOT_DATETIME

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_id = req.session_id
    
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        if session.user_id != current_user.user_id and current_user.role == "customer":
            raise HTTPException(status_code=403, detail="Access denied: Cannot chat in other users' sessions.")
    else:
        title = req.message[:30] + ("..." if len(req.message) > 30 else "")
        session = ChatSession(
            user_id=current_user.user_id,
            title=title,
            created_at=SNAPSHOT_DATETIME,
            updated_at=SNAPSHOT_DATETIME
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

    user_msg_db = ChatMessage(
        session_id=session_id,
        sender="user",
        text=req.message,
        created_at=SNAPSHOT_DATETIME
    )
    db.add(user_msg_db)
    
    history_list = []
    if req.chat_history:
        for h in req.chat_history:
            history_list.append({
                "role": h.role,
                "content": h.content
            })
    else:
        all_msgs = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.id != user_msg_db.id
        ).order_by(ChatMessage.created_at.asc()).all()
        for m in all_msgs:
            role = "user" if m.sender == "user" else "assistant"
            history_list.append({
                "role": role,
                "content": m.text
            })

    session.updated_at = SNAPSHOT_DATETIME

    agent = AgentService(db, current_user)
    result = agent.run_agent_loop(history_list, req.message)

    tool_calls_str = json.dumps(result.get("tool_calls")) if result.get("tool_calls") else None
    bot_msg_db = ChatMessage(
        session_id=session_id,
        sender="bot",
        text=result.get("text_response", ""),
        tool_calls=tool_calls_str,
        created_at=SNAPSHOT_DATETIME
    )
    db.add(bot_msg_db)
    db.commit()

    return {
        "text_response": result.get("text_response", ""),
        "tool_calls": result.get("tool_calls"),
        "session_id": session_id
    }


@router.post("/confirm")
def chat_confirm(
    req: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    action = db.query(PendingAction).filter(PendingAction.id == req.proposal_id).first()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal action {req.proposal_id} not found."
        )
        
    if action.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action proposal has already been processed: status is {action.status}."
        )

    # 1. Enforce Customer Role Scoping boundaries
    if current_user.role == "customer":
        # Customers can ONLY approve their own proposals
        if action.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security violation: Cannot approve actions proposed by other users."
            )
        # Customers CANNOT approve service credit adjustments
        if action.action_type == "ISSUE_CREDIT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Service credit issue proposals require internal support or manager authorization."
            )

    # 2. Enforce Service Credit Approval Limits (>1000 INR specifies internal_lead only)
    if action.action_type == "ISSUE_CREDIT":
        if action.amount and action.amount > 1000.0:
            if current_user.role != "internal_lead":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Credit adjustments exceeding INR 1,000 require manager (lead) approval."
                )

    # 3. Apply state mutation transitions
    action.status = "APPROVED"
    
    if action.action_type == "CANCEL_ORDER":
        order = db.query(Order).filter(Order.order_id == action.order_id).first()
        if order:
            order.status = "CANCELLED"
            order.cancellation_requested_at = SNAPSHOT_DATETIME
            order.notes = (order.notes or "") + f"\nCancelled via Proposal #{action.id} by {current_user.user_id}."
            
    elif action.action_type == "ISSUE_CREDIT":
        ticket = db.query(Ticket).filter(Ticket.ticket_id == action.ticket_id).first()
        if ticket:
            ticket.status = "RESOLVED"
            ticket.historical_resolution = (ticket.historical_resolution or "") + f"\nService credit of INR {action.amount} approved under proposal #{action.id}."
            
        esc = Escalation(
            ticket_id=action.ticket_id,
            user_id=current_user.user_id,
            reason=action.reason,
            amount=action.amount,
            status="APPROVED",
            created_at=SNAPSHOT_DATETIME
        )
        db.add(esc)
        
    elif action.action_type == "ESCALATE_TICKET":
        ticket = db.query(Ticket).filter(Ticket.ticket_id == action.ticket_id).first()
        if ticket:
            ticket.status = "ESCALATED"
            
        esc = Escalation(
            ticket_id=action.ticket_id,
            user_id=current_user.user_id,
            reason=action.reason,
            status="APPROVED",
            created_at=SNAPSHOT_DATETIME
        )
        db.add(esc)

    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully finalized and executed {action.action_type} for proposal #{action.id}.",
        "action": {
            "proposal_id": action.id,
            "action_type": action.action_type,
            "status": action.status,
            "order_id": action.order_id,
            "ticket_id": action.ticket_id,
            "amount": action.amount
        }
    }


@router.get("/sessions")
def get_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.user_id).order_by(ChatSession.updated_at.desc()).all()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        }
        for s in sessions
    ]


@router.post("/sessions")
def create_session(
    req: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = ChatSession(
        user_id=current_user.user_id,
        title=req.title,
        created_at=SNAPSHOT_DATETIME,
        updated_at=SNAPSHOT_DATETIME
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    if session.user_id != current_user.user_id and current_user.role == "customer":
        raise HTTPException(status_code=403, detail="Not authorized to delete this session.")
        
    db.delete(session)
    db.commit()
    return {"success": True, "message": "Chat session deleted."}


@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    if session.user_id != current_user.user_id and current_user.role == "customer":
        raise HTTPException(status_code=403, detail="Access denied: Cannot read other users' sessions.")
        
    return [
        {
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "tool_calls": json.loads(m.tool_calls) if m.tool_calls else None,
            "created_at": m.created_at
        }
        for m in session.messages
    ]
