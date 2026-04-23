from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChartAxisPayload(BaseModel):
    field: str | None = None
    values: list[Any] = Field(default_factory=list)
    type: str | None = None


class ChartYPayload(BaseModel):
    field: str | None = None
    values: list[float] = Field(default_factory=list)
    unit: str | None = None


class ChartSeriesItemPayload(BaseModel):
    name: str
    data: list[float] = Field(default_factory=list)


class ChartSlicePayload(BaseModel):
    name: str
    value: float


class ChartDecisionConfigPayload(BaseModel):
    xField: str | None = None
    yField: str | None = None
    seriesField: str | None = None
    facetField: str | None = None
    sort: str | None = None
    normalize: str | None = None
    seriesLimit: int | None = None
    categoryLimit: int | None = None
    topNStrategy: str | None = None
    valueFormat: str | None = None
    dataRoles: dict[str, Any] | None = None


class BaseChartPayload(BaseModel):
    kind: Literal["table", "kpi", "pie", "single_series", "multi_series"]
    chartType: str
    variant: str | None = None
    explanation: str | None = None
    reason: str
    ruleId: str | None = None
    confidence: float | None = None
    semanticIntent: str | None = None
    analysisMode: str | None = None
    visualGoal: str | None = None
    timeRole: str | None = None
    comparisonGoal: str | None = None
    preferredMark: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    constraintsApplied: list[str] = Field(default_factory=list)
    visualLoad: int | None = None
    reasonCodes: list[str] = Field(default_factory=list)
    queryInterpretation: dict[str, Any] | None = None
    decisionSummary: dict[str, Any] | None = None
    understanding: dict[str, Any] | None = None
    decision: dict[str, Any] = Field(default_factory=dict)
    explanationBlock: dict[str, Any] = Field(default_factory=dict)
    config: ChartDecisionConfigPayload


class TableChartPayload(BaseChartPayload):
    kind: Literal["table"]


class KpiChartPayload(BaseChartPayload):
    kind: Literal["kpi"]
    value: float | int | str
    metricLabel: str | None = None


class PieChartPayload(BaseChartPayload):
    kind: Literal["pie"]
    slices: list[ChartSlicePayload] = Field(default_factory=list)


class SingleSeriesChartPayload(BaseChartPayload):
    kind: Literal["single_series"]
    x: ChartAxisPayload
    y: ChartYPayload
    stacked: bool = False


class MultiSeriesChartPayload(BaseChartPayload):
    kind: Literal["multi_series"]
    x: ChartAxisPayload
    series: list[ChartSeriesItemPayload] = Field(default_factory=list)
    seriesField: str | None = None
    facetField: str | None = None
    stackable: bool = False
    stacked: bool = False

    @model_validator(mode="after")
    def validate_series_lengths(self) -> "MultiSeriesChartPayload":
        expected_length = len(self.x.values)
        for item in self.series:
            if len(item.data) != expected_length:
                raise ValueError("Series data length must match x axis length.")
        return self


def validate_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("kind")
    model: type[BaseModel]
    if kind == "table":
        model = TableChartPayload
    elif kind == "kpi":
        model = KpiChartPayload
    elif kind == "pie":
        model = PieChartPayload
    elif kind == "multi_series":
        model = MultiSeriesChartPayload
    elif kind == "single_series":
        model = SingleSeriesChartPayload
    else:
        raise ValueError(f"Unsupported chart payload kind: {kind}")
    return model.model_validate(payload).model_dump(mode="json")
