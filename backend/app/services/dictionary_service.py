from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import SemanticDictionaryModel
from app.schemas.dictionary import DictionaryEntryCreate


class DictionaryService:
    def list_entries(self, db: Session) -> list[SemanticDictionaryModel]:
        return db.query(SemanticDictionaryModel).order_by(SemanticDictionaryModel.term.asc()).all()

    def create_entry(self, db: Session, payload: DictionaryEntryCreate) -> SemanticDictionaryModel:
        entry = SemanticDictionaryModel(
            term=payload.term,
            synonyms=payload.synonyms,
            mapped_expression=payload.mapped_expression,
            description=payload.description,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def import_schema_tables(
        self,
        db: Session,
        tables: list[dict[str, object]],
        *,
        database_label: str,
        max_entries: int = 2000,
    ) -> int:
        """Create dictionary terms from introspected tables/columns (idempotent by term)."""
        added = 0
        for table in tables:
            if added >= max_entries:
                break
            name = str(table.get("name", "")).strip()
            if not name:
                continue
            cols_raw = table.get("columns")
            columns = cols_raw if isinstance(cols_raw, list) else []

            payload = DictionaryEntryCreate(
                term=name,
                synonyms=[f"{database_label}.{name}"],
                mapped_expression=name,
                description=f"Таблица «{name}» (импорт из подключения «{database_label}»).",
            )
            if self._try_add_entry(db, payload):
                added += 1

            for col in columns:
                if added >= max_entries:
                    break
                if not isinstance(col, dict):
                    continue
                col_name = str(col.get("name", "")).strip()
                if not col_name:
                    continue
                qualified = f"{name}.{col_name}"
                col_payload = DictionaryEntryCreate(
                    term=qualified,
                    synonyms=[col_name],
                    mapped_expression=qualified,
                    description=(
                        f"Колонка «{col_name}» ({col.get('type', '?')}) в таблице «{name}», "
                        f"БД «{database_label}»."
                    ),
                )
                if self._try_add_entry(db, col_payload):
                    added += 1

        db.commit()
        return added

    def _try_add_entry(self, db: Session, payload: DictionaryEntryCreate) -> bool:
        exists = db.query(SemanticDictionaryModel).filter(SemanticDictionaryModel.term == payload.term).first()
        if exists:
            return False
        db.add(
            SemanticDictionaryModel(
                term=payload.term,
                synonyms=payload.synonyms,
                mapped_expression=payload.mapped_expression,
                description=payload.description,
            )
        )
        return True
