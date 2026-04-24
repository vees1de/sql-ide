from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessageModel, ChatSessionModel, DatabaseConnectionModel, SemanticDictionaryModel
from app.evals.eval_judge_service import EvalJudgeService
from app.schemas.chat import ChatSessionCreate
from app.services.chat_service import ChatService
from app.services.chat_sql_adapter import ChatSqlAdapter
from app.services.database_connection_utils import DatabaseConnectionPayload, create_connection_engine
from app.services.database_resolution import invalidate_engine_cache


REFERENCE_DATE = date(2026, 4, 24)


@dataclass(frozen=True)
class ExecutionSnapshot:
    success: bool
    error: str | None
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class EvalRunner:
    def __init__(
        self,
        *,
        single_shot_path: Path,
        multi_turn_path: Path,
        edge_case_path: Path,
        output_dir: Path,
        judge_model: str = "gpt-4o-mini",
    ) -> None:
        self.single_shot_path = single_shot_path
        self.multi_turn_path = multi_turn_path
        self.edge_case_path = edge_case_path
        self.output_dir = output_dir
        self.judge = EvalJudgeService(model=judge_model)
        self.chat_service = ChatService()
        self.chat_adapter = ChatSqlAdapter()

    def run(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="sql-ide-eval-") as tmpdir:
            tmp_path = Path(tmpdir)
            service_db, service_engine = self._build_service_session()
            try:
                test_db_path = tmp_path / "static_eval.sqlite"
                test_engine = self._seed_test_database(test_db_path)
                try:
                    database_id = self._seed_service_database(service_db, test_db_path)
                    results: list[dict[str, Any]] = []
                    results.extend(self._run_dataset(service_db, test_engine, database_id, "single_shot", self.single_shot_path))
                    results.extend(self._run_dataset(service_db, test_engine, database_id, "multi_turn", self.multi_turn_path))
                    results.extend(self._run_dataset(service_db, test_engine, database_id, "edge_cases", self.edge_case_path))
                    summary = self._build_summary(results)
                    report = {
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "judge": {
                            "available": self.judge.available,
                            "model": self.judge.model,
                            "mode": "llm" if self.judge.available else "heuristic",
                        },
                        "results": results,
                        "summary": summary,
                    }
                    self._write_artifacts(report)
                    return report
                finally:
                    test_engine.dispose()
            finally:
                service_db.close()
                service_engine.dispose()

    def _build_service_session(self) -> tuple[Session, Engine]:
        service_engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=service_engine)
        SessionLocal = sessionmaker(bind=service_engine, autocommit=False, autoflush=False, class_=Session)
        return SessionLocal(), service_engine

    def _seed_test_database(self, path: Path) -> Engine:
        if path.exists():
            path.unlink()
        engine = create_connection_engine(
            DatabaseConnectionPayload(
                dialect="sqlite",
                database=str(path),
            )
        )
        self._create_static_schema(engine)
        self._seed_static_data(engine)
        return engine

    def _seed_service_database(self, db: Session, test_db_path: Path) -> str:
        database_id = "eval-db"
        connection = DatabaseConnectionModel(
            id=database_id,
            name="Eval DB",
            dialect="sqlite",
            database=str(test_db_path),
            read_only="true",
            status="connected",
            table_count=4,
            allowed_tables=["users", "drivers", "tariffs", "rides"],
            description="Static evaluation database used by backend/evals/runner.py",
        )
        db.add(connection)
        db.add_all(
            [
                SemanticDictionaryModel(
                    term="completion_rate",
                    synonyms=["conversion_rate", "conversion", "конверсия"],
                    mapped_expression="completion_rate",
                    description="Share of completed rides among all rides.",
                    object_type="metric",
                    table_name="rides",
                    column_name=None,
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="avg_ride_duration",
                    synonyms=["ride_duration", "trip_duration", "длительность поездки"],
                    mapped_expression="avg_ride_duration",
                    description="Average ride duration in minutes.",
                    object_type="metric",
                    table_name="rides",
                    column_name=None,
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="avg_pickup_minutes",
                    synonyms=["pickup_minutes", "time_to_arrival", "время подачи"],
                    mapped_expression="avg_pickup_minutes",
                    description="Average time from request to pickup in minutes.",
                    object_type="metric",
                    table_name="rides",
                    column_name=None,
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="city",
                    synonyms=["cities", "по городам"],
                    mapped_expression="users.city",
                    description="User city.",
                    object_type="column",
                    table_name="users",
                    column_name="city",
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="tariff_type",
                    synonyms=["tariff", "тариф"],
                    mapped_expression="tariffs.tariff_type",
                    description="Ride tariff category.",
                    object_type="column",
                    table_name="tariffs",
                    column_name="tariff_type",
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="driver_status",
                    synonyms=["driver status", "статус водителя"],
                    mapped_expression="drivers.status",
                    description="Driver status field.",
                    object_type="column",
                    table_name="drivers",
                    column_name="status",
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="driver_id",
                    synonyms=["drivers", "водителям"],
                    mapped_expression="rides.driver_id",
                    description="Driver identifier on a ride.",
                    object_type="column",
                    table_name="rides",
                    column_name="driver_id",
                    database_id=database_id,
                    source_database="Eval DB",
                ),
                SemanticDictionaryModel(
                    term="status",
                    synonyms=["ride status", "completed", "cancelled", "завершённые"],
                    mapped_expression="rides.status",
                    description="Ride status.",
                    object_type="column",
                    table_name="rides",
                    column_name="status",
                    database_id=database_id,
                    source_database="Eval DB",
                ),
            ]
        )
        db.commit()
        invalidate_engine_cache(database_id)
        return database_id

    def _create_static_schema(self, engine: Engine) -> None:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    city TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE drivers (
                    id INTEGER PRIMARY KEY,
                    city TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE tariffs (
                    id INTEGER PRIMARY KEY,
                    tariff_type TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE rides (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    driver_id INTEGER NOT NULL,
                    tariff_id INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    accepted_at DATETIME,
                    started_at DATETIME,
                    completed_at DATETIME,
                    duration_minutes REAL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(driver_id) REFERENCES drivers(id),
                    FOREIGN KEY(tariff_id) REFERENCES tariffs(id)
                )
                """
            )

    def _seed_static_data(self, engine: Engine) -> None:
        day = REFERENCE_DATE
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO users (id, city, created_at) VALUES
                    (1, 'Moscow', '2026-04-17T08:00:00'),
                    (2, 'Moscow', '2026-04-18T08:00:00'),
                    (3, 'Yakutsk', '2026-04-18T09:00:00'),
                    (4, 'Novosibirsk', '2026-04-19T10:00:00'),
                    (5, 'Moscow', '2026-04-20T11:00:00')
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO drivers (id, city, status, created_at) VALUES
                    (1, 'Moscow', 'active', '2026-04-10T09:00:00'),
                    (2, 'Moscow', 'active', '2026-04-10T09:30:00'),
                    (3, 'Yakutsk', 'banned', '2026-04-10T10:00:00'),
                    (4, 'Novosibirsk', 'active', '2026-04-11T10:00:00'),
                    (5, 'Moscow', 'banned', '2026-04-12T10:00:00')
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO tariffs (id, tariff_type) VALUES
                    (1, 'economy'),
                    (2, 'comfort'),
                    (3, 'business')
                """
            )

            rides = [
                (1, 1, 1, 1, day - timedelta(days=6), True, True, 18.0, "completed"),
                (2, 1, 2, 2, day - timedelta(days=5), True, True, 24.0, "completed"),
                (3, 2, 1, 1, day - timedelta(days=4), True, False, None, "cancelled"),
                (4, 2, 2, 2, day - timedelta(days=3), True, True, 31.0, "completed"),
                (5, 3, 3, 1, day - timedelta(days=3), True, True, 26.0, "completed"),
                (6, 3, 3, 2, day - timedelta(days=2), True, False, None, "cancelled"),
                (7, 4, 4, 3, day - timedelta(days=1), True, True, 40.0, "completed"),
                (8, 5, 1, 1, day - timedelta(days=1), True, True, 22.0, "completed"),
                (9, 1, 2, 3, day, True, True, 19.0, "completed"),
                (10, 2, 5, 2, day, True, True, 28.0, "completed"),
                (11, 3, 3, 1, day, True, False, None, "cancelled"),
                (12, 4, 4, 1, day, True, True, 17.0, "completed"),
            ]
            connection.exec_driver_sql(
                """
                INSERT INTO rides (
                    id, user_id, driver_id, tariff_id, created_at, accepted_at, started_at,
                    completed_at, duration_minutes, status
                ) VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        ride_id,
                        user_id,
                        driver_id,
                        tariff_id,
                        created_at.isoformat(),
                        (created_at + timedelta(minutes=3)).isoformat() if accepted else None,
                        (created_at + timedelta(minutes=6)).isoformat() if started else None,
                        (created_at + timedelta(minutes=6 + int(duration))).isoformat() if status == "completed" and duration is not None else None,
                        duration,
                        status,
                    )
                    for ride_id, user_id, driver_id, tariff_id, created_at, accepted, started, duration, status in rides
                ],
            )

    def _run_dataset(
        self,
        service_db: Session,
        test_engine: Engine,
        database_id: str,
        category: str,
        path: Path,
    ) -> list[dict[str, Any]]:
        cases = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cases, list):
            raise ValueError(f"Dataset {path} must contain a JSON array.")

        results: list[dict[str, Any]] = []
        for case in cases:
            results.append(self._run_case(service_db, test_engine, database_id, category, case))
        return results

    def _run_case(
        self,
        service_db: Session,
        test_engine: Engine,
        database_id: str,
        category: str,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.chat_service.create_session(
            service_db,
            database_id,
            ChatSessionCreate(title=f"eval::{category}::{case['id']}"),
        )
        self._seed_history(service_db, session, case.get("context") or {})
        service_db.commit()

        initial_intent = self._normalize_intent((case.get("context") or {}).get("previous_intent"))
        prompt = str(case.get("user_prompt") or "")
        generated = self.chat_adapter.generate_response(
            service_db,
            session.id,
            prompt,
            query_mode="fast",
            llm_model_alias=None,
        )
        generated_sql = self._extract_generated_sql(generated)
        generated_intent = self._clean_intent_dict(generated.session.last_intent_json or {})
        generated_execution = self._execute_sql(test_engine, generated_sql) if generated_sql else ExecutionSnapshot(False, "No SQL generated", [], [], 0)
        reference_sql = str(case.get("reference_sql") or "").strip()
        reference_execution = self._execute_sql(test_engine, reference_sql) if reference_sql else ExecutionSnapshot(False, "No reference SQL", [], [], 0)
        system_action_log = self._build_system_action_log(generated_sql, generated_execution)

        expected_intent = case.get("expected_intent")
        intent_match = None
        if expected_intent is not None:
            intent_match = self._intent_matches(generated_intent, expected_intent)

        ex_match = self._results_match(generated_execution, reference_execution) if generated_execution.success and reference_execution.success else False
        vsr = bool(generated_sql and generated_execution.success)
        judge_result = self._run_judge(category, case, generated_sql, generated_intent, system_action_log)

        result = {
            "id": case.get("id"),
            "category": category,
            "user_prompt": prompt,
            "context": case.get("context") or {},
            "expected_sql_logic": case.get("expected_sql_logic"),
            "expected_columns": case.get("expected_columns") or [],
            "expected_behavior": case.get("expected_behavior"),
            "reference_sql": reference_sql,
            "generated_sql": generated_sql,
            "generated_intent": generated_intent,
            "initial_intent": initial_intent,
            "system_action_log": system_action_log,
            "generated_execution": self._snapshot_dict(generated_execution),
            "reference_execution": self._snapshot_dict(reference_execution),
            "judge": judge_result.as_dict(),
            "metrics": {
                "vsr": int(vsr),
                "ex": int(ex_match),
                "intent": None if intent_match is None else int(intent_match),
            },
        }
        return result

    def _seed_history(self, db: Session, session: ChatSessionModel, context: dict[str, Any]) -> None:
        previous_intent = context.get("previous_intent")
        if previous_intent is not None:
            cleaned = self._clean_intent_dict(previous_intent)
            if not cleaned.get("raw_prompt"):
                history = context.get("history") or []
                if history:
                    cleaned["raw_prompt"] = str(history[0])
            session.last_intent_json = cleaned

        for item in context.get("history") or []:
            self.chat_service.append_message(
                db,
                session,
                "user",
                str(item),
                structured_payload=None,
                commit=False,
            )

    def _run_judge(
        self,
        category: str,
        case: dict[str, Any],
        generated_sql: str,
        generated_intent: dict[str, Any],
        system_action_log: str,
    ) -> Any:
        if category == "single_shot":
            return self.judge.judge_single_shot(
                user_prompt=str(case.get("user_prompt") or ""),
                generated_sql=generated_sql,
                expected_sql_logic=str(case.get("expected_sql_logic") or ""),
            )
        if category == "multi_turn":
            return self.judge.judge_multi_turn(
                previous_intent_json=self._clean_intent_dict((case.get("context") or {}).get("previous_intent")),
                user_prompt=str(case.get("user_prompt") or ""),
                generated_intent_json=generated_intent,
                expected_intent_json=self._clean_intent_dict(case.get("expected_intent") or {}),
            )
        return self.judge.judge_edge_case(
            user_prompt=str(case.get("user_prompt") or ""),
            generated_sql=generated_sql,
            system_action_log=system_action_log,
            expected_behavior=str(case.get("expected_behavior") or ""),
        )

    def _build_system_action_log(self, generated_sql: str, execution: ExecutionSnapshot) -> str:
        if not generated_sql:
            return "no SQL generated"
        if not execution.success:
            return f"executed with error: {execution.error or 'unknown'}"
        if execution.row_count == 0:
            return "executed normally; returned 0 rows"
        return f"executed normally; returned {execution.row_count} rows"

    def _extract_generated_sql(self, generated: Any) -> str:
        sql = getattr(generated, "sql_draft", None)
        if sql:
            return str(sql).strip()
        structured = getattr(generated, "structured_payload", None)
        if structured is not None:
            payload_sql = getattr(structured, "sql", None)
            if payload_sql:
                return str(payload_sql).strip()
            if isinstance(structured, dict):
                payload_sql = structured.get("sql")
                if payload_sql:
                    return str(payload_sql).strip()
        return ""

    def _execute_sql(self, engine: Engine, sql: str) -> ExecutionSnapshot:
        sql = sql.strip().rstrip(";")
        if not sql:
            return ExecutionSnapshot(False, "Empty SQL", [], [], 0)
        try:
            with engine.connect() as connection:
                dataframe = pd.read_sql_query(text(sql), connection)
        except Exception as exc:  # noqa: BLE001
            return ExecutionSnapshot(False, str(exc), [], [], 0)

        columns = [str(column) for column in dataframe.columns.tolist()]
        rows = self._normalize_rows(dataframe)
        return ExecutionSnapshot(True, None, columns, rows, int(len(dataframe.index)))

    def _normalize_rows(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        rows = dataframe.to_dict(orient="records")
        normalized = [{key: self._normalize_value(value) for key, value in row.items()} for row in rows]
        normalized.sort(key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False, default=str))
        return normalized

    def _results_match(self, generated: ExecutionSnapshot, reference: ExecutionSnapshot) -> bool:
        if generated.columns != reference.columns:
            return False
        return generated.rows == reference.rows

    def _normalize_intent(self, value: Any) -> dict[str, Any]:
        return self._clean_intent_dict(value or {})

    def _intent_matches(self, actual: dict[str, Any], expected: dict[str, Any]) -> bool:
        actual = self._clean_intent_dict(actual)
        expected = self._clean_intent_dict(expected)
        for key in ("metric",):
            if expected.get(key) is not None and _normalize_text(actual.get(key)) != _normalize_text(expected.get(key)):
                return False
        if expected.get("dimensions") is not None:
            if _normalize_list(actual.get("dimensions")) != _normalize_list(expected.get("dimensions")):
                return False
        if expected.get("filters") is not None:
            if _normalize_filters(actual.get("filters")) != _normalize_filters(expected.get("filters")):
                return False
        if expected.get("date_range") is not None:
            actual_range = _normalize_date_range(actual.get("date_range"))
            expected_range = _normalize_date_range(expected.get("date_range"))
            for key, expected_value in expected_range.items():
                if actual_range.get(key) != expected_value:
                    return False
            if not expected_range and actual.get("date_range") is not None:
                return False
        return True

    def _clean_intent_dict(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        cleaned = dict(value)
        cleaned.pop("_analytical_context", None)
        return cleaned

    def _snapshot_dict(self, snapshot: ExecutionSnapshot) -> dict[str, Any]:
        return {
            "success": snapshot.success,
            "error": snapshot.error,
            "columns": snapshot.columns,
            "rows": snapshot.rows,
            "row_count": snapshot.row_count,
        }

    def _normalize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            if value != value:  # NaN
                return None
            if value in (float("inf"), float("-inf")):
                return str(value)
            return round(value, 4)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:  # noqa: BLE001
                return str(value)
        return str(value)

    def _build_summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(results)
        vsr_count = sum(int(item["metrics"]["vsr"]) for item in results)
        ex_count = sum(int(item["metrics"]["ex"]) for item in results)
        intent_results = [item["metrics"]["intent"] for item in results if item["metrics"]["intent"] is not None]
        intent_count = sum(int(value) for value in intent_results)
        intent_total = len(intent_results)

        category_summary: dict[str, dict[str, Any]] = {}
        for category in ("single_shot", "multi_turn", "edge_cases"):
            items = [item for item in results if item["category"] == category]
            category_summary[category] = self._category_summary(items)

        summary = {
            "total_cases": total,
            "overall": {
                "vsr": _ratio(vsr_count, total),
                "ex": _ratio(ex_count, total),
                "intent_accuracy": _ratio(intent_count, intent_total),
                "counts": {
                    "vsr": vsr_count,
                    "ex": ex_count,
                    "intent": intent_count,
                    "intent_total": intent_total,
                },
            },
            "categories": category_summary,
            "judge": {
                "available": self.judge.available,
                "mode": "llm" if self.judge.available else "heuristic",
            },
            "failures_by_code": self._failure_codes(results),
        }
        return summary

    def _category_summary(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(items)
        judge_pass = sum(int(item["judge"]["score"]) for item in items)
        vsr_pass = sum(int(item["metrics"]["vsr"]) for item in items)
        ex_pass = sum(int(item["metrics"]["ex"]) for item in items)
        intent_values = [item["metrics"]["intent"] for item in items if item["metrics"]["intent"] is not None]
        intent_pass = sum(int(value) for value in intent_values)
        return {
            "count": count,
            "judge_pass_count": judge_pass,
            "judge_pass_rate": _ratio(judge_pass, count),
            "vsr_count": vsr_pass,
            "vsr": _ratio(vsr_pass, count),
            "ex_count": ex_pass,
            "ex": _ratio(ex_pass, count),
            "intent_count": intent_pass,
            "intent_accuracy": _ratio(intent_pass, len(intent_values)),
            "intent_total": len(intent_values),
        }

    def _failure_codes(self, results: list[dict[str, Any]]) -> dict[str, int]:
        codes = Counter()
        for item in results:
            if item["judge"]["score"]:
                continue
            codes[f"{item['category']}_judge"] += 1
            if not item["metrics"]["vsr"]:
                codes["vsr"] += 1
            if not item["metrics"]["ex"]:
                codes["ex"] += 1
            if item["metrics"]["intent"] is not None and not item["metrics"]["intent"]:
                codes["intent"] += 1
        return dict(codes.most_common())

    def _write_artifacts(self, report: dict[str, Any]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (self.output_dir / "summary.json").write_text(json.dumps(report["summary"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (self.output_dir / "report.md").write_text(self._render_report(report), encoding="utf-8")

    def _render_report(self, report: dict[str, Any]) -> str:
        summary = report["summary"]
        categories = summary["categories"]
        lines = [
            "=== EVALUATION REPORT ===",
            f"VSR: {summary['overall']['vsr'] * 100:.0f}% ({summary['overall']['counts']['vsr']}/{summary['total_cases']})",
            f"EX: {summary['overall']['ex'] * 100:.0f}% ({summary['overall']['counts']['ex']}/{summary['total_cases']})",
            f"Intent Accuracy: {summary['overall']['intent_accuracy'] * 100:.0f}% ({summary['overall']['counts']['intent']}/{summary['overall']['counts']['intent_total']})",
            f"Single-shot Accuracy: {categories['single_shot']['judge_pass_rate'] * 100:.0f}% ({categories['single_shot']['judge_pass_count']}/{categories['single_shot']['count']})",
            f"Multi-turn Context Retention: {categories['multi_turn']['judge_pass_rate'] * 100:.0f}% ({categories['multi_turn']['judge_pass_count']}/{categories['multi_turn']['count']})",
            f"Edge Case Handling: {categories['edge_cases']['judge_pass_rate'] * 100:.0f}% ({categories['edge_cases']['judge_pass_count']}/{categories['edge_cases']['count']})",
            "=========================",
            "",
            "Category breakdown:",
        ]
        for category, payload in categories.items():
            lines.append(
                f"- {category}: judge={payload['judge_pass_rate']:.3f}, vsr={payload['vsr']:.3f}, ex={payload['ex']:.3f}, intent={payload['intent_accuracy']:.3f}"
            )
        if summary["failures_by_code"]:
            lines.append("")
            lines.append("Top failure codes:")
            for code, count in list(summary["failures_by_code"].items())[:10]:
                lines.append(f"- {code}: {count}")
        return "\n".join(lines)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_list(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    return sorted(_normalize_text(item) for item in value if _normalize_text(item))


def _normalize_date_range(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key in ("kind", "lookback_value", "lookback_unit", "start", "end"):
        if value.get(key) is not None:
            result[key] = str(value[key])
    return result


def _normalize_filters(value: Any) -> list[tuple[str, str, str]]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    result: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            (
                _normalize_text(item.get("field")),
                _normalize_text(item.get("operator") or "="),
                _normalize_text(item.get("value")),
            )
        )
    return sorted(result)


def main(argv: list[str] | None = None) -> int:
    backend_dir = Path(__file__).resolve().parents[2]
    evals_dir = backend_dir / "evals"

    parser = argparse.ArgumentParser(description="Run the SQL IDE eval framework against a static SQLite test database.")
    parser.add_argument("--single-shot", type=Path, default=evals_dir / "evals_single_shot.json")
    parser.add_argument("--multi-turn", type=Path, default=evals_dir / "evals_multi_turn.json")
    parser.add_argument("--edge-cases", type=Path, default=evals_dir / "evals_edge_cases.json")
    parser.add_argument("--output-dir", type=Path, default=evals_dir / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--judge-model", default="gpt-4o-mini")
    args = parser.parse_args(argv)

    runner = EvalRunner(
        single_shot_path=args.single_shot,
        multi_turn_path=args.multi_turn,
        edge_case_path=args.edge_cases,
        output_dir=args.output_dir,
        judge_model=args.judge_model,
    )
    report = runner.run()
    print(runner._render_report(report))
    print(f"Artifacts written to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
