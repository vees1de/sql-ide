import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/api/client';
import { buildWorkspaceData } from '@/api/mappers';
import type {
  ClarificationCellContent,
  DatabaseConnection,
  Notebook,
  NotebookTraceStep,
  WorkspaceData
} from '@/types/app';

function augmentPromptWithClarifications(
  notebook: Notebook,
  prompt: string,
  answers: Record<string, string>
): string {
  const prefixes: string[] = [];
  for (const [cellId, optionId] of Object.entries(answers)) {
    const cell = notebook.cells.find((c) => c.id === cellId);
    if (!cell || cell.type !== 'clarification') {
      continue;
    }
    const content = cell.content as ClarificationCellContent;
    const option = content.options.find((item) => item.id === optionId);
    if (option) {
      prefixes.push(`[Уточнение: ${option.label}]`);
    }
  }
  if (!prefixes.length) {
    return prompt;
  }
  return `${prefixes.join('\n')}\n\n${prompt}`;
}

const emptyDatabase: DatabaseConnection = {
  id: 'unconfigured',
  name: 'No database',
  engine: 'Unknown',
  mode: 'read-only',
  tables: 0,
  schemas: [],
  status: 'syncing'
};

const emptyWorkspace: WorkspaceData = {
  id: 'workspace',
  name: 'AI Analytics Notebook',
  tagline: 'Backend connection is loading',
  databases: [],
  notebooks: [],
  reports: [],
  templates: [],
  dictionary: [],
  history: []
};

