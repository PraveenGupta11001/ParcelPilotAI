from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import DocumentChunk, User

def get_document_count(db: Session, user: User, include_deprecated: bool = False) -> dict:
    """
    Returns the distinct count of documents/policy files in the database,
    restricting visibility by user role/account_id for tenant isolation.
    """
    query = db.query(DocumentChunk.document_name)
    if user.role == "customer":
        query = query.filter((DocumentChunk.scope == 'general') | (DocumentChunk.scope == user.account_id))
    if not include_deprecated:
        query = query.filter(DocumentChunk.status == 'CURRENT')
    distinct_docs = query.distinct().count()
    return {"total_documents": distinct_docs}

def list_all_documents(db: Session, user: User, include_deprecated: bool = False) -> list[dict]:
    """
    Lists all distinct documents/policy files in the database along with their metadata,
    respecting tenant isolation scopes.
    """
    query = db.query(
        DocumentChunk.document_name,
        func.min(DocumentChunk.authority_level).label("authority_level"),
        func.max(DocumentChunk.effective_date).label("effective_date"),
        DocumentChunk.status,
        DocumentChunk.scope
    )
    if user.role == "customer":
        query = query.filter((DocumentChunk.scope == 'general') | (DocumentChunk.scope == user.account_id))
    if not include_deprecated:
        query = query.filter(DocumentChunk.status == 'CURRENT')
    
    query = query.group_by(DocumentChunk.document_name, DocumentChunk.status, DocumentChunk.scope)
    results = query.all()
    
    docs = []
    for r in results:
        docs.append({
            "document_name": r.document_name,
            "authority_level": r.authority_level,
            "effective_date": r.effective_date.isoformat() if r.effective_date else None,
            "status": r.status,
            "scope": r.scope
        })
    return docs
