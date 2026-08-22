import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_chat_endpoint_basic(client, db_session):
    # Ensure we have a token from mock login
    login_resp = client.post('/auth/mock-login', json={'email': 'northstar@parcelpilot.ai', 'password': 'password123'})
    assert login_resp.status_code == 200
    token = login_resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # Send a simple chat message
    chat_resp = client.post('/chat', json={'message': 'Hello', 'chat_history': []}, headers=headers)
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert 'text_response' in data
    assert isinstance(data['text_response'], str)
    assert 'session_id' in data
    assert isinstance(data['session_id'], str)
