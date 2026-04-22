<template>
  <aside class="chat-sidebar">
    <div class="chat-sidebar__top">
      <RouterLink to="/chat" class="chat-sidebar__brand" title="BimsDash">
        <span class="chat-sidebar__brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path
              d="M20 4H11.3A7.3 7.3 0 0 0 4 11.3v1.4A7.3 7.3 0 0 0 11.3 20H14a6 6 0 0 0 6-6z"
            />
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
      <div class="chat-sidebar__panel">
        <div class="chat-sidebar__section-head">
          <div>
            <p class="chat-sidebar__eyebrow">Навигатор</p>
            <h2 class="chat-sidebar__title">
              {{ isDatabaseMode ? "Базы данных" : "Чаты" }}
            </h2>
          </div>

          <button
            class="chat-sidebar__new"
            type="button"
            :disabled="isDatabaseMode ? false : !activeDbId"
            @click="
              isDatabaseMode
                ? $emit('add-database')
                : $emit('create-session', activeDbId)
            "
          >
            <svg
              viewBox="0 0 24 24"
              width="14"
              height="14"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            {{ isDatabaseMode ? "Добавить БД" : "Новый чат" }}
          </button>
        </div>

        <div
          v-if="isDatabaseMode || isDashboardsMode"
          class="chat-sidebar__search-wrap"
        >
          <input
            v-model="query"
            class="chat-sidebar__search"
            type="search"
            :placeholder="
              isDatabaseMode
                ? 'Поиск баз'
                : isDashboardsMode
                  ? 'Поиск дашбордов и виджетов'
                  : 'Поиск чатов'
            "
          />
        </div>

        <template v-if="loading">
          <div class="chat-sidebar__tree chat-sidebar__tree--skeleton">
            <template v-if="isChatMode">
              <div
                v-for="group in 3"
                :key="`chat-skeleton-${group}`"
                class="chat-sidebar__folder chat-sidebar__folder--skeleton"
              >
                <div class="chat-sidebar__folder-head chat-sidebar__folder-head--skeleton">
                  <AppSkeleton width="14px" height="14px" radius="6px" />
                  <AppSkeleton width="14px" height="14px" radius="6px" />
                  <AppSkeleton class="chat-sidebar__folder-name-skeleton" height="0.84rem" radius="6px" />
                  <AppSkeleton width="78px" height="0.72rem" radius="5px" />
                </div>
                <div class="chat-sidebar__folder-body">
                  <div class="chat-sidebar__session-list">
                    <div
                      v-for="session in 2"
                      :key="`chat-skeleton-session-${group}-${session}`"
                      class="chat-sidebar__session chat-sidebar__session--skeleton"
                    >
                      <AppSkeleton width="14px" height="14px" radius="6px" />
                      <div class="chat-sidebar__session-text">
                        <AppSkeleton height="0.82rem" width="58%" radius="6px" />
                        <AppSkeleton height="0.68rem" width="74%" radius="5px" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <template v-else>
              <div
                v-for="row in 5"
                :key="`sidebar-skeleton-row-${row}`"
                class="chat-sidebar__db-row chat-sidebar__db-row--skeleton"
              >
                <AppSkeleton width="14px" height="14px" radius="6px" />
                <div class="chat-sidebar__db-text">
                  <AppSkeleton height="0.88rem" width="54%" radius="6px" />
                  <AppSkeleton height="0.72rem" width="72%" radius="5px" />
                </div>
                <div class="chat-sidebar__db-meta">
                  <AppSkeleton width="60px" height="20px" radius="999px" />
                  <AppSkeleton width="42px" height="0.66rem" radius="5px" />
                </div>
                <div class="chat-sidebar__db-actions">
                  <AppSkeleton width="22px" height="22px" radius="6px" />
                </div>
              </div>
            </template>
          </div>
        </template>

        <div v-else-if="false" class="chat-sidebar__state">
          {{
            isDatabaseMode
              ? "Загружаю список баз…"
              : isDashboardsMode
                ? "Загружаю навигацию…"
                : "Загружаю дерево чатов…"
          }}
        </div>

        <div
          v-else-if="isDashboardsMode && !dashboardItems.length"
          class="chat-sidebar__state"
        >
          {{
            dashboardView === "widgets"
              ? "Виджетов пока нет"
              : "Дашбордов пока нет"
          }}
        </div>

        <div
          v-else-if="!isDashboardsMode && !databases.length"
          class="chat-sidebar__state"
        >
          Нет подключённых баз
        </div>

        <div
          v-else-if="!isDashboardsMode && !treeDatabases.length"
          class="chat-sidebar__state"
        >
          Ничего не найдено
        </div>

        <div
          v-else-if="isDashboardsMode && !filteredDashboardItems.length"
          class="chat-sidebar__state"
        >
          Ничего не найдено
        </div>

        <div v-else class="chat-sidebar__tree">
          <template v-if="isDashboardsMode">
            <div
              class="chat-sidebar__section-head chat-sidebar__section-head--stacked"
            >
              <div>
                <p class="chat-sidebar__eyebrow">Навигатор</p>
                <h2 class="chat-sidebar__title">
                  {{ dashboardView === "widgets" ? "Виджеты" : "Дашборды" }}
                </h2>
              </div>
              <button
                class="chat-sidebar__new"
                type="button"
                @click="toggleDashboardView()"
              >
                {{
                  dashboardView === "widgets"
                    ? "Показать дашборды"
                    : "Показать виджеты"
                }}
              </button>
            </div>

            <RouterLink
              v-for="item in filteredDashboardItems"
              :key="item.id"
              :to="
                dashboardView === 'widgets'
                  ? `/widget/${item.id}`
                  : `/dashboards/${item.id}`
              "
              class="chat-sidebar__db-row"
              :class="{
                'chat-sidebar__db-row--active': isDashboardItemActive(item.id),
              }"
            >
              <span class="chat-sidebar__db-icon" aria-hidden="true">
                <svg
                  v-if="dashboardView === 'widgets'"
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M4 19V5" />
                  <path d="M4 19h16" />
                  <path d="M8 15V9" />
                  <path d="M12 15V7" />
                  <path d="M16 15v-4" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="4" y="4" width="7" height="7" rx="1.5" />
                  <rect x="13" y="4" width="7" height="7" rx="1.5" />
                  <rect x="4" y="13" width="7" height="7" rx="1.5" />
                  <rect x="13" y="13" width="7" height="7" rx="1.5" />
                </svg>
              </span>

              <span class="chat-sidebar__db-text">
                <span class="chat-sidebar__db-name">{{ itemTitle(item) }}</span>
                <span class="chat-sidebar__db-sub">{{
                  itemSubtitle(item)
                }}</span>
              </span>

              <span class="chat-sidebar__db-meta">
                <span
                  v-if="isDashboardItemPublic(item)"
                  class="chat-sidebar__db-pill chat-sidebar__db-pill--accent"
                >
                  Публичный
                </span>
                <span
                  v-if="isDashboardItemHidden(item)"
                  class="chat-sidebar__db-pill"
                >
                  Скрытый
                </span>
                <span
                  v-else-if="isWidgetItem(item)"
                  class="chat-sidebar__db-pill"
                >
                  {{ widgetVisualizationLabel(item) }}
                </span>
              </span>
            </RouterLink>
          </template>

          <template v-else-if="isDatabaseMode">
            <div
              v-for="database in treeDatabases"
              :key="database.id"
              class="chat-sidebar__db-row"
              :class="{
                'chat-sidebar__db-row--active': database.id === activeDbId,
              }"
              role="button"
              tabindex="0"
              @click="selectDatabase(database.id)"
              @keydown.enter.prevent="selectDatabase(database.id)"
              @keydown.space.prevent="selectDatabase(database.id)"
            >
              <span class="chat-sidebar__db-icon" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <ellipse cx="12" cy="5" rx="8" ry="3" />
                  <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
                  <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
                </svg>
              </span>

                <span class="chat-sidebar__db-text">
                <span class="chat-sidebar__db-name">{{ database.name }}</span>
                <span class="chat-sidebar__db-sub">
                  {{ database.dialect }}
                  <span v-if="database.table_count != null">
                    · {{ formatTableCount(database.table_count) }}</span
                  >
                  <span v-if="database.description"
                    >· {{ database.description }}</span
                  >
                </span>
              </span>

              <span class="chat-sidebar__db-meta">
                <span
                  class="chat-sidebar__db-pill"
                  :class="`chat-sidebar__db-pill--${database.status}`"
                >
                  {{ translateDatabaseStatus(database.knowledge_status || database.status) }}
                </span>
                <span
                  v-if="database.last_scan_at"
                  class="chat-sidebar__db-time"
                >
                  {{ formatTime(database.last_scan_at) }}
                </span>
              </span>

              <span class="chat-sidebar__db-actions">
                <button
                  class="chat-sidebar__icon-btn"
                  type="button"
                  title="Переименовать"
                  aria-label="Переименовать"
                  :disabled="database.is_demo"
                  @click.stop="renameDatabase(database)"
                >
                  ✎
                </button>
                <button
                  class="chat-sidebar__icon-btn"
                  type="button"
                  title="Удалить"
                  aria-label="Удалить"
                  :disabled="database.is_demo"
                  @click.stop="remove(database)"
                >
                  ×
                </button>
              </span>
            </div>
          </template>

          <template v-else>
            <div
              v-for="database in treeDatabases"
              :key="database.id"
              class="chat-sidebar__folder"
              :class="{
                'chat-sidebar__folder--active': database.id === activeDbId,
                'chat-sidebar__folder--open': isOpen(database.id),
              }"
            >
              <button
                class="chat-sidebar__folder-head"
                type="button"
                :aria-expanded="isOpen(database.id)"
                @click="toggle(database.id)"
              >
                <span
                  class="chat-sidebar__folder-chevron"
                  :class="{
                    'chat-sidebar__folder-chevron--open': isOpen(database.id),
                  }"
                >
                  <svg
                    viewBox="0 0 24 24"
                    width="14"
                    height="14"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <polyline points="9 6 15 12 9 18" />
                  </svg>
                </span>
                <span class="chat-sidebar__folder-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    width="15"
                    height="15"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <ellipse cx="12" cy="5" rx="8" ry="3" />
                    <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
                    <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
                  </svg>
                </span>
                <span class="chat-sidebar__folder-name">{{
                  database.name
                }}</span>
                <span
                  class="chat-sidebar__folder-meta"
                  :title="folderMetaText(database)"
                >
                  {{ folderMetaText(database) }}
                </span>
              </button>

              <div
                v-show="isOpen(database.id)"
                class="chat-sidebar__folder-body"
              >
                <button
                  class="chat-sidebar__session chat-sidebar__session--create"
                  type="button"
                  @click="$emit('create-session', database.id)"
                >
                  <span class="chat-sidebar__session-icon" aria-hidden="true">
                    <svg
                      viewBox="0 0 24 24"
                      width="13"
                      height="13"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                  </span>
                  <span class="chat-sidebar__session-text">
                    <span class="chat-sidebar__session-title">Новый чат</span>
                    <span class="chat-sidebar__session-sub"
                      >Создать в этой базе</span
                    >
                  </span>
                </button>

                <div
                  v-if="!database.sessions.length"
                  class="chat-sidebar__empty-branch"
                >
                  Нет чатов в этой базе
                </div>

                <div v-else class="chat-sidebar__session-list">
                  <article
                    v-for="session in database.sessions"
                    :key="session.id"
                    class="chat-sidebar__session"
                    :class="{
                      'chat-sidebar__session--active':
                        session.id === activeSessionId,
                    }"
                    role="button"
                    tabindex="0"
                    @click="$emit('select-session', session.id)"
                    @keydown.enter.prevent="$emit('select-session', session.id)"
                    @keydown.space.prevent="$emit('select-session', session.id)"
                  >
                    <span class="chat-sidebar__session-icon" aria-hidden="true">
                      <svg
                        viewBox="0 0 24 24"
                        width="13"
                        height="13"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path
                          d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
                        />
                      </svg>
                    </span>

                    <span class="chat-sidebar__session-text">
                      <span class="chat-sidebar__session-title">{{
                        session.title
                      }}</span>
                      <span class="chat-sidebar__session-sub">{{
                        formatTime(session.updated_at)
                      }}</span>
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
                        @click.stop="removeSession(session)"
                      >
                        ×
                      </button>
                    </span>
                  </article>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </section>

    <footer class="chat-sidebar__footer">
      <RouterLink
        v-if="isDashboardsMode"
        class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent"
        :to="dashboardView === 'widgets' ? '/widgets' : '/dashboards/new'"
      >
        {{ dashboardView === "widgets" ? "Каталог виджетов" : "Новый дашборд" }}
      </RouterLink>
      <button
        v-else
        class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent"
        type="button"
      >
        <svg
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
        Профиль
      </button>
      <button
        class="chat-sidebar__footer-btn"
        type="button"
        title="Настройки"
        aria-label="Настройки"
      >
        <svg
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path
            d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 .6 1.65 1.65 0 0 0-.33 1.82v.16a2 2 0 1 1-4 0v-.16A1.65 1.65 0 0 0 9 20a1.65 1.65 0 0 0-1-.6 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-.6-1 1.65 1.65 0 0 0-1.82-.33h-.16a2 2 0 1 1 0-4h.16A1.65 1.65 0 0 0 4 9a1.65 1.65 0 0 0 .6-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6c.3 0 .59-.12.8-.33a1.65 1.65 0 0 0 .2-1.27v-.16a2 2 0 1 1 4 0v.16c-.03.45.06.9.26 1.3.2.39.53.71.92.9.4.2.85.3 1.3.26h.16a2 2 0 1 1 0 4h-.16a1.65 1.65 0 0 0-1.3.26c-.39.2-.72.52-.92.9-.2.4-.29.84-.26 1.3z"
          />
        </svg>
        Настройки
      </button>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import AppSkeleton from "@/components/ui/AppSkeleton.vue";
