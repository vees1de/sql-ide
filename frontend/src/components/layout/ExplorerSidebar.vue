<template>
  <aside class="sidebar">
    <div class="sidebar__head">
      <p class="eyebrow">Базы данных</p>
      <button
        class="sidebar__add"
        type="button"
        title="Добавить базу данных"
        @click="$emit('add-database')"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
      </button>
    </div>

    <div class="tree">
      <div
        v-if="workspace.databases.length === 0"
        class="empty-state"
      >
        <p>Нет подключённых БД</p>
        <button class="app-button app-button--link app-button--tiny" @click="$emit('add-database')">
          Добавить базу
        </button>
      </div>

      <div
        v-for="database in workspace.databases"
        :key="database.id"
        class="db-folder"
        :class="{ 'db-folder--active': activeDatabaseId === database.id }"
      >
        <button
          class="db-folder__head"
          type="button"
          @click="toggle(database.id)"
        >
          <span class="db-folder__chevron" :class="{ 'db-folder__chevron--open': isOpen(database.id) }">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>
          </span>
          <span class="db-folder__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>
          </span>
          <span class="db-folder__name">{{ database.name }}</span>
          <span
            class="db-folder__status"
            :class="`db-folder__status--${database.status}`"
            :title="database.status"
          ></span>
          <span class="db-folder__count">{{ notebooksOf(database.id).length }}</span>
          <span
            v-if="!database.isDemo"
            class="row-delete"
            role="button"
            tabindex="0"
            title="Удалить базу"
            @click="onDeleteDatabase($event, database.id)"
            @keydown.enter="onDeleteDatabase($event as unknown as MouseEvent, database.id)"
          >
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
          </span>
        </button>

        <div v-show="isOpen(database.id)" class="db-folder__body">
          <p class="db-folder__meta">{{ database.engine }}</p>
          <p v-if="database.allowedTables?.length" class="db-folder__access">
            Доступ: {{ database.allowedTables.length }} табл.
            <span v-if="database.allowedTables.length <= 4" class="db-folder__access-detail">
              ({{ database.allowedTables.join(', ') }})
            </span>
          </p>

          <nav class="chat-list">
            <button
              v-for="notebook in notebooksOf(database.id)"
              :key="notebook.id"
              class="chat-item"
              :class="{ 'chat-item--active': notebook.id === selectedNotebookId }"
              type="button"
              @click="$emit('open-notebook', notebook.id)"
            >
              <span class="chat-item__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
              </span>
              <span class="chat-item__text">
                <span class="chat-item__title">{{ notebook.title }}</span>
                <span class="chat-item__sub">{{ notebook.summary.lastRunLabel }}</span>
              </span>
              <span
                class="row-delete"
                role="button"
                tabindex="0"
                title="Удалить notebook"
                @click="onDeleteNotebook($event, notebook.id)"
                @keydown.enter="onDeleteNotebook($event as unknown as MouseEvent, notebook.id)"
              >
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
              </span>
            </button>

            <button
              class="chat-item chat-item--add"
              type="button"
              @click="$emit('create-notebook', database.id)"
            >
              <span class="chat-item__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
              </span>
              <span class="chat-item__text">
                <span class="chat-item__title">Новый чат</span>
              </span>
            </button>
          </nav>
        </div>
      </div>
    </div>

    <div v-if="workspace.dictionary.length" class="sidebar__section">
      <p class="eyebrow">Dictionary</p>
      <div class="tag-list">
        <span
          v-for="term in workspace.dictionary.slice(0, 10)"
          :key="term.id"
          class="tag-chip"
        >
          {{ term.term }}
        </span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { WorkspaceData } from '@/types/app';

const props = defineProps<{
  activeDatabaseId: string;
  selectedNotebookId: string;
  workspace: WorkspaceData;
}>();

const emit = defineEmits<{
  (event: 'open-notebook', notebookId: string): void;
  (event: 'add-database'): void;
  (event: 'create-notebook', databaseId: string): void;
  (event: 'delete-database', databaseId: string): void;
  (event: 'delete-notebook', notebookId: string): void;
}>();

function onDeleteDatabase(event: MouseEvent, databaseId: string) {
  event.stopPropagation();
  emit('delete-database', databaseId);
}

function onDeleteNotebook(event: MouseEvent, notebookId: string) {
  event.stopPropagation();
  emit('delete-notebook', notebookId);
}

const openIds = ref<Set<string>>(new Set());

