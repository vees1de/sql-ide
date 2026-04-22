#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import ServiceSessionLocal
from app.services.semantic_catalog_service import SemanticCatalogService


def _read_optional_notes(notes_path: str | None) -> str | None:
    if not notes_path:
        return None
    path = Path(notes_path).expanduser().resolve()
    return path.read_text(encoding="utf-8").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild semantic catalog for a database connection.")
    parser.add_argument("--database-id", required=True, help="Database connection id from /api/chat/databases.")
    parser.add_argument(
        "--notes",
        help="Optional markdown file with domain description. If omitted, built-in semantic seeds are used when available.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    database_description = _read_optional_notes(args.notes)
    service = SemanticCatalogService()
    db = ServiceSessionLocal()
    try:
        catalog = service.activate_catalog(
            db,
            args.database_id,
            refresh=True,
            database_description=database_description,
        )
    finally:
        db.close()

    summary = {
        "database_id": catalog.database_id,
        "dialect": catalog.dialect,
        "table_count": len(catalog.tables),
        "relationship_count": len(catalog.relationships),
        "tables": [
            {
                "table_name": table.table_name,
                "label": table.label,
                "table_role": table.table_role,
                "grain": table.grain,
                "main_entity": table.main_entity,
                "main_date_column": table.main_date_column,
                "sample_columns": [
                    {
                        "column_name": column.column_name,
                        "label": column.label,
                        "business_description": column.business_description,
                        "semantic_types": list(column.semantic_types),
                        "analytics_roles": list(column.analytics_roles),
                    }
                    for column in table.columns[:8]
                ],
            }
            for table in catalog.tables
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
