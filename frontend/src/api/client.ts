import type {
  ApiERDGraph,
  ApiCellRead,
  ApiDictionaryEntryCreate,
  ApiDatabaseConnectionCreate,
  ApiDatabaseConnectionUpdate,
  ApiDatabaseDescriptor,
  ApiKnowledgeScanRun,
  ApiKnowledgeSummary,
  ApiKnowledgeTable,
  ApiLlmModelAliasesResponse,
  ApiNotebookCellCreate,
  ApiNotebookCellRunRequest,
  ApiNotebookCellReorder,
  ApiNotebookCellUpdate,
  ApiSchemaPreviewResponse,
  ApiDictionaryEntryRead,
  ApiNotebookDetail,
  ApiNotebookRead,
  ApiPromptRunResponse,
  ApiQueryMode,
  ApiQueryTemplate,
  ApiReportRead,
  ApiSemanticCatalog,
  ApiSemanticCatalogActivationRequest,
  ApiSchemaMetadataResponse,
  ApiWorkspaceRead,
  ApiWidgetRead,
  ApiWidgetDetail,
  ApiWidgetCreate,
  ApiWidgetUpdate,
  ApiDashboardRead,
  ApiDashboardDetail,
  ApiDashboardScheduleRead,
  ApiDashboardScheduleUpsert,
  ApiDashboardCreate,
  ApiDashboardUpdate,
  ApiDashboardWidgetDetail,
  ApiDashboardWidgetAdd,
  ApiDashboardWidgetPatch,
  ApiDatasetRead,
  ApiDatasetUpdate,
  ApiDatasetPreviewResponse,
  ApiChartRecommendationRead,
  ApiBiChartSpec,
  ApiBiFilterCondition,
  ApiChartValidationResponse,
  ApiChartPreviewResponse,
  ApiChartSaveResponse,
  ApiQuickDashboardResponse,
} from "@/api/types";

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL
  ?? import.meta.env.BASE_URL.replace(/\/+$/, "")
).replace(/\/+$/, "");

function toUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(toUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail || "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  previewDatabaseSchema(payload: ApiDatabaseConnectionCreate) {
    return request<ApiSchemaPreviewResponse>("/api/databases/preview-schema", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  createDatabase(payload: ApiDatabaseConnectionCreate) {
    return request<ApiDatabaseDescriptor>("/api/databases", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateDatabase(databaseId: string, payload: ApiDatabaseConnectionUpdate) {
    return request<ApiDatabaseDescriptor>(`/api/databases/${databaseId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteDatabase(databaseId: string) {
    return request<void>(`/api/databases/${databaseId}`, {
      method: "DELETE",
    });
  },
  createNotebook(payload: {
    workspace_id: string;
    title: string;
    database_id: string;
  }) {
    return request<ApiNotebookRead>("/api/notebooks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteNotebook(notebookId: string) {
    return request<void>(`/api/notebooks/${notebookId}`, {
      method: "DELETE",
    });
  },
  createNotebookCell(notebookId: string, payload: ApiNotebookCellCreate) {
    return request<ApiCellRead>(`/api/notebooks/${notebookId}/cells`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateNotebookCell(
    notebookId: string,
    cellId: string,
    payload: ApiNotebookCellUpdate,
  ) {
    return request<ApiCellRead>(
      `/api/notebooks/${notebookId}/cells/${cellId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },
  runNotebookCell(
    notebookId: string,
    cellId: string,
    payload?: ApiNotebookCellRunRequest,
  ) {
    return request<ApiPromptRunResponse>(
      `/api/notebooks/${notebookId}/cells/${cellId}/run`,
      {
        method: "POST",
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      },
    );
  },
  formatNotebookSqlCell(notebookId: string, cellId: string) {
    return request<ApiCellRead>(
      `/api/notebooks/${notebookId}/cells/${cellId}/format-sql`,
      {
        method: "POST",
      },
    );
  },
  reorderNotebookCells(notebookId: string, payload: ApiNotebookCellReorder) {
    return request<ApiNotebookDetail>(
      `/api/notebooks/${notebookId}/cells/reorder`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  createReport(payload: {
    notebook_id: string;
    title: string;
    schedule?: string | null;
  }) {
    return request<ApiReportRead>("/api/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getDatabases() {
    return request<ApiDatabaseDescriptor[]>("/api/databases");
  },
  deleteSemanticCatalog(databaseId: string) {
    return request<void>(
      `/api/metadata/semantic-catalog?database_id=${encodeURIComponent(databaseId)}`,
      {
        method: "DELETE",
      },
    );
  },
  patchSemanticTable(
    databaseId: string,
    tableName: string,
    payload: import("./types").ApiSemanticTablePatch,
  ) {
    return request<import("./types").ApiSemanticTable>(
      `/api/metadata/semantic-catalog/table?database_id=${encodeURIComponent(databaseId)}&table_name=${encodeURIComponent(tableName)}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },
  patchSemanticColumn(
    databaseId: string,
    tableName: string,
    columnName: string,
    payload: import("./types").ApiSemanticColumnPatch,
  ) {
    return request<import("./types").ApiSemanticTable>(
      `/api/metadata/semantic-catalog/column?database_id=${encodeURIComponent(databaseId)}&table_name=${encodeURIComponent(tableName)}&column_name=${encodeURIComponent(columnName)}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },
  getDictionary(databaseId?: string) {
    const qs = databaseId
      ? `?database_id=${encodeURIComponent(databaseId)}`
      : "";
    return request<ApiDictionaryEntryRead[]>(`/api/semantic-dictionary${qs}`);
  },
  createDictionaryEntry(payload: ApiDictionaryEntryCreate) {
    return request<ApiDictionaryEntryRead>("/api/semantic-dictionary", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateDictionaryEntry(
    entryId: string,
    payload: Partial<ApiDictionaryEntryCreate>,
  ) {
    return request<ApiDictionaryEntryRead>(
      `/api/semantic-dictionary/${entryId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },
  deleteDictionaryEntry(entryId: string) {
    return request<void>(`/api/semantic-dictionary/${entryId}`, {
      method: "DELETE",
    });
  },
  importDictionaryFromSchema(payload: {
    database_id?: string;
    database_label: string;
    tables: Array<{
      name: string;
      columns: Array<{ name: string; type: string }>;
    }>;
    max_entries?: number;
  }) {
    return request<{ imported: number }>(
      "/api/semantic-dictionary/import-schema",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  getNotebook(notebookId: string) {
    return request<ApiNotebookDetail>(`/api/notebooks/${notebookId}`);
  },
  getNotebooks() {
    return request<ApiNotebookRead[]>("/api/notebooks");
  },
  getQueryTemplates() {
    return request<ApiQueryTemplate[]>("/api/query-templates");
  },
  getReports() {
    return request<ApiReportRead[]>("/api/reports");
  },
  getSchema() {
    return request<ApiSchemaMetadataResponse>("/api/metadata/schema");
  },
  getSemanticCatalog(databaseId: string, refresh = false) {
    const params = new URLSearchParams({
      database_id: databaseId,
    });
    if (refresh) {
      params.set("refresh", "true");
    }
    return request<ApiSemanticCatalog>(
      `/api/metadata/semantic-catalog?${params.toString()}`,
    );
  },
  activateSemanticCatalog(payload: ApiSemanticCatalogActivationRequest) {
    return request<ApiSemanticCatalog>(
      "/api/metadata/semantic-catalog/activate",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  getLlmModels() {
    return request<ApiLlmModelAliasesResponse>("/api/metadata/llm-models");
  },
  getKnowledge(databaseId: string) {
    return request<ApiKnowledgeSummary>(
      `/api/databases/${databaseId}/knowledge`,
    );
  },
  getKnowledgeTable(tableId: string) {
    return request<ApiKnowledgeTable>(`/api/tables/${tableId}`);
  },
  runKnowledgeFullScan(databaseId: string) {
    return request<ApiKnowledgeScanRun>(
      `/api/db-connections/${databaseId}/scan/full`,
      {
        method: "POST",
      },
    );
  },
  runKnowledgeIncrementalScan(databaseId: string) {
    return request<ApiKnowledgeScanRun>(
      `/api/db-connections/${databaseId}/scan/incremental`,
      {
        method: "POST",
      },
    );
  },
  getKnowledgeScanRuns(databaseId: string) {
    return request<ApiKnowledgeScanRun[]>(
      `/api/db-connections/${databaseId}/scan-runs`,
    );
  },
  updateKnowledgeTable(
    tableId: string,
    payload: {
      description_manual?: string | null;
      business_meaning_manual?: string | null;
      domain_manual?: string | null;
      semantic_label_manual?: string | null;
      semantic_table_role_manual?: string | null;
      semantic_grain_manual?: string | null;
      semantic_main_date_column_manual?: string | null;
      semantic_main_entity_manual?: string | null;
      semantic_synonyms?: string[] | null;
      semantic_important_metrics?: string[] | null;
      semantic_important_dimensions?: string[] | null;
      tags?: string[] | null;
      sensitivity?: string | null;
    },
  ) {
    return request<ApiKnowledgeTable>(`/api/tables/${tableId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  updateKnowledgeColumn(
    columnId: string,
    payload: {
      description_manual?: string | null;
      semantic_label_manual?: string | null;
      synonyms?: string[] | null;
      sensitivity?: string | null;
      hidden_for_llm?: boolean | null;
    },
  ) {
    return request<ApiKnowledgeTable>(`/api/columns/${columnId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  updateKnowledgeRelationship(
    relationshipId: string,
    payload: {
      cardinality?: string | null;
      confidence?: number | null;
      approved?: boolean | null;
      is_disabled?: boolean | null;
      description_manual?: string | null;
    },
  ) {
    return request<ApiKnowledgeTable>(`/api/relationships/${relationshipId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  getERD(databaseId: string) {
    return request<ApiERDGraph>(`/api/databases/${databaseId}/erd`);
  },
  getWorkspaces() {
    return request<ApiWorkspaceRead[]>("/api/workspaces");
  },
  runAll(notebookId: string) {
    return request<ApiPromptRunResponse[]>(
      `/api/notebooks/${notebookId}/run-all`,
      {
        method: "POST",
      },
    );
  },
  runPrompt(
    notebookId: string,
    prompt: string,
    queryMode: ApiQueryMode = "fast",
  ) {
    return request<ApiPromptRunResponse>(
      `/api/notebooks/${notebookId}/prompt-runs`,
      {
        method: "POST",
        body: JSON.stringify({ prompt, query_mode: queryMode }),
      },
    );
  },
  updateNotebook(
    notebookId: string,
    payload: { title?: string; status?: string },
  ) {
    return request<ApiNotebookRead>(`/api/notebooks/${notebookId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // --- Widgets ---
  listWidgets() {
    return request<ApiWidgetRead[]>("/api/widgets");
  },
  createWidget(payload: ApiWidgetCreate) {
    return request<ApiWidgetDetail>("/api/widgets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getWidget(widgetId: string) {
    return request<ApiWidgetDetail>(`/api/widgets/${widgetId}`);
  },
  updateWidget(widgetId: string, payload: ApiWidgetUpdate) {
    return request<ApiWidgetDetail>(`/api/widgets/${widgetId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteWidget(widgetId: string) {
    return request<void>(`/api/widgets/${widgetId}`, { method: "DELETE" });
  },
  runWidget(widgetId: string) {
    return request<ApiWidgetDetail>(`/api/widgets/${widgetId}/run`, {
      method: "POST",
    });
  },

  // --- Dashboards ---
  listDashboards(includeHidden = false) {
    const params = new URLSearchParams();
    if (includeHidden) {
      params.set("include_hidden", "true");
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<ApiDashboardRead[]>(`/api/dashboards${suffix}`);
  },
  createDashboard(payload: ApiDashboardCreate) {
    return request<ApiDashboardDetail>("/api/dashboards", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getDashboard(dashboardId: string) {
    return request<ApiDashboardDetail>(`/api/dashboards/${dashboardId}`);
  },
  updateDashboard(dashboardId: string, payload: ApiDashboardUpdate) {
    return request<ApiDashboardDetail>(`/api/dashboards/${dashboardId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteDashboard(dashboardId: string) {
    return request<void>(`/api/dashboards/${dashboardId}`, {
      method: "DELETE",
    });
  },
  addWidgetToDashboard(dashboardId: string, payload: ApiDashboardWidgetAdd) {
    return request<ApiDashboardWidgetDetail>(
      `/api/dashboards/${dashboardId}/widgets`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  updateDashboardWidget(
    dashboardId: string,
    dwId: string,
    payload: ApiDashboardWidgetPatch,
  ) {
    return request<ApiDashboardWidgetDetail>(
      `/api/dashboards/${dashboardId}/widgets/${dwId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },
  removeWidgetFromDashboard(dashboardId: string, dwId: string) {
    return request<void>(`/api/dashboards/${dashboardId}/widgets/${dwId}`, {
      method: "DELETE",
    });
  },
  getDashboardSchedule(dashboardId: string) {
    return request<ApiDashboardScheduleRead>(
      `/api/dashboards/${dashboardId}/schedule`,
    );
  },
  upsertDashboardSchedule(
    dashboardId: string,
    payload: ApiDashboardScheduleUpsert,
  ) {
    return request<ApiDashboardScheduleRead>(
      `/api/dashboards/${dashboardId}/schedule`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },
  deleteDashboardSchedule(dashboardId: string) {
    return request<void>(`/api/dashboards/${dashboardId}/schedule`, {
      method: "DELETE",
    });
  },
  exportDashboardPdf(dashboardId: string) {
    return fetch(toUrl(`/api/dashboards/${dashboardId}/export/pdf`));
  },
  listDatasets() {
    return request<ApiDatasetRead[]>("/api/datasets");
  },
  getDataset(datasetId: string) {
    return request<ApiDatasetRead>(`/api/datasets/${datasetId}`);
  },
  updateDataset(datasetId: string, payload: ApiDatasetUpdate) {
    return request<ApiDatasetRead>(`/api/datasets/${datasetId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteDataset(datasetId: string) {
    return request<void>(`/api/datasets/${datasetId}`, {
      method: "DELETE",
    });
  },
  previewDataset(datasetId: string) {
    return request<ApiDatasetPreviewResponse>(`/api/datasets/${datasetId}/preview`);
  },
  refreshDataset(datasetId: string) {
    return request<ApiDatasetRead>(`/api/datasets/${datasetId}/refresh`, {
      method: "POST",
    });
  },
  recommendDatasetCharts(datasetId: string) {
    return request<ApiChartRecommendationRead[]>(`/api/datasets/${datasetId}/chart-recommendations`);
  },
  validateBiChart(datasetId: string, chartSpec: ApiBiChartSpec, filters: ApiBiFilterCondition[] = []) {
    return request<ApiChartValidationResponse>("/api/charts/validate", {
      method: "POST",
      body: JSON.stringify({ dataset_id: datasetId, chart_spec: chartSpec, filters }),
    });
  },
  previewBiChart(datasetId: string, chartSpec: ApiBiChartSpec, filters: ApiBiFilterCondition[] = []) {
    return request<ApiChartPreviewResponse>("/api/charts/preview", {
      method: "POST",
      body: JSON.stringify({ dataset_id: datasetId, chart_spec: chartSpec, filters }),
    });
  },
  saveBiChart(payload: {
    dataset_id: string;
    chart_spec: ApiBiChartSpec;
    title?: string | null;
    description?: string | null;
    run_immediately?: boolean;
  }) {
    return request<ApiChartSaveResponse>("/api/charts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  createQuickDashboard(datasetId: string, payload: { title?: string | null; max_widgets?: number }) {
    return request<ApiQuickDashboardResponse>(`/api/datasets/${datasetId}/quick-dashboard`, {
      method: "POST",
      body: JSON.stringify({ dataset_id: datasetId, ...payload }),
    });
  },
};
