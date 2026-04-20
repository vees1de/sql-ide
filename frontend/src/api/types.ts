export interface ApiWorkspaceRead {
  id: string;
  name: string;
  databases: string[];
  created_at: string;
  updated_at: string;
}

export interface ApiDatabaseDescriptor {
  id: string;
  name: string;
  dialect: string;
  description: string;
  read_only: boolean;
  is_demo: boolean;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  username?: string | null;
  table_count?: number;
  status?: string;
  allowed_tables?: string[] | null;
  dictionary_entries_imported?: number | null;
}

export interface ApiDatabaseConnectionCreate {
  name: string;
  dialect?: string;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  username?: string | null;
  password?: string | null;
  description?: string;
  read_only?: boolean;
  table_count?: number;
  import_schema_to_dictionary?: boolean;
  allowed_tables?: string[] | null;
}

export interface ApiSchemaPreviewTable {
  name: string;
  columns: string[];
}

export interface ApiSchemaPreviewResponse {
  tables: ApiSchemaPreviewTable[];
  table_names: string[];
}

export interface ApiColumnMetadata {
  name: string;
  type: string;
}

export interface ApiTableMetadata {
  name: string;
  columns: ApiColumnMetadata[];
}

export interface ApiSchemaMetadataResponse {
  database_id: string;
  dialect: string;
  tables: ApiTableMetadata[];
}

export interface ApiNotebookRead {
  id: string;
  workspace_id: string;
  title: string;
  database_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ApiCellRead {
  id: string;
  notebook_id: string;
  query_run_id: string | null;
  type: string;
  position: number;
  content: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApiNotebookCellCreate {
  type: 'prompt' | 'sql';
  content: Record<string, unknown>;
}

export interface ApiNotebookCellUpdate {
  content: Record<string, unknown>;
}

export interface ApiNotebookCellReorder {
  ordered_cell_ids: string[];
}

export interface ApiQueryRunRead {
  id: string;
  notebook_id: string;
  prompt_cell_id: string;
  prompt_text: string;
  sql: string;
  explanation: Record<string, unknown>;
  agent_trace: Record<string, unknown>;
  confidence: number;
  execution_time_ms: number;
  row_count: number;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface ApiNotebookDetail extends ApiNotebookRead {
  cells: ApiCellRead[];
  query_runs: ApiQueryRunRead[];
}

export interface ApiReportRead {
  id: string;
  notebook_id: string;
  title: string;
  schedule: string | null;
  created_at: string;
}

export interface ApiDictionaryEntryRead {
  id: string;
  term: string;
  synonyms: string[];
  mapped_expression: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ApiDictionaryEntryCreate {
  term: string;
  synonyms: string[];
  mapped_expression: string;
  description?: string;
  object_type?: string | null;
  table_name?: string | null;
  column_name?: string | null;
  source_database?: string | null;
}

export interface ApiQueryTemplate {
  id: string;
  title: string;
  prompt: string;
}

export interface ApiPromptRunResponse {
  notebook_id: string;
  query_run_id: string;
  prompt_cell_id: string;
  generated_cell_ids: string[];
  status: string;
}
