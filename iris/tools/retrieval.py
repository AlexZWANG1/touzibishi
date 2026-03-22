import json
import math
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Optional

from core.schemas import Observation, Hypothesis, EvidenceCard, ValuationOutput, TradeScore, AuditTrail
from tools.embedder import Embedder
from tools.chunker import chunk_text


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EvidenceRetriever(ABC):
    """Abstract storage interface. query param reserved for future vector search."""

    @abstractmethod
    def save_observation(self, obs: Observation) -> None: ...

    @abstractmethod
    def query_observations(
        self,
        subject: str = None,
        min_relevance: float = 0.0,
        query: str = None,
    ) -> list[Observation]: ...

    @abstractmethod
    def save_hypothesis(self, hyp: Hypothesis) -> None: ...

    @abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]: ...

    @abstractmethod
    def list_hypotheses(self, company: str = None) -> list[Hypothesis]: ...

    @abstractmethod
    def save_valuation(self, valuation: ValuationOutput, valuation_id: str) -> None: ...

    @abstractmethod
    def get_valuation(self, valuation_id: str) -> Optional[ValuationOutput]: ...

    @abstractmethod
    def save_trade_score(self, score: TradeScore) -> None: ...

    @abstractmethod
    def get_trade_score(self, trade_score_id: str) -> Optional[TradeScore]: ...

    @abstractmethod
    def save_audit_trail(self, audit: AuditTrail) -> None: ...

    @abstractmethod
    def get_audit_trail(self, company: str) -> Optional[AuditTrail]: ...

    @abstractmethod
    def by_subject(
        self,
        subject: str,
        max_observations: int = 10,
        max_hypotheses: int = 3,
    ) -> dict: ...


