import os
import sys
import uuid
from datetime import datetime, timezone

# Add project path for imports
sys.path.append("/home/praveen/my_projects/ParcelPilot_Customer_Support/backend")

from app.db.session import SessionLocal
from app.db.models import Ticket, Order

# Configuration
ORDER_ID = "ORD-2002"
DESCRIPTION = "Pickup missed due to carrier fault; escalation required."
SUBJECT = "Escalation: Missed Pickup for Order ORD-2002"
CHANNEL = "chat"

# Generate a unique ticket ID
TICKET_ID = f"TKT-{uuid.uuid4().hex[:8].upper()}"

# Create DB session
db = SessionLocal()
try:
    # Fetch order to get account_id
    order = db.query(Order).filter(Order.order_id == ORDER_ID).first()
    if not order:
        raise ValueError(f"Order {ORDER_ID} not found in database.")

    # Insert new ticket
    new_ticket = Ticket(
        ticket_id=TICKET_ID,
        account_id=order.account_id,
        created_at=datetime.now(timezone.utc),
        status="OPEN",
        subject=SUBJECT,
        description=DESCRIPTION,
        channel=CHANNEL,
        assigned_to=None,
        last_customer_message_at=datetime.now(timezone.utc),
        historical_resolution="",
    )
    db.add(new_ticket)
    db.commit()
    print(f"Created new ticket: {TICKET_ID} for order {ORDER_ID} (account {order.account_id})")
except Exception as e:
    db.rollback()
    print(f"Error creating ticket: {e}")
finally:
    db.close()
