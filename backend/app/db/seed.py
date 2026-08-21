import os
import pandas as pd
from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import bcrypt

# Import our models and engine details
from app.db.session import engine, Base
from app.db.models import Account, Order, Ticket, User
from app.config import SNAPSHOT_DATETIME, IST_TZ

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def localize_dt(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, str):
        val = pd.to_datetime(val)
    # If it is a timestamp/datetime
    if hasattr(val, "to_pydatetime"):
        dt = val.to_pydatetime()
    else:
        dt = val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST_TZ)
    else:
        dt = dt.astimezone(IST_TZ)
    return dt

def seed_database():
    excel_path = "/home/praveen/my_projects/ParcelPilot_Customer_Support/Data/AI Agent Assessment - Candidate Pack/ParcelPilot_Assessment_Data.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found at {excel_path}")
        return

    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    
    print("Database vector extension enabled.")
    
    # Recreate tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

    # Read excel sheets
    xl = pd.ExcelFile(excel_path)
    
    accounts_df = xl.parse("accounts")
    orders_df = xl.parse("orders")
    tickets_df = xl.parse("tickets")

    db = Session(engine)

    try:
        # Seed Accounts
        print("Seeding accounts...")
        for _, row in accounts_df.iterrows():
            prem_support = False
            if "premium_support" in row and str(row["premium_support"]).lower() in ["yes", "true", "1"]:
                prem_support = True
            
            note_val = str(row["notes"]) if not pd.isna(row["notes"]) else None
            csm_val = str(row["csm"]) if not pd.isna(row["csm"]) else None
            contract_val = str(row["contract_file"]) if not pd.isna(row["contract_file"]) else None

            account = Account(
                account_id=str(row["account_id"]).strip(),
                account_name=str(row["account_name"]).strip(),
                plan=str(row["plan"]).strip(),
                status=str(row["status"]).strip(),
                csm=csm_val,
                contract_file=contract_val,
                premium_support=prem_support,
                notes=note_val
            )
            db.merge(account)
        db.commit()

        # Seed Orders
        print("Seeding orders...")
        for _, row in orders_df.iterrows():
            booked_at = localize_dt(row["booked_at"])
            win_start = localize_dt(row["pickup_window_start"])
            win_end = localize_dt(row["pickup_window_end"])
            pickup_actual = localize_dt(row["pickup_actual_at"])
            cancel_req = localize_dt(row.get("cancellation_requested_at"))

            carrier_f = None
            if not pd.isna(row["carrier_fault"]):
                carrier_f = bool(row["carrier_fault"])
            
            customer_f = None
            if not pd.isna(row["customer_fault"]):
                customer_f = bool(row["customer_fault"])

            notes_val = str(row["notes"]) if not pd.isna(row["notes"]) else None

            order = Order(
                order_id=str(row["order_id"]).strip(),
                account_id=str(row["account_id"]).strip(),
                carrier=str(row["carrier"]).strip(),
                status=str(row["status"]).strip(),
                booked_at=booked_at,
                pickup_window_start=win_start,
                pickup_window_end=win_end,
                pickup_actual_at=pickup_actual,
                shipment_fee_inr=float(row["shipment_fee_inr"]),
                carrier_fault=carrier_f,
                customer_fault=customer_f,
                cancellation_requested_at=cancel_req,
                notes=notes_val
            )
            db.merge(order)
        db.commit()

        # Seed Tickets
        print("Seeding tickets...")
        for _, row in tickets_df.iterrows():
            created_at = localize_dt(row["created_at"])
            last_msg = localize_dt(row.get("last_customer_message_at"))
            hist_res = str(row["historical_resolution"]) if not pd.isna(row["historical_resolution"]) else None
            assigned = str(row["assigned_to"]) if not pd.isna(row["assigned_to"]) else None

            ticket = Ticket(
                ticket_id=str(row["ticket_id"]).strip(),
                account_id=str(row["account_id"]).strip(),
                created_at=created_at,
                status=str(row["status"]).strip(),
                subject=str(row["subject"]).strip(),
                description=str(row["description"]),
                channel=str(row["channel"]).strip(),
                assigned_to=assigned,
                last_customer_message_at=last_msg,
                historical_resolution=hist_res
            )
            db.merge(ticket)
        db.commit()

        # Seed Mock Users
        print("Seeding mock users...")
        mock_users = [
            {"user_id": "cust-northstar", "role": "customer", "account_id": "ACCT-001", "name": "Northstar Logistics User", "email": "northstar@parcelpilot.ai", "password": "password123"},
            {"user_id": "cust-lumenworks", "role": "customer", "account_id": "ACCT-002", "name": "LumenWorks User", "email": "lumenworks@parcelpilot.ai", "password": "password123"},
            {"user_id": "cust-beacon", "role": "customer", "account_id": "ACCT-003", "name": "Beacon Retail User", "email": "beacon@parcelpilot.ai", "password": "password123"},
            {"user_id": "agent-maya", "role": "internal_support", "account_id": None, "name": "Maya Agent", "email": "maya@parcelpilot.ai", "password": "password123"},
            {"user_id": "lead-rohit", "role": "internal_lead", "account_id": None, "name": "Rohit Lead", "email": "rohit@parcelpilot.ai", "password": "password123"},
        ]

        for u in mock_users:
            user = User(
                user_id=u["user_id"],
                role=u["role"],
                account_id=u["account_id"],
                full_name=u["name"],
                email=u["email"],
                password_hash=get_password_hash(u["password"])
            )
            db.merge(user)
        db.commit()
        print("Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
