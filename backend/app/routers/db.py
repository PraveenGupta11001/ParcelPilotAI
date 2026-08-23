import os
import glob
import pypdf
import datetime
import pandas as pd
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db, engine, Base
from app.db.models import Account, Order, Ticket, User, DocumentChunk
from app.config import SNAPSHOT_DATETIME, IST_TZ
from app.ingestion.chunk import chunk_text
from app.ingestion.embed import get_embedding
from app.ingestion.parse_pdfs import SOURCE_REGISTRY

router = APIRouter(prefix="/db", tags=["db"])

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def localize_dt(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, str):
        val = pd.to_datetime(val)
    if hasattr(val, "to_pydatetime"):
        dt = val.to_pydatetime()
    else:
        dt = val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST_TZ)
    else:
        dt = dt.astimezone(IST_TZ)
    return dt

@router.post("/initialize-and-seed")
def initialize_and_seed(db: Session = Depends(get_db)):
    # 1. Resolve relative path to Data directory
    current_dir = os.path.dirname(os.path.abspath(__file__)) # backend/app/routers
    backend_dir = os.path.dirname(current_dir) # backend/app
    backend_root = os.path.dirname(backend_dir) # backend
    project_root = os.path.dirname(backend_root) # ParcelPilot_Customer_Support
    
    excel_path = os.path.join(project_root, "Data", "ParcelPilot_Assessment_Data.xlsx")
    pdf_dir = os.path.join(project_root, "Data")
    
    if not os.path.exists(excel_path):
        raise HTTPException(
            status_code=500,
            detail=f"Excel file not found at path: {excel_path}. Direct workspace root resolved as {project_root}"
        )
        
    try:
        # 2. Enable pgvector
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            
        # 3. Create tables
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # 4. Seed Excel sheets
        xl = pd.ExcelFile(excel_path)
        accounts_df = xl.parse("accounts")
        orders_df = xl.parse("orders")
        tickets_df = xl.parse("tickets")
        
        for _, row in accounts_df.iterrows():
            prem_support = False
            if "premium_support" in row and str(row["premium_support"]).lower() in ["yes", "true", "1"]:
                prem_support = True
            
            account = Account(
                account_id=str(row["account_id"]).strip(),
                account_name=str(row["account_name"]).strip(),
                plan=str(row["plan"]).strip(),
                status=str(row["status"]).strip(),
                csm=str(row["csm"]).strip() if not pd.isna(row["csm"]) else None,
                contract_file=str(row["contract_file"]).strip() if not pd.isna(row["contract_file"]) else None,
                premium_support=prem_support,
                notes=str(row["notes"]) if not pd.isna(row["notes"]) else None
            )
            db.merge(account)
        db.commit()
        
        for _, row in orders_df.iterrows():
            carrier_f = bool(row["carrier_fault"]) if not pd.isna(row["carrier_fault"]) else None
            customer_f = bool(row["customer_fault"]) if not pd.isna(row["customer_fault"]) else None
            
            order = Order(
                order_id=str(row["order_id"]).strip(),
                account_id=str(row["account_id"]).strip(),
                carrier=str(row["carrier"]).strip(),
                status=str(row["status"]).strip(),
                booked_at=localize_dt(row["booked_at"]),
                pickup_window_start=localize_dt(row["pickup_window_start"]),
                pickup_window_end=localize_dt(row["pickup_window_end"]),
                pickup_actual_at=localize_dt(row["pickup_actual_at"]),
                shipment_fee_inr=float(row["shipment_fee_inr"]),
                carrier_fault=carrier_f,
                customer_fault=customer_f,
                cancellation_requested_at=localize_dt(row.get("cancellation_requested_at")),
                notes=str(row["notes"]) if not pd.isna(row["notes"]) else None
            )
            db.merge(order)
        db.commit()
        
        for _, row in tickets_df.iterrows():
            ticket = Ticket(
                ticket_id=str(row["ticket_id"]).strip(),
                account_id=str(row["account_id"]).strip(),
                created_at=localize_dt(row["created_at"]),
                status=str(row["status"]).strip(),
                subject=str(row["subject"]).strip(),
                description=str(row["description"]),
                channel=str(row["channel"]).strip(),
                assigned_to=str(row["assigned_to"]).strip() if not pd.isna(row["assigned_to"]) else None,
                last_customer_message_at=localize_dt(row.get("last_customer_message_at")),
                historical_resolution=str(row["historical_resolution"]) if not pd.isna(row["historical_resolution"]) else None
            )
            db.merge(ticket)
        db.commit()
        
        # Seed users
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

        # 5. Ingest PDFs
        files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
        ingested_count = 0
        for fpath in sorted(files):
            fname = os.path.basename(fpath)
            if fname not in SOURCE_REGISTRY:
                continue
            
            meta = SOURCE_REGISTRY[fname]
            reader = pypdf.PdfReader(fpath)
            full_text = ""
            for page in reader.pages:
                full_text += (page.extract_text() or "") + "\n\n"
            
            chunks = chunk_text(full_text)
            for idx, chunk in enumerate(chunks):
                embed_vector = get_embedding(chunk)
                doc_chunk = DocumentChunk(
                    document_name=fname,
                    chunk_index=idx,
                    content=chunk,
                    embedding=embed_vector,
                    authority_level=meta["authority_level"],
                    effective_date=meta["effective_date"],
                    status=meta["status"],
                    scope=meta["scope"]
                )
                db.add(doc_chunk)
            ingested_count += 1
        db.commit()

        return {
            "success": True,
            "message": f"Successfully created tables, seeded Excel records, and ingested {ingested_count} PDF policies!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database initialization and seed failed: {str(e)}"
        )
