<template>
  <aside
    class="chat-sidebar"
    :class="{ 'chat-sidebar--collapsed': isCollapsed }"
  >
    <div class="chat-sidebar__top">
      <div class="chat-sidebar__top-bar">
        <RouterLink to="/chat" class="chat-sidebar__brand" title="BimsDash">
          <img src="../../assets/logo.svg" />
          <img v-if="!isCollapsed" src="../../assets/BimsDash.svg" />
        </RouterLink>

        <button
          class="chat-sidebar__rail-toggle"
          type="button"
          :title="isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'"
          :aria-label="isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'"
          :aria-expanded="!isCollapsed"
          @click="toggleSidebarRail"
        >
          <img src="../../assets//togglesidebar.svg" alt="" />
        </button>
      </div>

      <nav class="chat-sidebar__nav" aria-label="Навигация">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="chat-sidebar__nav-link"
          :class="{ 'chat-sidebar__nav-link--active': isRouteActive(item.key) }"
          :title="item.label"
          :aria-label="item.label"
        >
          <span
            class="chat-sidebar__nav-icon"
            aria-hidden="true"
            v-if="isCollapsed"
          >
            <svg
              v-if="item.key === 'chat'"
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
              />
            </svg>
            <svg
              v-else-if="item.key === 'dashboards'"
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="4" y="4" width="7" height="7" rx="1.5" />
              <rect x="13" y="4" width="7" height="7" rx="1.5" />
              <rect x="4" y="13" width="7" height="7" rx="1.5" />
              <rect x="13" y="13" width="7" height="7" rx="1.5" />
            </svg>
            <svg
              v-else
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <ellipse cx="12" cy="5" rx="8" ry="3" />
              <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
              <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
            </svg>
          </span>
          <span class="chat-sidebar__nav-label">{{ item.label }}</span>
        </RouterLink>
      </nav>
    </div>

    <Transition name="chat-sidebar-panel">
      <section
        v-if="!isCollapsed"
        class="chat-sidebar__section chat-sidebar__section--tree"
      >
        <div
          class="chat-sidebar__panel"
          :class="{
            'chat-sidebar__panel--chat': isChatMode,
            'chat-sidebar__panel--sources': isDatabaseMode,
            'chat-sidebar__panel--dashboards': isDashboardsMode,
          }"
        >
          <template v-if="isDatabaseMode">
            <div class="chat-sidebar__search-wrap">
              <input
                v-model="query"
                class="chat-sidebar__search"
                type="search"
                placeholder="Поиск баз"
              />
            </div>
          </template>

          <template v-else-if="isDashboardsMode">
            <div class="chat-sidebar__search-wrap">
              <input
                v-model="query"
                class="chat-sidebar__search"
                type="search"
                placeholder="Поиск дашбордов и виджетов"
              />
            </div>
          </template>
          <div v-if="showLoadingState" class="chat-sidebar__state">
            {{
              isDatabaseMode
                ? "Загружаю список баз…"
                : isDashboardsMode
                  ? "Загружаю навигацию…"
                  : "Загружаю дерево чатов…"
            }}
          </div>

          <div
            v-else-if="isDashboardsMode && !dashboards.length"
            class="chat-sidebar__state"
          >
            Дашбордов пока нет
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
            v-else-if="isDashboardsMode && !dashboardTree.length"
            class="chat-sidebar__state"
          >
            Ничего не найдено
          </div>

          <div v-else class="chat-sidebar__tree">
            <template v-if="isDashboardsMode">
              <div
                v-for="item in dashboardTree"
                :key="item.dashboard.id"
                class="chat-sidebar__dashboard-group"
              >
                <div
                  class="chat-sidebar__db-row chat-sidebar__dashboard-link"
                  :class="{
                    'chat-sidebar__db-row--active': isDashboardRouteActive(
                      item.dashboard.id,
                    ),
                    'chat-sidebar__dashboard-link--expanded':
                      isDashboardExpanded(item.dashboard.id),
                  }"
                >
                  <button
                    class="chat-sidebar__dashboard-toggle"
                    :class="{
                      'chat-sidebar__dashboard-toggle--open':
                        isDashboardExpanded(item.dashboard.id),
                    }"
                    type="button"
                    :aria-expanded="isDashboardExpanded(item.dashboard.id)"
                    :aria-label="
                      isDashboardExpanded(item.dashboard.id)
                        ? 'Свернуть виджеты'
                        : 'Показать виджеты'
                    "
                    @click.stop="toggleDashboardExpand(item.dashboard.id)"
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
                  </button>

                  <RouterLink
                    :to="`/dashboards/${item.dashboard.id}`"
                    class="chat-sidebar__dashboard-main"
                  >
                    <span class="chat-sidebar__db-text">
                      <span class="chat-sidebar__db-name">{{
                        dashboardTitle(item.dashboard)
                      }}</span>
                      <span class="chat-sidebar__db-sub">{{
                        dashboardSubtitle(item.dashboard)
                      }}</span>
                    </span>

                    <span class="chat-sidebar__db-meta">
                      <span
                        v-if="isDashboardPublic(item.dashboard)"
                        class="chat-sidebar__db-pill chat-sidebar__db-pill--accent"
                      >
                        Публичный
                      </span>
                      <span
                        v-if="isDashboardHidden(item.dashboard)"
                        class="chat-sidebar__db-pill"
                      >
                        Скрытый
                      </span>
                      <span
                        v-if="dashboardWidgetCountLabel(item.dashboard.id)"
                        class="chat-sidebar__db-time"
                      >
                        {{ dashboardWidgetCountLabel(item.dashboard.id) }}
                      </span>
                    </span>
                  </RouterLink>
                </div>

                <div
                  v-if="isDashboardExpanded(item.dashboard.id)"
                  class="chat-sidebar__dashboard-body"
                >
                  <div
                    v-if="isDashboardWidgetsLoading(item.dashboard.id)"
                    class="chat-sidebar__dashboard-state"
                  >
                    Загружаю виджеты…
                  </div>
                  <div
                    v-else-if="dashboardWidgetsErrorMessage(item.dashboard.id)"
                    class="chat-sidebar__dashboard-state"
                  >
                    {{ dashboardWidgetsErrorMessage(item.dashboard.id) }}
                  </div>
                  <div
                    v-else-if="!item.widgets.length"
                    class="chat-sidebar__dashboard-state"
                  >
                    Виджетов пока нет
                  </div>
                  <div v-else class="chat-sidebar__dashboard-widgets">
                    <RouterLink
                      v-for="widget in item.widgets"
                      :key="widget.id"
                      :to="`/widget/${widget.widget.id}`"
                      class="chat-sidebar__db-row chat-sidebar__db-row--widget"
                      :class="{
                        'chat-sidebar__db-row--active': isWidgetRouteActive(
                          widget.widget.id,
                        ),
                      }"
                    >
                      <span class="chat-sidebar__db-text">
                        <span class="chat-sidebar__db-name">{{
                          dashboardWidgetTitle(widget)
                        }}</span>
                      </span>

                      <span class="chat-sidebar__db-meta">
                        <span class="chat-sidebar__db-pill">
                          {{ widgetVisualizationLabel(widget.widget) }}
                        </span>
                      </span>
                    </RouterLink>
                  </div>
                </div>
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
                  'chat-sidebar__db-row--active': isDashboardItemActive(
                    item.id,
                  ),
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
                  <span class="chat-sidebar__db-name">{{
                    itemTitle(item)
                  }}</span>
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
                      В· {{ formatTableCount(database.table_count) }}</span
                    >
                    <span v-if="database.description"
                      >В· {{ database.description }}</span
                    >
                  </span>
                </span>

                <span class="chat-sidebar__db-meta">
                  <span
                    class="chat-sidebar__db-pill"
                    :class="`chat-sidebar__db-pill--${database.status}`"
                  >
                    {{
                      translateDatabaseStatus(
                        database.knowledge_status || database.status,
                      )
                    }}
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
                    :disabled="database.is_builtin"
                    @click.stop="renameDatabase(database)"
                  >
                    ✎
                  </button>
                  <button
                    class="chat-sidebar__icon-btn"
                    type="button"
                    title="Удалить"
                    aria-label="Удалить"
                    :disabled="database.is_builtin"
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
                      @click="selectSession(session.id)"
                      @keydown.enter.prevent="selectSession(session.id)"
                      @keydown.space.prevent="selectSession(session.id)"
                    >
                      <span
                        class="chat-sidebar__session-icon"
                        aria-hidden="true"
                      >
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

          <button
            v-if="isDatabaseMode"
            class="chat-sidebar__new chat-sidebar__new--sources"
            type="button"
            @click="$emit('add-database')"
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
            Добавить базу данных
          </button>

          <button
            v-if="isChatMode"
            class="chat-sidebar__new chat-sidebar__new--chat"
            type="button"
            :disabled="!activeDbId"
            @click="$emit('create-session', activeDbId)"
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
            Новый чат
          </button>
        </div>
      </section>
    </Transition>

    <footer class="chat-sidebar__footer">
      <RouterLink
        v-if="isDashboardsMode"
        class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent chat-sidebar__footer-btn--dashboard"
        :to="dashboardView === 'widgets' ? '/widgets' : '/dashboards/new'"
        :title="
          dashboardView === 'widgets' ? 'Каталог виджетов' : 'Новый дашборд'
        "
        :aria-label="
          dashboardView === 'widgets' ? 'Каталог виджетов' : 'Новый дашборд'
        "
      >
        {{ dashboardView === "widgets" ? "Каталог виджетов" : "Новый дашборд" }}
        <span class="chat-sidebar__footer-icon" aria-hidden="true">
          <svg
            v-if="dashboardView === 'widgets'"
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
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
        </span>
        <span class="chat-sidebar__footer-label">
          {{
            dashboardView === "widgets" ? "Каталог виджетов" : "Новый дашборд"
          }}
        </span>
      </RouterLink>
      <button
        v-else
        class="chat-sidebar__footer-btn chat-sidebar__footer-btn--accent"
        type="button"
        title="Профиль"
        aria-label="Профиль"
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
        <span class="chat-sidebar__footer-label">Профиль</span>
        Профиль
      </button>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api } from "@/api/client";
