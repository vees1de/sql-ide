# BI layer implementation

This project now has a dedicated BI layer on top of the existing SQL chat and dataset flow.

## Product flow

```text
SQL chat execution
  -> DatasetModel
  -> inferred BI fields: dimensions, measures, time fields
  -> ChartSpec validation and SQL compilation
  -> saved WidgetModel
  -> DashboardModel / DashboardWidgetModel
```

The important rule is that charts are not stored as images. A chart is stored as a JSON `ChartSpec`, and the backend compiles that spec into a safe aggregate SQL query over the saved dataset SQL.

## Backend files

- `backend/app/schemas/bi.py` — Dataset, field, ChartSpec, chart preview and quick dashboard DTOs.
- `backend/app/services/bi_service.py` — semantic field inference, chart recommendations, ChartSpec validation, SQL compilation, preview execution, chart/widget saving, quick dashboard generation.
- `backend/app/api/routes/bi.py` — public API endpoints for datasets, chart validation, chart preview, chart saving and auto dashboards.
- `backend/app/api/router.py` — registers the new BI routes.

## New API endpoints

```http
GET    /api/datasets
GET    /api/datasets/{dataset_id}
PATCH  /api/datasets/{dataset_id}
DELETE /api/datasets/{dataset_id}
GET    /api/datasets/{dataset_id}/preview
POST   /api/datasets/{dataset_id}/refresh
GET    /api/datasets/{dataset_id}/chart-recommendations
POST   /api/charts/validate
POST   /api/charts/preview
POST   /api/charts
POST   /api/datasets/{dataset_id}/quick-dashboard
```

## Frontend files

- `frontend/src/views/BIStudioView.vue` — new `/bi` screen for dataset selection, schema preview, chart recommendations, manual ChartSpec builder, live preview, widget saving and quick dashboard creation.
- `frontend/src/api/types.ts` — BI DTOs and extended ChartSpec typings.
- `frontend/src/api/client.ts` — API methods for the BI endpoints.
- `frontend/src/router/index.ts` — `/bi` route.
- `frontend/src/components/chat/ChatSidebar.vue` — BI Studio navigation item.

## How to use

1. Run any SQL query in the chat. Successful executions are already saved as `DatasetModel`.
2. Open `/bi` or click `BI Studio` in the sidebar.
3. Select a dataset.
4. Pick an auto recommendation or configure the ChartSpec manually.
5. Click `Preview` to compile and execute the ChartSpec.
6. Click `Save chart` to save it as a widget.
7. Click `Auto dashboard` to generate a dashboard from the best chart recommendations.

## ChartSpec example

```json
{
  "chart_type": "bar",
  "title": "Revenue by city",
  "dataset_id": "ds_123",
  "encoding": {
    "x_field": "city",
    "y_field": "revenue",
    "aggregation": "sum",
    "sort": "y_desc",
    "category_limit": 10,
    "value_format": "currency"
  },
  "filters": [],
  "options": {},
  "variant": null
}
```

## Safety model

- Dataset fields are whitelisted from `columns_schema` before SQL compilation.
- User-provided fields are always quoted as identifiers.
- Filter values are converted into SQL literals by the backend.
- The backend executes BI previews through the existing database resolution and read-only guard path.
- Saved charts keep both the compiled SQL and the original `chart_spec_json`.
