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


def test_download_document_not_found(client):
    headers = _get_auth_headers(client)
    response = client.get("/uploaded-documents/nonexistent_document.pdf/download", headers=headers)
    assert response.status_code == 404
    assert "Document metadata not found" in response.json()["detail"]


def test_download_text_only_document_fails(client, db_session):
    headers = _get_auth_headers(client)
    # First ingest a text document (which creates it in DB but doesn't save to physical Data folder)
    file_content = b"Some random content."
    files = {"file": ("test_only_text_doc.txt", file_content, "text/plain")}
    response = client.post("/upload-document", files=files, headers=headers)
    assert response.status_code == 200

    # Try downloading it (since it's not saved physically in Data/ folder, should return 404 physical file not available)
    response = client.get("/uploaded-documents/test_only_text_doc.txt/download", headers=headers)
    assert response.status_code == 404
    assert "Physical PDF file is not available" in response.json()["detail"]


def test_delete_document_not_found(client):
    headers = _get_auth_headers(client)
    res = client.delete("/uploaded-documents/non_existent.txt", headers=headers)
    assert res.status_code == 404
    assert "Document not found" in res.json()["detail"]


def test_delete_document_customer_permissions(client, db_session):
    headers_cust1 = _get_auth_headers(client, email="northstar@parcelpilot.ai", password="password123")
    headers_cust2 = _get_auth_headers(client, email="lumenworks@parcelpilot.ai", password="password123")
    headers_agent = _get_auth_headers(client, email="maya@parcelpilot.ai", password="password123")

    # 1. Ingest document as customer 1 (gets scoped to ACCT-001)
    file_content = b"Northstar custom agreement files."
    files = {"file": ("northstar_custom.txt", file_content, "text/plain")}
    res = client.post("/upload-document", files=files, headers=headers_cust1)
    assert res.status_code == 200

    # 2. Customer 2 trying to delete Customer 1's document should return 403 Forbidden
    res_del_cust2 = client.delete("/uploaded-documents/northstar_custom.txt", headers=headers_cust2)
    assert res_del_cust2.status_code == 403

    # 3. Customer 1 trying to delete their own document should return 200 OK
    res_del_cust1 = client.delete("/uploaded-documents/northstar_custom.txt", headers=headers_cust1)
    assert res_del_cust1.status_code == 200
    assert res_del_cust1.json()["success"] is True

    # 4. Ingest again as customer 1
    files = {"file": ("northstar_custom.txt", file_content, "text/plain")}
    res = client.post("/upload-document", files=files, headers=headers_cust1)
    assert res.status_code == 200

    # 5. Agent trying to delete Customer 1's document should return 200 OK (internal users can delete anything)
    res_del_agent = client.delete("/uploaded-documents/northstar_custom.txt", headers=headers_agent)
    assert res_del_agent.status_code == 200


