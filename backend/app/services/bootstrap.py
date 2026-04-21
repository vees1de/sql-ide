from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, MetaData, String, Table, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import NotebookModel, SavedReportModel, SemanticDictionaryModel, WorkspaceModel
from app.db.session import analytics_engine, service_engine


def _ensure_database_connections_allowed_tables_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "database_connections" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("database_connections")}
        if "allowed_tables" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE database_connections ADD COLUMN allowed_tables TEXT"))
            else:
                connection.execute(text("ALTER TABLE database_connections ADD COLUMN allowed_tables JSONB"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_semantic_dictionary_context_columns(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "semantic_dictionary" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("semantic_dictionary")}
        required = {
            "object_type": "VARCHAR(32)",
            "table_name": "VARCHAR(255)",
            "column_name": "VARCHAR(255)",
            "source_database": "VARCHAR(255)",
        }
        with engine.begin() as connection:
            for name, sql_type in required.items():
                if name in columns:
                    continue
                connection.execute(text(f"ALTER TABLE semantic_dictionary ADD COLUMN {name} {sql_type}"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_semantic_catalog_relationship_graph_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "semantic_catalogs" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("semantic_catalogs")}
        if "relationship_graph" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE semantic_catalogs ADD COLUMN relationship_graph JSON"))
            else:
                connection.execute(text("ALTER TABLE semantic_catalogs ADD COLUMN relationship_graph JSONB"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_dashboard_hidden_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "dashboards" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("dashboards")}
        if "is_hidden" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE dashboards ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT 0"))
            else:
                connection.execute(text("ALTER TABLE dashboards ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT FALSE"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def bootstrap_application() -> None:
    Base.metadata.create_all(bind=service_engine)
    _ensure_database_connections_allowed_tables_column(service_engine)
    _ensure_semantic_dictionary_context_columns(service_engine)
    _ensure_semantic_catalog_relationship_graph_column(service_engine)
    _ensure_dashboard_hidden_column(service_engine)
    if settings.analytics_uses_demo_data:
        ensure_demo_analytics_database(analytics_engine)
    with Session(service_engine) as session:
        seed_service_data(session)


def seed_service_data(session: Session) -> None:
    workspace = session.query(WorkspaceModel).first()
    if workspace is None:
        workspace = WorkspaceModel(
            name=settings.demo_workspace_name,
            databases=[settings.demo_database_id],
        )
        session.add(workspace)
        session.flush()

    if session.query(SemanticDictionaryModel).count() == 0:
        session.add_all(
            [
                SemanticDictionaryModel(
                    term="revenue",
                    synonyms=["выручка", "оборот", "sales revenue"],
                    mapped_expression="SUM(o.revenue)",
                    description="Общая выручка по заказам.",
                ),
                SemanticDictionaryModel(
                    term="order_count",
                    synonyms=["количество заказов", "orders"],
                    mapped_expression="COUNT(o.id)",
                    description="Количество заказов.",
                ),
                SemanticDictionaryModel(
                    term="avg_order_value",
                    synonyms=["средний чек", "aov"],
                    mapped_expression="AVG(o.revenue)",
                    description="Средний чек.",
                ),
            ]
        )

    session.commit()
    if settings.analytics_uses_demo_data:
        seed_demo_notebooks(session, workspace.id)


def seed_demo_notebooks(session: Session, workspace_id: str) -> None:
    if session.query(NotebookModel).count() > 0:
        return

    from app.services.orchestration_service import QueryOrchestrationService

    orchestrator = QueryOrchestrationService()
    notebook_specs = [
        {
            "title": "Q1 Revenue Analysis",
            "prompts": [
                "Покажи выручку по месяцам за последние 6 месяцев",
                "Теперь только по Москве",
                "Сравни с аналогичным периодом прошлого года",
            ],
            "report_title": "Moscow Revenue Snapshot",
            "report_schedule": "First day of month, 10:00",
        },
        {
            "title": "Campaign Performance",
            "prompts": [
                "Покажи продажи и рекламу по последней кампании",
            ],
            "report_title": None,
            "report_schedule": None,
        },
    ]

    for spec in notebook_specs:
        notebook = NotebookModel(
            workspace_id=workspace_id,
            title=spec["title"],
            database_id=settings.demo_database_id,
            status="draft",
        )
        session.add(notebook)
        session.commit()
        session.refresh(notebook)

        for prompt in spec["prompts"]:
            orchestrator.run_prompt(session, notebook, prompt)
            session.refresh(notebook)

        if spec["report_title"]:
            session.add(
                SavedReportModel(
                    notebook_id=notebook.id,
                    title=str(spec["report_title"]),
                    schedule=str(spec["report_schedule"]),
                )
            )
            notebook.status = "saved"
            session.commit()


def ensure_demo_analytics_database(engine: Engine) -> None:
    metadata = MetaData()
    customers = Table(
        "customers",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("city", String(255), nullable=False),
        Column("region", String(255), nullable=False),
        Column("segment", String(64), nullable=False),
    )
    campaigns = Table(
        "campaigns",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("channel", String(64), nullable=False),
    )
    orders = Table(
        "orders",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("order_date", Date, nullable=False),
        Column("customer_id", Integer, ForeignKey("customers.id"), nullable=False),
        Column("campaign_id", Integer, ForeignKey("campaigns.id"), nullable=False),
        Column("status", String(64), nullable=False),
        Column("quantity", Integer, nullable=False),
        Column("revenue", Float, nullable=False),
    )

    metadata.create_all(engine)
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        metadata.create_all(engine)

    with engine.begin() as connection:
        existing_orders = connection.execute(select(orders.c.id).limit(1)).first()
        if existing_orders is not None:
            return

        city_to_region = {
            "Moscow": "Central",
            "Saint Petersburg": "North-West",
            "Kazan": "Volga",
            "Novosibirsk": "Siberia",
            "Yekaterinburg": "Ural",
            "Yakutsk": "Far East",
        }
        segments = ["Enterprise", "SMB", "Retail"]
        customer_rows = []
        customer_id = 1
        for city, region in city_to_region.items():
            for segment in segments:
                for index in range(1, 7):
                    customer_rows.append(
                        {
                            "id": customer_id,
                            "name": f"{segment} {city} {index}",
                            "city": city,
                            "region": region,
                            "segment": segment,
                        }
                    )
                    customer_id += 1
        connection.execute(customers.insert(), customer_rows)

        campaign_rows = [
            {"id": 1, "name": "Brand Search", "channel": "SEO"},
            {"id": 2, "name": "Performance Ads", "channel": "Paid Ads"},
            {"id": 3, "name": "CRM Email", "channel": "Email"},
            {"id": 4, "name": "Social Boost", "channel": "Social"},
            {"id": 5, "name": "Partner Referral", "channel": "Referral"},
        ]
        connection.execute(campaigns.insert(), campaign_rows)

        rng = random.Random(42)
        order_rows = []
        current_date = date.today() - timedelta(days=540)
        end_date = date.today()
        order_id = 1

        customer_ids = [item["id"] for item in customer_rows]
        while current_date <= end_date:
            daily_orders = rng.randint(4, 10)
            for _ in range(daily_orders):
                customer_ref = rng.choice(customer_rows)
                campaign_ref = rng.choice(campaign_rows)
                quantity = rng.randint(1, 6)
                segment_multiplier = {"Enterprise": 2.4, "SMB": 1.3, "Retail": 0.9}[customer_ref["segment"]]
                channel_multiplier = {
                    "SEO": 1.25,
                    "Paid Ads": 1.45,
                    "Email": 0.95,
                    "Social": 1.1,
                    "Referral": 1.35,
                }[campaign_ref["channel"]]
                seasonal_multiplier = 1.0 + ((current_date.month % 6) * 0.05)
                base_value = rng.uniform(90, 420)
                revenue = round(base_value * quantity * segment_multiplier * channel_multiplier * seasonal_multiplier, 2)
                order_rows.append(
                    {
                        "id": order_id,
                        "order_date": current_date,
                        "customer_id": customer_ref["id"],
                        "campaign_id": campaign_ref["id"],
                        "status": "completed",
                        "quantity": quantity,
                        "revenue": revenue,
                    }
                )
                order_id += 1
            current_date += timedelta(days=1)

        connection.execute(orders.insert(), order_rows)
