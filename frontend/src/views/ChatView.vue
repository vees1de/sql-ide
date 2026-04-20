<template>
  <main class="chat-view">
    <header class="chat-view__header">
      <div>
        <p class="eyebrow">Chat</p>
        <h1>Прозрачный text-to-SQL</h1>
        <p class="chat-view__lead">
          Выберите базу, задайте вопрос по-русски, получите SQL и объяснение. Запуск всегда вручную.
        </p>
      </div>
      <div class="chat-view__meta">
        <span class="pill pill--ghost">{{ currentDatabase?.name ?? 'База не выбрана' }}</span>
        <span class="pill pill--ghost">{{ chat.statusLabel }}</span>
      </div>
    </header>

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

      <section class="chat-view__center">
        <ChatSqlEditor
          :auto-apply-sql="chat.autoApplySql"
          :busy="chat.generating || chat.executing"
          :model-value="chat.sqlDraft"
          :status="editorStatus"
          :version="chat.sqlDraftVersion"
          @run="runSql"
          @update:modelValue="updateSqlDraft"
        />

        <ChatAssistant
          :auto-apply-sql="chat.autoApplySql"
          :busy="chat.generating"
          :messages="chat.messages"
          @apply-sql="applySql"
          @clarification="sendClarification"
          @send="sendMessage"
        />
      </section>

      <ChatResultPanel
        :execution="chat.executionResult"
        :view="chat.resultView"
        @change-view="chat.setResultMode"
      />
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

const currentDatabase = computed(() => chat.currentDatabase);

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

function sendMessage(text: string) {
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
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  min-height: 0;
  flex: 1;
  padding: 1rem;
  background:
    radial-gradient(circle at top left, rgba(249, 171, 0, 0.08), transparent 28%),
    radial-gradient(circle at top right, rgba(138, 180, 248, 0.08), transparent 24%),
    var(--canvas);
}

.chat-view__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.8rem;
  padding-bottom: 0.35rem;
}

.chat-view__header h1 {
  margin: 0.25rem 0 0;
  font-size: clamp(1.25rem, 1.1rem + 1vw, 2rem);
  letter-spacing: -0.03em;
}

.chat-view__lead {
  margin: 0.35rem 0 0;
  max-width: 54rem;
  color: var(--muted);
  font-size: 0.92rem;
  line-height: 1.55;
}

.chat-view__meta {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.chat-view__grid {
  display: grid;
  grid-template-columns: minmax(16rem, 22%) minmax(0, 50%) minmax(18rem, 28%);
  gap: 0.9rem;
  min-height: 0;
  flex: 1;
}

.chat-view__center {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0.9rem;
  min-height: 0;
}

@media (max-width: 1100px) {
  .chat-view__grid {
    grid-template-columns: minmax(16rem, 28%) minmax(0, 1fr);
    grid-template-rows: auto auto;
  }

  .chat-view__center {
    grid-column: 2;
  }

  .chat-view__grid > :last-child {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .chat-view {
    padding: 0.85rem;
  }

  .chat-view__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-view__grid {
    grid-template-columns: 1fr;
  }

  .chat-view__center {
    grid-column: auto;
  }

  .chat-view__grid > :last-child {
    grid-column: auto;
  }
}
</style>
