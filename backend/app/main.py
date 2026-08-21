from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import bcrypt

from app.db.session import get_db
from app.db.models import User, PendingAction, Order, Ticket, Escalation
from app.auth.deps import get_current_user, RoleChecker
from app.auth.jwt import create_access_token
from app.agent.orchestration import AgentService
from app.tools.proactive_signals import get_operational_signals
from app.config import SNAPSHOT_DATETIME

app = FastAPI(title="ParcelPilot Customer Support AI System API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class LoginRequest(BaseModel):
    email: str
    password: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    chat_history: list[ChatMessage]

class ConfirmRequest(BaseModel):
    proposal_id: int

@app.post("/auth/mock-login")
def mock_login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    # Validate bcrypt password match
    hashed_pwd = user.password_hash.encode('utf-8')
    if not bcrypt.checkpw(req.password.encode('utf-8'), hashed_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
        
    # Generate token
    token = create_access_token({"sub": user.user_id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role,
            "account_id": user.account_id,
            "full_name": user.full_name
        }
    }

@app.post("/chat")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Convert history structure to raw list[dict]
    history_list = []
    for h in req.chat_history:
        history_list.append({
            "role": h.role,
            "content": h.content
        })
        
    agent = AgentService(db, current_user)
    result = agent.run_agent_loop(history_list, req.message)
    return result

@app.post("/chat/confirm")
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

@app.get("/insights")
def insights(
    current_user: User = Depends(RoleChecker(["internal_support", "internal_lead"])),
    db: Session = Depends(get_db)
):
    stats = get_operational_signals(db, current_user)
    return stats
