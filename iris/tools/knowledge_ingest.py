"""
Knowledge ingest tools — upload documents and search the human knowledge base.

These are agent-facing tools that the AI can call during analysis to store
and retrieve user-provided materials (research reports, notes, URL content).
"""

from tools.base import ToolResult, make_tool_schema
from tools.retrieval import EvidenceRetriever


# ── Schemas ───────────────────────────────────────────────

UPLOAD_DOCUMENT_SCHEMA = make_tool_schema(
    name="upload_document",
    description=(
        "Save a document (research note, article content, etc.) to the knowledge base "
        "for future reference. Use when the user provides text you should remember across sessions."
    ),
    properties={
        "title": {"type": "string", "description": "Document title"},
        "content": {"type": "string", "description": "Full text content of the document"},
        "doc_type": {
            "type": "string",
            "enum": ["note", "report", "url_content", "pdf"],
            "description": "Type of document",
        },
        "company": {
            "type": "string",
            "description": "Optional company ticker to associate with this document",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional tags for categorization",
        },
    },
    required=["title", "content", "doc_type"],
)

SEARCH_DOCUMENTS_SCHEMA = make_tool_schema(
    name="search_documents",
    description=(
        "Search the user's uploaded knowledge base (notes, reports, articles). "
        "Returns relevant passages with citations to the source document. "
        "Use to find information the user has previously provided."
    ),
    properties={
        "query": {"type": "string", "description": "Natural language search query"},
        "top_k": {"type": "integer", "description": "Max results to return. Default 5."},
        "company": {
            "type": "string",
            "description": "Optional: filter by company ticker",
        },
    },
    required=["query"],
)


# ── Tool implementations ──────────────────────────────────

def upload_document(
    retriever: EvidenceRetriever,
    title: str,
    content: str,
    doc_type: str,
    company: str = None,
    tags: list[str] = None,
) -> ToolResult:
    """Save a document to the knowledge base."""
    if not content or not content.strip():
        return ToolResult.fail("Document content is empty", hint="Provide non-empty text content")

    try:
        result = retriever.save_document(
            title=title,
            doc_type=doc_type,
            content_text=content,
            company=company,
            tags=tags,
        )
        return ToolResult.ok(result)
    except Exception as e:
        return ToolResult.fail(f"Failed to save document: {e}")


def search_documents(
    retriever: EvidenceRetriever,
    query: str,
    top_k: int = 5,
    company: str = None,
) -> ToolResult:
    """Search the knowledge base for relevant passages."""
    if not query or not query.strip():
        return ToolResult.fail("Search query is empty")

    try:
        results = retriever.semantic_search(
            query=query,
            top_k=top_k or 5,
            source_category="human_knowledge",
        )

        # Filter by company if specified
        if company:
            company_upper = company.upper()
            filtered = []
            for r in results:
                doc = retriever.get_document(r.get("document_id", ""))
                if doc and doc.get("company", "").upper() == company_upper:
                    filtered.append(r)
            results = filtered

        return ToolResult.ok({
            "query": query,
            "results": results,
            "count": len(results),
        })
    except Exception as e:
        return ToolResult.fail(f"Search failed: {e}")
