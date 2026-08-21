from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.models import DocumentChunk, User
from app.ingestion.embed import get_embedding

def search_documents(
    db: Session,
    user: User,
    query: str,
    include_deprecated: bool = False,
    limit: int = 4
) -> list[dict]:
    """
    RAG search against pdf document_chunks in pgvector database.
    Strictly filters scopes by user.account_id if user is a customer to prevent cross-tenant data leaks.
    """
    query_vector = get_embedding(query)
    
    # Base query filters
    filters = []
    params = {"q_vector": str(query_vector), "limit": limit}
    
    # 1. Enforce row-level tenant security scope
    if user.role == "customer":
        filters.append("(scope = 'general' OR scope = :user_account)")
        params["user_account"] = user.account_id
    else:
        # Internal roles can access all scopes
        pass
        
    # 2. Enforce active/deprecation filters
    if not include_deprecated:
        filters.append("status = 'CURRENT'")
    else:
        # Include both CURRENT and DEPRECATED files
        pass
        
    filter_clause = " AND ".join(filters) if filters else "TRUE"
    
    # Executing pgvector cosine similarity select statement
    sql = text(f"""
        SELECT id, document_name, chunk_index, content, authority_level, effective_date, status, scope,
               (embedding <=> :q_vector) as distance
        FROM document_chunks
        WHERE {filter_clause}
        ORDER BY distance ASC
        LIMIT :limit
    """)
    
    result = db.execute(sql, params).fetchall()
    
    hits = []
    for r in result:
        hits.append({
            "id": r[0],
            "document_name": r[1],
            "chunk_index": r[2],
            "content": r[3],
            "authority_level": r[4],
            "effective_date": r[5].isoformat() if r[5] else None,
            "status": r[6],
            "scope": r[7],
            "distance": float(r[8])
        })
    return hits
