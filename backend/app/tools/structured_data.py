from datetime import datetime
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.models import Account, Order, Ticket, User, AuditLog
from app.config import SNAPSHOT_DATETIME, IST_TZ

def query_structured_data(
    db: Session,
    user: User,
    entity: str,
    filters: dict,
    run_calculation: str = None
) -> dict:
    """
    Query database tables (accounts, orders, tickets) and perform business logic math (fees, service credits).
    Enforces row-level visibility constraints:
    - Customer users can ONLY see records of their own account_id.
    - Support and Lead roles can view all records.
    """
    # 1. Enforce tenant isolation
    account_id_filter = filters.get("account_id")
    if user.role == "customer":
        account_id_filter = user.account_id
    
    # 2. Querying based on Entity type
    if entity == "account":
        query = db.query(Account)
        if account_id_filter:
            query = query.filter(Account.account_id == account_id_filter)
        results = query.all()
        data = [{
            "account_id": a.account_id,
            "account_name": a.account_name,
            "plan": a.plan,
            "status": a.status,
            "csm": a.csm,
            "contract_file": a.contract_file,
            "premium_support": a.premium_support,
            "notes": a.notes
        } for a in results]
        return {"entity": "account", "records": data}

    elif entity == "order":
        query = db.query(Order)
        if account_id_filter:
            query = query.filter(Order.account_id == account_id_filter)
        if filters.get("order_id"):
            query = query.filter(Order.order_id == filters["order_id"])
        if filters.get("carrier"):
            query = query.filter(Order.carrier == filters["carrier"])
        if filters.get("status"):
            query = query.filter(Order.status == filters["status"])
            
        results = query.all()
        data = []
        for o in results:
            item = {
                "order_id": o.order_id,
                "account_id": o.account_id,
                "carrier": o.carrier,
                "status": o.status,
                "booked_at": o.booked_at.isoformat() if o.booked_at else None,
                "pickup_window_start": o.pickup_window_start.isoformat() if o.pickup_window_start else None,
                "pickup_window_end": o.pickup_window_end.isoformat() if o.pickup_window_end else None,
                "pickup_actual_at": o.pickup_actual_at.isoformat() if o.pickup_actual_at else None,
                "shipment_fee_inr": o.shipment_fee_inr,
                "carrier_fault": o.carrier_fault,
                "customer_fault": o.customer_fault,
                "cancellation_requested_at": o.cancellation_requested_at.isoformat() if o.cancellation_requested_at else None,
                "notes": o.notes
            }
            # Perform runtime calculations if requested for this order
            if run_calculation:
                calc_res = calculate_order_metrics(o, run_calculation)
                item["calculations"] = calc_res
                
            data.append(item)
        return {"entity": "order", "records": data}

    elif entity == "ticket":
        query = db.query(Ticket)
        if account_id_filter:
            query = query.filter(Ticket.account_id == account_id_filter)
        if filters.get("ticket_id"):
            query = query.filter(Ticket.ticket_id == filters["ticket_id"])
        if filters.get("status"):
            query = query.filter(Ticket.status == filters["status"])
            
        results = query.all()
        data = [{
            "ticket_id": t.ticket_id,
            "account_id": t.account_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "status": t.status,
            "subject": t.subject,
            "description": t.description,
            "channel": t.channel,
            "assigned_to": t.assigned_to,
            "last_customer_message_at": t.last_customer_message_at.isoformat() if t.last_customer_message_at else None,
            "historical_resolution": t.historical_resolution
        } for t in results]
        return {"entity": "ticket", "records": data}

    else:
        return {"error": f"Invalid entity: {entity}"}

