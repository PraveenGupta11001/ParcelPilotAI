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

def test_refresh_token_flow(client):
    # Login and get tokens
    response = client.post("/auth/login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    refresh_token = data["refresh_token"]
    
    # Use refresh token to get new tokens
    refresh_resp = client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data
    assert refresh_data["access_token"] != data["access_token"]
    assert refresh_data["refresh_token"] != data["refresh_token"]

def test_refresh_token_errors(client):
    # Invalid token type
    resp1 = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert resp1.status_code == 401
    
    # Try custom JWT with wrong type
    import uuid
    from app.auth.jwt import create_access_token
    wrong_token = create_access_token({"sub": "cust-northstar", "type": "access"})
    resp2 = client.post("/auth/refresh", json={"refresh_token": wrong_token})
    assert resp2.status_code == 401

