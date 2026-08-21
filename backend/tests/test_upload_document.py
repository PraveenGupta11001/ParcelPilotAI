import pytest
from app.db.models import DocumentChunk


def _get_auth_headers(client, email: str = "maya@parcelpilot.ai", password: str = "password123") -> dict:
    """Helper: log in and return Bearer auth headers."""
    resp = client.post("/auth/mock-login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_text_file_success(client, db_session):
    headers = _get_auth_headers(client)
    file_content = b"Hello, this is a test document for RAG ingestion."
    files = {"file": ("test.txt", file_content, "text/plain")}
    response = client.post("/upload-document", files=files, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "test.txt"
    assert data["chunks_count"] > 0
    # Verify chunks stored in DB
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_name == "test.txt").all()
    assert len(chunks) == data["chunks_count"]


def test_upload_unsupported_file_type(client):
    headers = _get_auth_headers(client)
    file_content = b"<html></html>"
    files = {"file": ("test.html", file_content, "text/html")}
    response = client.post("/upload-document", files=files, headers=headers)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