class SQLiteRetriever(EvidenceRetriever):
    # Synthetic rows produced by tests/mocks should not pollute user-facing history.
    _NON_TEST_RUNS_WHERE = (
        "NOT (query LIKE 'Analyze %' AND COALESCE(reasoning_text, '') = 'Test analysis complete')"
    )
    # Only include tickers from runs that look like real analysis requests.
    _ANALYSIS_INTENT_WHERE = (
        "("
        "query LIKE '%分析%' OR query LIKE '%估值%' OR query LIKE '%财报%' OR query LIKE '%复盘%' "
        "OR LOWER(COALESCE(query, '')) LIKE '%analysis%' "
        "OR LOWER(COALESCE(query, '')) LIKE '%valuation%' "
        "OR LOWER(COALESCE(query, '')) LIKE '%research%' "
        "OR UPPER(COALESCE(query, '')) GLOB '*[A-Z]*'"
        ")"
    )
    def __init__(self, db_path: str, usage_tracker: Callable[..., None] | None = None):
        self.db_path = db_path
        self._usage_tracker = usage_tracker
        self.embedder = Embedder(usage_tracker=usage_tracker)
        self._init_db()

    def set_usage_tracker(self, usage_tracker: Callable[..., None] | None):
        self._usage_tracker = usage_tracker

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hypotheses (
                    id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS valuations (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trade_scores (
                    id TEXT PRIMARY KEY,
                    hypothesis_id TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_trails (
                    id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    ticker TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    reasoning_text TEXT,
                    thinking_text TEXT,
                    timeline_json TEXT,
                    panels_json TEXT,
                    recommendation TEXT,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_runs_ticker
                    ON analysis_runs(ticker);
                CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
                    ON analysis_runs(created_at);

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    source_path TEXT,
                    content_text TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    company TEXT,
                    source_type TEXT DEFAULT 'manual',
                    source_name TEXT,
                    published_at TEXT,
                    canonical_url TEXT,
                    url_hash TEXT,
                    content_hash TEXT,
                    ai_metadata_json TEXT DEFAULT '{}',
                    extraction_meta_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_kdocs_company ON knowledge_documents(company);
                CREATE INDEX IF NOT EXISTS idx_kdocs_doc_type ON knowledge_documents(doc_type);
                CREATE INDEX IF NOT EXISTS idx_kdocs_canonical_url ON knowledge_documents(canonical_url);
                CREATE INDEX IF NOT EXISTS idx_kdocs_url_hash ON knowledge_documents(url_hash);
                CREATE INDEX IF NOT EXISTS idx_kdocs_content_hash ON knowledge_documents(content_hash);
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    char_offset_start INTEGER,
                    char_offset_end INTEGER,
                    embedding TEXT,
                    embedding_model TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES knowledge_documents(id)
                );
                CREATE INDEX IF NOT EXISTS idx_kchunks_doc ON knowledge_chunks(document_id);

                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    subject TEXT,
                    content TEXT NOT NULL,
                    structured_data TEXT DEFAULT '{}',
                    confidence REAL,
                    source TEXT,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ki_type ON knowledge_items(type);
                CREATE INDEX IF NOT EXISTS idx_ki_subject ON knowledge_items(subject);
                CREATE INDEX IF NOT EXISTS idx_ki_type_subject ON knowledge_items(type, subject);
            """)
            # Idempotent migration: add ticker column to valuations if missing
            try:
                conn.execute("ALTER TABLE valuations ADD COLUMN ticker TEXT")
            except Exception:
                pass  # column already exists
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_valuations_ticker ON valuations(ticker)")
            except Exception:
                pass
            # Idempotent migration: add embedding_model column to embeddings
            try:
                conn.execute("ALTER TABLE embeddings ADD COLUMN embedding_model TEXT DEFAULT 'text-embedding-3-small'")
            except Exception:
                pass
            # Idempotent migration: add URL-ingest metadata columns for knowledge_documents
            migrations = [
                "ALTER TABLE knowledge_documents ADD COLUMN source_type TEXT DEFAULT 'manual'",
                "ALTER TABLE knowledge_documents ADD COLUMN source_name TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN published_at TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN canonical_url TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN url_hash TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN content_hash TEXT",
                "ALTER TABLE knowledge_documents ADD COLUMN ai_metadata_json TEXT DEFAULT '{}'",
                "ALTER TABLE knowledge_documents ADD COLUMN extraction_meta_json TEXT DEFAULT '{}'",
                "ALTER TABLE knowledge_documents ADD COLUMN category TEXT DEFAULT 'other'",
                "ALTER TABLE knowledge_documents ADD COLUMN industry TEXT",
            ]
            for migration_sql in migrations:
                try:
                    conn.execute(migration_sql)
                except Exception:
                    pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_canonical_url ON knowledge_documents(canonical_url)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_url_hash ON knowledge_documents(url_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_content_hash ON knowledge_documents(content_hash)")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_category ON knowledge_documents(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kdocs_industry ON knowledge_documents(industry)")
            except Exception:
                pass
            # Idempotent migration: add conversation persistence columns
            for col, col_type in [("messages_json", "TEXT"), ("turn_count", "INTEGER DEFAULT 1")]:
                try:
                    conn.execute(f"ALTER TABLE analysis_runs ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

    def save_observation(self, obs: Observation) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO observations (id, subject, data) VALUES (?, ?, ?)",
                (obs.id, obs.subject, obs.model_dump_json()),
            )
        self.save_embedding(obs.id, f"{obs.subject}: {obs.claim}", "observation")

    def query_observations(
        self,
        subject: str = None,
        min_relevance: float = 0.0,
        query: str = None,
    ) -> list[Observation]:
        with self._conn() as conn:
            if subject:
                rows = conn.execute(
                    "SELECT data FROM observations WHERE UPPER(subject) = UPPER(?) ORDER BY rowid",
                    (subject,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT data FROM observations ORDER BY rowid").fetchall()
        results = [Observation.model_validate_json(r[0]) for r in rows]
        return [o for o in results if o.relevance >= min_relevance]

    def save_hypothesis(self, hyp: Hypothesis) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO hypotheses (id, company, data) VALUES (?, ?, ?)",
                (hyp.id, hyp.company, hyp.model_dump_json()),
            )
        self.save_embedding(hyp.id, f"{hyp.company}: {hyp.thesis}", "hypothesis")

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM hypotheses WHERE id = ?", (hypothesis_id,)
            ).fetchone()
        return Hypothesis.model_validate_json(row[0]) if row else None

    def list_hypotheses(self, company: str = None) -> list[Hypothesis]:
        with self._conn() as conn:
            if company:
                rows = conn.execute(
                    "SELECT data FROM hypotheses WHERE UPPER(company) = UPPER(?) ORDER BY rowid",
                    (company,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT data FROM hypotheses ORDER BY rowid").fetchall()
        return [Hypothesis.model_validate_json(r[0]) for r in rows]

    def save_valuation(self, valuation: ValuationOutput, valuation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO valuations (id, data) VALUES (?, ?)",
                (valuation_id, valuation.model_dump_json()),
            )

    def get_valuation(self, valuation_id: str) -> Optional[ValuationOutput]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM valuations WHERE id = ?", (valuation_id,)
            ).fetchone()
        return ValuationOutput.model_validate_json(row[0]) if row else None

    def save_trade_score(self, score: TradeScore) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trade_scores (id, hypothesis_id, data) VALUES (?, ?, ?)",
                (score.id, score.hypothesis_id, score.model_dump_json()),
            )

    def get_trade_score(self, trade_score_id: str) -> Optional[TradeScore]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM trade_scores WHERE id = ?", (trade_score_id,)
            ).fetchone()
        return TradeScore.model_validate_json(row[0]) if row else None

    def save_audit_trail(self, audit: AuditTrail) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO audit_trails (id, company, data) VALUES (?, ?, ?)",
                (audit.id, audit.company, audit.model_dump_json()),
            )

    def get_audit_trail(self, company: str) -> Optional[AuditTrail]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM audit_trails WHERE UPPER(company) = UPPER(?) ORDER BY rowid DESC LIMIT 1",
                (company,)
            ).fetchone()
        return AuditTrail.model_validate_json(row[0]) if row else None

    def by_subject(
        self,
        subject: str,
        max_observations: int = 10,
        max_hypotheses: int = 3,
    ) -> dict:
        subject_norm = (subject or "").strip().upper()
        if subject_norm:
            obs_source = self.query_observations(subject=subject_norm)
            hyp_source = self.list_hypotheses(company=subject_norm)
            with self._conn() as conn:
                rows = conn.execute(
                    """
                    SELECT subject AS s FROM observations WHERE UPPER(subject) != UPPER(?)
                    UNION
                    SELECT company AS s FROM hypotheses WHERE UPPER(company) != UPPER(?)
                    ORDER BY s
                    LIMIT 8
                    """,
                    (subject_norm, subject_norm),
                ).fetchall()
            other_subjects = [r[0] for r in rows if r[0]]
        else:
            obs_source = self.query_observations()
            hyp_source = self.list_hypotheses()
            other_subjects = []

        observations = [
            {
                "id": o.id,
                "subject": o.subject,
                "claim": o.claim,
                "source": o.source,
                "relevance": o.relevance,
            }
            for o in obs_source
        ][-max_observations:]

        hypotheses = [
            {
                "id": h.id,
                "company": h.company,
                "thesis": h.thesis,
                "confidence": h.confidence,
                "drivers": [{"name": d.name} for d in h.drivers],
            }
            for h in hyp_source
        ][-max_hypotheses:]

        return {
            "subject": subject_norm,
            "observations": observations,
            "hypotheses": hypotheses,
            "other_subjects": other_subjects,
        }

    # ---- analysis_runs CRUD ----

    def save_analysis_run(
        self,
        *,
        id: str,
        query: str,
        ticker: str,
        status: str,
        reasoning_text: str,
        thinking_text: str,
        timeline_json: str,
        panels_json: str,
        recommendation: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        messages_json: str | None = None,
        turn_count: int = 1,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analysis_runs
                   (id, query, ticker, status, reasoning_text, thinking_text,
                    timeline_json, panels_json, recommendation, tokens_in, tokens_out,
                    messages_json, turn_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (id, query, ticker, status, reasoning_text, thinking_text,
                 timeline_json, panels_json, recommendation, tokens_in, tokens_out,
                 messages_json, turn_count),
            )

    def get_analysis_run(self, run_id: str) -> dict | None:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_analysis_runs(
        self, *, ticker: str | None = None, limit: int = 30, offset: int = 0
    ) -> dict:
        where_base = self._NON_TEST_RUNS_WHERE
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            if ticker:
                total = conn.execute(
                    f"SELECT COUNT(*) FROM analysis_runs WHERE {where_base} AND UPPER(ticker) = UPPER(?)",
                    (ticker,)
                ).fetchone()[0]
                rows = conn.execute(
                    f"SELECT * FROM analysis_runs WHERE {where_base} AND UPPER(ticker) = UPPER(?) "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                    (ticker, limit, offset)
                ).fetchall()
            else:
                total = conn.execute(
                    f"SELECT COUNT(*) FROM analysis_runs WHERE {where_base}"
                ).fetchone()[0]
                rows = conn.execute(
                    f"SELECT * FROM analysis_runs WHERE {where_base} "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_latest_run_for_ticker(self, ticker: str) -> dict | None:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM analysis_runs WHERE UPPER(ticker) = UPPER(?) ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (ticker,),
            ).fetchone()
        return dict(row) if row else None

    def save_valuation_record(
        self,
        *,
        ticker: str,
        fair_value: float,
        current_price: float,
        gap_pct: float,
        run_id: str,
    ) -> None:
        import uuid
        val_id = str(uuid.uuid4())
        data = json.dumps({
            "fair_value": fair_value,
            "current_price": current_price,
            "gap_pct": gap_pct,
            "run_id": run_id,
        })
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO valuations (id, data, ticker) VALUES (?, ?, ?)",
                (val_id, data, ticker),
            )

    def get_latest_valuation(self, ticker: str) -> dict | None:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM valuations WHERE UPPER(ticker) = UPPER(?) ORDER BY rowid DESC LIMIT 1",
                (ticker,),
            ).fetchone()
        return dict(row) if row else None

    def get_tracked_tickers(self) -> list[str]:
        where_base = self._NON_TEST_RUNS_WHERE
        where_intent = self._ANALYSIS_INTENT_WHERE
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT UPPER(ticker) AS ticker "
                "FROM analysis_runs "
                f"WHERE {where_base} "
                "AND ticker IS NOT NULL "
                "AND TRIM(ticker) != '' "
                "AND LENGTH(TRIM(ticker)) BETWEEN 1 AND 5 "
                "AND UPPER(ticker) = ticker "
                f"AND {where_intent} "
                "ORDER BY ticker"
            ).fetchall()
        return [r[0] for r in rows]

    # ---- vector search methods ----

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Delegate to Embedder abstraction."""
        return self.embedder.embed(texts)

    def save_embedding(self, id: str, content: str, source_type: str) -> None:
        """Embed content and store in embeddings table. Best-effort: catches exceptions."""
        try:
            vectors = self._embed([content])
            embedding_json = json.dumps(vectors[0])
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (id, content, embedding, source_type, created_at, embedding_model) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (id, content, embedding_json, source_type,
                     datetime.now(timezone.utc).isoformat(), self.embedder.model_id),
                )
        except Exception:
            pass  # best-effort

    def semantic_search(
        self, query: str, top_k: int = 5, source_type: str = None,
        source_category: str = "all",
    ) -> list[dict]:
        """Unified semantic search across AI memory and human knowledge.

        source_category: "ai_memory", "human_knowledge", or "all" (default).
        """
        try:
            query_vec = self._embed([query])[0]
        except Exception:
            return []

        scored = []

        # Search AI memory (embeddings table)
        if source_category in ("all", "ai_memory"):
            try:
                with self._conn() as conn:
                    if source_type:
                        rows = conn.execute(
                            "SELECT id, content, embedding, source_type FROM embeddings WHERE source_type = ?",
                            (source_type,),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT id, content, embedding, source_type FROM embeddings"
                        ).fetchall()
                for row in rows:
                    emb = json.loads(row[2])
                    score = cosine_similarity(query_vec, emb)
                    scored.append({
                        "id": row[0],
                        "content": row[1],
                        "source_type": row[3],
                        "source_category": "ai_memory",
                        "score": score,
                    })
            except Exception:
                pass

        # Search human knowledge (knowledge_chunks table)
        if source_category in ("all", "human_knowledge"):
            try:
                with self._conn() as conn:
                    rows = conn.execute(
                        "SELECT kc.id, kc.content, kc.embedding, kc.document_id, kd.title, kd.doc_type "
                        "FROM knowledge_chunks kc "
                        "JOIN knowledge_documents kd ON kc.document_id = kd.id "
                        "WHERE kc.embedding IS NOT NULL"
                    ).fetchall()
                for row in rows:
                    emb = json.loads(row[2])
                    score = cosine_similarity(query_vec, emb)
                    scored.append({
                        "id": row[0],
                        "content": row[1],
                        "source_type": "knowledge",
                        "source_category": "human_knowledge",
                        "document_id": row[3],
                        "document_title": row[4],
                        "doc_type": row[5],
                        "score": score,
                    })
            except Exception:
                pass

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ---- knowledge document methods ----

    def save_document(
        self,
        title: str,
        doc_type: str,
        content_text: str,
        source_path: str = None,
        company: str = None,
        tags: list[str] = None,
        category: str = "other",
        industry: str = None,
        source_type: str = "manual",
        source_name: str = None,
        published_at: str = None,
        canonical_url: str = None,
        url_hash: str = None,
        content_hash: str = None,
        ai_metadata: dict | None = None,
        extraction_meta: dict | None = None,
    ) -> dict:
        """Save a document, chunk it, embed chunks. Returns document metadata."""
        doc_id = f"kdoc_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [])
        ai_metadata_json = json.dumps(ai_metadata or {}, ensure_ascii=False)
        extraction_meta_json = json.dumps(extraction_meta or {}, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO knowledge_documents "
                "(id, title, doc_type, source_path, content_text, tags, company, category, industry, source_type, source_name, "
                "published_at, canonical_url, url_hash, content_hash, ai_metadata_json, extraction_meta_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_id, title, doc_type, source_path, content_text, tags_json, company, category, industry, source_type, source_name,
                    published_at, canonical_url, url_hash, content_hash, ai_metadata_json, extraction_meta_json, now, now,
                ),
            )
        # Chunk and embed
        chunks = chunk_text(content_text)
        chunk_ids = []
        for chunk in chunks:
            chunk_id = f"kchunk_{uuid.uuid4().hex[:8]}"
            embedding_json = None
            model_id = None
            try:
                vectors = self._embed([chunk.content])
                embedding_json = json.dumps(vectors[0])
                model_id = self.embedder.model_id
            except Exception:
                pass  # best-effort embedding
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO knowledge_chunks (id, document_id, chunk_index, content, char_offset_start, char_offset_end, embedding, embedding_model, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, doc_id, chunk.chunk_index, chunk.content,
                     chunk.char_offset_start, chunk.char_offset_end,
                     embedding_json, model_id, now),
                )
            chunk_ids.append(chunk_id)
        return {
            "id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "chunk_count": len(chunk_ids),
            "company": company,
            "category": category,
            "industry": industry,
            "source_type": source_type,
            "source_name": source_name,
            "published_at": published_at,
            "canonical_url": canonical_url,
        }
    def list_documents(self, company: str = None, doc_type: str = None, category: str = None, industry: str = None) -> list[dict]:
        """List knowledge documents with metadata."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT id, title, doc_type, source_path, tags, company, category, industry, source_type, source_name, "
                "published_at, canonical_url, url_hash, content_hash, ai_metadata_json, extraction_meta_json, "
                "created_at, updated_at FROM knowledge_documents"
            )
            conditions = []
            params = []
            if company:
                conditions.append("UPPER(company) = UPPER(?)")
                params.append(company)
            if doc_type:
                conditions.append("doc_type = ?")
                params.append(doc_type)
            if category:
                conditions.append("category = ?")
                params.append(category)
            if industry:
                conditions.append("industry = ?")
                params.append(industry)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = self._hydrate_document_row(dict(row))
            # Get chunk count
            with self._conn() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
                    (d["id"],),
                ).fetchone()[0]
            d["chunk_count"] = count
            results.append(d)
        return results
    def get_document(self, doc_id: str) -> dict | None:
        """Get full document with content and chunk count."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)
            ).fetchone()
        if not row:
            return None
        d = self._hydrate_document_row(dict(row))
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
                (doc_id,),
            ).fetchone()[0]
        d["chunk_count"] = count
        return d
    def find_document_by_hashes(
        self,
        *,
        url_hash: str | None = None,
        content_hash: str | None = None,
    ) -> dict | None:
        """Find a potentially duplicate document by URL hash or content hash."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = None
            if url_hash:
                row = conn.execute(
                    "SELECT * FROM knowledge_documents WHERE url_hash = ? ORDER BY created_at DESC LIMIT 1",
                    (url_hash,),
                ).fetchone()
            if row is None and content_hash:
                row = conn.execute(
                    "SELECT * FROM knowledge_documents WHERE content_hash = ? ORDER BY created_at DESC LIMIT 1",
                    (content_hash,),
                ).fetchone()
        if row is None:
            return None
        d = self._hydrate_document_row(dict(row))
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
                (d["id"],),
            ).fetchone()[0]
        d["chunk_count"] = count
        return d
    def delete_document(self, doc_id: str) -> bool:
        """Delete document and its chunks. Returns True if found."""
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM knowledge_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if not existing:
                return False
            conn.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM knowledge_documents WHERE id = ?", (doc_id,))
        return True
    @staticmethod
    def _hydrate_document_row(doc: dict) -> dict:
        """Convert serialized JSON fields to Python objects."""
        doc["tags"] = json.loads(doc.get("tags") or "[]")
        doc["ai_metadata_json"] = json.loads(doc.get("ai_metadata_json") or "{}")
        doc["extraction_meta_json"] = json.loads(doc.get("extraction_meta_json") or "{}")
        return doc

    # ---- knowledge_items CRUD ----

    def save_knowledge_item(
        self,
        *,
        type: str,
        subject: str = None,
        content: str,
        structured_data: dict = None,
        confidence: float = None,
        source: str = None,
        tags: list[str] = None,
        item_id: str = None,
    ) -> str:
        """Save a knowledge item and auto-generate embedding. Returns the item ID."""
        item_id = item_id or f"ki_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        sd_json = json.dumps(structured_data or {}, ensure_ascii=False, default=str)
        tags_json = json.dumps(tags or [])
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_items "
                "(id, type, subject, content, structured_data, confidence, source, tags, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, type, subject, content, sd_json, confidence, source, tags_json, now, now),
            )
        # Auto-embed (best-effort)
        embed_text = f"{subject}: {content}" if subject else content
        self.save_embedding(item_id, embed_text, type)
        return item_id

    def get_knowledge_item(self, item_id: str) -> dict | None:
        """Get a single knowledge_item by ID."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM knowledge_items WHERE id = ?", (item_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["structured_data"] = json.loads(d.get("structured_data") or "{}")
        d["tags"] = json.loads(d.get("tags") or "[]")
        return d

    def query_knowledge_items(
        self, *, type: str = None, subject: str = None, limit: int = 50
    ) -> list[dict]:
        """Query knowledge_items with optional filters."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM knowledge_items"
            conditions = []
            params: list = []
            if type:
                conditions.append("type = ?")
                params.append(type)
            if subject:
                conditions.append("UPPER(subject) = UPPER(?)")
                params.append(subject)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["structured_data"] = json.loads(d.get("structured_data") or "{}")
            d["tags"] = json.loads(d.get("tags") or "[]")
            results.append(d)
        return results

    def update_knowledge_item_structured_data(self, item_id: str, updates: dict) -> bool:
        """Merge updates into the structured_data JSON of a knowledge_item."""
        item = self.get_knowledge_item(item_id)
        if not item:
            return False
        sd = item["structured_data"]
        sd.update(updates)
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE knowledge_items SET structured_data = ?, updated_at = ? WHERE id = ?",
                (json.dumps(sd, ensure_ascii=False, default=str), now, item_id),
            )
        return True

    def migrate_to_unified_memory(self):
        """Migrate data from legacy storage to knowledge_items table. Idempotent."""
        migrated = {"observations": 0, "experiences": 0, "notes": 0, "predictions": 0, "documents": 0}

        # 1. Migrate observations
        with self._conn() as conn:
            rows = conn.execute("SELECT id, subject, data FROM observations").fetchall()
        for row in rows:
            obs_id, subject, data_json = row
            if self.get_knowledge_item(obs_id):
                continue  # already migrated
            try:
                data = json.loads(data_json)
                self.save_knowledge_item(
                    item_id=obs_id,
                    type="observation",
                    subject=subject,
                    content=data.get("claim", ""),
                    structured_data={
                        "fact_or_view": data.get("fact_or_view", "fact"),
                        "relevance": data.get("relevance", 0.5),
                        "citation": data.get("citation", ""),
                        "source": data.get("source", ""),
                        "time": data.get("time", ""),
                    },
                    confidence=data.get("relevance"),
                    source=data.get("source", ""),
                    tags=["migrated"],
                )
                migrated["observations"] += 1
            except Exception:
                pass

        # 2. Migrate experience_library.json
        from pathlib import Path
        exp_path = Path("memory") / "experience_library.json"
        if exp_path.exists():
            try:
                lib = json.loads(exp_path.read_text(encoding="utf-8"))
                for exp in lib.get("experiences", []):
                    exp_id = exp.get("id", f"ki_{uuid.uuid4().hex[:8]}")
                    if self.get_knowledge_item(exp_id):
                        continue
                    companies = exp.get("companies", [])
                    subject = companies[0] if companies else exp.get("sector", "")
                    self.save_knowledge_item(
                        item_id=exp_id,
                        type="experience",
                        subject=subject,
                        content=exp.get("content", ""),
                        structured_data={
                            "zone": exp.get("zone"),
                            "level": exp.get("level"),
                            "evidence": exp.get("evidence", []),
                            "evidence_count": exp.get("evidence_count", 0),
                            "methodology": exp.get("methodology"),
                            "times_retrieved": exp.get("times_retrieved", 0),
                            "times_useful": exp.get("times_useful", 0),
                            "status": exp.get("status", "active"),
                        },
                        confidence=exp.get("confidence", 0.5),
                        tags=["migrated"],
                    )
                    migrated["experiences"] += 1
            except Exception:
                pass

        # 3. Migrate company/sector/pattern notes
        from core.config import get as config_get
        base = Path(config_get("memory.base_dir", "./memory"))
        for dir_name, note_cat in [("companies", "company"), ("sectors", "sector"), ("patterns", "patterns")]:
            note_dir = base / dir_name
            if not note_dir.exists():
                continue
            for f in note_dir.iterdir():
                if not f.is_file() or not f.name.endswith(".md"):
                    continue
                subject = f.stem.upper()
                note_id = f"ki_note_{note_cat}_{subject.lower()}"
                if self.get_knowledge_item(note_id):
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    self.save_knowledge_item(
                        item_id=note_id,
                        type="note",
                        subject=subject,
                        content=content,
                        structured_data={"note_category": note_cat},
                        tags=["migrated"],
                    )
                    migrated["notes"] += 1
                except Exception:
                    pass

        # 4. Migrate calibration log
        cal_path = base / "calibration" / "prediction_log.jsonl"
        if cal_path.exists():
            try:
                for i, line in enumerate(cal_path.read_text(encoding="utf-8").strip().splitlines()):
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    pred_id = f"ki_pred_{i}"
                    if self.get_knowledge_item(pred_id):
                        continue
                    self.save_knowledge_item(
                        item_id=pred_id,
                        type="prediction",
                        subject=entry.get("company", ""),
                        content=f"Fair value prediction: ${entry.get('predicted', 0):.2f}/share",
                        structured_data={
                            "metric": entry.get("metric", "fair_value"),
                            "predicted": entry.get("predicted"),
                            "actual": entry.get("actual"),
                            "review_after": entry.get("date", ""),
                        },
                        source=entry.get("note", ""),
                        tags=["migrated"],
                    )
                    migrated["predictions"] += 1
            except Exception:
                pass

        return migrated
