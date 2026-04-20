from __future__ import annotations

from app.agents.intent import IntentAgent
from app.agents.semantic import SemanticMappingAgent
from app.agents.sql_generation import SQLGenerationAgent
from app.schemas.metadata import ColumnMetadata, RelationshipMetadata, SchemaMetadataResponse, TableMetadata


def _payment_schema() -> SchemaMetadataResponse:
    return SchemaMetadataResponse(
        database_id="dvdrental",
        dialect="postgresql",
        tables=[
            TableMetadata(
                name="payment",
                columns=[
                    ColumnMetadata(name="payment_id", type="integer"),
                    ColumnMetadata(name="amount", type="numeric(5,2)"),
                    ColumnMetadata(name="payment_date", type="timestamp without time zone"),
                ],
            )
        ],
        relationships=[],
    )


def _orders_schema() -> SchemaMetadataResponse:
    return SchemaMetadataResponse(
        database_id="demo",
        dialect="postgresql",
        tables=[
            TableMetadata(
                name="orders",
                columns=[
                    ColumnMetadata(name="id", type="integer"),
                    ColumnMetadata(name="order_date", type="date"),
                    ColumnMetadata(name="customer_id", type="integer"),
                    ColumnMetadata(name="revenue", type="numeric(12,2)"),
                ],
            ),
            TableMetadata(
                name="customers",
                columns=[
                    ColumnMetadata(name="id", type="integer"),
                    ColumnMetadata(name="city", type="text"),
                ],
            ),
        ],
        relationships=[
            RelationshipMetadata(
                from_table="orders",
                from_column="customer_id",
                to_table="customers",
                to_column="id",
                relation_type="foreign_key",
                cardinality="many_to_one",
            )
        ],
    )


def test_schema_aware_semantic_uses_payment_table_for_yearly_revenue() -> None:
    intent = IntentAgent().run("Покажи выручку по месяцам за 2006 год")
    schema = _payment_schema()

    semantic = SemanticMappingAgent().run(intent, [], schema.dialect, schema)
    sql = SQLGenerationAgent().run(intent, semantic)

    assert intent.date_range is not None
    assert intent.date_range.start.isoformat() == "2006-01-01"
    assert intent.date_range.end.isoformat() == "2006-12-31"
    assert semantic.base_table == "payment"
    assert semantic.base_alias == "t0"
    assert semantic.time_expression == "t0.payment_date"
    assert semantic.metric_expression == "SUM(t0.amount)"
    assert semantic.metric_alias == "total_revenue"
    assert semantic.dimension_mappings[0].expression == "date_trunc('month', t0.payment_date)"
    assert "FROM payment t0" in sql
    assert "SUM(t0.amount) AS total_revenue" in sql
    assert "t0.payment_date >= '2006-01-01'" in sql
    assert "t0.payment_date < '2007-01-01'" in sql


def test_schema_aware_semantic_joins_customers_for_city_dimension() -> None:
    intent = IntentAgent().run("Покажи выручку по городам")
    schema = _orders_schema()

    semantic = SemanticMappingAgent().run(intent, [], schema.dialect, schema)
    sql = SQLGenerationAgent().run(intent, semantic)

    assert semantic.base_table == "orders"
    assert semantic.time_expression is None
    assert any(mapping.expression.endswith(".city") for mapping in semantic.dimension_mappings)
    assert any("JOIN customers" in join for join in semantic.joins)
    assert "FROM orders t0" in sql
    assert "JOIN customers" in sql
    assert "t1.city" in sql
