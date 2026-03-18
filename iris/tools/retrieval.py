import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Optional

from core.schemas import Observation, Hypothesis, EvidenceCard, ValuationOutput, TradeScore, AuditTrail


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


class SQLiteRetriever(EvidenceRetriever):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

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
            """)

    def save_observation(self, obs: Observation) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO observations (id, subject, data) VALUES (?, ?, ?)",
                (obs.id, obs.subject, obs.model_dump_json()),
            )

    def query_observations(
        self,
        subject: str = None,
        min_relevance: float = 0.0,
        query: str = None,
    ) -> list[Observation]:
        with self._conn() as conn:
            if subject:
                rows = conn.execute(
                    "SELECT data FROM observations WHERE subject = ?", (subject,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT data FROM observations").fetchall()
        results = [Observation.model_validate_json(r[0]) for r in rows]
        return [o for o in results if o.relevance >= min_relevance]

    def save_hypothesis(self, hyp: Hypothesis) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO hypotheses (id, company, data) VALUES (?, ?, ?)",
                (hyp.id, hyp.company, hyp.model_dump_json()),
            )

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
                    "SELECT data FROM hypotheses WHERE company = ?", (company,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT data FROM hypotheses").fetchall()
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
                "SELECT data FROM audit_trails WHERE company = ? ORDER BY rowid DESC LIMIT 1",
                (company,)
            ).fetchone()
        return AuditTrail.model_validate_json(row[0]) if row else None
