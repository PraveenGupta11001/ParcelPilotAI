from datetime import datetime
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import Ticket, Order, Account, User
from app.config import SNAPSHOT_DATETIME, IST_TZ

# Support SLA Target configurations (in minutes)
# For standard business hour math, assume 9 AM to 5 PM (8 hours/day)
def get_sla_target_minutes(account_id: str, priority: str, is_business_time: bool = True) -> int:
    """
    Returns the first response target SLA in minutes for a given account and priority.
    """
    p_upper = priority.upper()
    
    # 1. Northstar Enterprise Agreement: 24x7 coverage
    if account_id == "ACCT-001":
        if p_upper == "P1":
            return 15
        elif p_upper == "P2":
            return 60
        elif p_upper == "P3":
            return 480  # 8 business hours
        return 1440
        
    # 2. LumenWorks Agreement: Workdays only (no SLA for after-hours)
    if account_id == "ACCT-002":
        if not is_business_time:
            return 999999  # effectively infinite / no SLA target
        if p_upper == "P1":
            return 120  # 2 business hours
        elif p_upper == "P2":
            return 240  # 4 business hours
        elif p_upper == "P3":
            return 960  # 2 business days (16 hours)
        return 2880

    # 3. Standard fallback policy targets
    if p_upper == "P1":
        return 60    # 1 hour
    elif p_upper == "P2":
        return 240   # 4 hours
    elif p_upper == "P3":
        return 1440  # 24 business hours (3 business days)
    return 2880

def get_operational_signals(db: Session, user: User) -> dict:
    """
    Computes proactive signals and indicators for operations dashboard.
    Restricts visibility if user is a customer.
    """
    now = SNAPSHOT_DATETIME
    
    # Filter by user's tenant if customer
    ticket_query = db.query(Ticket).filter(Ticket.status != "RESOLVED", Ticket.status != "CLOSED")
    order_query = db.query(Order).filter(Order.status != "DELIVERED")
    
    if user.role == "customer":
        ticket_query = ticket_query.filter(Ticket.account_id == user.account_id)
        order_query = order_query.filter(Order.account_id == user.account_id)
        
    active_tickets = ticket_query.all()
    active_orders = order_query.all()
    
    # 1. Compute SLA breaches and warnings
    sla_breaches = []
    sla_warnings = []
    
    for t in active_tickets:
        # Determine priority from ticket subject (standard priority tagging P1/P2/P3 in subjects)
        subject_upper = t.subject.upper()
        priority = "P3"
        if "P1" in subject_upper or "URGENT" in subject_upper:
            priority = "P1"
        elif "P2" in subject_upper or "CRITICAL" in subject_upper or "MAJOR" in subject_upper:
            priority = "P2"
            
        # Determine is_business_time (Monday to Friday, 9 AM to 5 PM)
        # Snapshot in ISO is Sunday, 2026-08-16 11:00:00 (which is outside working hours!)
        # So LumenWorks has no SLA coverage at snap time.
        # Standard policy might check day of week:
        day_of_week = now.weekday()  # 6 is Sunday
        hour_of_day = now.hour
        is_business_time = (day_of_week < 5) and (9 <= hour_of_day < 17)
        
        target = get_sla_target_minutes(t.account_id, priority, is_business_time)
        
        # Calculate time since ticket creation or customer's last message
        start_time = t.last_customer_message_at if t.last_customer_message_at else t.created_at
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=IST_TZ)
            
        elapsed_mins = int((now - start_time).total_seconds() / 60.0)
        
        # Warning starts at 75% of target
        warning_threshold = int(0.75 * target)
        
        ticket_data = {
            "ticket_id": t.ticket_id,
            "account_id": t.account_id,
            "subject": t.subject,
            "priority": priority,
            "elapsed_minutes": elapsed_mins,
            "sla_target_minutes": target,
            "assigned_to": t.assigned_to
        }
        
        if elapsed_mins > target:
            sla_breaches.append(ticket_data)
        elif elapsed_mins > warning_threshold:
            sla_warnings.append(ticket_data)

    # 2. Unassigned tickets
    unassigned_tickets = [{
        "ticket_id": t.ticket_id,
        "account_id": t.account_id,
        "subject": t.subject,
        "created_at": t.created_at.isoformat()
    } for t in active_tickets if not t.assigned_to]

    # 3. Delivery breaches / Delayed Pickups
    delayed_pickups = []
    for o in active_orders:
        win_end_dt = o.pickup_window_end
        if win_end_dt.tzinfo is None:
            win_end_dt = win_end_dt.replace(tzinfo=IST_TZ)
        if now > win_end_dt:
            delay = int((now - win_end_dt).total_seconds() / 60.0)
            delayed_pickups.append({
                "order_id": o.order_id,
                "account_id": o.account_id,
                "status": o.status,
                "carrier": o.carrier,
                "delay_minutes": delay,
                "pickup_window_end": win_end_dt.isoformat()
            })

    # 4. Carrier Health scorecard (only for internals)
    carrier_scorecard = {}
    if user.role != "customer":
        # Group carrier faults of DELIVERED/PICKED_UP orders
        all_orders = db.query(Order).all()
        for o in all_orders:
            if o.carrier not in carrier_scorecard:
                carrier_scorecard[o.carrier] = {"total_orders": 0, "carrier_faults": 0}
            
            carrier_scorecard[o.carrier]["total_orders"] += 1
            if o.carrier_fault is True:
                carrier_scorecard[o.carrier]["carrier_faults"] += 1
        
        for carrier, stats in carrier_scorecard.items():
            tot = stats["total_orders"]
            flt = stats["carrier_faults"]
            stats["failure_rate"] = round(flt / tot, 2) if tot > 0 else 0.0

    return {
        "snapshot_time": now.isoformat(),
        "unassigned_tickets_count": len(unassigned_tickets),
        "sla_breaches_count": len(sla_breaches),
        "sla_warnings_count": len(sla_warnings),
        "delayed_pickups_count": len(delayed_pickups),
        "unassigned_tickets": unassigned_tickets[:10],
        "sla_breaches": sla_breaches[:10],
        "sla_warnings": sla_warnings[:10],
        "delayed_pickups": delayed_pickups[:10],
        "carrier_scorecard": carrier_scorecard
    }