export const useWorkspaceStore = defineStore('workspace', () => {
  const workspace = ref<WorkspaceData>(emptyWorkspace);
  const selectedNotebookId = ref('');
  const selectedCellId = ref('');
  const visibleCellCount = ref(0);
  const isRunning = ref(false);
  const isBootstrapping = ref(false);
  const isSubmittingPrompt = ref(false);
  const isSavingReport = ref(false);
  const initialized = ref(false);
  const statusLabel = ref('Connecting backend');
  const banner = ref('Connecting frontend to backend API.');
  const errorMessage = ref<string | null>(null);
  const draftPrompt = ref('');
  const clarificationAnswers = ref<Record<string, string>>({});
  const activePipelineIndex = ref(0);

  let loadPromise: Promise<void> | null = null;

  const currentNotebook = computed(
    () =>
      workspace.value.notebooks.find(
        (notebook) => notebook.id === selectedNotebookId.value
      ) ?? null
  );

  const currentDatabase = computed(
    () =>
      workspace.value.databases.find(
        (database) => database.id === currentNotebook.value?.databaseId
      ) ??
      workspace.value.databases[0] ??
      emptyDatabase
  );

  const selectedCell = computed(
    () =>
      currentNotebook.value?.cells.find((cell) => cell.id === selectedCellId.value) ??
      currentNotebook.value?.cells[0] ??
      null
  );

  const visibleCells = computed(() =>
    currentNotebook.value?.cells.slice(0, visibleCellCount.value) ?? []
  );

  const canSubmitPrompt = computed(
    () => !!currentNotebook.value && draftPrompt.value.trim().length > 0 && !isSubmittingPrompt.value
  );

  function setBanner(message: string) {
    banner.value = message;
  }

  function syncNotebookSelection(preferredNotebookId?: string, cellStrategy: 'first' | 'last' | 'keep' = 'keep') {
    const notebooks = workspace.value.notebooks;
    const targetId =
      (preferredNotebookId &&
        notebooks.some((notebook) => notebook.id === preferredNotebookId) &&
        preferredNotebookId) ||
      (selectedNotebookId.value &&
        notebooks.some((notebook) => notebook.id === selectedNotebookId.value) &&
        selectedNotebookId.value) ||
      notebooks[0]?.id ||
      '';

    selectedNotebookId.value = targetId;

    const notebook = notebooks.find((item) => item.id === targetId) ?? null;
    visibleCellCount.value = notebook?.cells.length ?? 0;

    if (!notebook) {
      selectedCellId.value = '';
      activePipelineIndex.value = 0;
      statusLabel.value = 'Create your first notebook';
      return;
    }

    if (cellStrategy === 'last') {
      selectedCellId.value = notebook.cells[notebook.cells.length - 1]?.id ?? '';
    } else if (cellStrategy === 'first') {
      selectedCellId.value = notebook.cells[0]?.id ?? '';
    } else if (!notebook.cells.some((cell) => cell.id === selectedCellId.value)) {
      selectedCellId.value = notebook.cells[0]?.id ?? '';
    }

    activePipelineIndex.value = Math.max(notebook.trace.length - 1, 0);
    statusLabel.value = notebook.cells.length
      ? 'Notebook ready'
      : 'Notebook is empty. Add a prompt to begin.';
  }

  function syncAgentStateFromCell() {
    if (!selectedCell.value || !currentNotebook.value) {
      activePipelineIndex.value = Math.max(currentNotebook.value?.trace.length ?? 1, 1) - 1;
      return;
    }

    const pipelineIndex = currentNotebook.value.trace.findIndex(
      (step) => step.agent === selectedCell.value?.agent
    );

    activePipelineIndex.value =
      pipelineIndex >= 0 ? pipelineIndex : Math.max(currentNotebook.value.trace.length - 1, 0);
    statusLabel.value = `${selectedCell.value.agent} · ${selectedCell.value.subtitle}`;
  }

  async function loadWorkspace(preferredNotebookId?: string, force = false) {
    if (loadPromise && !force) {
      await loadPromise;
      return;
    }

    loadPromise = (async () => {
      isBootstrapping.value = true;
      errorMessage.value = null;
      if (!initialized.value) {
        statusLabel.value = 'Loading workspace';
      }

      try {
        const [
          workspaces,
          databases,
          reports,
          dictionary,
          templates,
          schema,
          notebookSummaries
        ] = await Promise.all([
          api.getWorkspaces(),
          api.getDatabases(),
          api.getReports(),
          api.getDictionary(),
          api.getQueryTemplates(),
          api.getSchema().catch(() => null),
          api.getNotebooks()
        ]);

        const notebookDetails = await Promise.all(
          notebookSummaries.map((notebook) => api.getNotebook(notebook.id))
        );

        workspace.value = buildWorkspaceData({
          workspace: workspaces[0] ?? null,
          databases,
          reports,
          dictionary,
          templates,
          schema,
          notebookDetails
        });

        initialized.value = true;
        syncNotebookSelection(preferredNotebookId, preferredNotebookId ? 'last' : 'keep');
        syncAgentStateFromCell();
        setBanner(
          workspace.value.notebooks.length
            ? `Loaded ${workspace.value.notebooks.length} notebook(s) from backend API.`
            : 'Backend is connected. Create a notebook to start exploring data.'
        );
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load workspace data.';
        errorMessage.value = message;
        statusLabel.value = 'Backend unavailable';
        setBanner(message);
      } finally {
        isBootstrapping.value = false;
      }
    })();

    try {
      await loadPromise;
    } finally {
      loadPromise = null;
    }
  }

  async function ensureInitialized(preferredNotebookId?: string) {
    if (!initialized.value) {
      await loadWorkspace(preferredNotebookId);
    }
  }

  async function refreshWorkspace(preferredNotebookId?: string, cellStrategy: 'first' | 'last' | 'keep' = 'keep') {
    await loadWorkspace(preferredNotebookId, true);
    syncNotebookSelection(preferredNotebookId, cellStrategy);
    syncAgentStateFromCell();
  }

  async function selectNotebook(id: string) {
    await ensureInitialized(id);
    selectedNotebookId.value = id;
    draftPrompt.value = '';
    syncNotebookSelection(id, 'first');
    syncAgentStateFromCell();
    setBanner(`Opened notebook “${currentNotebook.value?.title ?? id}”.`);
  }

  function selectCell(id: string) {
    selectedCellId.value = id;
    syncAgentStateFromCell();
  }

  async function renameCurrentNotebook(title: string) {
    const notebook = currentNotebook.value;
    const trimmedTitle = title.trim();
    if (!notebook || !trimmedTitle || trimmedTitle === notebook.title) {
      return;
    }

    statusLabel.value = 'Saving notebook title';
    await api.updateNotebook(notebook.id, { title: trimmedTitle });
    notebook.title = trimmedTitle;
    notebook.updatedAt = new Date().toISOString();
    setBanner(`Notebook renamed to “${trimmedTitle}”.`);
  }

  async function createNotebook(databaseId?: string) {
    await ensureInitialized();

    const targetDb =
      (databaseId && workspace.value.databases.find((db) => db.id === databaseId)) ||
      currentDatabase.value;

    if (!workspace.value.id || !targetDb?.id || targetDb.id === emptyDatabase.id) {
      throw new Error('Workspace or database is not ready yet.');
    }

    statusLabel.value = 'Creating notebook';
    const created = await api.createNotebook({
      workspace_id: workspace.value.id,
      title: 'New AI Notebook',
      database_id: targetDb.id
    });
    await refreshWorkspace(created.id, 'first');
    setBanner(`Created notebook “${created.title}”.`);
    return created.id;
  }

  async function runCurrentNotebook() {
    const notebook = currentNotebook.value;
    if (!notebook) {
      return;
    }

    isRunning.value = true;
    statusLabel.value = 'Running notebook';
    setBanner(`Running all prompt cells in “${notebook.title}”.`);

    try {
      await api.runAll(notebook.id);
      await refreshWorkspace(notebook.id, 'last');
      setBanner(`Run completed for “${currentNotebook.value?.title ?? notebook.title}”.`);
    } finally {
      isRunning.value = false;
    }
  }

  async function submitPrompt(promptText?: string) {
    const notebook = currentNotebook.value;
    const prompt = (promptText ?? draftPrompt.value).trim();
    if (!notebook || !prompt) {
      return;
    }

    isSubmittingPrompt.value = true;
    statusLabel.value = 'Running prompt';
    setBanner(`Submitting prompt to “${notebook.title}”.`);

    try {
      const finalPrompt = augmentPromptWithClarifications(
        notebook,
        prompt,
        clarificationAnswers.value
      );
      await api.runPrompt(notebook.id, finalPrompt);
      draftPrompt.value = '';
      clarificationAnswers.value = {};
      await refreshWorkspace(notebook.id, 'last');
      setBanner('Prompt processed and notebook updated from backend.');
    } finally {
      isSubmittingPrompt.value = false;
    }
  }

  async function saveCurrentReport() {
    const notebook = currentNotebook.value;
    if (!notebook) {
      return;
    }

    const reportTitle = `${notebook.title} Report`;
    if (workspace.value.reports.some((report) => report.title === reportTitle)) {
      setBanner(`Report “${reportTitle}” already exists.`);
      return;
    }

    isSavingReport.value = true;
    statusLabel.value = 'Saving report';

    try {
      await api.createReport({
        notebook_id: notebook.id,
        title: reportTitle,
        schedule: 'Manual save'
      });
      await refreshWorkspace(notebook.id, 'keep');
      setBanner(`Saved report “${reportTitle}”.`);
    } finally {
      isSavingReport.value = false;
    }
  }

  function shareCurrentNotebook() {
    const notebook = currentNotebook.value;
    if (!notebook) {
      return;
    }

    const url = `${window.location.origin}/notebooks/${notebook.id}`;
    statusLabel.value = 'Share link ready';
    setBanner(`Share URL: ${url}`);
  }

  function updateDraftPrompt(value: string) {
    draftPrompt.value = value;
  }

  function answerClarification(cellId: string, optionId: string) {
    clarificationAnswers.value = { ...clarificationAnswers.value, [cellId]: optionId };
    statusLabel.value = 'Уточнение сохранено';
    setBanner(
      'Выбор учтён. Отправьте следующий запрос (например: «используй вариант выше» или уточните метрику).'
    );
  }

  async function connectDatabase(payload: {
    name: string;
    engine?: string;
    host?: string;
    port?: string | number;
    database?: string;
    user?: string;
    password?: string;
    tables?: number;
    importSchemaToDictionary?: boolean;
    allowedTables?: string[] | null;
  }) {
    statusLabel.value = 'Connecting database';
    setBanner(`Подключение к «${payload.name}»…`);

    const portNumber =
      typeof payload.port === 'number'
        ? payload.port
        : payload.port
          ? Number.parseInt(String(payload.port), 10) || null
          : null;

    try {
      const created = await api.createDatabase({
        name: payload.name,
        dialect: (payload.engine ?? 'postgresql').toLowerCase(),
        host: payload.host ?? null,
        port: portNumber ?? null,
        database: payload.database ?? null,
        username: payload.user ?? null,
        password: payload.password ?? null,
        table_count: payload.tables ?? 0,
        import_schema_to_dictionary: Boolean(payload.importSchemaToDictionary),
        allowed_tables: payload.allowedTables ?? null
      });
      await refreshWorkspace(selectedNotebookId.value || undefined, 'keep');
      const dictPart =
        typeof created.dictionary_entries_imported === 'number' && created.dictionary_entries_imported > 0
          ? ` В Dictionary добавлено ${created.dictionary_entries_imported} терминов.`
          : '';
      const message =
        created.status === 'syncing'
          ? `База «${created.name}» сохранена, но подключение не удалось проверить.`
          : `База «${created.name}» подключена.${dictPart}`;
      setBanner(message);
      return created;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Не удалось добавить базу данных.';
      setBanner(message);
      throw error;
    }
  }

  async function deleteDatabase(databaseId: string) {
    statusLabel.value = 'Deleting database';
    try {
      await api.deleteDatabase(databaseId);
      await refreshWorkspace(selectedNotebookId.value || undefined, 'keep');
      setBanner('База удалена.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Не удалось удалить базу данных.';
      setBanner(message);
      throw error;
    }
  }

  async function deleteNotebook(notebookId: string) {
    statusLabel.value = 'Deleting notebook';
    try {
      await api.deleteNotebook(notebookId);
      const remaining = workspace.value.notebooks.filter((item) => item.id !== notebookId);
      const fallback = remaining[0]?.id;
      await refreshWorkspace(fallback, 'first');
      setBanner('Notebook удалён.');
      return fallback ?? '';
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Не удалось удалить notebook.';
      setBanner(message);
      throw error;
    }
  }

  function traceStatus(step: NotebookTraceStep, index: number) {
    if (isRunning.value || isSubmittingPrompt.value) {
      if (index < activePipelineIndex.value) {
        return 'completed';
      }
      if (index === activePipelineIndex.value) {
        return 'running';
      }
      return 'pending';
    }

    return index <= activePipelineIndex.value ? 'completed' : 'pending';
  }

  return {
    activePipelineIndex,
    answerClarification,
    banner,
    canSubmitPrompt,
    clarificationAnswers,
    connectDatabase,
    createNotebook,
    deleteDatabase,
    deleteNotebook,
    currentDatabase,
    currentNotebook,
    draftPrompt,
    ensureInitialized,
    errorMessage,
    initialized,
    isBootstrapping,
    isRunning,
    isSavingReport,
    isSubmittingPrompt,
    loadWorkspace,
    refreshWorkspace,
    renameCurrentNotebook,
    runCurrentNotebook,
    saveCurrentReport,
    selectedCell,
    selectedCellId,
    selectedNotebookId,
    selectCell,
    selectNotebook,
    shareCurrentNotebook,
    statusLabel,
    submitPrompt,
    traceStatus,
    updateDraftPrompt,
    visibleCells,
    visibleCellCount,
    workspace
  };
});