import type {
  ApiChatSessionRead,
  ApiDashboardRead,
  ApiDatabaseDescriptor,
  ApiWidgetRead,
} from "@/api/types";

type TreeDatabase = ApiDatabaseDescriptor & { sessions: ApiChatSessionRead[] };
type DashboardItem = ApiDashboardRead | ApiWidgetRead;

const props = defineProps<{
  databases: ApiDatabaseDescriptor[];
  sessions: ApiChatSessionRead[];
  activeDbId: string;
  activeSessionId: string;
  loading: boolean;
  mode?: "chat" | "database" | "dashboards";
  dashboards?: ApiDashboardRead[];
  widgets?: ApiWidgetRead[];
  dashboardView?: "dashboards" | "widgets";
}>();

const emit = defineEmits<{
  (event: "select-database", databaseId: string): void;
  (event: "select-session", sessionId: string): void;
  (event: "create-session", databaseId?: string): void;
  (event: "rename-session", sessionId: string, title: string): void;
  (event: "delete-session", sessionId: string): void;
  (event: "add-database"): void;
  (event: "rename-database", databaseId: string, title: string): void;
  (event: "delete-database", databaseId: string): void;
  (event: "update:dashboardView", value: "dashboards" | "widgets"): void;
}>();

const route = useRoute();
const query = ref("");
const openIds = ref<Set<string>>(new Set());
const isDatabaseMode = computed(() => props.mode === "database");
const isDashboardsMode = computed(() => props.mode === "dashboards");
const isChatMode = computed(
  () => !isDatabaseMode.value && !isDashboardsMode.value,
);
const dashboardView = computed(() => props.dashboardView ?? "dashboards");