import type {
  ApiChatSessionRead,
  ApiDashboardRead,
  ApiDashboardWidgetDetail,
  ApiDatabaseDescriptor,
  ApiWidgetRead,
} from "@/api/types";

type TreeDatabase = ApiDatabaseDescriptor & { sessions: ApiChatSessionRead[] };
type DashboardTreeItem = {
  dashboard: ApiDashboardRead;
  widgets: ApiDashboardWidgetDetail[];
};

const SIDEBAR_COLLAPSED_LS_KEY = "app-chat-sidebar-collapsed";
const SIDEBAR_WIDTH_EXPANDED = "200px";
const SIDEBAR_WIDTH_COLLAPSED = "56px";

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
const expandedDashboardIds = ref<Set<string>>(new Set());
const dashboardWidgetsById = ref<Record<string, ApiDashboardWidgetDetail[]>>(
  {},
);
const dashboardWidgetsLoading = ref<Record<string, boolean>>({});
const dashboardWidgetsError = ref<Record<string, string>>({});
const isCollapsed = ref(
  typeof window !== "undefined"
    ? window.localStorage.getItem(SIDEBAR_COLLAPSED_LS_KEY) === "true"
    : false,
);
const isDatabaseMode = computed(() => props.mode === "database");
const isDashboardsMode = computed(() => props.mode === "dashboards");
const isChatMode = computed(() => (props.mode ?? "chat") === "chat");
const dashboardView = computed(() => props.dashboardView ?? "dashboards");
const sectionTitleByMode = {
  chat: "Чаты",
  database: "Базы данных",
  dashboards: "Дашборды",
} as const;
const sectionTitle = computed(() => sectionTitleByMode[props.mode ?? "chat"]);

