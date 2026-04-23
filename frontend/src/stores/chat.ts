import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { chatApi } from '@/api/chat';
import type {
  ApiChatAction,
  ApiChatExecutionRead,
  ApiChatMessageRead,
  ApiChatSemanticParse,
  ApiChatAgentState,
  ApiQueryMode,
  ApiChatSessionDetail,
  ApiChatSessionRead,
  ApiDatabaseDescriptor
} from '@/api/types';

const emptyExecution: ApiChatExecutionRead | null = null;

export const useChatStore = defineStore('chat', () => {
  const defaultSessionTitle = 'Новый чат';
  const databases = ref<ApiDatabaseDescriptor[]>([]);
  const sessions = ref<ApiChatSessionRead[]>([]);
  const messages = ref<ApiChatMessageRead[]>([]);
  const sqlDraft = ref('');
  const sqlDraftVersion = ref(0);
  const preparedSql = ref<string | null>(null);
  const state = ref<ApiChatAgentState>('SQL_DRAFTING');
  const assistantActions = ref<ApiChatAction[]>([]);
  const semanticParse = ref<ApiChatSemanticParse | null>(null);
  const executionResult = ref<ApiChatExecutionRead | null>(emptyExecution);
  const resultView = ref<'table' | 'chart'>('table');
  const queryMode = ref<ApiQueryMode>('fast');
  const llmModelAliases = ref<string[]>([]);
  const llmModelAlias = ref('gpt120');
  const activeDbId = ref('');
  const activeSessionId = ref('');
  const lastSyncedSqlDraft = ref('');
  const pendingUserMessage = ref('');
  const generating = ref(false);
  const executing = ref(false);
  const suggestingChart = ref(false);
  const loadingSessions = ref(false);
  const loadingMessages = ref(false);
  const errorMessage = ref<string | null>(null);
  const statusLabel = ref('Чат готов');

  let draftSaveTimer: number | null = null;
  const pendingSessionCreates = new Map<string, Promise<string>>();

  const currentDatabase = computed(
    () => databases.value.find((database) => database.id === activeDbId.value) ?? null
  );

  const currentSession = computed(
    () => sessions.value.find((session) => session.id === activeSessionId.value) ?? null
  );

  function setStatus(value: string) {
    statusLabel.value = value;
  }

  function setError(value: string | null) {
    errorMessage.value = value;
  }

  function clearDraftTimer() {
    if (draftSaveTimer !== null) {
      window.clearTimeout(draftSaveTimer);
      draftSaveTimer = null;
    }
  }

  function syncSession(session: ApiChatSessionRead) {
    const index = sessions.value.findIndex((item) => item.id === session.id);
    if (index >= 0) {
      sessions.value[index] = session;
    } else {
      sessions.value = [session, ...sessions.value];
    }
  }

  function setSessionDraft(sql: string | null | undefined, version: number) {
    sqlDraft.value = sql ?? '';
    preparedSql.value = sqlDraft.value || null;
    lastSyncedSqlDraft.value = sqlDraft.value;
    sqlDraftVersion.value = version;
    clearDraftTimer();
    const session = currentSession.value;
    if (session) {
      const index = sessions.value.findIndex((item) => item.id === session.id);
      if (index >= 0) {
        sessions.value[index] = {
          ...sessions.value[index],
          current_sql_draft: sql ?? '',
          sql_draft_version: version
        };
      }
    }
  }

  function setSessionResult(execution: ApiChatExecutionRead | null) {
    executionResult.value = execution;
    const aiChartType = execution?.chart_recommendation?.ai_chart_spec?.chart_type;
    if (aiChartType && aiChartType !== 'table') {
      resultView.value = 'chart';
      return;
    }
    resultView.value = execution?.chart_recommendation?.recommended_view ?? 'table';
  }

  function applyAssistantState(message: ApiChatMessageRead | null) {
    const payload = message?.structured_payload;
    state.value = payload?.state ?? 'SQL_DRAFTING';
    assistantActions.value = payload?.actions ?? [];
    semanticParse.value = payload?.semantic_parse ?? null;
    preparedSql.value = payload?.sql ?? currentSession.value?.current_sql_draft ?? null;
  }

  async function loadDatabases() {
    try {
      databases.value = await chatApi.getDatabases();
      if (!databases.value.length) {
        activeDbId.value = '';
        sessions.value = [];
        messages.value = [];
        sqlDraft.value = '';
        sqlDraftVersion.value = 0;
        preparedSql.value = null;
        state.value = 'SQL_DRAFTING';
        assistantActions.value = [];
        semanticParse.value = null;
        pendingUserMessage.value = '';
        setSessionResult(null);
        return;
      }

      if (!activeDbId.value || !databases.value.some((database) => database.id === activeDbId.value)) {
        activeDbId.value = databases.value[0]?.id ?? '';
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось загрузить базы данных.');
      throw error;
    }
  }

  async function loadSessions(databaseId = activeDbId.value) {
    if (!databaseId) {
      return;
    }

    loadingSessions.value = true;
    try {
      sessions.value = await chatApi.getSessions(databaseId);
      activeDbId.value = databaseId;

      if (!sessions.value.length) {
        await createSession(databaseId);
        return;
      }

      if (!activeSessionId.value || !sessions.value.some((session) => session.id === activeSessionId.value)) {
        await selectSession(sessions.value[0]?.id ?? '');
        return;
      }

      await selectSession(activeSessionId.value);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось загрузить чаты.');
      throw error;
    } finally {
      loadingSessions.value = false;
    }
  }

  async function loadLlmModels() {
    try {
      const payload = await chatApi.getLlmModels();
      const fetchedAliases = payload.aliases
        .map((item) => item.alias.trim())
        .filter(Boolean);
      const candidateDefault = payload.default_alias?.trim() || llmModelAlias.value || 'gpt120';
      const candidateCurrent = payload.current_alias?.trim() || candidateDefault;
      const nextAliases = fetchedAliases.length ? fetchedAliases : [candidateDefault];
      llmModelAliases.value = nextAliases;
      llmModelAlias.value = nextAliases.includes(candidateCurrent)
        ? candidateCurrent
        : nextAliases[0];
    } catch {
      if (!llmModelAliases.value.length) {
        llmModelAliases.value = [llmModelAlias.value || 'gpt120'];
      }
      llmModelAlias.value = llmModelAliases.value[0];
    }
  }

  async function initialize() {
    await loadLlmModels();
    await loadDatabases();
    if (activeDbId.value) {
      await loadSessions(activeDbId.value);
    }
  }

  async function createSession(databaseId = activeDbId.value) {
    if (!databaseId) {
      throw new Error('База данных не выбрана.');
    }

    const pendingCreate = pendingSessionCreates.get(databaseId);
    if (pendingCreate) {
      return pendingCreate;
    }

    const createPromise = (async () => {
      const session = await chatApi.createSession(databaseId);
      if (databaseId !== activeDbId.value) {
        sessions.value = [];
      }
      activeDbId.value = databaseId;
      syncSession(session);
      activeSessionId.value = session.id;
      messages.value = [];
      setSessionDraft(session.current_sql_draft, session.sql_draft_version);
      applyAssistantState(null);
      setSessionResult(null);
      pendingUserMessage.value = '';
      setStatus(session.title === defaultSessionTitle ? 'Пустой чат открыт' : 'Новый чат создан');
      return session.id;
    })();

    pendingSessionCreates.set(databaseId, createPromise);
    try {
      return await createPromise;
    } finally {
      pendingSessionCreates.delete(databaseId);
    }
  }

  async function selectDatabase(databaseId: string) {
    if (!databaseId || databaseId === activeDbId.value) {
      return;
    }
    activeDbId.value = databaseId;
    activeSessionId.value = '';
    messages.value = [];
    pendingUserMessage.value = '';
    setSessionDraft('', 0);
    applyAssistantState(null);
    setSessionResult(null);
    await loadSessions(databaseId);
  }

  async function selectSession(sessionId: string) {
    if (!sessionId) {
      return;
    }

    loadingMessages.value = true;
    try {
      activeSessionId.value = sessionId;
      const detail = await chatApi.getSession(sessionId);
      activeDbId.value = detail.database_connection_id;
      syncSession(detail);
      messages.value = detail.messages;
      pendingUserMessage.value = '';
      setSessionDraft(detail.current_sql_draft, detail.sql_draft_version);
      applyAssistantState(
        [...detail.messages].reverse().find((message) => message.role === 'assistant') ?? null
      );
      setSessionResult(detail.last_execution);
      setStatus(detail.title || 'Чат готов');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось открыть чат.');
      throw error;
    } finally {
      loadingMessages.value = false;
    }
  }

  async function renameSession(sessionId: string, title: string) {
    const session = await chatApi.updateSession(sessionId, { title });
    syncSession(session);
    if (activeSessionId.value === sessionId) {
      setStatus(session.title);
    }
  }

  async function deleteSession(sessionId: string) {
    await chatApi.deleteSession(sessionId);
    const nextSessions = sessions.value.filter((session) => session.id !== sessionId);
    sessions.value = nextSessions;
    pendingUserMessage.value = '';

    if (activeSessionId.value === sessionId) {
      activeSessionId.value = '';
      messages.value = [];
      setSessionDraft('', 0);
      applyAssistantState(null);
      setSessionResult(null);
      if (nextSessions.length) {
        await selectSession(nextSessions[0].id);
      } else if (activeDbId.value) {
        await createSession(activeDbId.value);
      }
    }
  }

  async function flushSqlDraftSave() {
    clearDraftTimer();
    const session = currentSession.value;
    if (!session) {
      return;
    }

    if (lastSyncedSqlDraft.value === sqlDraft.value) {
      return;
    }

    try {
      const updated = await chatApi.updateSqlDraft(session.id, {
        sql: sqlDraft.value,
        expected_version: sqlDraftVersion.value
      });
      syncSession(updated);
      setSessionDraft(updated.current_sql_draft, updated.sql_draft_version);
      setStatus('SQL-черновик сохранён');
    } catch (error) {
      if (error instanceof Error && error.message.toLowerCase().includes('version')) {
        await selectSession(session.id);
        setError('SQL-черновик был изменён на сервере. Загружена свежая версия.');
        return;
      }
      setError(error instanceof Error ? error.message : 'Не удалось сохранить SQL-черновик.');
      throw error;
    }
  }

  function updateSqlDraft(nextSql: string) {
    sqlDraft.value = nextSql;
    preparedSql.value = nextSql.trim() ? nextSql : null;

    clearDraftTimer();
    draftSaveTimer = window.setTimeout(() => {
      void flushSqlDraftSave();
    }, 500);
  }

  function applyAssistantSqlDraft(sql: string | null | undefined, version?: number) {
    if (!sql) {
      return;
    }
    sqlDraft.value = sql;
    preparedSql.value = sql;
    lastSyncedSqlDraft.value = sql;
    if (typeof version === 'number') {
      sqlDraftVersion.value = version;
    }
    const session = currentSession.value;
    if (session) {
      const index = sessions.value.findIndex((item) => item.id === session.id);
      if (index >= 0) {
        sessions.value[index] = {
          ...sessions.value[index],
          current_sql_draft: sql,
          sql_draft_version: typeof version === 'number' ? version : sessions.value[index].sql_draft_version
        };
      }
    }
  }

  async function sendMessage(text: string) {
    const mode = queryMode.value;
    if (!text.trim()) {
      return;
    }

    if (!currentSession.value) {
      if (!activeDbId.value) {
        await loadDatabases();
      }
      if (!activeSessionId.value) {
        await createSession(activeDbId.value);
      }
    }

    await flushSqlDraftSave();
    const session = currentSession.value;
    if (!session) {
      throw new Error('Сессия чата не выбрана.');
    }

    generating.value = true;
    pendingUserMessage.value = text;
    setError(null);
    setStatus(mode === 'thinking' ? 'Генерирую SQL (Thinking)' : 'Генерирую SQL (Fast)');
    try {
      const response = await chatApi.sendMessage(session.id, {
        text,
        query_mode: mode,
        llm_model_alias: llmModelAlias.value
      });
      syncSession(response.session);
      messages.value = [...messages.value, response.user_message, response.assistant_message];
      applyAssistantState(response.assistant_message);
      if (response.sql_draft) {
        applyAssistantSqlDraft(response.sql_draft, response.sql_draft_version);
      } else {
        preparedSql.value = response.assistant_message.structured_payload?.sql ?? null;
        sqlDraftVersion.value = response.sql_draft_version;
      }
      setSessionResult(null);
      if (response.assistant_message.structured_payload?.state === 'CLARIFYING' || response.assistant_message.structured_payload?.needs_clarification) {
        setStatus('Нужно уточнение');
      } else if (response.assistant_message.structured_payload?.state === 'SQL_READY' || response.sql_draft) {
        setStatus('SQL готов');
      } else {
        setStatus('Ответ получен');
      }
      return response;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось отправить сообщение.');
      throw error;
    } finally {
      generating.value = false;
      pendingUserMessage.value = '';
    }
  }

  async function answerClarification(clarificationId: string, selectedOptionId?: string | null, textAnswer?: string | null) {
    if (!currentSession.value) {
      throw new Error('Сессия чата не выбрана.');
    }

    generating.value = true;
    setError(null);
    setStatus('Обрабатываю уточнение');
    try {
      const response = await chatApi.answerClarification(currentSession.value.id, clarificationId, {
        selected_option_id: selectedOptionId ?? null,
        text_answer: textAnswer ?? null
      });
      syncSession(response.session);
      messages.value = [...messages.value, response.user_message, response.assistant_message];
      applyAssistantState(response.assistant_message);
      if (response.sql_draft) {
        applyAssistantSqlDraft(response.sql_draft, response.sql_draft_version);
      } else {
        setSessionDraft('', response.sql_draft_version);
      }
      setSessionResult(null);
      if (response.assistant_message.structured_payload?.state === 'CLARIFYING') {
        setStatus('Нужно дополнительное уточнение');
      } else if (response.assistant_message.structured_payload?.state === 'SQL_READY') {
        setStatus('SQL готов');
      } else {
        setStatus('Ответ получен');
      }
      return response;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось обработать уточнение.');
      throw error;
    } finally {
      generating.value = false;
    }
  }

  async function runSql() {
    if (!currentSession.value) {
      throw new Error('Сессия чата не выбрана.');
    }

    await flushSqlDraftSave();
    const sql = sqlDraft.value.trim();
    if (!sql) {
      throw new Error('SQL пустой.');
    }

    executing.value = true;
    setError(null);
    setStatus('Выполняю SQL');
    try {
      const response = await chatApi.executeSql(currentSession.value.id, { sql });
      syncSession(response.session);
      setSessionResult(response.execution);
      setStatus(response.execution.error_message ? 'Выполнение завершилось с ошибкой' : 'Запрос выполнен');
      return response;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось выполнить SQL.');
      throw error;
    } finally {
      executing.value = false;
    }
  }

  async function runPreparedSql() {
    if (!currentSession.value) {
      throw new Error('Сессия чата не выбрана.');
    }

    await flushSqlDraftSave();
    executing.value = true;
    setError(null);
    setStatus('Выполняю подготовленный SQL');
    try {
      const response = await chatApi.runPreparedSql(currentSession.value.id, preparedSql.value ? { sql: preparedSql.value } : undefined);
      syncSession(response.session);
      setSessionResult(response.execution);
      setStatus(response.execution.error_message ? 'Выполнение завершилось с ошибкой' : 'Запрос выполнен');
      return response;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось выполнить подготовленный SQL.');
      throw error;
    } finally {
      executing.value = false;
    }
  }

  async function suggestChart(goal: 'best_chart' | 'explain_visualization' | 'dashboard_ready' = 'best_chart') {
    if (!currentSession.value || !executionResult.value?.id) {
      throw new Error('Нет результата SQL для AI-подсказки.');
    }

    suggestingChart.value = true;
    setError(null);
    setStatus('Получаю AI-подсказку для графика');
    try {
      const execution = await chatApi.suggestChart(currentSession.value.id, executionResult.value.id, { goal });
      setSessionResult(execution);
      if (execution.chart_recommendation?.ai_chart_spec?.chart_type && execution.chart_recommendation.ai_chart_spec.chart_type !== 'table') {
        resultView.value = 'chart';
      }
      setStatus('AI-подсказка готова');
      return execution;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось получить AI-подсказку.');
      throw error;
    } finally {
      suggestingChart.value = false;
    }
  }

  function setResultMode(view: 'table' | 'chart') {
    resultView.value = view;
  }

  function setQueryMode(mode: ApiQueryMode) {
    if (mode !== 'fast' && mode !== 'thinking') {
      return;
    }
    queryMode.value = mode;
  }

  function setLlmModelAlias(alias: string) {
    const nextAlias = alias?.trim();
    if (!nextAlias) {
      return;
    }
    llmModelAlias.value = nextAlias;
    if (!llmModelAliases.value.includes(nextAlias)) {
      llmModelAliases.value = [nextAlias, ...llmModelAliases.value];
    }
  }

  function clearExecutionResult() {
    setSessionResult(null);
  }

  return {
    activeDbId,
    activeSessionId,
    applyAssistantSqlDraft,
    answerClarification,
    assistantActions,
    clearExecutionResult,
    createSession,
    currentDatabase,
    currentSession,
    databases,
    deleteSession,
    executing,
    executionResult,
    flushSqlDraftSave,
    generating,
    initialize,
    loadingMessages,
    loadingSessions,
    loadDatabases,
    llmModelAlias,
    llmModelAliases,
    pendingUserMessage,
    preparedSql,
    loadSessions,
    messages,
    queryMode,
    runPreparedSql,
    sessions,
    semanticParse,
    renameSession,
    resultView,
    runSql,
    suggestChart,
    selectDatabase,
    selectSession,
    sendMessage,
    setError,
    setLlmModelAlias,
    setResultMode,
    state,
    setStatus,
    setQueryMode,
    statusLabel,
    sqlDraft,
    sqlDraftVersion,
    suggestingChart,
    updateSqlDraft,
    errorMessage
  };
});
