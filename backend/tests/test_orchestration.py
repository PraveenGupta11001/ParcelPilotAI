import pytest
from app.db.models import PendingAction, Order, Ticket, Escalation

def test_propose_confirm_cancellation_workflow(client, db_session):
    # 1. Login as customer (Northstar cust-northstar)
    login_resp = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Propose cancellation of ORD-101 using agent API parameters or direct DB propose call in main router
    # Let's test the endpoint directly to ensure integration completeness.
    # First, let's call /chat to test that mock-fallback or loop returns tool call proposal draft
    # Otherwise call the main propose action helper directly to seed a proposed action.
    # To check the proposal endpoint security and confirm state transitions, we verify both stages:
    from app.tools.actions import propose_action
    from app.db.models import User
    
    cust_user = db_session.query(User).filter(User.user_id == "cust-northstar").first()
    prop = propose_action(
        db=db_session,
        user=cust_user,
        action_type="CANCEL_ORDER",
        order_id="ORD-101",
        reason="Customer requested cancellation"
    )
    
    proposal_id = prop["proposal_id"]
    
    # Confirm using /chat/confirm with customer token
    confirm_resp = client.post("/chat/confirm", json={"proposal_id": proposal_id}, headers=headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["success"] is True
    
    # Check that order status transitioned to CANCELLED in DB
    order = db_session.query(Order).filter(Order.order_id == "ORD-101").first()
    assert order.status == "CANCELLED"
    assert order.cancellation_requested_at is not None

def test_service_credit_approval_limits(client, db_session):
    # Propose a service credit of INR 1200 on ORD-301 (exceeding 1000 threshold)
    from app.tools.actions import propose_action
    from app.db.models import User
    
    agent_user = db_session.query(User).filter(User.user_id == "agent-maya").first()
    prop = propose_action(
        db=db_session,
        user=agent_user,
        action_type="ISSUE_CREDIT",
        order_id="ORD-301",
        ticket_id="TKT-101",
        amount=1200.0,
        reason="Severely delayed, manual goodwill credit"
    )
    proposal_id = prop["proposal_id"]

    # 1. Standard agent (maya) tries to confirm the > 1000 credit -> should fail
    login_resp = client.post("/auth/mock-login", json={
        "email": "maya@parcelpilot.ai",
        "password": "password123"
    })
    agent_token = login_resp.json()["access_token"]
    agent_headers = {"Authorization": f"Bearer {agent_token}"}
    
    confirm_resp1 = client.post("/chat/confirm", json={"proposal_id": proposal_id}, headers=agent_headers)
    assert confirm_resp1.status_code == 403
    assert "require manager (lead) approval" in confirm_resp1.json()["detail"]

    # 2. Customer tries to confirm service credit -> should fail
    login_resp = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    cust_token = login_resp.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    confirm_resp2 = client.post("/chat/confirm", json={"proposal_id": proposal_id}, headers=cust_headers)
    assert confirm_resp2.status_code == 403

    # 3. Operations Lead (rohit) is authorized to confirm -> should succeed
    login_resp = client.post("/auth/mock-login", json={
        "email": "rohit@parcelpilot.ai",
        "password": "password123"
    })
    lead_token = login_resp.json()["access_token"]
    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    
    confirm_resp3 = client.post("/chat/confirm", json={"proposal_id": proposal_id}, headers=lead_headers)
    assert confirm_resp3.status_code == 200
    assert confirm_resp3.json()["success"] is True
    
    # Verify escalation was stored
    esc = db_session.query(Escalation).filter(Escalation.amount == 1200.0).first()
    assert esc is not None
    assert esc.status == "APPROVED"
