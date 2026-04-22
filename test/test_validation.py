from __future__ import annotations

from types import SimpleNamespace

import app.agents.validation as validation_module
from app.agents.validation import SQLValidationAgent
from app.schemas.semantic_catalog import SemanticCatalog, SemanticColumn, SemanticJoinPath, SemanticRelationship, SemanticTable


def _set_limit_settings(monkeypatch, default_row_limit: int = 50, max_row_limit: int = 1000) -> None:
    monkeypatch.setattr(
        validation_module,
        "settings",
        SimpleNamespace(default_row_limit=default_row_limit, max_row_limit=max_row_limit),
    )


def test_validation_adds_default_limit_when_missing(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer", "postgresql")

    assert result.valid
    assert "LIMIT 50" in result.sql
    assert any("LIMIT 50 was added automatically." == warning for warning in result.warnings)


def test_validation_preserves_user_limit(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer LIMIT 5", "postgresql")

    assert result.valid
    assert "LIMIT 5" in result.sql
    assert all("added automatically" not in warning for warning in result.warnings)


def test_validation_caps_limit_at_max(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run("SELECT * FROM customer LIMIT 5000", "postgresql")

    assert result.valid
    assert "LIMIT 1000" in result.sql
    assert any("LIMIT 5000 was reduced to 1000." == warning for warning in result.warnings)


def _semantic_catalog() -> SemanticCatalog:
    orders_columns = [
        SemanticColumn(
            schema_name="public",
            table_name="orders",
            column_name="id",
            label="ID",
            business_description="Order identifier",
            semantic_types=["id"],
            analytics_roles=["display_name"],
            filterable=True,
            groupable=True,
            data_type="integer",
            is_pk=True,
        ),
        SemanticColumn(
            schema_name="public",
            table_name="orders",
            column_name="customer_id",
            label="Customer",
            business_description="Customer reference",
            semantic_types=["foreign_key"],
            analytics_roles=["default_filter"],
            filterable=True,
            groupable=True,
            data_type="integer",
            is_fk=True,
            referenced_table="customers",
            referenced_column="id",
        ),
        SemanticColumn(
            schema_name="public",
            table_name="orders",
            column_name="revenue",
            label="Revenue",
            business_description="Booked revenue",
            semantic_types=["metric", "currency"],
            analytics_roles=["primary_metric"],
            filterable=True,
            groupable=False,
            aggregation=["sum", "avg"],
            data_type="numeric",
        ),
        SemanticColumn(
            schema_name="public",
            table_name="orders",
            column_name="order_date",
            label="Order Date",
            business_description="Order timestamp",
            semantic_types=["datetime"],
            analytics_roles=["time_axis"],
            filterable=True,
            groupable=True,
            data_type="timestamp",
        ),
    ]
    customers_columns = [
        SemanticColumn(
            schema_name="public",
            table_name="customers",
            column_name="id",
            label="ID",
            business_description="Customer identifier",
            semantic_types=["id"],
            analytics_roles=["display_name"],
            filterable=True,
            groupable=True,
            data_type="integer",
            is_pk=True,
        ),
        SemanticColumn(
            schema_name="public",
            table_name="customers",
            column_name="city",
            label="City",
            business_description="Customer city",
            semantic_types=["location"],
            analytics_roles=["default_group_by"],
            filterable=True,
            groupable=True,
            data_type="text",
        ),
    ]
    relationship = SemanticRelationship(
        from_table="orders",
        from_column="customer_id",
        to_table="customers",
        to_column="id",
        relationship_type="many-to-one",
        business_meaning="Each order belongs to one customer.",
        confidence=1.0,
    )
    return SemanticCatalog(
        database_id="demo",
        dialect="postgresql",
        tables=[
            SemanticTable(
                schema_name="public",
                table_name="orders",
                label="Orders",
                business_description="Fact table for orders",
                table_role="fact",
                grain="one row = one order",
                main_date_column="order_date",
                important_metrics=["total_revenue: SUM(revenue)"],
                columns=orders_columns,
            ),
            SemanticTable(
                schema_name="public",
                table_name="customers",
                label="Customers",
                business_description="Customer dimension",
                table_role="dimension",
                columns=customers_columns,
            ),
        ],
        relationships=[relationship],
        join_paths=[
            SemanticJoinPath(
                path_id="orders_to_customers",
                from_table="orders",
                to_table="customers",
                joins=["orders.customer_id = customers.id"],
                business_use_case="Analyze orders by customer attributes.",
                tables=["orders", "customers"],
            )
        ],
        relationship_graph=[],
    )


def test_validation_reports_high_semantic_confidence_for_catalog_backed_query(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run(
        (
            "SELECT c.city, SUM(o.revenue) AS total_revenue "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "GROUP BY c.city"
        ),
        "postgresql",
        semantic_catalog=_semantic_catalog(),
    )

    assert result.valid
    assert result.semantic_confidence_level == "high"
    assert any("semantic catalog" in reason.lower() for reason in result.semantic_confidence_reasons)


def test_validation_reports_low_semantic_confidence_when_query_uses_table_outside_catalog(monkeypatch) -> None:
    _set_limit_settings(monkeypatch)
    agent = SQLValidationAgent()

    result = agent.run(
        (
            "SELECT d.name, SUM(o.revenue) AS total_revenue "
            "FROM orders o "
            "JOIN drivers d ON o.driver_id = d.id "
            "GROUP BY d.name"
        ),
        "postgresql",
        semantic_catalog=_semantic_catalog(),
    )

    assert not result.valid
    assert result.semantic_confidence_level == "low"
    assert any("semantic catalog does not contain tables" in error.lower() for error in result.errors)
