from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.db.models import SemanticDictionaryModel
from app.schemas.dictionary import DictionaryEntryCreate, DictionaryEntryUpdate


class DictionaryService:
    def list_entries(self, db: Session, database_id: str | None = None) -> list[SemanticDictionaryModel]:
        q = db.query(SemanticDictionaryModel)
        if database_id:
            q = q.filter(SemanticDictionaryModel.source_database == database_id)
        return q.order_by(SemanticDictionaryModel.term.asc()).all()

    def create_entry(self, db: Session, payload: DictionaryEntryCreate) -> SemanticDictionaryModel:
        entry = SemanticDictionaryModel(
            term=payload.term,
            synonyms=payload.synonyms,
            mapped_expression=payload.mapped_expression,
            description=payload.description,
            object_type=payload.object_type,
            table_name=payload.table_name,
            column_name=payload.column_name,
            source_database=payload.source_database,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def update_entry(
        self,
        db: Session,
        entry_id: str,
        payload: DictionaryEntryUpdate,
    ) -> SemanticDictionaryModel | None:
        entry = db.query(SemanticDictionaryModel).filter(SemanticDictionaryModel.id == entry_id).first()
        if entry is None:
            return None
        if payload.term is not None:
            entry.term = payload.term
        if payload.synonyms is not None:
            entry.synonyms = payload.synonyms
        if payload.mapped_expression is not None:
            entry.mapped_expression = payload.mapped_expression
        if payload.description is not None:
            entry.description = payload.description
        if payload.object_type is not None:
            entry.object_type = payload.object_type
        if payload.table_name is not None:
            entry.table_name = payload.table_name
        if payload.column_name is not None:
            entry.column_name = payload.column_name
        if payload.source_database is not None:
            entry.source_database = payload.source_database
        db.commit()
        db.refresh(entry)
        return entry

    def delete_entry(self, db: Session, entry_id: str) -> bool:
        entry = db.query(SemanticDictionaryModel).filter(SemanticDictionaryModel.id == entry_id).first()
        if entry is None:
            return False
        db.delete(entry)
        db.commit()
        return True

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
                synonyms=sorted(self._expand_synonyms([f"{database_label}.{name}", name])),
                mapped_expression=name,
                description=f"Таблица «{name}» (импорт из подключения «{database_label}»).",
                object_type="table",
                table_name=name,
                source_database=database_label,
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
                    synonyms=sorted(self._expand_synonyms([col_name, f"{name}_{col_name}"])),
                    mapped_expression=qualified,
                    description=(
                        f"Колонка «{col_name}» ({col.get('type', '?')}) в таблице «{name}», "
                        f"БД «{database_label}»."
                    ),
                    object_type="column",
                    table_name=name,
                    column_name=col_name,
                    source_database=database_label,
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
                object_type=payload.object_type,
                table_name=payload.table_name,
                column_name=payload.column_name,
                source_database=payload.source_database,
            )
        )
        return True

    def _expand_synonyms(self, raw: list[str]) -> set[str]:
        variants: set[str] = set()
        for item in raw:
            token = str(item).strip()
            if not token:
                continue
            variants.add(token)
            snake = token.replace(".", "_")
            variants.add(snake)
            words = [part for part in re.split(r"[_\.\s]+", token) if part]
            if words:
                variants.add(" ".join(words))
        return {item for item in variants if item}
