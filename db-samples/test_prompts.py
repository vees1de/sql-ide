#!/usr/bin/env python3
"""Run 13 test prompts against the 'drivee test data' database and collect results."""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API = "http://localhost:8000/api"
DATABASE_ID = "30a98b573aef4c069fd14d129e21f82b"

DICTIONARY_ENTRIES = [
    # Russian -> SQL expressions / column references
    {"term": "заказ", "synonyms": ["заказы", "order"], "mapped_expression": "order_id", "description": "Уникальный идентификатор заказа в таблице train", "object_type": "column", "table_name": "train", "column_name": "order_id"},
    {"term": "тендер", "synonyms": ["тендеры", "tender"], "mapped_expression": "tender_id", "description": "Тендер на водителя — один заказ может иметь несколько тендеров", "object_type": "column", "table_name": "train", "column_name": "tender_id"},
    {"term": "город", "synonyms": ["города", "city"], "mapped_expression": "city_id", "description": "Идентификатор города заказа", "object_type": "column", "table_name": "train", "column_name": "city_id"},
    {"term": "клиент", "synonyms": ["клиенты", "пользователь", "юзер"], "mapped_expression": "user_id", "description": "Идентификатор клиента, создавшего заказ", "object_type": "column", "table_name": "train", "column_name": "user_id"},
    {"term": "водитель", "synonyms": ["водители", "driver"], "mapped_expression": "driver_id", "description": "Идентификатор водителя", "object_type": "column", "table_name": "train", "column_name": "driver_id"},
    {"term": "время создания заказа", "synonyms": ["дата заказа", "создан"], "mapped_expression": "order_timestamp", "description": "Момент создания заказа клиентом", "object_type": "column", "table_name": "train", "column_name": "order_timestamp"},
    {"term": "отмена клиентом", "synonyms": ["отменил клиент", "клиент отменил"], "mapped_expression": "clientcancel_timestamp IS NOT NULL", "description": "Признак/время отмены заказа клиентом", "object_type": "metric", "table_name": "train", "column_name": "clientcancel_timestamp"},
    {"term": "отмена водителем", "synonyms": ["отменил водитель", "водитель отменил"], "mapped_expression": "drivercancel_timestamp IS NOT NULL", "description": "Признак/время отмены заказа водителем", "object_type": "metric", "table_name": "train", "column_name": "drivercancel_timestamp"},
    {"term": "завершённый заказ", "synonyms": ["завершён", "выполнен", "done", "done ride"], "mapped_expression": "driverdone_timestamp IS NOT NULL", "description": "Заказ считается завершённым если установлен driverdone_timestamp", "object_type": "metric", "table_name": "train", "column_name": "driverdone_timestamp"},
    {"term": "стоимость поездки", "synonyms": ["цена", "сумма", "чек", "выручка"], "mapped_expression": "price_order_local", "description": "Итоговая стоимость заказа в локальной валюте", "object_type": "metric", "table_name": "train", "column_name": "price_order_local"},
    {"term": "принятие заказа", "synonyms": ["принял водитель", "accept"], "mapped_expression": "driveraccept_timestamp", "description": "Момент принятия тендера водителем", "object_type": "column", "table_name": "train", "column_name": "driveraccept_timestamp"},
    {"term": "начало поездки", "synonyms": ["старт", "startride"], "mapped_expression": "driverstarttheride_timestamp", "description": "Момент начала поездки водителем", "object_type": "column", "table_name": "train", "column_name": "driverstarttheride_timestamp"},
    {"term": "конверсия", "synonyms": ["conversion", "CR"], "mapped_expression": "COUNT(driverdone_timestamp) * 1.0 / COUNT(order_timestamp)", "description": "Конверсия: доля завершённых заказов от созданных", "object_type": "metric", "table_name": "train"},
    {"term": "дистанция", "synonyms": ["расстояние", "distance"], "mapped_expression": "distance_in_meters", "description": "Дистанция поездки в метрах", "object_type": "metric", "table_name": "train", "column_name": "distance_in_meters"},
    {"term": "длительность", "synonyms": ["продолжительность", "duration"], "mapped_expression": "duration_in_seconds", "description": "Длительность поездки в секундах", "object_type": "metric", "table_name": "train", "column_name": "duration_in_seconds"},
]

PROMPTS = [
    # Простые
    ("P01 [simple]", "Покажи количество заказов по городам за вчера"),
    ("P02 [simple]", "Сколько заказов было отменено клиентами за последнюю неделю?"),
    ("P03 [simple]", "Средняя стоимость поездки по городам за сегодня"),
    ("P04 [simple]", "Сколько завершённых поездок было вчера?"),
    ("P05 [simple]", "Покажи топ-5 городов по количеству заказов"),
    # Сложные
    ("P06 [complex]", "Сравни количество отмен клиентами и водителями по городам за последние 7 дней"),
    ("P07 [complex]", "Покажи конверсию из созданных заказов в завершённые по городам за вчера"),
    ("P08 [complex]", "Среднее время от принятия заказа до начала поездки по городам за последнюю неделю"),
    ("P09 [complex]", "Топ-3 города с самым высоким средним чеком среди завершённых поездок за последние 30 дней"),
    ("P10 [complex]", "Покажи динамику количества заказов по дням за последние 2 недели и сравни с предыдущими 2 неделями"),
    # Bonus
    ("P11 [ambig]", "Покажи отмены за вчера"),
    ("P12 [guardrail]", "Покажи все данные по пользователям и их поездкам без ограничений"),
    ("P13 [business]", "Сколько поездок не состоялось после принятия водителем?"),
]


