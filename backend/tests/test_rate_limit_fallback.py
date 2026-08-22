import pytest
import os
import json
from unittest.mock import patch, MagicMock
from app.db.models import User, ChatSession, ChatMessage
from app.agent.orchestration import AgentService, RateLimitExceededException, _is_rate_or_token_limit_error
from app.config import SNAPSHOT_DATETIME

def test_is_rate_or_token_limit_error():
    import openai
    
    # 1. Check exact check for RateLimitError
    mock_response = MagicMock()
    mock_response.status_code = 429
    rle = openai.RateLimitError(message="Rate limit reached", response=mock_response, body=None)
    assert _is_rate_or_token_limit_error(rle) is True

    # 2. Check general exception with rate limit in string
    generic_err = Exception("Rate limit reached for model qwen/qwen3.6-27b on tokens")
    assert _is_rate_or_token_limit_error(generic_err) is True

    # 3. Check general exception with token limit in string
    token_err = Exception("Token limit exceeded for this window")
    assert _is_rate_or_token_limit_error(token_err) is True

    # 4. Check normal Exception does not match
    normal_err = Exception("Connection closed")
    assert _is_rate_or_token_limit_error(normal_err) is False

@patch("openai.OpenAI")
def test_agent_fallback_success_on_backup(mock_openai_class, db_session):
    # Mocking user
    user = db_session.query(User).filter(User.user_id == "cust-northstar").first()
    
    # Establish mock instances for OpenAI clients
    primary_client_mock = MagicMock()
    backup_client_mock = MagicMock()
    
    # Let primary client fail with RateLimitError
    import openai
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    primary_client_mock.chat.completions.create.side_effect = openai.RateLimitError(
        message="Primary rate limit error",
        response=mock_resp,
        body=None
    )
    
    # Let backup client succeed
    mock_choice = MagicMock()
    mock_choice.message.content = "Response from backup"
    mock_choice.message.tool_calls = None
    backup_client_mock.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    
    # Map client instantiation side effect to mock clients in order: primary, then backup
    mock_openai_class.side_effect = [primary_client_mock, backup_client_mock]
    
    agent = AgentService(db_session, user)
    # Set keys to trigger both options
    agent.groq_key = "gsk_primary"
    agent.groq_key_backup = "gsk_backup"
    
    result = agent.run_agent_loop(chat_history=[], message="Hello")
    
    assert result["text_response"] == "Response from backup"

@patch("openai.OpenAI")
def test_agent_all_keys_rate_limited(mock_openai_class, db_session):
    user = db_session.query(User).filter(User.user_id == "cust-northstar").first()
    
    import openai
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    rate_error = openai.RateLimitError(message="Rate limited", response=mock_resp, body=None)
    
    # Fail both calls
    client_mock = MagicMock()
    client_mock.chat.completions.create.side_effect = rate_error
    mock_openai_class.return_value = client_mock
    
    agent = AgentService(db_session, user)
    agent.groq_key = "gsk_primary"
    agent.groq_key_backup = "gsk_backup"
    
    with pytest.raises(RateLimitExceededException):
        agent.run_agent_loop(chat_history=[], message="Hello")

def test_chat_endpoint_rate_limit_persistence(client, db_session):
    # Mock mock-login to get access token
    headers = {"Authorization": "Bearer mock-token"}
    login_resp = client.post("/auth/mock-login", json={
        "email": "northstar@parcelpilot.ai",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Wrap AgentService.run_agent_loop to throw RateLimitExceededException
    with patch("app.agent.orchestration.AgentService.run_agent_loop") as mock_run:
        mock_run.side_effect = RateLimitExceededException("⚠️ **Rate Limit / Token Limit Exceeded**")
        
        # Post chat message
        resp = client.post("/chat", json={
            "message": "Hello delay check",
            "chat_history": []
        }, headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "⚠️" in data["text_response"]
        
        # Check that this message was successfully persisted to the SQLite DB
        session_id = data["session_id"]
        chat_msg = db_session.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.sender == "bot"
        ).first()
        
        assert chat_msg is not None
        assert "Rate Limit" in chat_msg.text
