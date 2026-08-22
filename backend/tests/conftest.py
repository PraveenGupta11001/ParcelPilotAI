import warnings
warnings.filterwarnings("ignore", message=".*ARC4.*")
warnings.filterwarnings("ignore", message=".*utcnow.*")

import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Set testing environment variables before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Force relative PYTHONPATH imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import Base, get_db
from app.db.models import User, Account, Order, Ticket
from app.main import app
from app.config import SNAPSHOT_DATETIME, IST_TZ

# SQLite URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # SQLite doesn't support pgvector type natively, but for unit tests
    # we can define mock vector behavior or let it register SQLite-compatible columns.
    # Fortunately, pgvector column maps to a float list. Under SQLite, Base.metadata.create_all
    # works by treating Vector as a base UserDefinedType or custom compiler binding.
    # Let's verify if creating tables works out-of-the-box or needs compiler adaptation.
    # To prevent SQLite from failing on Vector type, we can register compiling mappings.
    from sqlalchemy.ext.compiler import compiles
    from pgvector.sqlalchemy import Vector

    @compiles(Vector, "sqlite")
    def compile_sqlite_vector(type_, compiler, **kw):
        return "TEXT"  # Store vector as comma-separated or JSON string under SQLite test DB

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Seed mock data for unit tests
    db = TestingSessionLocal()
    
    # 1. Accounts
    a1 = Account(account_id="ACCT-001", account_name="Northstar Logistics", plan="Enterprise", status="ACTIVE", premium_support=True)
    a2 = Account(account_id="ACCT-002", account_name="LumenWorks", plan="Growth", status="ACTIVE", premium_support=False)
    a3 = Account(account_id="ACCT-003", account_name="Beacon Retail", plan="Standard", status="ACTIVE", premium_support=False)
    db.add_all([a1, a2, a3])
    db.commit()

    # 2. Users
    import bcrypt
    u1 = User(user_id="cust-northstar", role="customer", account_id="ACCT-001", full_name="Northstar User", email="northstar@parcelpilot.ai", password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode('utf-8'))
    u2 = User(user_id="cust-lumenworks", role="customer", account_id="ACCT-002", full_name="LumenWorks User", email="lumenworks@parcelpilot.ai", password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode('utf-8'))
    u3 = User(user_id="agent-maya", role="internal_support", account_id=None, full_name="Maya Agent", email="maya@parcelpilot.ai", password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode('utf-8'))
    u4 = User(user_id="lead-rohit", role="internal_lead", account_id=None, full_name="Rohit Lead", email="rohit@parcelpilot.ai", password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode('utf-8'))
    db.add_all([u1, u2, u3, u4])
    db.commit()

    # 3. Orders
    from datetime import datetime, timedelta
    o1 = Order(
        order_id="ORD-101", account_id="ACCT-001", carrier="ShipFast", status="BOOKED",
        booked_at=SNAPSHOT_DATETIME - timedelta(minutes=45),  # 45 mins elapsed (outside 30m grace)
        pickup_window_start=SNAPSHOT_DATETIME - timedelta(hours=2),
        pickup_window_end=SNAPSHOT_DATETIME - timedelta(hours=1),
        pickup_actual_at=None, shipment_fee_inr=1500.0, carrier_fault=None, customer_fault=None
    )
    o2 = Order(
        order_id="ORD-102", account_id="ACCT-003", carrier="Speedy", status="BOOKED",
        booked_at=SNAPSHOT_DATETIME - timedelta(minutes=15),  # 15 mins elapsed (within grace)
        pickup_window_start=SNAPSHOT_DATETIME - timedelta(hours=1),
        pickup_window_end=SNAPSHOT_DATETIME + timedelta(hours=1),
        pickup_actual_at=None, shipment_fee_inr=800.0, carrier_fault=None, customer_fault=None
    )
    o3 = Order(
        order_id="ORD-201", account_id="ACCT-002", carrier="ShipFast", status="BOOKED",
        booked_at=SNAPSHOT_DATETIME - timedelta(hours=5),
        pickup_window_start=SNAPSHOT_DATETIME - timedelta(hours=5),
        pickup_window_end=SNAPSHOT_DATETIME - timedelta(hours=3),  # Delayed by 3 hours (not eligible under >4h LW rule)
        pickup_actual_at=None, shipment_fee_inr=1200.0, carrier_fault=True, customer_fault=False
    )
    o4 = Order(
        order_id="ORD-202", account_id="ACCT-002", carrier="ShipFast", status="BOOKED",
        booked_at=SNAPSHOT_DATETIME - timedelta(hours=6),
        pickup_window_start=SNAPSHOT_DATETIME - timedelta(hours=6),
        pickup_window_end=SNAPSHOT_DATETIME - timedelta(hours=5),  # Delayed by 5 hours (eligible under >4h LW rule, INR 300)
        pickup_actual_at=None, shipment_fee_inr=1200.0, carrier_fault=True, customer_fault=False
    )
    o5 = Order(
        order_id="ORD-301", account_id="ACCT-003", carrier="CarrierX", status="BOOKED",
        booked_at=SNAPSHOT_DATETIME - timedelta(hours=6),
        pickup_window_start=SNAPSHOT_DATETIME - timedelta(hours=5),
        pickup_window_end=SNAPSHOT_DATETIME - timedelta(hours=3),  # Delayed by 3 hours (eligible under Standard >2h rule, credit=min(500, 10% fee))
        pickup_actual_at=None, shipment_fee_inr=4000.0, carrier_fault=True, customer_fault=False
    )
    db.add_all([o1, o2, o3, o4, o5])
    db.commit()

    # 4. Tickets
    t1 = Ticket(
        ticket_id="TKT-101", account_id="ACCT-001", created_at=SNAPSHOT_DATETIME - timedelta(hours=3),
        status="OPEN", subject="Order delay P1 URGENT", description="My shipment is late.", channel="CHAT"
    )
    db.add_all([t1])
    db.commit()
    
    db.close()
    yield
    
    # Cleanup
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