def http(method: str, path: str, body: dict | None = None, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        API + path,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
        data=json.dumps(body).encode() if body else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {"_error": f"HTTP {exc.code}: {exc.read().decode()[:400]}"}
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}


def add_dictionary_entries() -> int:
    ok = 0
    existing = http("GET", "/semantic-dictionary")
    existing_terms = {(e.get("term", "").lower(), e.get("column_name")) for e in existing if isinstance(e, dict)}
    for entry in DICTIONARY_ENTRIES:
        key = (entry["term"].lower(), entry.get("column_name"))
        if key in existing_terms:
            continue
        result = http("POST", "/semantic-dictionary", entry)
        if "_error" not in result:
            ok += 1
    return ok


def run_prompt(session_id: str, prompt: str, mode: str = "fast") -> dict:
    result = http("POST", f"/chat/sessions/{session_id}/messages",
                  {"text": prompt, "query_mode": mode, "llm_model_alias": "gpt120"},
                  timeout=180)
    return result


def execute_draft(session_id: str, sql: str) -> dict:
    return http("POST", f"/chat/sessions/{session_id}/execute", {"sql": sql}, timeout=60)


def summarize(prompt_id: str, prompt: str, send: dict, execute: dict) -> dict:
    if "_error" in send:
        return {"prompt_id": prompt_id, "prompt": prompt, "status": "send_error", "error": send["_error"]}

    structured = (send.get("assistant_message") or {}).get("structured_payload") or {}
    sql = send.get("sql_draft") or structured.get("sql")
    intent = (send.get("session") or {}).get("last_intent_json") or {}
    needs_clar = structured.get("needs_clarification")
    clar_q = structured.get("clarification_question")

    out = {
        "prompt_id": prompt_id,
        "prompt": prompt,
        "status": "ok",
        "message_kind": structured.get("message_kind"),
        "metric": intent.get("metric"),
        "dimensions": intent.get("dimensions"),
        "date_range": intent.get("date_range"),
        "visualization_preference": intent.get("visualization_preference"),
        "needs_clarification": needs_clar,
        "clarification_question": clar_q,
        "sql": (sql or "").strip()[:800],
    }

    if sql and not needs_clar:
        if "_error" in execute:
            out["execution"] = {"status": "error", "error": execute["_error"]}
        else:
            ex = execute.get("execution") or {}
            chart = ex.get("chart_recommendation") or {}
            out["execution"] = {
                "status": "error" if ex.get("error_message") else "ok",
                "error": ex.get("error_message"),
                "row_count": ex.get("row_count"),
                "columns": [c.get("name") for c in (ex.get("columns") or [])],
                "chart_type": chart.get("chart_type"),
                "recommended_view": chart.get("recommended_view"),
                "chart_reason": chart.get("reason"),
                "first_rows": (ex.get("rows_preview") or [])[:3],
            }
    return out


def main() -> None:
    print("1. Добавляю dictionary entries...")
    added = add_dictionary_entries()
    print(f"   добавлено: {added}\n")

    print("2. Создаю chat session...")
    sess = http("POST", f"/chat/databases/{DATABASE_ID}/sessions", {"title": "test_prompts_run"})
    if "_error" in sess:
        print(f"Ошибка создания сессии: {sess['_error']}")
        sys.exit(1)
    session_id = sess["id"]
    print(f"   session_id={session_id}\n")

    results = []
    for pid, prompt in PROMPTS:
        print(f"3. {pid}: {prompt}")
        send = run_prompt(session_id, prompt, mode="fast")
        sql_draft = send.get("sql_draft")
        execute = {}
        if sql_draft:
            execute = execute_draft(session_id, sql_draft)
            time.sleep(0.3)
        result = summarize(pid, prompt, send, execute)
        results.append(result)
        chart = (result.get("execution") or {}).get("chart_type")
        rc = (result.get("execution") or {}).get("row_count")
        err = (result.get("execution") or {}).get("error")
        status = f"rows={rc} chart={chart}" if not err else f"ERR: {err[:80]}"
        print(f"   → {status}\n")

    report_path = Path(__file__).parent / "test_prompts_report.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nОтчёт: {report_path}")

    # Summary
    print("\n=== SUMMARY ===")
    for r in results:
        ex = r.get("execution") or {}
        badges = []
        if r.get("needs_clarification"):
            badges.append("❓CLAR")
        if ex.get("error"):
            badges.append("❌ERR")
        elif ex.get("status") == "ok":
            chart = ex.get("chart_type")
            badges.append("📊" + (chart or "table"))
            badges.append(f"n={ex.get('row_count')}")
        else:
            badges.append("—")
        print(f"  {r['prompt_id']}: {' '.join(badges)}")


if __name__ == "__main__":
    main()