const navItems = [
  { to: "/chat", label: "Чат", key: "chat" as const },
  { to: "/dashboards", label: "Дашборды", key: "dashboards" as const },
  { to: "/data", label: "Настройки", key: "data" as const },
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
        (database.description ?? "").toLowerCase().includes(q) ||
        (database.status ?? "").toLowerCase().includes(q) ||
        (database.knowledge_status ?? "").toLowerCase().includes(q);

      if (isDatabaseMode.value) {
        return matchesDatabase ? { ...database, sessions: [] } : null;
      }

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

const dashboardItems = computed(() =>
  dashboardView.value === "widgets"
    ? (props.widgets ?? [])
    : (props.dashboards ?? []),
);

const filteredDashboardItems = computed(() => {
  const q = normalizedQuery.value;
  if (!q) {
    return dashboardItems.value;
  }
  return dashboardItems.value.filter((item) => {
    if ("visualization_type" in item) {
      return [
        item.title,
        item.description ?? "",
        item.visualization_type,
        item.refresh_policy,
      ].some((value) => String(value).toLowerCase().includes(q));
    }
    return [
      item.title,
      item.description ?? "",
      item.slug ?? "",
      item.layout_type,
    ].some((value) => String(value).toLowerCase().includes(q));
  });
});

watch(
  () => props.activeDbId,
  (id) => {
    if (id) {
      openIds.value = new Set([...openIds.value, id]);
    }
  },
  { immediate: true },
);

watch(
  () => props.activeSessionId,
  (sessionId) => {
    const session = props.sessions.find((item) => item.id === sessionId);
    if (session?.database_connection_id) {
      openIds.value = new Set([
        ...openIds.value,
        session.database_connection_id,
      ]);
    }
  },
  { immediate: true },
);

watch(
  () => props.dashboardView,
  (value) => {
    if (value === "dashboards" || value === "widgets") {
      query.value = "";
    }
  },
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
  },
);

