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
  confidence_level?: 'low' | 'medium' | 'high';
  confidence_reasons?: string[];
  debug_trace?: Array<{
    stage: string;
    status: 'success' | 'warning' | 'error' | 'info';
    code?: string | null;
    detail: string;
  }>;
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
  chart_type?: 'line' | 'bar' | 'stacked_bar' | 'pie' | 'metric_card' | null;
  x?: string | null;
  y?: string | null;
  series?: string | null;
  facet?: string | null;
  variant?: string | null;
  explanation?: string | null;
  rule_id?: string | null;
  confidence?: number | null;
  data?: Record<string, unknown> | null;
  reason: string;
  semantic_intent?: string | null;
  analysis_mode?: string | null;
  visual_goal?: string | null;
  time_role?: string | null;
  comparison_goal?: string | null;
  preferred_mark?: string | null;
  normalize?: string | null;
  value_format?: string | null;
  series_limit?: number | null;
  category_limit?: number | null;
  top_n_strategy?: string | null;
  alternatives?: string[] | null;
  candidates?: Array<{ type: string; score: number; why: string }> | null;
  constraints_applied?: string[] | null;
  visual_load?: number | null;
  query_interpretation?: {
    user_goal: string;
    intent?: string | null;
    analysis_mode?: string | null;
    entities?: string[];
    metrics?: Array<{ name: string; aggregation?: string | null; format?: string | null }>;
    dimensions?: Array<{ name: string; role?: string | null }>;
    time_dimension?: string | null;
    series_dimension?: string | null;
    requested_output?: 'chart' | 'table' | 'stat';
    assumptions?: string[];
    ambiguities?: string[];
    confidence?: number;
    short_explanation?: string | null;
  } | null;
  decision_summary?: {
    selected_chart: string;
    why: string;
    reason_codes?: string[];
    alternatives?: Array<{ type: string; why_not: string }>;
    confidence?: number;
  } | null;
  reason_codes?: string[] | null;
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
  is_builtin: boolean;
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

