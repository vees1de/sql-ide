import type {
  ApiERDGraph,
  ApiCellRead,
  ApiDictionaryEntryCreate,
  ApiDatabaseConnectionCreate,
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
  ApiSchemaMetadataResponse,
  ApiWorkspaceRead
} from '@/api/types';

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

function toUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(toUrl(path), {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {})
    },
    ...options
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail || 'Request failed');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  previewDatabaseSchema(payload: ApiDatabaseConnectionCreate) {
    return request<ApiSchemaPreviewResponse>('/api/databases/preview-schema', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  createDatabase(payload: ApiDatabaseConnectionCreate) {
    return request<ApiDatabaseDescriptor>('/api/databases', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  updateDatabase(databaseId: string, payload: { allowed_tables: string[] | null }) {
    return request<ApiDatabaseDescriptor>(`/api/databases/${databaseId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },
  deleteDatabase(databaseId: string) {
    return request<void>(`/api/databases/${databaseId}`, {
      method: 'DELETE'
    });
  },
  createNotebook(payload: {
    workspace_id: string;
    title: string;
    database_id: string;
  }) {
    return request<ApiNotebookRead>('/api/notebooks', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  deleteNotebook(notebookId: string) {
    return request<void>(`/api/notebooks/${notebookId}`, {
      method: 'DELETE'
    });
  },
  createNotebookCell(notebookId: string, payload: ApiNotebookCellCreate) {
    return request<ApiCellRead>(`/api/notebooks/${notebookId}/cells`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  updateNotebookCell(notebookId: string, cellId: string, payload: ApiNotebookCellUpdate) {
    return request<ApiCellRead>(`/api/notebooks/${notebookId}/cells/${cellId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },
  runNotebookCell(notebookId: string, cellId: string, payload?: ApiNotebookCellRunRequest) {
    return request<ApiPromptRunResponse>(`/api/notebooks/${notebookId}/cells/${cellId}/run`, {
      method: 'POST',
      ...(payload ? { body: JSON.stringify(payload) } : {})
    });
  },
  formatNotebookSqlCell(notebookId: string, cellId: string) {
    return request<ApiCellRead>(`/api/notebooks/${notebookId}/cells/${cellId}/format-sql`, {
      method: 'POST'
    });
  },
  reorderNotebookCells(notebookId: string, payload: ApiNotebookCellReorder) {
    return request<ApiNotebookDetail>(`/api/notebooks/${notebookId}/cells/reorder`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  createReport(payload: {
    notebook_id: string;
    title: string;
    schedule?: string | null;
  }) {
    return request<ApiReportRead>('/api/reports', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  getDatabases() {
    return request<ApiDatabaseDescriptor[]>('/api/databases');
  },
  getDictionary() {
    return request<ApiDictionaryEntryRead[]>('/api/semantic-dictionary');
  },
  createDictionaryEntry(payload: ApiDictionaryEntryCreate) {
    return request<ApiDictionaryEntryRead>('/api/semantic-dictionary', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  updateDictionaryEntry(entryId: string, payload: Partial<ApiDictionaryEntryCreate>) {
    return request<ApiDictionaryEntryRead>(`/api/semantic-dictionary/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },
  deleteDictionaryEntry(entryId: string) {
    return request<void>(`/api/semantic-dictionary/${entryId}`, {
      method: 'DELETE'
    });
  },
  importDictionaryFromSchema(payload: {
    database_label: string;
    tables: Array<{ name: string; columns: Array<{ name: string; type: string }> }>;
    max_entries?: number;
  }) {
    return request<{ imported: number }>('/api/semantic-dictionary/import-schema', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  getNotebook(notebookId: string) {
    return request<ApiNotebookDetail>(`/api/notebooks/${notebookId}`);
  },
  getNotebooks() {
    return request<ApiNotebookRead[]>('/api/notebooks');
  },
  getQueryTemplates() {
    return request<ApiQueryTemplate[]>('/api/query-templates');
  },
  getReports() {
    return request<ApiReportRead[]>('/api/reports');
  },
  getSchema() {
    return request<ApiSchemaMetadataResponse>('/api/metadata/schema');
  },
  getLlmModels() {
    return request<ApiLlmModelAliasesResponse>('/api/metadata/llm-models');
  },
  getKnowledge(databaseId: string) {
    return request<ApiKnowledgeSummary>(`/api/databases/${databaseId}/knowledge`);
  },
  getKnowledgeTable(tableId: string) {
    return request<ApiKnowledgeTable>(`/api/tables/${tableId}`);
  },
  runKnowledgeFullScan(databaseId: string) {
    return request<ApiKnowledgeScanRun>(`/api/db-connections/${databaseId}/scan/full`, {
      method: 'POST'
    });
  },
  runKnowledgeIncrementalScan(databaseId: string) {
    return request<ApiKnowledgeScanRun>(`/api/db-connections/${databaseId}/scan/incremental`, {
      method: 'POST'
    });
  },
  getKnowledgeScanRuns(databaseId: string) {
    return request<ApiKnowledgeScanRun[]>(`/api/db-connections/${databaseId}/scan-runs`);
  },
  updateKnowledgeTable(
    tableId: string,
    payload: {
      description_manual?: string | null;
      business_meaning_manual?: string | null;
      domain_manual?: string | null;
      tags?: string[] | null;
      sensitivity?: string | null;
    }
  ) {
    return request<ApiKnowledgeTable>(`/api/tables/${tableId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
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
    }
  ) {
    return request<ApiKnowledgeTable>(`/api/columns/${columnId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
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
    }
  ) {
    return request<ApiKnowledgeTable>(`/api/relationships/${relationshipId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },
  getERD(databaseId: string) {
    return request<ApiERDGraph>(`/api/databases/${databaseId}/erd`);
  },
  getWorkspaces() {
    return request<ApiWorkspaceRead[]>('/api/workspaces');
  },
  runAll(notebookId: string) {
    return request<ApiPromptRunResponse[]>(`/api/notebooks/${notebookId}/run-all`, {
      method: 'POST'
    });
  },
  runPrompt(notebookId: string, prompt: string, queryMode: ApiQueryMode = 'fast') {
    return request<ApiPromptRunResponse>(`/api/notebooks/${notebookId}/prompt-runs`, {
      method: 'POST',
      body: JSON.stringify({ prompt, query_mode: queryMode })
    });
  },
  updateNotebook(notebookId: string, payload: { title?: string; status?: string }) {
    return request<ApiNotebookRead>(`/api/notebooks/${notebookId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  }
};
