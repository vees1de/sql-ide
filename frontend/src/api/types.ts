export interface ApiWorkspaceRead {
  id: string;
  name: string;
  databases: string[];
  created_at: string;
  updated_at: string;
}

export type ApiQueryMode = 'fast' | 'thinking';

export interface ApiLlmModelAlias {
  alias: string;
  model: string;
}

export interface ApiLlmModelAliasesResponse {
  aliases: ApiLlmModelAlias[];
  default_alias: string;
  current_alias: string;
}

export interface ApiChatDateRange {
  kind: string;
  start?: string | null;
  end?: string | null;
  lookback_value?: number | null;
  lookback_unit?: string | null;
}

export interface ApiChatFilterCondition {
  field: string;
  operator: string;
  value: unknown;
}

export interface ApiChatInterpretation {
  metric: string | null;
  dimensions: string[];
  date_range: ApiChatDateRange | null;
  filters: ApiChatFilterCondition[];
  comparison: string | null;
  ambiguities: string[];
  confidence: number;
}

export interface ApiChatTableUsage {
  table: string;
  reason: string;
}

export interface ApiChatClarificationOption {
  id: string;
  label: string;
  detail: string;
}

export interface ApiChatStructuredPayload {
  interpretation: ApiChatInterpretation;
  tables_used: ApiChatTableUsage[];
  sql: string | null;
  warnings: string[];
  needs_clarification: boolean;
  clarification_question: string | null;
  clarification_options: ApiChatClarificationOption[] | null;
  dialect: string;
  query_mode: ApiQueryMode;
  llm_model_alias?: string | null;
  complexity: 'simple' | 'complex';
  mode_suggestion?: ApiQueryMode | null;
  mode_suggestion_reason?: string | null;
}

export interface ApiChatSessionRead {
  id: string;
  database_connection_id: string;
  title: string;
  current_sql_draft: string | null;
  sql_draft_version: number;
  last_executed_sql: string | null;
  last_intent_json: Record<string, unknown> | null;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiChatMessageRead {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  text: string;
  structured_payload: ApiChatStructuredPayload | null;
  created_at: string;
}

export interface ApiChatExecutionRecommendation {
  recommended_view: 'table' | 'chart';
  chart_type?: 'line' | 'bar' | 'stacked_bar' | 'pie' | null;
  x?: string | null;
  y?: string | null;
  series?: string | null;
  reason: string;
}

export interface ApiChatExecutionRead {
  id: string;
  session_id: string;
  sql_text: string;
  columns: Array<{ name: string; type: string }> | null;
  rows_preview: Array<Record<string, unknown>> | null;
  rows_preview_truncated: boolean;
  row_count: number;
  execution_time_ms: number;
  chart_recommendation: ApiChatExecutionRecommendation | null;
  error_message: string | null;
  created_at: string;
}

export interface ApiChatSessionDetail extends ApiChatSessionRead {
  messages: ApiChatMessageRead[];
  last_execution: ApiChatExecutionRead | null;
}

export interface ApiChatSessionCreate {
  title?: string | null;
}

export interface ApiChatSessionUpdate {
  title?: string | null;
  archived?: boolean | null;
}

export interface ApiChatMessageCreate {
  text: string;
  query_mode?: ApiQueryMode;
  llm_model_alias?: string | null;
}

export interface ApiChatSqlDraftUpdate {
  sql: string;
  expected_version: number;
}

export interface ApiChatExecuteRequest {
  sql: string;
}

export interface ApiChatSendMessageResponse {
  session: ApiChatSessionRead;
  user_message: ApiChatMessageRead;
  assistant_message: ApiChatMessageRead;
  sql_draft: string | null;
  sql_draft_version: number;
}

export interface ApiChatExecuteResponse {
  session: ApiChatSessionRead;
  execution: ApiChatExecutionRead;
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
  knowledge_status?: string | null;
  last_scan_at?: string | null;
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

export interface ApiSchemaRelationship {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relation_type: string;
  cardinality?: string | null;
}

export interface ApiSchemaMetadataResponse {
  database_id: string;
  dialect: string;
  tables: ApiTableMetadata[];
  relationships: ApiSchemaRelationship[];
}

export interface ApiKnowledgeScanRun {
  id: string;
  database_id: string;
  database_label: string;
  dialect: string;
  scan_type: string;
  status: string;
  stage: string;
  summary: Record<string, unknown>;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
}

export interface ApiKnowledgeColumn {
  id: string;
  database_id: string;
  table_id: string;
  schema_name: string;
  table_name: string;
  column_name: string;
  data_type: string;
  ordinal_position: number;
  is_nullable: boolean;
  default_value?: string | null;
  status: string;
  distinct_count?: number | null;
  null_ratio?: number | null;
  min_value?: string | null;
  max_value?: string | null;
  sample_values: string[];
  semantic_label_auto?: string | null;
  semantic_label_manual?: string | null;
  description_auto?: string | null;
  description_manual?: string | null;
  synonyms: string[];
  sensitivity?: string | null;
  hidden_for_llm: boolean;
}

export interface ApiKnowledgeRelationship {
  id: string;
  database_id: string;
  from_schema_name: string;
  from_table_name: string;
  from_column_name: string;
  to_schema_name: string;
  to_table_name: string;
  to_column_name: string;
  relation_type: string;
  cardinality?: string | null;
  confidence: number;
  approved: boolean;
  is_disabled: boolean;
  description_manual?: string | null;
  status: string;
}

export interface ApiKnowledgeTable {
  id: string;
  database_id: string;
  schema_name: string;
  table_name: string;
  object_type: string;
  status: string;
  column_count: number;
  row_count?: number | null;
  primary_key: string[];
  description_auto?: string | null;
  description_manual?: string | null;
  business_meaning_auto?: string | null;
  business_meaning_manual?: string | null;
  domain_auto?: string | null;
  domain_manual?: string | null;
  tags: string[];
  sensitivity?: string | null;
  usage_score?: number | null;
  columns?: ApiKnowledgeColumn[];
  relationships?: ApiKnowledgeRelationship[];
}

export interface ApiKnowledgeSummary {
  database_id: string;
  database_label: string;
  dialect: string;
  status: string;
  active_table_count: number;
  active_column_count: number;
  active_relationship_count: number;
  last_scan?: ApiKnowledgeScanRun | null;
  tables: ApiKnowledgeTable[];
}

export interface ApiERDNode {
  id: string;
  label: string;
  schema_name: string;
  table_name: string;
  column_count: number;
  row_count?: number | null;
  tags: string[];
}

export interface ApiERDEdge {
  id: string;
  source: string;
  target: string;
  source_label: string;
  target_label: string;
  relation_type: string;
  confidence: number;
  cardinality?: string | null;
}

export interface ApiERDGraph {
  database_id: string;
  nodes: ApiERDNode[];
  edges: ApiERDEdge[];
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

export interface ApiNotebookCellRunRequest {
  query_mode?: ApiQueryMode;
  llm_model_alias?: string | null;
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
