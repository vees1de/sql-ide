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

    <section class="chat-sidebar__section chat-sidebar__section--tree">
      <div class="chat-sidebar__section-head">
        <div>
          <p class="chat-sidebar__eyebrow">Навигатор</p>
          <h2 class="chat-sidebar__title">Чаты</h2>
        </div>

        <button
          class="chat-sidebar__new"
          type="button"
          :disabled="!activeDbId"
          @click="$emit('create-session', activeDbId)"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Новый чат
        </button>
      </div>

      <div class="chat-sidebar__search-wrap">
        <input
          v-model="query"
          class="chat-sidebar__search"
          type="search"
          placeholder="Поиск чатов"
        />
      </div>

      <div v-if="loading" class="chat-sidebar__state">
        Загружаю дерево чатов…
      </div>

      <div v-else-if="!databases.length" class="chat-sidebar__state">
        Нет подключённых баз
      </div>

      <div v-else-if="!treeDatabases.length" class="chat-sidebar__state">
        Ничего не найдено
      </div>

      <div v-else class="chat-sidebar__tree">
        <div
          v-for="database in treeDatabases"
          :key="database.id"
          class="chat-sidebar__folder"
          :class="{
            'chat-sidebar__folder--active': database.id === activeDbId,
            'chat-sidebar__folder--open': isOpen(database.id)
          }"
        >
          <button
            class="chat-sidebar__folder-head"
            type="button"
            :aria-expanded="isOpen(database.id)"
            @click="toggle(database.id)"
          >
            <span class="chat-sidebar__folder-chevron" :class="{ 'chat-sidebar__folder-chevron--open': isOpen(database.id) }">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 6 15 12 9 18" />
              </svg>
            </span>
            <span class="chat-sidebar__folder-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <ellipse cx="12" cy="5" rx="8" ry="3" />
                <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
                <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
              </svg>
            </span>
            <span class="chat-sidebar__folder-name">{{ database.name }}</span>
            <span class="chat-sidebar__folder-meta-pill">{{ database.sessions.length }}</span>
          </button>

          <div v-show="isOpen(database.id)" class="chat-sidebar__folder-body">
            <p class="chat-sidebar__folder-meta">
              {{ database.dialect }}
              <span v-if="database.table_count != null">· {{ database.table_count }} tables</span>
            </p>

            <div v-if="!database.sessions.length" class="chat-sidebar__empty-branch">
              Нет чатов в этой базе
            </div>

            <div v-else class="chat-sidebar__session-list">
              <article
                v-for="session in database.sessions"
                :key="session.id"
                class="chat-sidebar__session"
                :class="{ 'chat-sidebar__session--active': session.id === activeSessionId }"
                role="button"
                tabindex="0"
                @click="$emit('select-session', session.id)"
                @keydown.enter.prevent="$emit('select-session', session.id)"
                @keydown.space.prevent="$emit('select-session', session.id)"
              >
                <span class="chat-sidebar__session-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                  </svg>
                </span>

                <span class="chat-sidebar__session-text">
                  <span class="chat-sidebar__session-title">{{ session.title }}</span>
                  <span class="chat-sidebar__session-sub">{{ formatTime(session.updated_at) }}</span>
                </span>

                <span class="chat-sidebar__session-actions">
                  <button
                    class="chat-sidebar__icon-btn"
                    type="button"
                    title="Переименовать"
                    aria-label="Переименовать"
                    @click.stop="rename(session)"
                  >
                    ✎
                  </button>
                  <button
                    class="chat-sidebar__icon-btn"
                    type="button"
                    title="Удалить"
                    aria-label="Удалить"
                    @click.stop="remove(session)"
                  >
                    ×
                  </button>
                </span>
              </article>
            </div>

            <button
              class="chat-sidebar__session chat-sidebar__session--create"
              type="button"
              @click="$emit('create-session', database.id)"
            >
              <span class="chat-sidebar__session-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </span>
              <span class="chat-sidebar__session-text">
                <span class="chat-sidebar__session-title">Новый чат</span>
                <span class="chat-sidebar__session-sub">Создать в этой базе</span>
              </span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <footer class="chat-sidebar__footer">
      <button class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent" type="button">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
        Профиль
      </button>
      <button class="chat-sidebar__footer-btn" type="button" title="Настройки" aria-label="Настройки">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.82v.16a2 2 0 1 1-4 0v-.16A1.65 1.65 0 0 0 9 20a1.65 1.65 0 0 0-1-.6 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-.6-1 1.65 1.65 0 0 0-1.82-.33h-.16a2 2 0 1 1 0-4h.16A1.65 1.65 0 0 0 4 9a1.65 1.65 0 0 0 .6-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6c.3 0 .59-.12.8-.33a1.65 1.65 0 0 0 .2-1.27v-.16a2 2 0 1 1 4 0v.16c-.03.45.06.9.26 1.3.2.39.53.71.92.9.4.2.85.3 1.3.26h.16a2 2 0 1 1 0 4h-.16a1.65 1.65 0 0 0-1.3.26c-.39.2-.72.52-.92.9-.2.4-.29.84-.26 1.3z" />
        </svg>
        Настройки
      </button>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import type { ApiChatSessionRead, ApiDatabaseDescriptor } from '@/api/types';

type TreeDatabase = ApiDatabaseDescriptor & { sessions: ApiChatSessionRead[] };

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
  (event: 'create-session', databaseId?: string): void;
  (event: 'rename-session', sessionId: string, title: string): void;
  (event: 'delete-session', sessionId: string): void;
}>();

const route = useRoute();
const query = ref('');
const openIds = ref<Set<string>>(new Set());

