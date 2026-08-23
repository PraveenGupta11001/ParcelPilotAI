import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import User, PendingAction, Order, Ticket, Escalation, ChatSession, ChatMessage
from app.auth.deps import get_current_user
from app.schemas.chat import ChatRequest, ConfirmRequest, CreateSessionRequest
from app.agent.orchestration import AgentService, RateLimitExceededException
from app.config import SNAPSHOT_DATETIME

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Processes a conversational user message through the AI agent loop.

    Creates/initializes a new chat session if session_id is omitted. Appends messages
    to history before running the agent orchestrator.

    Args:
        req: ChatRequest schema containing message description and history list.
        current_user: Authenticated caller user object.
        db: Database session.

    Returns:
        dict: A dictionary containing the text response, tool calls list, and session_id.

    Raises:
        HTTPException: 404 if the session ID is not found, or 403 authorization violation.
    """
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
    db.commit()

    if req.stream:
        # Capture critical user state parameters before the API session expires
        caller_user_id = current_user.user_id
        
        def stream_generator():
            from app.db.session import SessionLocal
            gen_db = SessionLocal()
            try:
                # Retrieve a fresh user instance tied to this generator's session context
                fresh_user = gen_db.query(User).filter(User.user_id == caller_user_id).first()
                if not fresh_user:
                    return

                stream_agent = AgentService(gen_db, fresh_user)
                if not req.session_id:
                    yield f"data: {json.dumps({'event': 'session_created', 'session_id': session_id})}\n\n"
                
                final_text = ""
                for step in stream_agent.run_agent_stream(history_list, req.message):
                    yield f"data: {json.dumps(step)}\n\n"
                    if step.get("event") == "done":
                        final_text = step.get("text_response", "")

                # Save response to history
                tool_calls_str = json.dumps(stream_agent.trace) if stream_agent.trace else None
                bot_msg_db = ChatMessage(
                    session_id=session_id,
                    sender="bot",
                    text=final_text,
                    tool_calls=tool_calls_str,
                    created_at=SNAPSHOT_DATETIME
                )
                gen_db.add(bot_msg_db)
                
                # Fetch and update active chat session
                db_session = gen_db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if db_session:
                    db_session.updated_at = SNAPSHOT_DATETIME
                gen_db.commit()
            except RateLimitExceededException as rle:
                error_text = str(rle)
                yield f"data: {json.dumps({'event': 'text', 'text': error_text})}\n\n"
                yield f"data: {json.dumps({'event': 'done', 'text_response': error_text, 'tool_calls': stream_agent.trace})}\n\n"
                
                tool_calls_str = json.dumps(stream_agent.trace) if stream_agent.trace else None
                bot_msg_db = ChatMessage(
                    session_id=session_id,
                    sender="bot",
                    text=error_text,
                    tool_calls=tool_calls_str,
                    created_at=SNAPSHOT_DATETIME
                )
                gen_db.add(bot_msg_db)
                
                db_session = gen_db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if db_session:
                    db_session.updated_at = SNAPSHOT_DATETIME
                gen_db.commit()
            except Exception as e:
                yield f"data: {json.dumps({'event': 'status', 'message': f'Internal agent error: {str(e)}'})}\n\n"
            finally:
                gen_db.close()

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )

    # Synchronous non-streaming path
    agent = AgentService(db, current_user)
    try:
        result = agent.run_agent_loop(history_list, req.message)
        text_response = result.get("text_response", "")
        tool_calls = result.get("tool_calls")
    except RateLimitExceededException as rle:
        text_response = str(rle)
        tool_calls = agent.trace
        
    tool_calls_str = json.dumps(tool_calls) if tool_calls else None
    bot_msg_db = ChatMessage(
        session_id=session_id,
        sender="bot",
        text=text_response,
        tool_calls=tool_calls_str,
        created_at=SNAPSHOT_DATETIME
    )
    db.add(bot_msg_db)
    db.commit()

    return {
        "text_response": text_response,
        "tool_calls": tool_calls,
        "session_id": session_id
    }
@router.post("/confirm")
def chat_confirm(
    req: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Finalizes and executes a proposed pending customer support action.

    Validates user scopes and manager verification constraints on credit transfers.
    Updates DB states for orders, tickets, and escalations accordingly.

    Args:
        req: ConfirmRequest schema enclosing the target proposal_id.
        current_user: Authenticated caller.
        db: Database session.

    Returns:
        dict: Confirmation status, completion description string, and completed action fields.

    Raises:
        HTTPException: 404 if the proposal ID does not exist, 400 if already processed, and
                       403/Forbidden if security bounds and lead credit permissions check fail.
    """
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
    """Retrieves all chat sessions initiated by the authenticated user.

    Args:
        current_user: Authenticated caller.
        db: Database session.

    Returns:
        list: A list of serialized chat session dictionaries ordered by last update.
    """
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
    """Creates a new empty chat session with a custom user-defined title.

    Args:
        req: CreateSessionRequest containing the new session title.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        dict: The created chat session record attributes.
    """
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
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a specified chat session.

    Enforces ownership permissions check (customers may only delete their own sessions).

    Args:
        session_id: Numeric session ID.
        current_user: Authenticated caller.
        db: Database session.

    Returns:
        dict: A success message status payload.

    Raises:
        HTTPException: 404 if not found, 403 if user lacks access rights.
    """
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
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the message history list for a specified chat session.

    Args:
        session_id: Numeric session ID.
        current_user: Authenticated caller.
        db: Database session.

    Returns:
        list: Messages containing sender tags, text value, tool calls trace, and timestamps.

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    if session.user_id != current_user.user_id and current_user.role == "customer":
        raise HTTPException(status_code=403, detail="Access denied: Cannot read other users' sessions.")
        
    messages_out = []
    for m in session.messages:
        tcs = None
        if m.tool_calls:
            try:
                tcs = json.loads(m.tool_calls)
                if isinstance(tcs, list):
                    for tc in tcs:
                        if tc.get("tool_name") == "propose_action" or tc.get("name") == "propose_action":
                            output_field = tc.get("output")
                            if output_field:
                                try:
                                    if isinstance(output_field, str):
                                        output_dict = json.loads(output_field)
                                    else:
                                        output_dict = output_field
                                        
                                    p_id = output_dict.get("proposal_id")
                                    if p_id:
                                        action_rec = db.query(PendingAction).filter(PendingAction.id == p_id).first()
                                        if action_rec:
                                            output_dict["status"] = action_rec.status
                                            if isinstance(output_field, str):
                                                tc["output"] = json.dumps(output_dict)
                                            else:
                                                tc["output"] = output_dict
                                except Exception as inner_ex:
                                    pass
            except Exception as ex:
                tcs = None
                
        messages_out.append({
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "tool_calls": tcs,
            "created_at": m.created_at
        })
        
    return messages_out