function isRouteActive(key: "chat" | "dashboards" | "data") {
  const path = route.path;
  if (key === "chat") {
    return (
      path === "/chat" ||
      path.startsWith("/notebooks") ||
      path === "/colab" ||
      path === "/notebook"
    );
  }
  if (key === "dashboards") {
    return (
      path.startsWith("/dashboards") ||
      path.startsWith("/widgets") ||
      path.startsWith("/widget/")
    );
  }
  return path === "/data" || path.startsWith("/data");
}

function isOpen(id: string) {
  return openIds.value.has(id);
}

function toggle(id: string) {
  if (isDatabaseMode.value) {
    selectDatabase(id);
    return;
  }
  const next = new Set(openIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  openIds.value = next;
  if (id !== props.activeDbId) {
    emit("select-database", id);
  }
}

function selectDatabase(id: string) {
  emit("select-database", id);
}

function toggleDashboardView() {
  emit(
    "update:dashboardView",
    dashboardView.value === "dashboards" ? "widgets" : "dashboards",
  );
}

function isDashboardItemActive(id: string) {
  if (!isDashboardsMode.value) {
    return false;
  }
  if (dashboardView.value === "widgets") {
    return route.path === `/widget/${id}`;
  }
  return route.path === "/dashboards" || route.path === `/dashboards/${id}`;
}

function isWidgetItem(item: DashboardItem): item is ApiWidgetRead {
  return "visualization_type" in item;
}

function isDashboardItem(item: DashboardItem): item is ApiDashboardRead {
  return "layout_type" in item;
}

function isDashboardItemPublic(item: DashboardItem) {
  return isDashboardItem(item) && item.is_public;
}

function isDashboardItemHidden(item: DashboardItem) {
  return isDashboardItem(item) && item.is_hidden;
}

function widgetVisualizationLabel(item: DashboardItem) {
  return isWidgetItem(item) ? translateVisualizationType(item.visualization_type) : "";
}

function itemTitle(item: DashboardItem) {
  return item.title;
}

function itemSubtitle(item: DashboardItem) {
  if (isWidgetItem(item)) {
    return `${translateVisualizationType(item.visualization_type)} · ${translateRefreshPolicy(item.refresh_policy)}`;
  }
  return item.description || "Без описания";
}

function translateVisualizationType(value: string) {
  switch (value) {
    case "table":
      return "Таблица";
    case "bar":
      return "Столбчатая";
    case "line":
      return "Линейная";
    case "area":
      return "Областная";
    case "pie":
      return "Круговая";
    case "metric":
      return "Метрика";
    default:
      return value;
  }
}

function translateRefreshPolicy(value: string) {
  switch (value) {
    case "manual":
      return "Вручную";
    case "scheduled":
      return "По расписанию";
    case "on_view":
      return "При открытии";
    default:
      return value;
  }
}

function translateDatabaseStatus(value?: string | null) {
  switch (value) {
    case "active":
      return "Активна";
    case "connected":
      return "Подключена";
    case "syncing":
      return "Сканируется";
    case "not_scanned":
      return "Не сканировалась";
    case "failed":
      return "Ошибка";
    case "disabled":
      return "Отключена";
    default:
      return value || "Неизвестно";
  }
}

function formatTableCount(count: number) {
  return `${count} табл.`;
}

function folderMetaText(database: TreeDatabase) {
  const parts = [database.dialect];
  if (database.table_count != null) {
    parts.push(formatTableCount(database.table_count));
  }
  return parts.join(" · ");
}

function rename(session: ApiChatSessionRead) {
  const title = window.prompt("Новое название чата", session.title)?.trim();
  if (title) {
    emit("rename-session", session.id, title);
  }
}

function removeSession(session: ApiChatSessionRead) {
  if (window.confirm(`Удалить чат «${session.title}»?`)) {
    emit("delete-session", session.id);
  }
}

function renameDatabase(database: ApiDatabaseDescriptor) {
  const title = window.prompt("Новое название базы", database.name)?.trim();
  if (title) {
    emit("rename-database", database.id, title);
  }
}

function remove(database: ApiDatabaseDescriptor) {
  emit("delete-database", database.id);
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
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
  line-height: 1.1;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.chat-sidebar__nav-link:hover:not(.chat-sidebar__nav-link--active) {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.32);
  background: rgba(112, 59, 247, 0.12);
}

.chat-sidebar__nav-link--active {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.22);
}

