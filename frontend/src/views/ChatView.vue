<template>
  <main class="chat-view">
    <div class="chat-view__grid">
      <ChatSidebar
        :active-db-id="chat.activeDbId"
        :active-session-id="chat.activeSessionId"
        :databases="chat.databases"
        :loading="chat.loadingSessions || chat.loadingMessages"
        :sessions="chat.sessions"
        @create-session="createSession"
        @delete-session="deleteSession"
        @rename-session="renameSession"
        @select-database="selectDatabase"
        @select-session="selectSession"
      />

      <section class="chat-view__panel chat-view__panel--center">
        <ChatSqlEditor
          :busy="chat.generating || chat.executing"
          :model-value="chat.sqlDraft"
          :status="editorStatus"
          @run="runSql"
          @update:modelValue="updateSqlDraft"
        />
        <ChatResultPanel
          :execution="chat.executionResult"
          :view="chat.resultView"
          @change-view="chat.setResultMode"
        />
      </section>

      <section class="chat-view__panel chat-view__panel--chat">
        <ChatAssistant
          :busy="chat.generating"
          :messages="chat.messages"
          :query-mode="chat.queryMode ?? 'fast'"
          :llm-model-alias="chat.llmModelAlias ?? 'gpt120'"
          :llm-model-aliases="chat.llmModelAliases?.length ? chat.llmModelAliases : ['gpt120']"
          @apply-sql="applySql"
          @clarification="sendClarification"
          @set-llm-model-alias="chat.setLlmModelAlias"
          @set-query-mode="chat.setQueryMode"
          @send="sendMessage"
        />
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import ChatAssistant from '@/components/chat/ChatAssistant.vue';
import ChatResultPanel from '@/components/chat/ChatResultPanel.vue';
import ChatSidebar from '@/components/chat/ChatSidebar.vue';
import ChatSqlEditor from '@/components/chat/ChatSqlEditor.vue';
import { useChatStore } from '@/stores/chat';

const chat = useChatStore();

const editorStatus = computed<'idle' | 'executing' | 'error' | 'generating'>(() => {
  if (chat.executing) {
    return 'executing';
  }
  if (chat.generating) {
    return 'generating';
  }
  if (chat.errorMessage) {
    return 'error';
  }
  return 'idle';
});

onMounted(() => {
  void chat.initialize().catch(() => {
    /* store already captures the error */
  });
});

function selectDatabase(databaseId: string) {
  void chat.selectDatabase(databaseId);
}

function selectSession(sessionId: string) {
  void chat.selectSession(sessionId);
}

function createSession() {
  void chat.createSession();
}

function renameSession(sessionId: string, title: string) {
  void chat.renameSession(sessionId, title);
}

function deleteSession(sessionId: string) {
  void chat.deleteSession(sessionId);
}

function sendMessage(text: string, mode: 'fast' | 'thinking') {
  chat.setQueryMode(mode);
  void chat.sendMessage(text);
}

function sendClarification(answer: string) {
  void chat.sendMessage(answer);
}

function runSql() {
  void chat.runSql();
}

function updateSqlDraft(value: string) {
  chat.updateSqlDraft(value);
}

function applySql(sql: string) {
  chat.applyAssistantSqlDraft(sql, chat.sqlDraftVersion);
}
</script>

<style scoped lang="scss">
.chat-view {
  padding: 16px;
  background: var(--bg);
  flex: 1;
  min-height: 0;
}

.chat-view__grid {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr) minmax(300px, 360px);
  gap: 16px;
  min-height: 0;
  flex: 1;
  height: 100%;
}

.chat-view__panel {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 12px;
}

.chat-view__panel--center {
  display: grid;
  grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.chat-view__panel--chat {
  display: flex;
  min-height: 0;
}

.chat-view__panel--chat :deep(.chat-assistant) {
  width: 100%;
  min-height: 0;
}

@media (max-width: 1260px) {
  .chat-view__grid {
    grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
    grid-template-rows: auto auto;
  }

  .chat-view__panel--center {
    grid-column: 2;
  }

  .chat-view__panel--chat {
    grid-column: 1 / -1;
    min-height: 380px;
  }
}

@media (max-width: 940px) {
  .chat-view {
    padding: 12px;
  }

  .chat-view__grid {
    grid-template-columns: 1fr;
  }

  .chat-view__panel--center,
  .chat-view__panel--chat {
    grid-column: auto;
  }
}
</style>