const navItems = [
  { to: "/chat", label: "Чат", key: "chat" as const },
  { to: "/dashboards", label: "Дашборды", key: "dashboards" as const },
  { to: "/data", label: "Источники", key: "data" as const },
];

const normalizedQuery = computed(() => query.value.trim().toLowerCase());

watch(
  isCollapsed,
  (value) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_LS_KEY, String(value));
    }
    if (typeof document !== "undefined") {
      document.documentElement.style.setProperty(
        "--app-shell-sidebar-width",
        value ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED,
      );
    }
  },
  { immediate: true },
);

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

const dashboards = computed(() => props.dashboards ?? []);

const hasSessionsForActiveDatabase = computed(() => {
  if (!props.activeDbId) {
    return props.sessions.length > 0;
  }

  return props.sessions.some(
    (session) => session.database_connection_id === props.activeDbId,
  );
});

const showLoadingState = computed(() => {
  if (!props.loading) {
    return false;
  }

  if (isDashboardsMode.value) {
    return dashboards.value.length === 0;
  }

  if (isDatabaseMode.value) {
    return props.databases.length === 0;
  }

  return props.databases.length === 0 || !hasSessionsForActiveDatabase.value;
});

const dashboardTree = computed<DashboardTreeItem[]>(() => {
  const q = normalizedQuery.value;
  return dashboards.value
    .map((dashboard) => {
      const widgets = dashboardWidgetsById.value[dashboard.id] ?? [];
      const matchedWidgets = q
        ? widgets.filter((item) => matchesDashboardWidgetQuery(item, q))
        : widgets;
      const matchesDashboard = !q || matchesDashboardQuery(dashboard, q);

      if (!matchesDashboard && !matchedWidgets.length) {
        return null;
      }

      return {
        dashboard,
        widgets: matchesDashboard ? widgets : matchedWidgets,
      };
    })
    .filter((item): item is DashboardTreeItem => Boolean(item));
});