export interface ApiDatabaseConnectionUpdate {
  name?: string | null;
  description?: string | null;
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

export interface ApiSchemaRelationshipGraphEdge {
  from_table: string;
  to_table: string;
  on: string;
}

export interface ApiSchemaMetadataResponse {
  database_id: string;
  dialect: string;
  tables: ApiTableMetadata[];
  relationships: ApiSchemaRelationship[];
  relationship_graph: ApiSchemaRelationshipGraphEdge[];
}

export interface ApiSemanticCatalogActivationRequest {
  database_id: string;
  refresh?: boolean;
  database_description?: string | null;
  table_descriptions?: Array<{
    table_name: string;
    business_description: string;
  }>;
  relationship_descriptions?: Array<{
    from_table: string;
    from_column: string;
    to_table: string;
    to_column: string;
    business_meaning: string;
  }>;
  column_descriptions?: Array<{
    table_name: string;
    column_name: string;
    business_description: string;
  }>;
}

export interface ApiSemanticTablePatch {
  label?: string | null;
  business_description?: string | null;
  table_role?: 'fact' | 'dimension' | 'bridge' | 'lookup' | 'event' | 'snapshot' | null;
  grain?: string | null;
  main_date_column?: string | null;
  main_entity?: string | null;
  synonyms?: string[] | null;
  important_metrics?: string[] | null;
  important_dimensions?: string[] | null;
}

export interface ApiSemanticColumnPatch {
  label?: string | null;
  business_description?: string | null;
  semantic_types?: string[] | null;
  analytics_roles?: string[] | null;
  synonyms?: string[] | null;
  groupable?: boolean | null;
  filterable?: boolean | null;
}

export interface ApiSemanticColumnProfile {
  distinct_count?: number | null;
  null_ratio?: number | null;
  min_value?: string | null;
  max_value?: string | null;
  avg_length?: number | null;
  top_values: unknown[];
  uniqueness_ratio?: number | null;
  numeric_mean?: number | null;
  numeric_min?: number | null;
  numeric_max?: number | null;
}

export interface ApiSemanticColumn {
  schema_name: string;
  table_name: string;
  column_name: string;
  label: string;
  business_description: string;
  semantic_types: string[];
  analytics_roles: string[];
  value_type?: string | null;
  aggregation: string[];
  filterable: boolean;
  groupable: boolean;
  sortable: boolean;
  synonyms: string[];
  example_values: unknown[];
  data_type: string;
  nullable: boolean;
  default_value?: string | null;
  max_length?: number | null;
  ordinal_position: number;
  is_pk: boolean;
  is_fk: boolean;
  referenced_table?: string | null;
  referenced_column?: string | null;
  comment?: string | null;
  profile: ApiSemanticColumnProfile;
}

export interface ApiSemanticRelationship {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relationship_type: string;
  join_type: string;
  business_meaning: string;
  join_priority: string;
  confidence: number;
  path_id?: string | null;
}

export interface ApiSemanticJoinPath {
  path_id: string;
  from_table: string;
  to_table: string;
  joins: string[];
  business_use_case: string;
  tables: string[];
}

export interface ApiSemanticRelationshipGraphEdge {
  from_table: string;
  to_table: string;
  on: string;
}

export interface ApiSemanticTable {
  schema_name: string;
  table_name: string;
  label: string;
  business_description: string;
  table_role: 'fact' | 'dimension' | 'bridge' | 'lookup' | 'event' | 'snapshot';
  grain?: string | null;
  main_date_column?: string | null;
  main_entity?: string | null;
  synonyms: string[];
  important_metrics: string[];
  important_dimensions: string[];
  row_count_estimate?: number | null;
  primary_key: string[];
  indexes: Array<Record<string, unknown>>;
  comment?: string | null;
  columns: ApiSemanticColumn[];
  relationships: ApiSemanticRelationship[];
  join_paths: ApiSemanticJoinPath[];
}

export interface ApiSemanticCatalog {
  database_id: string;
  dialect: string;
  tables: ApiSemanticTable[];
  relationships: ApiSemanticRelationship[];
  join_paths: ApiSemanticJoinPath[];
  relationship_graph: ApiSemanticRelationshipGraphEdge[];
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

// ---------------------------------------------------------------------------
// Widgets
// ---------------------------------------------------------------------------

export type ApiVisualizationType = 'table' | 'line' | 'bar' | 'area' | 'pie' | 'metric' | 'stacked_bar' | 'text';
export type ApiRefreshPolicy = 'manual' | 'on_view' | 'scheduled';
export type ApiWidgetSourceType = 'sql' | 'text_to_sql' | 'text';

export interface ApiWidgetRunRead {
  id: string;
  widget_id: string;
  status: string;
  columns: Array<{ name: string; type: string }> | null;
  rows_preview: Array<Record<string, unknown>> | null;
  rows_preview_truncated: boolean;
  row_count: number;
  execution_time_ms: number;
  error_text: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface ApiWidgetRead {
  id: string;
  title: string;
  description: string | null;
  source_type: ApiWidgetSourceType;
  source_query_run_id: string | null;
  sql_text: string;
  visualization_type: ApiVisualizationType;
  visualization_config: Record<string, unknown> | null;
  result_schema: Record<string, unknown> | null;
  refresh_policy: ApiRefreshPolicy;
  is_public: boolean;
  owner_id: string;
  database_connection_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiWidgetDetail extends ApiWidgetRead {
  last_run: ApiWidgetRunRead | null;
}

export interface ApiWidgetCreate {
  title: string;
  description?: string | null;
  source_type?: ApiWidgetSourceType;
  source_query_run_id?: string | null;
  sql_text?: string;
  visualization_type?: ApiVisualizationType;
  visualization_config?: Record<string, unknown> | null;
  refresh_policy?: ApiRefreshPolicy;
  is_public?: boolean;
  database_connection_id?: string | null;
}

export interface ApiWidgetUpdate {
  title?: string | null;
  description?: string | null;
  sql_text?: string | null;
  visualization_type?: ApiVisualizationType | null;
  visualization_config?: Record<string, unknown> | null;
  refresh_policy?: ApiRefreshPolicy | null;
  is_public?: boolean | null;
}

// ---------------------------------------------------------------------------
// Dashboards
// ---------------------------------------------------------------------------

export interface ApiDashboardWidgetLayout {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ApiDashboardWidgetRead {
  id: string;
  dashboard_id: string;
  widget_id: string;
  title_override: string | null;
  layout: ApiDashboardWidgetLayout;
  display_options: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ApiDashboardWidgetDetail extends ApiDashboardWidgetRead {
  widget: ApiWidgetRead;
}

export interface ApiDashboardRead {
  id: string;
  title: string;
  description: string | null;
  slug: string | null;
  layout_type: string;
  is_public: boolean;
  is_hidden: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ApiDashboardScheduleRead {
  id: string;
  dashboard_id: string;
  recipient_emails: string[];
  weekdays: string[];
  send_time: string;
  timezone: string;
  enabled: boolean;
  subject: string;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiDashboardDetail extends ApiDashboardRead {
  widgets: ApiDashboardWidgetDetail[];
  schedule: ApiDashboardScheduleRead | null;
}

export interface ApiDashboardWidgetCreateItem {
  widget_id: string;
  layout?: ApiDashboardWidgetLayout;
  title_override?: string | null;
}

export interface ApiDashboardCreate {
  title: string;
  description?: string | null;
  is_public?: boolean;
  widgets?: ApiDashboardWidgetCreateItem[];
}

export interface ApiDashboardUpdate {
  title?: string | null;
  description?: string | null;
  is_public?: boolean | null;
  is_hidden?: boolean | null;
  slug?: string | null;
}

export interface ApiDashboardWidgetAdd {
  widget_id: string;
  layout?: ApiDashboardWidgetLayout;
  title_override?: string | null;
}

export interface ApiDashboardWidgetPatch {
  layout?: ApiDashboardWidgetLayout | null;
  title_override?: string | null;
}

export interface ApiDashboardScheduleUpsert {
  recipient_emails: string[];
  weekdays: string[];
  send_time: string;
  timezone: string;
  enabled: boolean;
  subject: string;
}
