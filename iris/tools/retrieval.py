import json
import math
import sqlite3
from abc import ABC, abstractmethod
from typing import Callable, Optional

from core.schemas import Observation, Hypothesis, EvidenceCard, ValuationOutput, TradeScore, AuditTrail


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
    def __init__(self, db_path: str, usage_tracker: Callable[..., None] | None = None):
        self.db_path = db_path
        self._usage_tracker = usage_tracker
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
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analysis_runs
                   (id, query, ticker, status, reasoning_text, thinking_text,
                    timeline_json, panels_json, recommendation, tokens_in, tokens_out)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (id, query, ticker, status, reasoning_text, thinking_text,
                 timeline_json, panels_json, recommendation, tokens_in, tokens_out),
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
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            if ticker:
                total = conn.execute(
                    "SELECT COUNT(*) FROM analysis_runs WHERE UPPER(ticker) = UPPER(?)",
                    (ticker,),
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM analysis_runs WHERE UPPER(ticker) = UPPER(?) ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                    (ticker, limit, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM analysis_runs ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                    (limit, offset),
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
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT UPPER(ticker) AS ticker FROM analysis_runs WHERE ticker IS NOT NULL ORDER BY ticker"
            ).fetchall()
        return [r[0] for r in rows]

    # ---- vector search methods ----

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API. Returns one embedding vector per input text."""
        import os
        import openai
        client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        response = client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            input=texts,
        )
        usage = getattr(response, "usage", None)
        if self._usage_tracker:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            try:
                self._usage_tracker(input_tokens=prompt_tokens)
            except TypeError:
                # Backward-compatible callback signature support.
                self._usage_tracker(prompt_tokens)
        return [item.embedding for item in response.data]

    def save_embedding(self, id: str, content: str, source_type: str) -> None:
        """Embed content and store in embeddings table. Best-effort: catches exceptions."""
        try:
            from datetime import datetime, timezone
            vectors = self._embed([content])
            embedding_json = json.dumps(vectors[0])
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (id, content, embedding, source_type, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (id, content, embedding_json, source_type, datetime.now(timezone.utc).isoformat()),
                )
        except Exception:
            pass  # best-effort

    def semantic_search(
        self, query: str, top_k: int = 5, source_type: str = None
    ) -> list[dict]:
        """Embed query, load all embeddings, rank by cosine similarity. Returns list of dicts."""
        try:
            query_vec = self._embed([query])[0]
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
            if not rows:
                return []
            scored = []
            for row in rows:
                emb = json.loads(row[2])
                score = cosine_similarity(query_vec, emb)
                scored.append({
                    "id": row[0],
                    "content": row[1],
                    "source_type": row[3],
                    "score": score,
                })
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:top_k]
        except Exception:
            return []
