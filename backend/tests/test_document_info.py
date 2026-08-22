import pytest
import datetime
from app.db.models import User, DocumentChunk
from app.tools.document_info import get_document_count, list_all_documents
from app.agent.orchestration import AgentService

@pytest.fixture(autouse=True)
def seed_test_documents(db_session):
    dummy_embedding = [0.0] * 1536
    # Seed mock document chunks
    d1 = DocumentChunk(
        document_name="05_Northstar_Logistics_Enterprise_Agreement.pdf",
        chunk_index=0,
        content="Northstar policy details.",
        embedding=dummy_embedding,
        authority_level=1,
        effective_date=datetime.date(2026, 1, 1),
        status="CURRENT",
        scope="ACCT-001"
    )
    d2 = DocumentChunk(
        document_name="06_LumenWorks_Service_Agreement.pdf",
        chunk_index=0,
        content="LumenWorks policy details.",
        embedding=dummy_embedding,
        authority_level=1,
        effective_date=datetime.date(2026, 3, 1),
        status="CURRENT",
        scope="ACCT-002"
    )
    d3 = DocumentChunk(
        document_name="03_Cancellation_and_Service_Credit_SOP_v4.pdf",
        chunk_index=0,
        content="General Cancellation SOP.",
        embedding=dummy_embedding,
        authority_level=2,
        effective_date=datetime.date(2026, 6, 15),
        status="CURRENT",
        scope="general"
    )
    d4 = DocumentChunk(
        document_name="03_Cancellation_and_Service_Credit_SOP_v4.pdf",
        chunk_index=1,
        content="General cancellation fee details.",
        embedding=dummy_embedding,
        authority_level=2,
        effective_date=datetime.date(2026, 6, 15),
        status="CURRENT",
        scope="general"
    )
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

def test_document_info_tenant_restriction(db_session):
    # Retrieve representative users
    cust_northstar = db_session.query(User).filter(User.user_id == "cust-northstar").first()
    agent_maya = db_session.query(User).filter(User.user_id == "agent-maya").first()
    
    assert cust_northstar is not None
    assert agent_maya is not None

    # Get document count for internal support (should see all 3 distinct files: Northstar, LumenWorks, general SOP)
    internal_count = get_document_count(db=db_session, user=agent_maya)
    assert "total_documents" in internal_count
    assert internal_count["total_documents"] == 3
    
    # Get document count for customer (should only see general + Northstar documents, not LumenWorks -> 2 distinct files)
    customer_count = get_document_count(db=db_session, user=cust_northstar)
    assert customer_count["total_documents"] == 2

    # List all documents for internal support (should list Northstar, LumenWorks, general SOPs, etc.)
    internal_list = list_all_documents(db=db_session, user=agent_maya)
    internal_names = [d["document_name"] for d in internal_list]
    assert len(internal_list) == 3
    assert any("Northstar" in name for name in internal_names)
    assert any("LumenWorks" in name for name in internal_names)
    assert any("SOP" in name for name in internal_names)

    # List all documents for customer (should NOT list LumenWorks)
    customer_list = list_all_documents(db=db_session, user=cust_northstar)
    customer_names = [d["document_name"] for d in customer_list]
    assert len(customer_list) == 2
    assert any("Northstar" in name for name in customer_names)
    assert any("SOP" in name for name in customer_names)
    assert not any("LumenWorks" in name for name in customer_names)

def test_agent_run_tool_integration(db_session):
    agent_maya = db_session.query(User).filter(User.user_id == "agent-maya").first()
    agent_service = AgentService(db=db_session, user=agent_maya)
    
    # Validate count execution via AgentService
    count_res = agent_service.run_tool("get_document_count", {})
    import json
    parsed_count = json.loads(count_res)
    assert "total_documents" in parsed_count
    assert parsed_count["total_documents"] == 3
    
    # Validate list execution via AgentService
    list_res = agent_service.run_tool("list_all_documents", {})
    parsed_list = json.loads(list_res)
    assert isinstance(parsed_list, list)
    assert len(parsed_list) == 3
    assert "document_name" in parsed_list[0]