const navItems = [
  { to: '/colab', label: 'Коллаб', key: 'colab' as const },
  { to: '/data', label: 'Дэшборд', key: 'data' as const },
  { to: '/chat', label: 'BimsChat', key: 'chat' as const }
];

const normalizedQuery = computed(() => query.value.trim().toLowerCase());

const sessionsByDatabase = computed(() => {
  const map = new Map<string, ApiChatSessionRead[]>();
  for (const session of props.sessions) {
    const list = map.get(session.database_connection_id) ?? [];
    list.push(session);
    map.set(session.database_connection_id, list);
  }
  for (const list of map.values()) {
    list.sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at));
  }
  return map;
});

const treeDatabases = computed<TreeDatabase[]>(() => {
  const q = normalizedQuery.value;
  const items = props.databases
    .map((database) => {
      const sessions = sessionsByDatabase.value.get(database.id) ?? [];
      if (!q) {
        return { ...database, sessions };
      }

      const matchesDatabase =
        database.name.toLowerCase().includes(q) ||
        database.dialect.toLowerCase().includes(q) ||
        (database.description ?? '').toLowerCase().includes(q);

      const filteredSessions = matchesDatabase
        ? sessions
        : sessions.filter((session) => session.title.toLowerCase().includes(q));

      if (!matchesDatabase && !filteredSessions.length) {
        return null;
      }

      return { ...database, sessions: filteredSessions };
    })
    .filter((item): item is TreeDatabase => Boolean(item));

  return items;
});

watch(
  () => props.activeDbId,
  (id) => {
    if (id) {
      openIds.value = new Set([...openIds.value, id]);
    }
  },
  { immediate: true }
);

watch(
  () => props.activeSessionId,
  (sessionId) => {
    const session = props.sessions.find((item) => item.id === sessionId);
    if (session?.database_connection_id) {
      openIds.value = new Set([...openIds.value, session.database_connection_id]);
    }
  },
  { immediate: true }
);

watch(
  () => normalizedQuery.value,
  (q) => {
    if (!q) {
      return;
    }

    const next = new Set(openIds.value);
    for (const database of treeDatabases.value) {
      next.add(database.id);
    }
    openIds.value = next;
  }
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

function isOpen(id: string) {
  return openIds.value.has(id);
}

function toggle(id: string) {
  const next = new Set(openIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  openIds.value = next;
  if (id !== props.activeDbId) {
    emit('select-database', id);
  }
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
  gap: 10px;
  min-height: 0;
  flex: 1 1 auto;
}

.chat-sidebar__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.chat-sidebar__eyebrow {
  margin: 0;
  color: var(--muted-2);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.chat-sidebar__title {
  margin: 0.2rem 0 0;
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.chat-sidebar__new {
  min-height: 34px;
  border: 1px solid rgba(112, 59, 247, 0.8);
  border-radius: 10px;
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
  font-size: 0.8rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  white-space: nowrap;
}

.chat-sidebar__new:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-sidebar__search-wrap {
  flex: 0 0 auto;
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

.chat-sidebar__tree {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.chat-sidebar__folder {
  border: 1px solid transparent;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
}

.chat-sidebar__folder--active {
  border-color: rgba(112, 59, 247, 0.28);
  background: rgba(112, 59, 247, 0.08);
}

.chat-sidebar__folder-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 0.55rem 0.6rem;
  border: none;
  background: transparent;
  color: var(--ink);
  text-align: left;
  font-size: 0.84rem;
  transition: background 140ms ease;
}

.chat-sidebar__folder-head:hover {
  background: rgba(255, 255, 255, 0.04);
}

.chat-sidebar__folder-chevron {
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  transition: transform 160ms ease;
}

.chat-sidebar__folder-chevron--open {
  transform: rotate(90deg);
}

.chat-sidebar__folder-icon {
  color: var(--accent);
  display: inline-grid;
  place-items: center;
}

.chat-sidebar__folder-name {
  flex: 1;
  min-width: 0;
  font-weight: 550;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__folder-meta-pill {
  min-width: 24px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  border: 1px solid var(--line);
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  font-size: 0.68rem;
  flex-shrink: 0;
}

.chat-sidebar__folder-body {
  padding: 0 0.6rem 0.65rem 1.85rem;
}

.chat-sidebar__folder-meta {
  margin: 0 0 0.5rem;
  color: var(--muted-2);
  font-size: 0.7rem;
  letter-spacing: 0.03em;
}

.chat-sidebar__empty-branch {
  margin-bottom: 0.45rem;
  padding: 0.55rem 0.6rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
  color: var(--muted);
  font-size: 0.78rem;
}

.chat-sidebar__session-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-sidebar__session {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  width: 100%;
  padding: 0.45rem 0.55rem;
  border: none;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  color: var(--ink);
  transition:
    background 140ms ease,
    color 140ms ease,
    transform 140ms ease;
}

.chat-sidebar__session:hover {
  background: rgba(255, 255, 255, 0.04);
}

.chat-sidebar__session--active {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.chat-sidebar__session--create {
  margin-top: 0.35rem;
  color: var(--muted);
}

.chat-sidebar__session--create:hover {
  color: var(--accent-strong);
}

.chat-sidebar__session-icon {
  color: var(--muted);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
}

.chat-sidebar__session--active .chat-sidebar__session-icon {
  color: var(--accent);
}

.chat-sidebar__session-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.chat-sidebar__session-title {
  font-size: 0.83rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__session-sub {
  font-size: 0.7rem;
  color: var(--muted-2);
}

.chat-sidebar__session--active .chat-sidebar__session-sub {
  color: rgba(255, 255, 255, 0.72);
}

.chat-sidebar__session-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
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
