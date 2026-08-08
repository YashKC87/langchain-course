from app.models.model_interface import ModelType
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.rag import RAGPattern
from app.services.vector_store import VectorStore


def test_rag_retrieves_sop_and_uses_slm(trace_store):
    store = VectorStore()
    hits = store.search(
        "low disk space OneDrive synchronization failures approved remediation",
        top_k=4,
    )
    names = {h.document_name for h in hits}
    assert "disk_remediation.md" in names or "onedrive_troubleshooting.md" in names

    pattern = RAGPattern(tracer=LangSmithTracer(store=trace_store), vector_store=store)
    result = pattern.run()
    assert result.device_id == "LAPTOP-1507"
    gen = next(s for s in result.segments if s.segment == "SLM Grounded Generation")
    assert gen.model_type == ModelType.SLM
    assert result.comparisons["grounding_score"] >= 0
    assert "rag_slm_vs_rag_frontier" in result.comparisons
    assert result.comparisons["retrieved_documents"]
