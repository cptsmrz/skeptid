"""SQLite storage and shadow-mode provider logging for SKEPTID.

Stores analysis verdicts, shadow-mode provider telemetry, and feedback.
All user feedback is tagged source=demo and excluded from frozen holdouts (SPEC 9).
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skeptid.core.types import Verdict
from skeptid.store.models import FeedbackRecord

DEFAULT_DB_PATH = Path("data/skeptid.db")


class SkeptidDatabase:
    """Thread-safe SQLite storage for analyses, provider runs, and user feedback."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    modality TEXT NOT NULL,
                    label TEXT NOT NULL,
                    risk REAL NOT NULL,
                    level TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    disagreement INTEGER NOT NULL,
                    primary_provider TEXT NOT NULL,
                    mock INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    risk REAL NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    model_version TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL UNIQUE,
                    correct INTEGER NOT NULL,
                    true_label TEXT,
                    source TEXT NOT NULL DEFAULT 'demo',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)
            # feedback_samples: text stored ONLY when user explicitly opted in.
            # Retrain uses only rows in this table (SPEC §9, §10).
            # Media is never stored.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL UNIQUE,
                    text TEXT NOT NULL,
                    true_label TEXT,
                    source TEXT NOT NULL DEFAULT 'demo',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)
            conn.commit()

    def record_analysis(self, verdict: Verdict) -> None:
        """Persist analysis verdict and shadow-mode provider run logs."""
        now = datetime.now(UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analyses (
                    id, modality, label, risk, level, confidence,
                    disagreement, primary_provider, mock, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verdict.id,
                    verdict.modality.value,
                    verdict.label,
                    verdict.risk,
                    verdict.level,
                    verdict.confidence,
                    1 if verdict.disagreement else 0,
                    verdict.primary_provider,
                    1 if verdict.mock else 0,
                    now,
                ),
            )

            for p in verdict.providers:
                conn.execute(
                    """
                    INSERT INTO provider_runs (
                        analysis_id, provider_id, ok, risk, latency_ms, model_version, error, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        verdict.id,
                        p["id"],
                        1 if p["ok"] else 0,
                        float(p.get("risk", 0.0)),
                        int(p.get("latency_ms", 0)),
                        str(p.get("model_version", "unknown")),
                        p.get("error"),
                        now,
                    ),
                )
            conn.commit()

    def record_feedback(
        self,
        analysis_id: str,
        correct: bool,
        true_label: str | None = None,
        share_example: bool = False,
        text: str | None = None,
    ) -> FeedbackRecord:
        """Record user feedback, deduped by analysis_id and tagged source=demo.

        If share_example=True and text is provided, the message text is additionally
        stored in feedback_samples for future retrain use (SPEC §9, §10).
        Media is never stored.
        """
        now = datetime.now(UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO feedback (analysis_id, correct, true_label, source, created_at)
                VALUES (?, ?, ?, 'demo', ?)
                ON CONFLICT(analysis_id) DO UPDATE SET
                    correct = excluded.correct,
                    true_label = excluded.true_label,
                    created_at = excluded.created_at
                """,
                (analysis_id, 1 if correct else 0, true_label, now),
            )
            if share_example and text:
                conn.execute(
                    """
                    INSERT INTO feedback_samples (analysis_id, text, true_label, source, created_at)
                    VALUES (?, ?, ?, 'demo', ?)
                    ON CONFLICT(analysis_id) DO UPDATE SET
                        text = excluded.text,
                        true_label = excluded.true_label,
                        created_at = excluded.created_at
                    """,
                    (analysis_id, text, true_label, now),
                )
            conn.commit()
        return FeedbackRecord(
            analysis_id=analysis_id,
            correct=correct,
            true_label=true_label,
            source="demo",
            created_at=now,
        )

    def get_summary_stats(self) -> dict[str, Any]:
        """Compute provider agreement rates, fallback count, and latency stats."""
        with self._connection() as conn:
            analyses_count = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            disagreements = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE disagreement = 1"
            ).fetchone()[0]

            agreement_rate = (
                round(1.0 - (disagreements / analyses_count), 4) if analyses_count > 0 else 1.0
            )

            # Provider latencies
            provider_stats: dict[str, Any] = {}
            p_ids = [
                r[0]
                for r in conn.execute("SELECT DISTINCT provider_id FROM provider_runs").fetchall()
            ]
            for pid in p_ids:
                latencies = [
                    r[0]
                    for r in conn.execute(
                        "SELECT latency_ms FROM provider_runs WHERE provider_id = ? AND ok = 1 ORDER BY latency_ms ASC",
                        (pid,),
                    ).fetchall()
                ]
                n = len(latencies)
                if n > 0:
                    p50 = latencies[int(n * 0.50)]
                    p95 = latencies[min(n - 1, int(n * 0.95))]
                    provider_stats[pid] = {"count": n, "p50_latency_ms": p50, "p95_latency_ms": p95}

            # Fallback count: where primary provider is not the first in chain or ok=0
            fallback_count = conn.execute(
                "SELECT COUNT(*) FROM provider_runs WHERE ok = 0"
            ).fetchone()[0]

        return {
            "total_analyses": analyses_count,
            "total_feedback": feedback_count,
            "agreement_rate": agreement_rate,
            "fallback_count": fallback_count,
            "provider_stats": provider_stats,
        }
