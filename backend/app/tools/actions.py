from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.db.models import User, PendingAction, Order, Ticket
from app.tools.structured_data import calculate_order_metrics

def propose_action(
    db: Session,
    user: User,
    action_type: str,  # CANCEL_ORDER, ISSUE_CREDIT, ESCALATE_TICKET
    reason: str,
    order_id: str = None,
    ticket_id: str = None,
    amount: float = None
) -> dict:
    """
    Proposes an action and stores it in the database in a PENDING state.
    Enforces security boundaries:
    - Customer users can only propose actions for orders/tickets belonging to their own account.
    - Performs validation against policy rules.
    """
    action_type = action_type.upper()
    
    # 1. Enforce row-level security for inputs
    if order_id:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found."
            )
        if user.role == "customer" and order.account_id != user.account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security violation: Cannot propose actions on orders outside your account."
            )
            
    if ticket_id:
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found."
            )
        if user.role == "customer" and ticket.account_id != user.account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security violation: Cannot propose actions on tickets outside your account."
            )

    # 2. Policy validaton at proposal time
    if action_type == "CANCEL_ORDER":
        if not order_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order ID required for cancellation.")
        # Calculate fee
        metrics = calculate_order_metrics(order, "cancellation")
        if not metrics["cancellable"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order is not cancellable: {metrics['reason']}"
            )
        # Capture fee in proposal
        amount = metrics["fee_inr"]

    elif action_type == "ISSUE_CREDIT":
        if not order_id or not ticket_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order ID and Ticket ID are required for service credits.")
        metrics = calculate_order_metrics(order, "service_credit")
        
        # Verify eligibility
        if metrics.get("needs_verification"):
            # Can still propose, but must flag manual verification
            pass
        elif not metrics["eligible"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order is not eligible for credit: {metrics['reason']}"
            )
        
        # Capture computed amount if client didn't supply one, or override
        amount = metrics["credit_inr"] if amount is None else amount

    # 3. Create PendingAction record
    pending = PendingAction(
        user_id=user.user_id,
        action_type=action_type,
        order_id=order_id,
        ticket_id=ticket_id,
        amount=amount,
        reason=reason,
        status="PENDING"
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    
    # 4. Generate proposal card representation
    # Indicate if manager approval will be required at execution phase
    req_lead_approval = False
    if action_type == "ISSUE_CREDIT" and amount is not None and amount > 1000.0:
        req_lead_approval = True

    return {
        "proposal_id": pending.id,
        "action_type": pending.action_type,
        "order_id": pending.order_id,
        "ticket_id": pending.ticket_id,
        "amount": pending.amount,
        "reason": pending.reason,
        "status": pending.status,
        "requires_manager_approval": req_lead_approval,
        "message": f"Successfully drafted {pending.action_type} proposal. Please confirm to finalize."
    }
