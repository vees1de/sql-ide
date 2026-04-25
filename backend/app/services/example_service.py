"""RAG few-shot example service backed by TF-IDF cosine similarity."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.db.models import QueryExampleModel

if TYPE_CHECKING:
    pass

_STOP_WORDS = frozenset(
    "а в и к на не по с то у что это как за из от со все при так или"
    " the a an is are was were be been have has had do does did will would could should may might"
    .split()
)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zа-яё0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    n = len(tokens) or 1
    return {t: c / n for t, c in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class ExampleService:
    def find_exact(
        self,
        db: Session,
        database_id: str,
        prompt: str,
        sql: str,
    ) -> QueryExampleModel | None:
        return (
            db.query(QueryExampleModel)
            .filter(
                QueryExampleModel.database_id == database_id,
                QueryExampleModel.prompt == prompt,
                QueryExampleModel.sql == sql,
            )
            .first()
        )

    def find_similar(
        self,
        db: Session,
        database_id: str,
        query: str,
        *,
        top_k: int = 3,
        min_score: float = 0.15,
    ) -> list[dict]:
        examples = (
            db.query(QueryExampleModel)
            .filter(
                QueryExampleModel.database_id == database_id,
                QueryExampleModel.active.is_(True),
            )
            .order_by(QueryExampleModel.quality_score.desc(), QueryExampleModel.use_count.desc())
            .limit(200)
            .all()
        )
        if not examples:
            return []

        query_tokens = _tokenize(query)
        query_tf = _tf(query_tokens)

        scored: list[tuple[float, QueryExampleModel]] = []
        for ex in examples:
            tokens = ex.tokens_json or _tokenize(ex.prompt)
            ex_tf = _tf(tokens)
            score = _cosine(query_tf, ex_tf) * ex.quality_score
            if score >= min_score:
                scored.append((score, ex))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, ex in scored[:top_k]:
            ex.use_count = (ex.use_count or 0) + 1
            db.add(ex)
            results.append({"prompt": ex.prompt, "sql": ex.sql, "score": round(score, 3)})
        db.commit()
        return results

    def save_example(
        self,
        db: Session,
        database_id: str,
        prompt: str,
        sql: str,
        *,
        source: str = "auto",
        quality_score: float = 1.0,
    ) -> QueryExampleModel:
        existing = self.find_exact(db, database_id, prompt, sql)
        if existing is not None:
            if source == "manual" and existing.source == "auto":
                existing.source = source
            existing.quality_score = max(existing.quality_score or 1.0, quality_score)
            existing.active = True
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        tokens = _tokenize(prompt)
        ex = QueryExampleModel(
            database_id=database_id,
            prompt=prompt,
            sql=sql,
            source=source,
            tokens_json=tokens,
            quality_score=quality_score,
        )
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return ex

    def record_feedback(
        self,
        db: Session,
        example_id: str,
        feedback: str,  # "good" | "bad"
    ) -> None:
        ex = db.query(QueryExampleModel).filter(QueryExampleModel.id == example_id).first()
        if ex is None:
            return
        if feedback == "good":
            ex.quality_score = min(2.0, (ex.quality_score or 1.0) + 0.2)
        elif feedback == "bad":
            ex.quality_score = max(0.0, (ex.quality_score or 1.0) - 0.5)
            if ex.quality_score <= 0.1:
                ex.active = False
        db.add(ex)
        db.commit()

    def list_examples(
        self,
        db: Session,
        database_id: str,
        *,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[QueryExampleModel]:
        q = db.query(QueryExampleModel).filter(QueryExampleModel.database_id == database_id)
        if active_only:
            q = q.filter(QueryExampleModel.active.is_(True))
        return q.order_by(QueryExampleModel.created_at.desc()).limit(limit).all()

    def delete_example(self, db: Session, example_id: str) -> bool:
        ex = db.query(QueryExampleModel).filter(QueryExampleModel.id == example_id).first()
        if ex is None:
            return False
        db.delete(ex)
        db.commit()
        return True
