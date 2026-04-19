from __future__ import annotations

import json
import time

import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.db.session import analytics_engine
from app.schemas.query import QueryExecutionResult


class AnalyticsExecutionService:
    def execute(self, sql: str) -> QueryExecutionResult:
        started_at = time.perf_counter()
        with analytics_engine.begin() as connection:
            if analytics_engine.dialect.name == "postgresql":
                timeout_ms = max(settings.query_timeout_seconds * 1000, 1000)
                connection.execute(text("SET LOCAL default_transaction_read_only = on"))
                connection.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            dataframe = pd.read_sql_query(text(sql), connection)
        execution_time_ms = int((time.perf_counter() - started_at) * 1000)

        rows = json.loads(dataframe.to_json(orient="records", date_format="iso"))
        return QueryExecutionResult(
            sql=sql,
            rows=rows,
            columns=list(dataframe.columns),
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
        )
