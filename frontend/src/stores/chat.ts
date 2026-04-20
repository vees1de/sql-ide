import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { chatApi } from '@/api/chat';
import type {
  ApiChatExecutionRead,
  ApiChatMessageRead,
  ApiChatSessionDetail,
  ApiChatSessionRead,
  ApiDatabaseDescriptor
} from '@/api/types';

const emptyExecution: ApiChatExecutionRead | null = null;

export const useChatStore = defineStore('chat', () => {
  const databases = ref<ApiDatabaseDescriptor[]>([]);
  const sessions = ref<ApiChatSessionRead[]>([]);
  const messages = ref<ApiChatMessageRead[]>([]);
  const sqlDraft = ref('');
  const sqlDraftVersion = ref(0);
  const executionResult = ref<ApiChatExecutionRead | null>(emptyExecution);
  const resultView = ref<'table' | 'chart'>('table');
  const autoApplySql = ref(true);
  const activeDbId = ref('');
  const activeSessionId = ref('');
  const lastSyncedSqlDraft = ref('');
  const generating = ref(false);
  const executing = ref(false);
  const loadingSessions = ref(false);
  const loadingMessages = ref(false);
  const errorMessage = ref<string | null>(null);
  const statusLabel = ref('Чат готов');

  let draftSaveTimer: number | null = null;

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
    resultView.value = execution?.chart_recommendation?.recommended_view ?? 'table';
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

  async function initialize() {
    await loadDatabases();
    if (activeDbId.value) {
      await loadSessions(activeDbId.value);
    }
  }

  async function createSession(databaseId = activeDbId.value) {
    if (!databaseId) {
      throw new Error('База данных не выбрана.');
    }

    const session = await chatApi.createSession(databaseId);
    activeDbId.value = databaseId;
    syncSession(session);
    activeSessionId.value = session.id;
    messages.value = [];
    setSessionDraft(session.current_sql_draft, session.sql_draft_version);
    setSessionResult(null);
    setStatus('Новый чат создан');
    return session.id;
  }

  async function selectDatabase(databaseId: string) {
    if (!databaseId || databaseId === activeDbId.value) {
      return;
    }
    activeDbId.value = databaseId;
    activeSessionId.value = '';
    messages.value = [];
    setSessionDraft('', 0);
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
      setSessionDraft(detail.current_sql_draft, detail.sql_draft_version);
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

    if (activeSessionId.value === sessionId) {
      activeSessionId.value = '';
      messages.value = [];
      setSessionDraft('', 0);
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
    setError(null);
    setStatus('Генерирую SQL');
    try {
      const response = await chatApi.sendMessage(session.id, { text });
      syncSession(response.session);
      messages.value = [...messages.value, response.user_message, response.assistant_message];
      if (response.sql_draft) {
        applyAssistantSqlDraft(response.sql_draft, response.sql_draft_version);
      } else {
        sqlDraftVersion.value = response.sql_draft_version;
      }
      setSessionResult(null);
      if (response.assistant_message.structured_payload?.needs_clarification) {
        setStatus('Нужно уточнение');
      } else if (response.sql_draft) {
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

  function setResultMode(view: 'table' | 'chart') {
    resultView.value = view;
  }

  function setAutoApplySql(next: boolean) {
    autoApplySql.value = next;
  }

  function clearExecutionResult() {
    setSessionResult(null);
  }

  return {
    activeDbId,
    activeSessionId,
    applyAssistantSqlDraft,
    autoApplySql,
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
    loadSessions,
    messages,
    sessions,
    renameSession,
    resultView,
    runSql,
    selectDatabase,
    selectSession,
    sendMessage,
    setAutoApplySql,
    setError,
    setResultMode,
    setStatus,
    statusLabel,
    sqlDraft,
    sqlDraftVersion,
    updateSqlDraft,
    errorMessage
  };
});
