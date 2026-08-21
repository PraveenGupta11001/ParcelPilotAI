import datetime
import pypdf
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import User, DocumentChunk
from app.auth.deps import get_current_user
from app.ingestion.chunk import chunk_text
from app.ingestion.embed import get_embedding

router = APIRouter(tags=["documents"])

# Helper function to parse DOCX in pure python
def extract_docx_text(file_bytes) -> str:
    try:
        from io import BytesIO
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(BytesIO(file_bytes)) as docx:
            xml_content = docx.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            texts = []
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for para in tree.findall('.//w:p', ns):
                para_text = []
                for run in para.findall('.//w:t', ns):
                    if run.text:
                        para_text.append(run.text)
                if para_text:
                    texts.append("".join(para_text))
            return "\n\n".join(texts)
    except Exception as e:
        print(f"Docx parsing failed: {e}")
        return ""

@router.post("/upload-document")
def upload_document(
    file: UploadFile = File(...),
    scope: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_scope = "general"
    if current_user.role == "customer":
        if not current_user.account_id:
            raise HTTPException(status_code=403, detail="Customer without an assigned account scope.")
        target_scope = current_user.account_id
    else:
        target_scope = scope if scope else "general"

    filename = file.filename
    content_bytes = file.file.read()
    
    text_content = ""
    if filename.endswith(".pdf"):
        from io import BytesIO
        try:
            reader = pypdf.PdfReader(BytesIO(content_bytes))
            pages_text = []
            for page in reader.pages:
                txt = page.extract_text() or ""
                pages_text.append(txt)
            text_content = "\n\n".join(pages_text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {e}")
            
    elif filename.endswith(".docx"):
        text_content = extract_docx_text(content_bytes)
        if not text_content:
            raise HTTPException(status_code=400, detail="Failed to parse DOCX file XML structure.")
            
    elif filename.endswith((".txt", ".md")):
        try:
            text_content = content_bytes.decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to decode text file: {e}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Supported are PDF, DOCX, TXT, MD.")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="The uploaded document contains no readable text content.")

    chunks = chunk_text(text_content)
    if not chunks:
        raise HTTPException(status_code=400, detail="Text could not be chunked properly (too short or parsing issue).")

    authority_level = 1 if target_scope != "general" else 2
    eff_date = datetime.date.today()
    
    for idx, chunk_txt in enumerate(chunks):
        embed_vector = get_embedding(chunk_txt)
        chunk_model = DocumentChunk(
            document_name=filename,
            chunk_index=idx,
            content=chunk_txt,
            embedding=embed_vector,
            authority_level=authority_level,
            effective_date=eff_date,
            status="CURRENT",
            scope=target_scope
        )
        db.add(chunk_model)
        
    db.commit()
    
    return {
        "success": True,
        "filename": filename,
        "chunks_count": len(chunks),
        "scope": target_scope,
        "message": f"Successfully ingested {filename} into RAG database under '{target_scope}' scope."
    }

@router.get("/uploaded-documents")
def list_uploaded_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(DocumentChunk.document_name, DocumentChunk.scope).distinct()
    if current_user.role == "customer":
        query = query.filter(DocumentChunk.scope.in_(["general", current_user.account_id]))
    
    results = query.all()
    return [
        {
            "filename": r[0],
            "scope": r[1]
        }
        for r in results
    ]

@router.get("/uploaded-documents/{filename}")
def get_uploaded_document_content(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_name == filename).order_by(DocumentChunk.chunk_index.asc()).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    for c in chunks:
        if current_user.role == "customer" and c.scope not in ["general", current_user.account_id]:
            raise HTTPException(status_code=403, detail="Access denied: Not authorized to view this document.")
            
    return {
        "filename": filename,
        "scope": chunks[0].scope,
        "authority_level": chunks[0].authority_level,
        "effective_date": chunks[0].effective_date,
        "status": chunks[0].status,
        "content": "\n\n".join([c.content for c in chunks]),
        "chunks": [{"index": c.chunk_index, "content": c.content} for c in chunks]
    }
