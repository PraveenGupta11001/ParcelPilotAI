import os
import glob
import pypdf
import datetime
from sqlalchemy.orm import Session

from app.db.session import engine
from app.db.models import DocumentChunk
from app.ingestion.chunk import chunk_text
from app.ingestion.embed import get_embedding

# Metadata Registry as per prompt specifications
SOURCE_REGISTRY = {
    "01_Support_Policy_v3_CURRENT.pdf": {
        "authority_level": 2,
        "effective_date": datetime.date(2026, 5, 1),
        "status": "CURRENT",
        "scope": "general"
    },
    "02_Support_Policy_v2_DEPRECATED.pdf": {
        "authority_level": 4,
        "effective_date": datetime.date(2025, 1, 1),
        "status": "DEPRECATED",
        "scope": "general"
    },
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
        "authority_level": 2,
        "effective_date": datetime.date(2026, 6, 15),
        "status": "CURRENT",
        "scope": "general"
    },
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {
        "authority_level": 3,
        "effective_date": datetime.date(2026, 8, 14),
        "status": "CURRENT",
        "scope": "general"
    },
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
        "authority_level": 1,
        "effective_date": datetime.date(2026, 1, 1),
        "status": "CURRENT",
        "scope": "ACCT-001"
    },
    "06_LumenWorks_Service_Agreement.pdf": {
        "authority_level": 1,
        "effective_date": datetime.date(2026, 3, 1),
        "status": "CURRENT",
        "scope": "ACCT-002"
    }
}

def ingest_all_pdfs():
    pack_dir = "/home/praveen/my_projects/ParcelPilot_Customer_Support/Data"
    files = glob.glob(os.path.join(pack_dir, "*.pdf"))
    
    if not files:
        print(f"No PDF files found in {pack_dir}!")
        return

    db = Session(engine)
    try:
        # Clear existing doc chunks
        db.query(DocumentChunk).delete()
        db.commit()
        print("Cleared prior document chunks.")

        for fpath in sorted(files):
            fname = os.path.basename(fpath)
            if fname not in SOURCE_REGISTRY:
                print(f"Skipping unregistered document: {fname}")
                continue
            
            meta = SOURCE_REGISTRY[fname]
            print(f"Processing: {fname}...")
            
            reader = pypdf.PdfReader(fpath)
            full_text = ""
            for p_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                full_text += page_text + "\n\n"
            
            # Segment semantic chunks
            chunks = chunk_text(full_text)
            print(f"Generated {len(chunks)} chunks for {fname}")
            
            for idx, chunk in enumerate(chunks):
                print(f"  Embedding chunk {idx+1}/{len(chunks)}...")
                embed_vector = get_embedding(chunk)
                
                doc_chunk = DocumentChunk(
                    document_name=fname,
                    chunk_index=idx,
                    content=chunk,
                    embedding=embed_vector,
                    authority_level=meta["authority_level"],
                    effective_date=meta["effective_date"],
                    status=meta["status"],
                    scope=meta["scope"]
                )
                db.add(doc_chunk)
            db.commit()
            print(f"Ingested {fname} chunks successfully!")
            
        print("All PDF documents processed and registered in pgvector database!")
    except Exception as e:
        db.rollback()
        print(f"Ingestion failed: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    ingest_all_pdfs()