.chat-sidebar__section {
  min-height: 0;
  flex: 1 1 auto;
}

.chat-sidebar__panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(
      circle at top right,
      rgba(138, 180, 248, 0.08),
      transparent 28%
    ),
    linear-gradient(180deg, rgba(26, 29, 36, 0.96), rgba(18, 20, 27, 0.98));
  padding: 12px;
  box-shadow: var(--shadow-soft);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  height: 100%;
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
  line-height: 1.1;
  white-space: nowrap;
  transition:
    background 180ms ease,
    border-color 180ms ease;
}

.chat-sidebar__new:hover:not(:disabled) {
  border-color: rgba(112, 59, 247, 0.92);
  background: rgba(112, 59, 247, 0.28);
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
  flex: 1 1 auto;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}

.chat-sidebar__tree--skeleton {
  padding-right: 0;
}

.chat-sidebar__db-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 0.7rem 0.75rem;
  border: 1px solid transparent;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--ink);
  text-align: left;
  transition:
    background 140ms ease,
    border-color 140ms ease,
    transform 140ms ease;
}

.chat-sidebar__db-row--skeleton {
  pointer-events: none;
}

.chat-sidebar__db-row:hover:not(.chat-sidebar__db-row--active) {
  background: rgba(255, 255, 255, 0.05);
}

