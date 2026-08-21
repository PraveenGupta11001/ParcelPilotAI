import pytest
from app.db.models import Order
from app.tools.structured_data import calculate_order_metrics

def test_cancellation_grace_period(db_session):
    # Retrieve order ORD-102 (Axis/Northstar booked 15 mins ago - within grace period)
    order = db_session.query(Order).filter(Order.order_id == "ORD-102").first()
    assert order is not None
    
    metrics = calculate_order_metrics(order, "cancellation")
    assert metrics["cancellable"] is True
    assert metrics["fee_inr"] == 0.0
    assert "within 30 minutes" in metrics["reason"].lower()

def test_cancellation_outside_grace_period(db_session):
    # Retrieve order ORD-101 (Northstar order but wait, Northstar waives the fee even outside grace!)
    # Let's test standard account first. Axis or ACCT-003 Beacon (ORD-301, booked 6 hours ago)
    order = db_session.query(Order).filter(Order.order_id == "ORD-301").first()
    assert order is not None
    
    metrics = calculate_order_metrics(order, "cancellation")
    assert metrics["cancellable"] is True
    assert metrics["fee_inr"] == 250.0  # Standard flat fee
    assert "outside 30 minutes" in metrics["reason"].lower()

def test_northstar_cancellation_waiver(db_session):
    # Retrieve ORD-101 (Northstar ACCT-001 booked 45 mins ago - outside 30 mins, but fee waived)
    order = db_session.query(Order).filter(Order.order_id == "ORD-101").first()
    assert order is not None
    
    metrics = calculate_order_metrics(order, "cancellation")
    assert metrics["cancellable"] is True
    assert metrics["fee_inr"] == 0.0  # Waived by contract!
    assert "waives all cancellation fees" in metrics["reason"].lower()

def test_lumenworks_service_credit_threshold(db_session):
    # LumenWorks contract replaces standard service credits:
    # Requires >4 hours delay (240 mins) for a flat credit of INR 300.
    
    # ORD-201: LumenWorks, delayed by 3 hours (180 mins). Not eligible.
    o201 = db_session.query(Order).filter(Order.order_id == "ORD-201").first()
    metrics1 = calculate_order_metrics(o201, "service_credit")
    assert metrics1["eligible"] is False
    assert metrics1["credit_inr"] == 0.0

    # ORD-202: LumenWorks, delayed by 5 hours (300 mins). Eligible!
    o202 = db_session.query(Order).filter(Order.order_id == "ORD-202").first()
    metrics2 = calculate_order_metrics(o202, "service_credit")
    assert metrics2["eligible"] is True
    assert metrics2["credit_inr"] == 300.0
    assert "exceeds the 4-hour threshold" in metrics2["reason"].lower()

def test_standard_service_credit(db_session):
    # Standard account Axis / Beacon: threshold is >2 hours (120 mins). Credit = min(500, 10% shipment fee).
    # ORD-301: Beacon retail, delayed by 3 hours, fee is 4000. Eligible for min(500, 400) = 400 INR.
    o301 = db_session.query(Order).filter(Order.order_id == "ORD-301").first()
    metrics = calculate_order_metrics(o301, "service_credit")
    assert metrics["eligible"] is True
    assert metrics["credit_inr"] == 400.0  # 10% of 4000 is 400, lower than 500 cap
    assert "exceeds the 2-hour threshold" in metrics["reason"].lower()
