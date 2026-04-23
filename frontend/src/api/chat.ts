import { request } from '@/api/client';
import type {
  ApiChatChartSuggestionRequest,
  ApiChatClarificationAnswerRequest,
  ApiChatExecuteRequest,
  ApiChatExecuteResponse,
  ApiChatExecutionRead,
  ApiChatMessageCreate,
  ApiChatRunPreparedSqlRequest,
  ApiChatSendMessageResponse,
  ApiChatSessionCreate,
  ApiChatSessionDetail,
  ApiChatSessionRead,
  ApiChatSessionUpdate,
  ApiChatSqlDraftUpdate,
  ApiDatabaseDescriptor,
  ApiLlmModelAliasesResponse
} from '@/api/types';

export const chatApi = {
  getDatabases() {
    return request<ApiDatabaseDescriptor[]>('/api/chat/databases');
  },

  getLlmModels() {
    return request<ApiLlmModelAliasesResponse>('/api/metadata/llm-models');
  },

  getSessions(databaseId: string) {
    return request<ApiChatSessionRead[]>(`/api/chat/databases/${databaseId}/sessions`);
  },

  createSession(databaseId: string, payload?: ApiChatSessionCreate) {
    return request<ApiChatSessionRead>(`/api/chat/databases/${databaseId}/sessions`, {
      method: 'POST',
      body: JSON.stringify(payload ?? {})
    });
  },

  getSession(sessionId: string) {
    return request<ApiChatSessionDetail>(`/api/chat/sessions/${sessionId}`);
  },

  updateSession(sessionId: string, payload: ApiChatSessionUpdate) {
    return request<ApiChatSessionRead>(`/api/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },

  deleteSession(sessionId: string) {
    return request<void>(`/api/chat/sessions/${sessionId}`, {
      method: 'DELETE'
    });
  },

  sendMessage(sessionId: string, payload: ApiChatMessageCreate) {
    return request<ApiChatSendMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  answerClarification(sessionId: string, clarificationId: string, payload: ApiChatClarificationAnswerRequest) {
    return request<ApiChatSendMessageResponse>(
      `/api/chat/sessions/${sessionId}/clarifications/${clarificationId}/answer`,
      {
        method: 'POST',
        body: JSON.stringify(payload)
      }
    );
  },

  updateSqlDraft(sessionId: string, payload: ApiChatSqlDraftUpdate) {
    return request<ApiChatSessionRead>(`/api/chat/sessions/${sessionId}/sql-draft`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },

  executeSql(sessionId: string, payload: ApiChatExecuteRequest) {
    return request<ApiChatExecuteResponse>(`/api/chat/sessions/${sessionId}/execute`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  runPreparedSql(sessionId: string, payload?: ApiChatRunPreparedSqlRequest) {
    return request<ApiChatExecuteResponse>(`/api/chat/sessions/${sessionId}/actions/run-sql`, {
      method: 'POST',
      ...(payload ? { body: JSON.stringify(payload) } : {})
    });
  },

  suggestChart(sessionId: string, executionId: string, payload?: ApiChatChartSuggestionRequest) {
    return request<ApiChatExecutionRead>(
      `/api/chat/sessions/${sessionId}/executions/${executionId}/chart-suggestion`,
      {
        method: 'POST',
        body: JSON.stringify(payload ?? {})
      }
    );
  }
};