def calculate_order_metrics(order: Order, calc_type: str) -> dict:
    """
    Applies business logic and calculations (late cancellation fees, service credits).
    Uses SNAPSHOT_DATETIME as baselines for elapsed time calculations.
    """
    now = SNAPSHOT_DATETIME
    
    # Calculate minutes since booking (for cancellation policies)
    booked_dt = order.booked_at
    if booked_dt.tzinfo is None:
        booked_dt = booked_dt.replace(tzinfo=IST_TZ)
    minutes_since_booking = int((now - booked_dt).total_seconds() / 60.0)

    # Calculate actual/potential delays in minutes
    # Delay is relative to pickup_window_end
    window_end_dt = order.pickup_window_end
    if window_end_dt.tzinfo is None:
        window_end_dt = window_end_dt.replace(tzinfo=IST_TZ)
        
    delay_minutes = 0
    if order.status == "BOOKED":
        # Pickup has not happened: delay is relative to now
        if now > window_end_dt:
            # Already delayed
            delay_minutes = int((now - window_end_dt).total_seconds() / 60.0)
    elif order.status in ["PICKED_UP", "DELIVERED"]:
        # Pickup has happened
        if order.pickup_actual_at:
            pickup_dt = order.pickup_actual_at
            if pickup_dt.tzinfo is None:
                pickup_dt = pickup_dt.replace(tzinfo=IST_TZ)
            if pickup_dt > window_end_dt:
                delay_minutes = int((pickup_dt - window_end_dt).total_seconds() / 60.0)

    if calc_type == "cancellation":
        # Logic: 
        # - DRAFT -> fee = 0
        # - ACCT-001 (Northstar) Enterprise Agreement -> waives the cancellation fee entirely for booked orders
        # - Other accounts: 30 minutes grace period, else 250 INR fee
        # - PICKED_UP -> Not cancellable
        # - DELIVERED -> Not cancellable
        
        status = order.status.upper()
        if status == "DRAFT":
            return {
                "cancellable": True,
                "fee_inr": 0.0,
                "reason": "Draft shipments can always be cancelled without charge."
            }
        elif status == "DELIVERED":
            return {
                "cancellable": False,
                "fee_inr": 0.0,
                "reason": "Shipment is already delivered; cannot be cancelled."
            }
        elif status == "PICKED_UP":
            return {
                "cancellable": False,
                "fee_inr": 0.0,
                "reason": "Shipment has been picked up; use return-to-origin workflow instead."
            }
        
        # Status is BOOKED
        if order.account_id == "ACCT-001":  # Northstar Logistics
            return {
                "cancellable": True,
                "fee_inr": 0.0,
                "reason": "Northstar Logistics agreement waives all cancellation fees on booked shipments."
            }
            
        # Standard policy fallback
        is_grace = minutes_since_booking <= 30
        fee = 0.0 if is_grace else 250.0
        reason = (
            f"Within 30 minutes grace period since booking ({minutes_since_booking} mins elapsed). Free cancellation."
            if is_grace else
            f"Outside 30 minutes grace period ({minutes_since_booking} mins elapsed). Flat fee of INR 250 applies."
        )
        return {
            "cancellable": True,
            "fee_inr": fee,
            "reason": reason
        }

    elif calc_type == "service_credit":
        # Logic:
        # - Must be delayed.
        # - Carrier must be at fault (`carrier_fault = True`) AND Customer not at fault (`customer_fault = False` or None).
        # - Threshold:
        #   - ACCT-002 (LumenWorks) Growth Agreement -> threshold is > 4 hours (240 mins). Credit is flat INR 300.
        #   - Other accounts -> threshold is > 2 hours (120 mins). Credit is min(500, 10% shipment fee).
        #   - ACCT-001 (Northstar) -> Cap limit INR 5000 / month.
        
        carrier_at_fault = order.carrier_fault is True
        customer_at_fault = order.customer_fault is True
        
        # Check fault fields
        if order.carrier_fault is None:
            return {
                "eligible": False,
                "needs_verification": True,
                "reason": "Carrier fault field in database is null; manual ops verification is required to determine fault.",
                "credit_inr": 0.0
            }
        if not carrier_at_fault or customer_at_fault:
            return {
                "eligible": False,
                "needs_verification": False,
                "reason": "Service credit not applicable: carrier is not at fault or customer fault is True.",
                "credit_inr": 0.0
            }

        # Fault is resolved and carrier is at fault
        if order.account_id == "ACCT-002":  # LumenWorks
            threshold = 240
            eligible = delay_minutes > threshold
            credit = 300.0 if eligible else 0.0
            reason = (
                f"LumenWorks contract: pickup delay of {delay_minutes} minutes exceeds the 4-hour threshold. Flat INR 300 credit."
                if eligible else
                f"LumenWorks contract: pickup delay of {delay_minutes} minutes does not exceed the 4-hour threshold."
            )
            return {
                "eligible": eligible,
                "needs_verification": False,
                "reason": reason,
                "credit_inr": credit
            }
        else:
            # Standard fallback (including Northstar ACCT-001, Axis ACCT-004, Beacon ACCT-003)
            threshold = 120
            eligible = delay_minutes > threshold
            credit = 0.0
            if eligible:
                credit = min(500.0, 0.1 * order.shipment_fee_inr)
            reason = (
                f"Standard Policy: pickup delay of {delay_minutes} minutes exceeds the 2-hour threshold. Credit computed as min(500, 10% fee) on INR {order.shipment_fee_inr}."
                if eligible else
                f"Standard Policy: pickup delay of {delay_minutes} minutes does not exceed the 2-hour threshold."
            )
            ret_val = {
                "eligible": eligible,
                "needs_verification": False,
                "reason": reason,
                "credit_inr": credit
            }
            if order.account_id == "ACCT-001":
                ret_val["reason"] += " (Subject to Northstar's aggregate monthly limit of INR 5,000)."
            return ret_val

    else:
        return {"error": f"Invalid calculation type: {calc_type}"}
