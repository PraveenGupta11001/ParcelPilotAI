import pytest
from jose import jwt
from app.config import SECRET_KEY, ALGORITHM

def test_mock_login_success(client):
    # Test customer login
    response = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["user_id"] == "cust-northstar"
    assert data["user"]["role"] == "customer"
    assert data["user"]["account_id"] == "ACCT-001"

    # Decode token check
    token = data["access_token"]
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "cust-northstar"

def test_mock_login_invalid_credentials(client):
    response = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

def test_role_enforcement_insights_endpoint(client):
    # 1. Customer login
    login_resp = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Customer tries to call /insights -> should fail
    resp = client.get("/insights", headers=headers)
    assert resp.status_code == 403
    assert "Required privileges missing" in resp.json()["detail"]

    # 2. Support Agent login
    login_resp = client.post("/auth/mock-login", json={
        "email": "maya@parcelpilot.ai",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Support agent calls /insights -> should succeed
    resp = client.get("/insights", headers=headers)
    assert resp.status_code == 200
