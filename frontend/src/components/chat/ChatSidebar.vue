<template>
  <aside class="chat-sidebar">
    <div class="chat-sidebar__top">
      <RouterLink to="/chat" class="chat-sidebar__brand" title="BimsDash">
        <span class="chat-sidebar__brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M20 4H11.3A7.3 7.3 0 0 0 4 11.3v1.4A7.3 7.3 0 0 0 11.3 20H14a6 6 0 0 0 6-6z" />
          </svg>
        </span>
        <span class="chat-sidebar__brand-text">BimsDash</span>
      </RouterLink>

      <nav class="chat-sidebar__nav" aria-label="Навигация">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="chat-sidebar__nav-link"
          :class="{ 'chat-sidebar__nav-link--active': isRouteActive(item.key) }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </div>

    <section class="chat-sidebar__section">
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
            <span>{{ database.dialect }}</span>
          </div>
          <span class="chat-sidebar__count">{{ database.table_count }}</span>
        </button>
      </div>
    </section>

    <section class="chat-sidebar__section chat-sidebar__section--fill">
      <div class="chat-sidebar__sessions-head">
        <input
          v-model="query"
          class="chat-sidebar__search"
          type="search"
          placeholder="Поиск"
        />
        <button
          class="chat-sidebar__new"
          type="button"
          :disabled="!activeDbId"
          @click="$emit('create-session')"
        >
          +
        </button>
      </div>

      <div v-if="loading" class="chat-sidebar__state">
        Загружаю…
      </div>

      <div v-else-if="!filteredSessions.length" class="chat-sidebar__state">
        Пусто
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

    <footer class="chat-sidebar__footer">
      <button class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent" type="button">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        Профиль
      </button>
      <button class="chat-sidebar__footer-btn" type="button" title="Настройки" aria-label="Настройки">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.82v.16a2 2 0 1 1-4 0v-.16A1.65 1.65 0 0 0 9 20a1.65 1.65 0 0 0-1-.6 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-.6-1 1.65 1.65 0 0 0-1.82-.33h-.16a2 2 0 1 1 0-4h.16A1.65 1.65 0 0 0 4 9a1.65 1.65 0 0 0 .6-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6c.3 0 .59-.12.8-.33a1.65 1.65 0 0 0 .2-1.27v-.16a2 2 0 1 1 4 0v.16c-.03.45.06.9.26 1.3.2.39.53.71.92.9.4.2.85.3 1.3.26h.16a2 2 0 1 1 0 4h-.16a1.65 1.65 0 0 0-1.3.26c-.39.2-.72.52-.92.9-.2.4-.29.84-.26 1.3z"/></svg>
        Настройки
      </button>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
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

const route = useRoute();
const query = ref('');

const navItems = [
  { to: '/colab', label: 'Коллаб', key: 'colab' as const },
  { to: '/data', label: 'Дэшборд', key: 'data' as const },
  { to: '/chat', label: 'BimsChat', key: 'chat' as const }
];

const filteredSessions = computed(() =>
  props.sessions.filter((session) => session.title.toLowerCase().includes(query.value.toLowerCase()))
);

function isRouteActive(key: 'chat' | 'colab' | 'data') {
  const path = route.path;
  if (key === 'chat') {
    return path === '/chat' || path.startsWith('/notebooks');
  }
  if (key === 'colab') {
    return path === '/colab' || path === '/notebook';
  }
  return path === '/data' || path.startsWith('/data');
}

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
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-sidebar__top {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 0 0 auto;
}

.chat-sidebar__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--ink-strong);
}

.chat-sidebar__brand-mark {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  display: inline-grid;
  place-items: center;
  color: var(--accent);
  border: 1px solid var(--line);
  background: rgba(112, 59, 247, 0.12);
}

.chat-sidebar__brand-text {
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.chat-sidebar__nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-sidebar__nav-link {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  font-size: 0.78rem;
}

.chat-sidebar__nav-link--active {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.22);
}

.chat-sidebar__section {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: rgba(0, 0, 0, 0.12);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  flex: 0 0 auto;
}

.chat-sidebar__section--fill {
  flex: 1 1 auto;
}

.chat-sidebar__db-list,
.chat-sidebar__session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.chat-sidebar__session-list {
  overflow-y: auto;
  flex: 1 1 auto;
}

.chat-sidebar__sessions-head {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}

.chat-sidebar__sessions-head .chat-sidebar__search {
  flex: 1 1 auto;
  min-width: 0;
}

.chat-sidebar__search {
  width: 100%;
  height: 34px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--ink);
  font-size: 0.82rem;
  padding: 0 10px;
}

.chat-sidebar__search:focus {
  outline: none;
  border-color: rgba(112, 59, 247, 0.75);
}

.chat-sidebar__new {
  width: 34px;
  height: 34px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
  font-size: 1rem;
}

.chat-sidebar__new:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-sidebar__item {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
  padding: 9px 10px;
  text-align: left;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chat-sidebar__item--active {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.2);
}

.chat-sidebar__item-main {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.chat-sidebar__item-main strong {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--ink-strong);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.chat-sidebar__item-main span {
  font-size: 0.72rem;
  color: var(--muted);
}

.chat-sidebar__count {
  min-width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid var(--line);
  display: inline-grid;
  place-items: center;
  font-size: 0.68rem;
  color: var(--muted);
}

.chat-sidebar__session-actions {
  display: flex;
  gap: 4px;
}

.chat-sidebar__icon-btn {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
}

.chat-sidebar__icon-btn:hover {
  border-color: var(--line);
  color: var(--ink-strong);
}

.chat-sidebar__state {
  border: 1px dashed var(--line);
  border-radius: 10px;
  padding: 10px;
  color: var(--muted);
  font-size: 0.78rem;
}

.chat-sidebar__footer {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}

.chat-sidebar__footer .chat-sidebar__footer-btn--accent {
  flex: 1 1 auto;
  min-width: 0;
}

.chat-sidebar__footer-btn {
  min-height: 36px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--ink);
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
}

.chat-sidebar__footer-btn--accent {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

@media (max-width: 940px) {
  .chat-sidebar__nav {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .chat-sidebar__nav-link {
    justify-content: center;
  }
}
</style>