watch(
  () => props.activeDatabaseId,
  (id) => {
    if (id && !openIds.value.has(id)) {
      openIds.value = new Set([...openIds.value, id]);
    }
  },
  { immediate: true }
);

watch(
  () => props.workspace.databases.map((db) => db.id).join(','),
  () => {
    // Auto-open the first DB if nothing is open yet
    if (openIds.value.size === 0 && props.workspace.databases[0]) {
      openIds.value = new Set([props.workspace.databases[0].id]);
    }
  },
  { immediate: true }
);

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
}

const notebooksByDb = computed(() => {
  const map = new Map<string, typeof props.workspace.notebooks>();
  for (const notebook of props.workspace.notebooks) {
    const list = map.get(notebook.databaseId) ?? [];
    list.push(notebook);
    map.set(notebook.databaseId, list);
  }
  return map;
});

function notebooksOf(dbId: string) {
  return notebooksByDb.value.get(dbId) ?? [];
}
</script>

<style scoped lang="scss">
.sidebar {
  height: 100%;
  overflow-y: auto;
  padding: 0.75rem 0.55rem 1rem;
  background: var(--bg-elev);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sidebar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.1rem 0.55rem 0;
}

.sidebar__add {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  transition: background 160ms ease, color 160ms ease;
}

.sidebar__add:hover {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.tree {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.empty-state {
  padding: 1rem 0.6rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.82rem;
}

.empty-state p {
  margin: 0 0 0.55rem;
}

.db-folder {
  border-radius: 8px;
  overflow: hidden;
}

.db-folder__head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  width: 100%;
  padding: 0.4rem 0.55rem;
  border: none;
  background: transparent;
  color: var(--ink);
  text-align: left;
  font-size: 0.85rem;
  border-radius: 8px;
  transition: background 140ms ease;
}

.db-folder__name {
  flex: 1;
  min-width: 0;
}

.db-folder__head:hover {
  background: rgba(255, 255, 255, 0.04);
}

.db-folder--active > .db-folder__head {
  background: rgba(255, 255, 255, 0.05);
}

.db-folder__chevron {
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  transition: transform 160ms ease;
}

.db-folder__chevron--open {
  transform: rotate(90deg);
}

.db-folder__icon {
  color: var(--accent);
  display: inline-grid;
  place-items: center;
}

.db-folder__name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.row-delete {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  color: var(--muted);
  opacity: 0;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
  cursor: pointer;
  flex-shrink: 0;
}

.db-folder__head:hover .row-delete,
.chat-item:hover .row-delete,
.row-delete:focus {
  opacity: 1;
}

.row-delete:hover {
  background: rgba(242, 139, 130, 0.14);
  color: var(--danger);
}

.db-folder__status {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--muted-2);
}

.db-folder__status--connected { background: var(--success); }
.db-folder__status--syncing { background: var(--warning); }

.db-folder__count {
  color: var(--muted);
  font-size: 0.72rem;
  padding-left: 0.2rem;
}

.db-folder__body {
  padding: 0.1rem 0 0.35rem 1.85rem;
}

.db-folder__meta {
  margin: 0.1rem 0 0.35rem;
  color: var(--muted-2);
  font-size: 0.7rem;
  letter-spacing: 0.04em;
}

.db-folder__access {
  margin: 0 0 0.45rem;
  font-size: 0.68rem;
  color: var(--muted);
  line-height: 1.35;
}

.db-folder__access-detail {
  display: block;
  margin-top: 0.12rem;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  opacity: 0.9;
}

.chat-list {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.chat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.38rem 0.55rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  text-align: left;
  color: var(--ink);
  transition: background 140ms ease, color 140ms ease;
}

.chat-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.chat-item--active {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.chat-item__icon {
  color: var(--muted);
  display: inline-grid;
  place-items: center;
}

.chat-item--active .chat-item__icon {
  color: var(--accent);
}

.chat-item__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.chat-item__title {
  font-size: 0.83rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-item__sub {
  font-size: 0.7rem;
  color: var(--muted-2);
}

.chat-item--add {
  color: var(--muted);
  font-style: italic;
}

.chat-item--add:hover {
  color: var(--accent-strong);
}

.sidebar__section {
  padding: 0 0.55rem;
}

.sidebar__section .eyebrow {
  margin-bottom: 0.45rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.tag-chip {
  padding: 0.22rem 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
  font-size: 0.74rem;
}
</style>