watch(
  () => props.activeDbId,
  (id) => {
    if (id) {
      openIds.value = new Set([id]);
    }
  },
  { immediate: true },
);

watch(
  () => props.activeSessionId,
  (sessionId) => {
    const session = props.sessions.find((item) => item.id === sessionId);
    if (session?.database_connection_id) {
      openIds.value = new Set([session.database_connection_id]);
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

    if (isDashboardsMode.value) {
      void ensureAllDashboardWidgetsLoaded().then(() => {
        expandedDashboardIds.value = new Set(
          dashboards.value.map((item) => item.id),
        );
      });
      return;
    }

    const nextOpenId =
      treeDatabases.value.find((database) => database.id === props.activeDbId)
        ?.id ??
      treeDatabases.value[0]?.id ??
      "";
    openIds.value = nextOpenId ? new Set([nextOpenId]) : new Set();
  },
);

watch(
  dashboards,
  (items) => {
    const ids = new Set(items.map((item) => item.id));
    expandedDashboardIds.value = new Set(
      [...expandedDashboardIds.value].filter((id) => ids.has(id)),
    );
    dashboardWidgetsById.value = Object.fromEntries(
      Object.entries(dashboardWidgetsById.value).filter(([id]) => ids.has(id)),
    );
    dashboardWidgetsLoading.value = Object.fromEntries(
      Object.entries(dashboardWidgetsLoading.value).filter(([id]) =>
        ids.has(id),
      ),
    );
    dashboardWidgetsError.value = Object.fromEntries(
      Object.entries(dashboardWidgetsError.value).filter(([id]) => ids.has(id)),
    );
  },
  { immediate: true },
);

watch(
  () => route.path,
  (path) => {
    if (!isDashboardsMode.value) {
      return;
    }

    if (path.startsWith("/dashboards/")) {
      const dashboardId = String(route.params.id ?? "");
      if (!dashboardId || dashboardId === "new") {
        return;
      }
      expandedDashboardIds.value = new Set([
        ...expandedDashboardIds.value,
        dashboardId,
      ]);
      void ensureDashboardWidgetsLoaded(dashboardId);
      return;
    }

    if (path.startsWith("/widget/")) {
      const widgetId = String(route.params.id ?? "");
      if (!widgetId) {
        return;
      }
      void expandDashboardForWidget(widgetId);
    }
  },
  { immediate: true },
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

function toggleSidebarRail() {
  isCollapsed.value = !isCollapsed.value;
}

function isOpen(id: string) {
  return openIds.value.has(id);
}

function toggle(id: string) {
  if (isDatabaseMode.value) {
    selectDatabase(id);
    return;
  }
  openIds.value = openIds.value.has(id) ? new Set() : new Set([id]);
  if (id !== props.activeDbId) {
    emit("select-database", id);
  }
}

function selectDatabase(id: string) {
  emit("select-database", id);
}

function selectSession(sessionId: string) {
  if (!sessionId || sessionId === props.activeSessionId) {
    return;
  }

  emit("select-session", sessionId);
}

function isDashboardExpanded(id: string) {
  return expandedDashboardIds.value.has(id);
}

function toggleDashboardExpand(id: string) {
  const next = new Set(expandedDashboardIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
    void ensureDashboardWidgetsLoaded(id);
  }
  expandedDashboardIds.value = next;
}

function isDashboardRouteActive(id: string) {
  return route.path === `/dashboards/${id}`;
}

function isWidgetRouteActive(id: string) {
  return route.path === `/widget/${id}`;
}

function isDashboardPublic(item: ApiDashboardRead) {
  return item.is_public;
}

function isDashboardHidden(item: ApiDashboardRead) {
  return item.is_hidden;
}

function dashboardTitle(item: ApiDashboardRead) {
  return item.title;
}

function dashboardSubtitle(item: ApiDashboardRead) {
  return item.description || "Без описания";
}

function dashboardWidgetTitle(item: ApiDashboardWidgetDetail) {
  return item.title_override || item.widget.title;
}

function dashboardWidgetSubtitle(item: ApiDashboardWidgetDetail) {
  return `${translateVisualizationType(item.widget.visualization_type)} В· ${translateRefreshPolicy(item.widget.refresh_policy)}`;
}

function widgetVisualizationLabel(item: ApiWidgetRead) {
  return translateVisualizationType(item.visualization_type);
}

function dashboardWidgetCountLabel(dashboardId: string) {
  const count = dashboardWidgetsById.value[dashboardId]?.length;
  if (count == null) {
    return "";
  }
  if (count % 10 === 1 && count % 100 !== 11) {
    return `${count} виджет`;
  }
  if (
    count % 10 >= 2 &&
    count % 10 <= 4 &&
    (count % 100 < 12 || count % 100 > 14)
  ) {
    return `${count} виджета`;
  }
  return `${count} виджетов`;
}

function isDashboardWidgetsLoading(id: string) {
  return Boolean(dashboardWidgetsLoading.value[id]);
}

function dashboardWidgetsErrorMessage(id: string) {
  return dashboardWidgetsError.value[id] ?? "";
}

function matchesDashboardQuery(item: ApiDashboardRead, q: string) {
  return [
    item.title,
    item.description ?? "",
    item.slug ?? "",
    item.layout_type,
  ].some((value) => String(value).toLowerCase().includes(q));
}

function matchesDashboardWidgetQuery(
  item: ApiDashboardWidgetDetail,
  q: string,
) {
  return [
    item.title_override ?? "",
    item.widget.title,
    item.widget.description ?? "",
    item.widget.visualization_type,
    item.widget.refresh_policy,
  ].some((value) => String(value).toLowerCase().includes(q));
}

async function ensureDashboardWidgetsLoaded(id: string) {
  if (dashboardWidgetsById.value[id] || dashboardWidgetsLoading.value[id]) {
    return;
  }

  dashboardWidgetsLoading.value = {
    ...dashboardWidgetsLoading.value,
    [id]: true,
  };
  dashboardWidgetsError.value = {
    ...dashboardWidgetsError.value,
    [id]: "",
  };

  try {
    const detail = await api.getDashboard(id);
    dashboardWidgetsById.value = {
      ...dashboardWidgetsById.value,
      [id]: detail.widgets,
    };
  } catch (error) {
    dashboardWidgetsError.value = {
      ...dashboardWidgetsError.value,
      [id]:
        error instanceof Error
          ? error.message
          : "Не удалось загрузить виджеты.",
    };
  } finally {
    dashboardWidgetsLoading.value = {
      ...dashboardWidgetsLoading.value,
      [id]: false,
    };
  }
}

async function ensureAllDashboardWidgetsLoaded() {
  await Promise.all(
    dashboards.value.map((item) => ensureDashboardWidgetsLoaded(item.id)),
  );
}

async function expandDashboardForWidget(widgetId: string) {
  await ensureAllDashboardWidgetsLoaded();
  for (const [dashboardId, widgets] of Object.entries(
    dashboardWidgetsById.value,
  )) {
    if (widgets.some((item) => item.widget.id === widgetId)) {
      expandedDashboardIds.value = new Set([
        ...expandedDashboardIds.value,
        dashboardId,
      ]);
      return;
    }
  }
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
  return parts.join(" В· ");
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
  transition: width 220ms ease;
}

.chat-sidebar__top {
  display: flex;
  flex-direction: column;
  gap: 24px;
  flex: 0 0 auto;
}

.chat-sidebar__top-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-sidebar__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 auto;
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
  white-space: nowrap;
  overflow: hidden;
  max-width: 180px;
  transition:
    max-width 220ms ease,
    opacity 180ms ease,
    transform 220ms ease;
}

.chat-sidebar__rail-toggle {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: inline-grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--muted);
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.chat-sidebar__rail-toggle:hover {
  color: var(--ink-strong);
}

.chat-sidebar__rail-toggle img {
  transition: transform 220ms ease;
}

.chat-sidebar__nav {
  display: grid;
  gap: 16px;
}

.chat-sidebar__nav-link {
  color: var(--muted);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  font-size: 1rem;
  line-height: 1;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.chat-sidebar__nav-link:hover:not(.chat-sidebar__nav-link--active) {
  color: var(--ink-strong);
}

.chat-sidebar__nav-link--active {
  color: var(--ink);
  font-size: 1.1rem;
}

.chat-sidebar__nav-icon {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;

  svg {
    width: 20px;
    height: 20px;
  }
}

.chat-sidebar__nav-label {
  white-space: nowrap;
  overflow: hidden;
  max-width: 120px;
  transition:
    max-width 220ms ease,
    opacity 180ms ease,
    transform 220ms ease;
}

.chat-sidebar__section {
  min-height: 0;
  flex: 1 1 auto;
  overflow: hidden;
}

.chat-sidebar__panel {
  display: flex;
  flex-direction: column;
}

.chat-sidebar__panel--chat,
.chat-sidebar__panel--sources,
.chat-sidebar__panel--dashboards {
  border: none;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0;
  gap: 12px;
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
  line-height: 1;
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

.chat-sidebar__new--sources,
.chat-sidebar__new--chat {
  display: flex;
  justify-content: center;
  width: 100%;
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

.chat-sidebar__dashboard-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-sidebar__dashboard-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0.62rem 0.68rem 0.62rem 0.56rem;
}

.chat-sidebar__dashboard-link--expanded {
  padding-left: 0.46rem;
}

.chat-sidebar__dashboard-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
  color: inherit;
  text-decoration: none;
}

.chat-sidebar__dashboard-main .chat-sidebar__db-meta {
  margin-left: auto;
  justify-content: flex-end;
  align-self: center;
}

.chat-sidebar__dashboard-main:focus-visible {
  outline: 2px solid rgba(112, 59, 247, 0.55);
  outline-offset: 2px;
  border-radius: 10px;
}

.chat-sidebar__dashboard-toggle {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  transition:
    background 140ms ease,
    border-color 140ms ease,
    color 140ms ease;
}

.chat-sidebar__dashboard-toggle:hover {
  color: var(--ink-strong);
  border-color: var(--line);
  background: rgba(255, 255, 255, 0.04);
}

.chat-sidebar__dashboard-toggle svg {
  transition: transform 160ms ease;
}

.chat-sidebar__dashboard-toggle--open svg {
  transform: rotate(90deg);
}

.chat-sidebar__dashboard-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 10px;
}

.chat-sidebar__dashboard-widgets {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-sidebar__dashboard-state {
  padding: 0.55rem 0.7rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
  color: var(--muted);
  font-size: 0.76rem;
}

.chat-sidebar__db-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas:
    "icon text actions"
    "icon meta actions";
  column-gap: 10px;
  row-gap: 4px;
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
  text-decoration: none;
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

.chat-sidebar__db-row--widget {
  margin-left: 4px;
  padding: 0.62rem 0.7rem;
}

.chat-sidebar__db-row--widget .chat-sidebar__db-icon {
  color: var(--muted-2);
}

.chat-sidebar__db-icon {
  grid-area: icon;
  color: var(--accent);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  align-self: center;
}

.chat-sidebar__db-text {
  grid-area: text;
  display: flex;
  flex-direction: column;
  min-width: 0;
  align-self: center;
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
  white-space: normal;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.chat-sidebar__db-meta {
  grid-area: meta;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 6px 8px;
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
  grid-area: actions;
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  align-self: center;
}

.chat-sidebar__folder {
  display: flex;
  flex-direction: column;
  border: 1px solid #262626;
  border-radius: 12px;
  overflow: hidden;
  background: #262626;
  min-height: 0;
}

.chat-sidebar__folder--active {
  border-color: #2a1f3d;
  background: #262626;
}

.chat-sidebar__folder-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  width: 100%;
  padding: 0.55rem 0.6rem;
  border: none;
  background: #262626;
  color: var(--ink);
  text-align: left;
  font-size: 0.84rem;
  transition: background 140ms ease;
}

.chat-sidebar__folder--active .chat-sidebar__folder-head {
  background: #2a1f3d;
}

.chat-sidebar__folder:not(.chat-sidebar__folder--active)
  .chat-sidebar__folder-head:hover {
  background: #1a1a1a;
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
  align-self: stretch;
  width: min(100%, 200px);
  max-width: 200px;
  gap: 6px;
  min-height: 0;
  padding: 0 0.45rem 0.55rem 0.55rem;
  background: #1a1a1a;
  box-sizing: border-box;
}

.chat-sidebar__folder--active.chat-sidebar__folder--open
  .chat-sidebar__folder-body {
  max-height: min(42vh, 24rem);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.chat-sidebar__empty-branch {
  padding: 0.5rem 0.55rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: #1a1a1a;
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.3;
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
  gap: 0.42rem;
  width: 100%;
  min-width: 0;
  padding: 0.42rem 0.45rem;
  border: none;
  border-radius: 8px;
  background: #262626;
  text-align: left;
  color: var(--ink);
  transition:
    background 140ms ease,
    color 140ms ease,
    transform 140ms ease;
  cursor: pointer;
}

.chat-sidebar__session:hover:not(.chat-sidebar__session--active) {
  background: #1a1a1a;
}

.chat-sidebar__session--active {
  background: #2a1f3d;
  color: var(--ink-strong);
}

.chat-sidebar__session--create {
  background: #1a1a1a;
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
  flex: 0 0 16px;

  svg {
    width: 15px;
    height: 15px;
  }
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
  font-size: 0.78rem;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__session-sub {
  margin-top: 1px;
  font-size: 0.66rem;
  line-height: 1.2;
  color: var(--muted-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-sidebar__session--active .chat-sidebar__session-sub {
  color: rgba(255, 255, 255, 0.72);
}

.chat-sidebar__session-actions {
  display: flex;
  gap: 4px;
  flex: 0 0 auto;
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  transition:
    max-width 140ms ease,
    opacity 140ms ease;
}

.chat-sidebar__session:hover .chat-sidebar__session-actions,
.chat-sidebar__session:focus-within .chat-sidebar__session-actions,
.chat-sidebar__session--active .chat-sidebar__session-actions {
  max-width: 52px;
  opacity: 1;
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

.chat-sidebar__footer-icon {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
}

.chat-sidebar__footer-label {
  display: none;
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
  line-height: 1;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease,
    width 220ms ease,
    padding 220ms ease,
    font-size 180ms ease;
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

.chat-sidebar__footer-btn--dashboard {
  flex-direction: row-reverse;
}

.chat-sidebar__footer-btn--accent:hover {
  border-color: rgba(112, 59, 247, 0.92);
  background: rgba(112, 59, 247, 0.32);
}

.chat-sidebar--collapsed .chat-sidebar__rail-toggle img {
  transform: rotate(180deg);
}

.chat-sidebar--collapsed .chat-sidebar__top {
  width: 100%;
  align-items: center;
}

.chat-sidebar--collapsed .chat-sidebar__top-bar,
.chat-sidebar--collapsed .chat-sidebar__footer {
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}

.chat-sidebar--collapsed .chat-sidebar__top-bar {
  width: 100%;
  gap: 16px;
}

.chat-sidebar--collapsed .chat-sidebar__brand {
  flex: 0 0 auto;
  width: 36px;
  justify-content: center;
}

.chat-sidebar--collapsed .chat-sidebar__brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
}

.chat-sidebar--collapsed {
  justify-content: space-between;
}

.chat-sidebar--collapsed .chat-sidebar__brand-text,
.chat-sidebar--collapsed .chat-sidebar__nav-label {
  max-width: 0;
  opacity: 0;
  transform: translateX(-6px);
}

.chat-sidebar--collapsed .chat-sidebar__nav {
  width: 100%;
  justify-items: center;
}

.chat-sidebar--collapsed .chat-sidebar__rail-toggle,
.chat-sidebar--collapsed .chat-sidebar__nav-link,
.chat-sidebar--collapsed .chat-sidebar__footer-btn {
  width: 36px;
  min-width: 36px;
  padding: 0;
  justify-content: center;
}

.chat-sidebar--collapsed .chat-sidebar__nav-link,
.chat-sidebar--collapsed .chat-sidebar__footer-btn {
  gap: 0;
}

.chat-sidebar--collapsed .chat-sidebar__footer {
  width: 100%;
  justify-content: center;
  gap: 6px;
}

.chat-sidebar--collapsed
  .chat-sidebar__footer
  .chat-sidebar__footer-btn--accent {
  flex: 0 0 auto;
}

.chat-sidebar--collapsed .chat-sidebar__footer-btn {
  font-size: 0;
}

.chat-sidebar-panel-enter-active,
.chat-sidebar-panel-leave-active {
  transition:
    opacity 180ms ease,
    transform 220ms ease;
}

.chat-sidebar-panel-enter-from,
.chat-sidebar-panel-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

@media (max-width: 940px) {
  .chat-sidebar:not(.chat-sidebar--collapsed) .chat-sidebar__nav {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .chat-sidebar:not(.chat-sidebar--collapsed) .chat-sidebar__nav-link {
    justify-content: center;
  }
}
</style>
