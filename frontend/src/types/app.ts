export type CellType =
  | 'prompt'
  | 'sql'
  | 'table'
  | 'chart'
  | 'insight'
  | 'clarification';

export type QueryMode = 'fast' | 'thinking';

export interface PromptCellContent {
  prompt: string;
  queryMode?: QueryMode;
  llmModelAlias?: string;
  chips?: string[];
  context?: string[];
}

export interface SqlCellContent {
  sql: string;
  explanation: string;
  mode?: 'editable' | 'generated';
  queryMode?: QueryMode;
  llmModelAlias?: string;
  warnings?: string[];
}

export interface TableCellContent {
  columns: string[];
  rows: Array<Record<string, string | number>>;
  footnote?: string;
}

export interface ChartCellContent {
  chartType: 'line' | 'bar' | 'pie';
  title: string;
  subtitle?: string;
  xAxis?: string[];
  series?: Array<{
    name: string;
    data: number[];
  }>;
  pieData?: Array<{
    name: string;
    value: number;
  }>;
  unit?: string;
  palette?: string[];
  stacked?: boolean;
}

export interface InsightCellContent {
  headline: string;
  bullets: string[];
}

export interface ClarificationCellContent {
  question: string;
  options: Array<{
    id: string;
    label: string;
    detail: string;
  }>;
  recommended: string;
}

export type NotebookCellContent =
  | PromptCellContent
  | SqlCellContent
  | TableCellContent
  | ChartCellContent
  | InsightCellContent
  | ClarificationCellContent;

export interface CellMeta {
  confidence: number;
  executionTimeMs?: number;
  rowCount?: number;
  tablesUsed: string[];
  warnings: string[];
  businessTerms: string[];
  summary: string;
}

export interface NotebookCell {
  id: string;
  type: CellType;
  order: number;
  title: string;
  subtitle: string;
  agent: string;
  tone: 'accent' | 'neutral' | 'success' | 'warning';
  content: NotebookCellContent;
  meta: CellMeta;
  queryRunId?: string | null;
  sourceCellId?: string | null;
  runStatus?: string | null;
}

export interface NotebookQueryBlock {
  id: string;
  inputCell: NotebookCell;
  sqlCell?: NotebookCell;
  tableCell?: NotebookCell;
  chartCell?: NotebookCell;
  insightCell?: NotebookCell;
  clarificationCell?: NotebookCell;
  otherCells: NotebookCell[];
}

export interface NotebookConversationTurn {
  id: string;
  order: number;
  cellIds: string[];
  prompt: NotebookCell | null;
  sqlCell?: NotebookCell;
  tableCell?: NotebookCell;
  chartCell?: NotebookCell;
  insightCell?: NotebookCell;
  clarificationCell?: NotebookCell;
  otherCells: NotebookCell[];
}

export interface NotebookTraceStep {
  agent: string;
  purpose: string;
  output: string;
  confidence: number;
  latencyMs: number;
  warnings?: string[];
}

export interface NotebookSummary {
  objective: string;
  lastRunLabel: string;
  highlight: string;
  owner: string;
}

export interface Notebook {
  id: string;
  title: string;
  databaseId: string;
  createdAt: string;
  updatedAt: string;
  status: 'draft' | 'saved';
  summary: NotebookSummary;
  trace: NotebookTraceStep[];
  cells: NotebookCell[];
}

export interface DatabaseConnection {
  id: string;
  name: string;
  engine: string;
  mode: string;
  tables: number;
  schemas: string[];
  status: 'connected' | 'syncing';
  knowledgeStatus?: 'not_scanned' | 'queued' | 'running' | 'completed' | 'failed' | string;
  lastScanAt?: string;
  isDemo?: boolean;
  /** Whitelist таблиц для доступа; null — не ограничено отдельно (все из интроспекции при импорте). */
  allowedTables?: string[] | null;
}

export interface SavedReport {
  id: string;
  title: string;
  notebookId: string;
  createdAt: string;
  schedule?: string;
}

export interface QueryTemplate {
  id: string;
  title: string;
  description: string;
}

export interface DictionaryTerm {
  id: string;
  term: string;
  synonyms: string[];
  mappedExpression: string;
  description: string;
}

export interface HistoryItem {
  id: string;
  label: string;
  timestamp: string;
}

export interface WorkspaceData {
  id: string;
  name: string;
  tagline: string;
  databases: DatabaseConnection[];
  notebooks: Notebook[];
  reports: SavedReport[];
  templates: QueryTemplate[];
  dictionary: DictionaryTerm[];
  history: HistoryItem[];
}
