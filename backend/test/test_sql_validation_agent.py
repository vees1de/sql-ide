from app.agents.validation import SQLValidationAgent


def test_validation_allows_cte_names_outside_table_whitelist() -> None:
    sql = """
WITH filtered AS (
    SELECT *
    FROM train
)
SELECT COUNT(*)
FROM filtered
""".strip()

    validation = SQLValidationAgent().run(sql, "postgresql", allowed_tables=["train"])

    assert validation.valid is True
    assert validation.tables == ["train"]
