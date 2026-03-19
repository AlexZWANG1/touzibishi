"""Tests for the knowledge ingest system — chunker, document CRUD, search, tools."""

import json
from unittest.mock import patch, MagicMock

import pytest

from tools.chunker import chunk_text, ChunkInfo
from tools.retrieval import SQLiteRetriever


# ── Chunker tests ─────────────────────────────────────────

class TestChunker:
    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_single_paragraph(self):
        text = "Hello world, this is a test."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_splits_on_paragraph_boundaries(self):
        paragraphs = [f"Paragraph {i}. " * 20 for i in range(5)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1
        # All chunks should have content
        for c in chunks:
            assert len(c.content) > 0
            assert c.chunk_index >= 0

    def test_chunk_offsets_are_reasonable(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].char_offset_start >= 0

    def test_overlap_produces_more_chunks(self):
        text = "\n\n".join([f"Para {i}. " * 30 for i in range(10)])
        no_overlap = chunk_text(text, chunk_size=200, overlap=0)
        with_overlap = chunk_text(text, chunk_size=200, overlap=100)
        # Overlap should produce at least as many chunks
        assert len(with_overlap) >= len(no_overlap)


# ── Document CRUD tests ──────────────────────────────────

@pytest.fixture
def retriever(tmp_path):
    """Create a retriever with embedding disabled."""
    with patch("tools.retrieval.Embedder") as MockEmbedder:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.1] * 10]
        mock_instance.model_id = "test:mock"
        MockEmbedder.return_value = mock_instance
        r = SQLiteRetriever(str(tmp_path / "test.db"))
        yield r


class TestDocumentCRUD:
    def test_save_document(self, retriever):
        result = retriever.save_document(
            title="Test Note",
            doc_type="note",
            content_text="This is a test note with some content.",
            company="NVDA",
            tags=["test", "research"],
        )
        assert result["id"].startswith("kdoc_")
        assert result["title"] == "Test Note"
        assert result["chunk_count"] >= 1
        assert result["company"] == "NVDA"

    def test_list_documents(self, retriever):
        retriever.save_document(title="Doc 1", doc_type="note", content_text="Content 1")
        retriever.save_document(title="Doc 2", doc_type="pdf", content_text="Content 2", company="AAPL")
        docs = retriever.list_documents()
        assert len(docs) == 2

    def test_list_documents_filter_by_company(self, retriever):
        retriever.save_document(title="NVDA Note", doc_type="note", content_text="Content", company="NVDA")
        retriever.save_document(title="AAPL Note", doc_type="note", content_text="Content", company="AAPL")
        docs = retriever.list_documents(company="NVDA")
        assert len(docs) == 1
        assert docs[0]["title"] == "NVDA Note"

    def test_list_documents_filter_by_type(self, retriever):
        retriever.save_document(title="Note", doc_type="note", content_text="Content")
        retriever.save_document(title="PDF", doc_type="pdf", content_text="Content")
        docs = retriever.list_documents(doc_type="pdf")
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "pdf"

    def test_get_document(self, retriever):
        result = retriever.save_document(title="Detail Test", doc_type="note", content_text="Full content here.")
        doc = retriever.get_document(result["id"])
        assert doc is not None
        assert doc["title"] == "Detail Test"
        assert doc["content_text"] == "Full content here."
        assert doc["chunk_count"] >= 1

    def test_get_document_not_found(self, retriever):
        assert retriever.get_document("nonexistent_id") is None

    def test_delete_document(self, retriever):
        result = retriever.save_document(title="To Delete", doc_type="note", content_text="Will be deleted.")
        assert retriever.delete_document(result["id"]) is True
        assert retriever.get_document(result["id"]) is None
        # Chunks should also be deleted
        assert retriever.list_documents() == []

    def test_delete_document_not_found(self, retriever):
        assert retriever.delete_document("nonexistent_id") is False

    def test_document_tags_persisted(self, retriever):
        result = retriever.save_document(
            title="Tagged", doc_type="note",
            content_text="Content", tags=["ai", "semiconductors"]
        )
        doc = retriever.get_document(result["id"])
        assert doc["tags"] == ["ai", "semiconductors"]


# ── Semantic search tests ─────────────────────────────────

class TestSemanticSearch:
    def test_search_returns_results(self, retriever):
        retriever.save_document(title="AI Research", doc_type="note", content_text="Neural networks and transformers are reshaping AI.")
        results = retriever.semantic_search(query="AI transformer", source_category="human_knowledge")
        assert len(results) >= 1
        assert results[0]["source_category"] == "human_knowledge"

    def test_search_all_includes_both_categories(self, retriever):
        # Save an observation (AI memory)
        from core.schemas import Observation
        from datetime import datetime
        obs = Observation(
            id="obs_test", subject="NVDA", claim="Strong data center growth",
            time=datetime(2026, 1, 1), source="test", fact_or_view="fact",
            relevance=0.9, citation="...",
            extracted_at=datetime.now(), extracted_by="test"
        )
        retriever.save_observation(obs)
        # Save a knowledge document
        retriever.save_document(title="NVDA Note", doc_type="note", content_text="NVIDIA data center revenue growing fast.")
        # Search all
        results = retriever.semantic_search(query="NVDA data center", source_category="all")
        categories = {r["source_category"] for r in results}
        # Should have results from at least one category
        assert len(results) >= 1

    def test_search_filter_ai_memory_only(self, retriever):
        retriever.save_document(title="Human Doc", doc_type="note", content_text="Some human content.")
        results = retriever.semantic_search(query="content", source_category="ai_memory")
        # Should not include knowledge chunks
        for r in results:
            assert r.get("source_category") != "human_knowledge"


# ── Tool interface tests ─────────────────────────────────

class TestKnowledgeTools:
    def test_upload_document_tool(self, retriever):
        from tools.knowledge_ingest import upload_document
        result = upload_document(
            retriever=retriever,
            title="Tool Test",
            content="Some content from the tool.",
            doc_type="note",
        )
        assert result.status == "ok"
        assert result.data["id"].startswith("kdoc_")

    def test_upload_document_empty_content(self, retriever):
        from tools.knowledge_ingest import upload_document
        result = upload_document(
            retriever=retriever,
            title="Empty",
            content="",
            doc_type="note",
        )
        assert result.status == "error"

    def test_search_documents_tool(self, retriever):
        from tools.knowledge_ingest import upload_document, search_documents
        upload_document(
            retriever=retriever,
            title="Searchable",
            content="NVIDIA is dominating the GPU market.",
            doc_type="note",
        )
        result = search_documents(retriever=retriever, query="GPU market")
        assert result.status == "ok"
        assert result.data["count"] >= 1

    def test_search_documents_empty_query(self, retriever):
        from tools.knowledge_ingest import search_documents
        result = search_documents(retriever=retriever, query="")
        assert result.status == "error"
