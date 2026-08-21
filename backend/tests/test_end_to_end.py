import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.models import Order, Ticket, PendingAction

def test_full_customer_propose_confirm_flow(client, db_session):
    # 1. Login as Northstar Customer
    login_resp = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Chat query to compute order ORD-101 cancellation
    # Since VITE client hits /chat, let's call the endpoint
    chat_resp = client.post("/chat", json={
        "message": "Is order ORD-101 eligible for cancellation, and what is the fee?",
        "chat_history": []
    }, headers=headers)
    assert chat_resp.status_code == 200
    res = chat_resp.json()
    assert "text_response" in res
    
    # 3. Create a proposal for cancellation
    from app.tools.actions import propose_action
    from app.db.models import User
    
    user = db_session.query(User).filter(User.user_id == "cust-northstar").first()
    prop_data = propose_action(
        db=db_session,
        user=user,
        action_type="CANCEL_ORDER",
        order_id="ORD-101",
        reason="Requested cancel in chat"
    )
    assert prop_data["action_type"] == "CANCEL_ORDER"
    assert prop_data["amount"] == 0.0  # Waived by contract!
    proposal_id = prop_data["proposal_id"]

    # 4. Confirm proposal
    confirm_resp = client.post("/chat/confirm", json={"proposal_id": proposal_id}, headers=headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["success"] is True
    assert confirm_resp.json()["action"]["status"] == "APPROVED"

    # 5. Check order status in DB
    order = db_session.query(Order).filter(Order.order_id == "ORD-101").first()
    assert order.status == "CANCELLED"
    assert order.cancellation_requested_at is not None

def test_full_support_insights_aggregate_flow(client):
    # 1. Login as Support Agent Maya
    login_resp = client.post("/auth/mock-login", json={
        "email": "maya@parcelpilot.ai",
        "password": "password123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Fetch insights
    insights_resp = client.get("/insights", headers=headers)
    assert insights_resp.status_code == 200
    data = insights_resp.json()
    assert "sla_breaches_count" in data
    assert "sla_warnings_count" in data
    assert "delayed_pickups_count" in data
    assert "carrier_scorecard" in data

    # Verify standard values from sqlite seed
    assert data["unassigned_tickets_count"] == 1
    assert data["sla_breaches_count"] >= 1
    assert data["delayed_pickups_count"] >= 3  # ORD-101 (delayed), ORD-201 (delayed), ORD-202 (delayed), ORD-301 (delayed)
