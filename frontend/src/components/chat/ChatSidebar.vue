<template>
  <aside class="chat-sidebar">
    <header class="chat-sidebar__head">
      <div>
        <p class="eyebrow">Базы</p>
        <h2>Подключения и чаты</h2>
      </div>
      <button class="app-button app-button--tiny" type="button" :disabled="!activeDbId" @click="$emit('create-session')">
        + Чат
      </button>
    </header>

    <section class="chat-sidebar__section">
      <div class="chat-sidebar__section-head">
        <h3>Базы данных</h3>
      </div>
      <div class="chat-sidebar__db-list">
        <button
          v-for="database in databases"
          :key="database.id"
          class="chat-sidebar__item chat-sidebar__item--database"
          :class="{ 'chat-sidebar__item--active': database.id === activeDbId }"
          type="button"
          @click="$emit('select-database', database.id)"
        >
          <div class="chat-sidebar__item-main">
            <strong>{{ database.name }}</strong>
            <span>{{ database.dialect }} · {{ database.status }}</span>
          </div>
          <span class="pill pill--ghost">{{ database.table_count }}</span>
        </button>
      </div>
    </section>

    <section class="chat-sidebar__section chat-sidebar__section--fill">
      <div class="chat-sidebar__section-head">
        <h3>Сессии</h3>
        <input
          v-model="query"
          class="chat-sidebar__search"
          type="search"
          placeholder="Поиск"
        />
      </div>

      <div v-if="loading" class="chat-sidebar__loading">
        Загружаю чаты…
      </div>

      <div v-else-if="!filteredSessions.length" class="chat-sidebar__empty">
        <p>Пока нет чатов. Создайте первый.</p>
      </div>

      <div v-else class="chat-sidebar__session-list">
        <article
          v-for="session in filteredSessions"
          :key="session.id"
          class="chat-sidebar__item chat-sidebar__item--session"
          :class="{ 'chat-sidebar__item--active': session.id === activeSessionId }"
          role="button"
          tabindex="0"
          @click="$emit('select-session', session.id)"
          @keydown.enter.prevent="$emit('select-session', session.id)"
        >
          <div class="chat-sidebar__item-main">
            <strong>{{ session.title }}</strong>
            <span>{{ formatTime(session.updated_at) }}</span>
          </div>
          <div class="chat-sidebar__session-actions">
            <button class="chat-sidebar__icon-btn" type="button" title="Переименовать" @click.stop="rename(session)">
              ✎
            </button>
            <button class="chat-sidebar__icon-btn" type="button" title="Удалить" @click.stop="remove(session)">
              ×
            </button>
          </div>
        </article>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { ApiChatSessionRead, ApiDatabaseDescriptor } from '@/api/types';

const props = defineProps<{
  databases: ApiDatabaseDescriptor[];
  sessions: ApiChatSessionRead[];
  activeDbId: string;
  activeSessionId: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  (event: 'select-database', databaseId: string): void;
  (event: 'select-session', sessionId: string): void;
  (event: 'create-session'): void;
  (event: 'rename-session', sessionId: string, title: string): void;
  (event: 'delete-session', sessionId: string): void;
}>();

const query = ref('');

const filteredSessions = computed(() =>
  props.sessions.filter((session) => session.title.toLowerCase().includes(query.value.toLowerCase()))
);

function rename(session: ApiChatSessionRead) {
  const title = window.prompt('Новое название чата', session.title)?.trim();
  if (title) {
    emit('rename-session', session.id, title);
  }
}

function remove(session: ApiChatSessionRead) {
  if (window.confirm(`Удалить чат «${session.title}»?`)) {
    emit('delete-session', session.id);
  }
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: 'short'
  }).format(new Date(value));
}
</script>

<style scoped lang="scss">
.chat-sidebar {
  display: grid;
  gap: 1rem;
  min-height: 0;
  height: 100%;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.015)),
    var(--bg-elev);
  box-shadow: var(--shadow-soft);
}

.chat-sidebar__head,
.chat-sidebar__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem;
}

.chat-sidebar__head h2,
.chat-sidebar__section-head h3 {
  margin: 0.3rem 0 0;
  font-size: 1rem;
}

.chat-sidebar__section {
  display: grid;
  gap: 0.65rem;
  min-height: 0;
}

.chat-sidebar__section--fill {
  min-height: 0;
  grid-template-rows: auto auto minmax(0, 1fr);
}

.chat-sidebar__db-list,
.chat-sidebar__session-list {
  display: grid;
  gap: 0.4rem;
  min-height: 0;
}

.chat-sidebar__session-list {
  overflow-y: auto;
  padding-right: 0.2rem;
}

.chat-sidebar__item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.02);
  color: inherit;
}

.chat-sidebar__item:hover {
  border-color: rgba(249, 171, 0, 0.25);
  background: rgba(255, 255, 255, 0.04);
}

.chat-sidebar__item--active {
  border-color: rgba(249, 171, 0, 0.45);
  background: rgba(249, 171, 0, 0.08);
}

.chat-sidebar__item-main {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.chat-sidebar__item-main strong {
  color: var(--ink);
  font-size: 0.83rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__item-main span {
  color: var(--muted);
  font-size: 0.74rem;
}

.chat-sidebar__item--database {
  padding: 0.72rem 0.75rem;
}

.chat-sidebar__item--session {
  padding: 0.65rem 0.7rem;
}

.chat-sidebar__session-actions {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.chat-sidebar__icon-btn {
  width: 1.9rem;
  height: 1.9rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
}

.chat-sidebar__icon-btn:hover {
  color: var(--ink);
  background: rgba(255, 255, 255, 0.08);
}

.chat-sidebar__search {
  width: 100%;
  min-width: 8rem;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.02);
  color: var(--ink);
  font-size: 0.82rem;
}

.chat-sidebar__search:focus {
  outline: none;
  border-color: rgba(249, 171, 0, 0.35);
}

.chat-sidebar__empty,
.chat-sidebar__loading {
  padding: 0.9rem 0.75rem;
  border-radius: var(--radius);
  border: 1px dashed var(--line);
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

.chat-sidebar__empty p {
  margin: 0;
}

@media (max-width: 900px) {
  .chat-sidebar {
    min-height: auto;
  }
}
</style>