.chat-sidebar__db-row--active {
  border-color: rgba(112, 59, 247, 0.28);
  background: rgba(112, 59, 247, 0.1);
}

.chat-sidebar__db-row:focus-visible {
  outline: 2px solid rgba(112, 59, 247, 0.55);
  outline-offset: 2px;
}

.chat-sidebar__db-icon {
  color: var(--accent);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
}

.chat-sidebar__db-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-sidebar__db-name {
  font-size: 0.88rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__db-sub {
  margin-top: 0.12rem;
  color: var(--muted-2);
  font-size: 0.72rem;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__db-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 0;
}

.chat-sidebar__db-pill {
  min-height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.68rem;
  display: inline-flex;
  align-items: center;
}

.chat-sidebar__db-pill--connected,
.chat-sidebar__db-pill--active {
  border-color: rgba(129, 201, 149, 0.35);
  color: #aef0c2;
}

.chat-sidebar__db-pill--syncing,
.chat-sidebar__db-pill--not_scanned {
  border-color: rgba(248, 182, 94, 0.35);
  color: #f4c26b;
}

.chat-sidebar__db-time {
  color: var(--muted-2);
  font-size: 0.66rem;
  white-space: nowrap;
}

.chat-sidebar__db-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.chat-sidebar__folder {
  display: flex;
  flex-direction: column;
  border: 1px solid transparent;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
  min-height: 0;
}

.chat-sidebar__folder--skeleton {
  pointer-events: none;
}

.chat-sidebar__folder--active {
  border-color: rgba(112, 59, 247, 0.28);
  background: rgba(112, 59, 247, 0.08);
}

.chat-sidebar__folder-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  width: 100%;
  padding: 0.55rem 0.6rem;
  border: none;
  background: transparent;
  color: var(--ink);
  text-align: left;
  font-size: 0.84rem;
  transition: background 140ms ease;
}

.chat-sidebar__folder-head--skeleton {
  pointer-events: none;
}

.chat-sidebar__folder:not(.chat-sidebar__folder--active) .chat-sidebar__folder-head:hover {
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

.chat-sidebar__folder-name-skeleton {
  flex: 1;
}

.chat-sidebar__folder-meta {
  flex: 0 1 42%;
  min-width: 0;
  color: var(--muted-2);
  font-size: 0.7rem;
  letter-spacing: 0.03em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: right;
}

.chat-sidebar__folder-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 0 0.6rem 0.65rem 1.2rem;
}

.chat-sidebar__folder--active.chat-sidebar__folder--open .chat-sidebar__folder-body {
  max-height: min(42vh, 24rem);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.chat-sidebar__empty-branch {
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
  min-height: 0;
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
  cursor: pointer;
}

.chat-sidebar__session--skeleton {
  pointer-events: none;
}

.chat-sidebar__session:hover:not(.chat-sidebar__session--active) {
  background: rgba(255, 255, 255, 0.04);
}

.chat-sidebar__session--active {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.chat-sidebar__session--create {
  color: var(--muted);
  flex-shrink: 0;
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
  line-height: 1.1;
  text-decoration: none;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.chat-sidebar__footer-btn:hover {
  color: var(--ink-strong);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
}

.chat-sidebar__footer-btn--accent {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

.chat-sidebar__footer-btn--accent:hover {
  border-color: rgba(112, 59, 247, 0.92);
  background: rgba(112, 59, 247, 0.32);
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
