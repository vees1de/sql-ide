<template>
  <main class="dashboards-shell">
    <aside class="dashboards-shell__sidebar">
      <ChatSidebar
        mode="dashboards"
        v-model:dashboardView="sidebarMode"
        :dashboards="dashboardsStore.dashboards"
        :loading="dashboardsStore.loading || widgetsStore.loading"
        :active-db-id="''"
        :active-session-id="''"
        :databases="[]"
        :widgets="widgetsStore.widgets"
        :sessions="[]"
        @select-database="() => {}"
        @select-session="() => {}"
        @create-session="() => {}"
        @rename-session="() => {}"
        @delete-session="() => {}"
        @add-database="() => {}"
        @rename-database="() => {}"
        @delete-database="() => {}"
      />
    </aside>

    <section class="dashboards-shell__content app-route-section">
      <div class="dashboards-list-view">
        <div
          class="dashboards-list-view__panel dashboards-list-view__panel--hero"
        >
          <div class="dashboards-list-view__header">
            <div class="dashboards-list-view__header-copy">
              <p
                v-if="sidebarMode === 'dashboards'"
                class="dashboards-list-view__hero-note"
              >
                {{ heroTagline }}
              </p>
            </div>
            <div class="dashboards-list-view__header-actions">
              <label
                v-if="sidebarMode === 'dashboards'"
                class="dashboards-list-view__toggle"
              >
                <input
                  :checked="dashboardsStore.includeHidden"
                  type="checkbox"
                  @change="toggleHidden"
                />
                <span>Показывать скрытые</span>
              </label>
              <router-link
                v-if="sidebarMode === 'dashboards'"
                to="/dashboards/new"
                class="wbtn wbtn--primary"
              >
                + Новый дашборд
              </router-link>
              <router-link v-else to="/widgets" class="wbtn wbtn--primary">
                Открыть каталог
              </router-link>
            </div>
          </div>
        </div>

        <div
          class="dashboards-list-view__panel dashboards-list-view__panel--content"
        >
          <div
            v-if="sidebarMode === 'dashboards'"
            class="dashboards-list-view__panel-content"
          >
            <div
              v-if="dashboardsStore.loading"
              class="dashboards-list-view__hint"
            ></div>
            <div
              v-else-if="!dashboardsStore.dashboards.length"
              class="dashboards-list-view__empty"
            >
              <p>Дашбордов пока нет.</p>
            </div>
            <div v-else class="dashboards-list-view__grid">
              <router-link
                v-for="dashboard in dashboardsStore.dashboards"
                :key="dashboard.id"
                :to="`/dashboards/${dashboard.id}`"
                class="dashboards-list-view__card"
              >
                <div class="dashboards-list-view__card-header">
                  <span class="dashboards-list-view__card-title">{{
                    dashboard.title
                  }}</span>
                  <span
                    v-if="dashboard.is_public"
                    class="dashboards-list-view__card-badge"
                    >публичный</span
                  >
                  <span
                    v-if="dashboard.is_hidden"
                    class="dashboards-list-view__card-badge dashboards-list-view__card-badge--muted"
                    >скрытый</span
                  >
                </div>
                <p
                  v-if="dashboard.description"
                  class="dashboards-list-view__card-desc"
                >
                  {{ dashboard.description }}
                </p>
                <span class="dashboards-list-view__card-updated">{{
                  formatDate(dashboard.updated_at)
                }}</span>
              </router-link>
            </div>
          </div>

          <div v-else class="dashboards-list-view__panel-content">
            <div v-if="widgetsStore.loading" class="dashboards-list-view__hint">
              Загрузка виджетов…
            </div>
            <div
              v-else-if="!widgetsStore.widgets.length"
              class="dashboards-list-view__empty"
            >
              <p>Графиков пока нет.</p>
              <p class="dashboards-list-view__hint-sub">
                Сохраните график из чата, чтобы он появился здесь.
              </p>
            </div>
            <div
              v-else
              class="dashboards-list-view__grid dashboards-list-view__grid--widgets"
            >
              <router-link
                v-for="widget in widgetsStore.widgets"
                :key="widget.id"
                :to="`/widget/${widget.id}`"
                class="dashboards-list-view__card"
              >
                <div class="dashboards-list-view__card-header">
                  <span class="dashboards-list-view__card-title">{{
                    widget.title
                  }}</span>
                  <span class="dashboards-list-view__card-badge">{{
                    translateVisualizationType(widget.visualization_type)
                  }}</span>
                </div>
                <p
                  v-if="widget.description"
                  class="dashboards-list-view__card-desc"
                >
                  {{ widget.description }}
                </p>
                <span class="dashboards-list-view__card-updated">{{
                  formatDate(widget.updated_at)
                }}</span>
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import ChatSidebar from "@/components/chat/ChatSidebar.vue";
import { useDashboardsStore } from "@/stores/dashboards";
import { useWidgetsStore } from "@/stores/widgets";

const dashboardsStore = useDashboardsStore();
const widgetsStore = useWidgetsStore();
const sidebarMode = ref<"dashboards" | "widgets">("dashboards");
const heroTagline =
  "\u0414\u0430\u0448\u0431\u043e\u0440\u0434 \u043f\u0440\u043e\u0434\u0430\u0436 \u0438 \u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0438";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function toggleHidden(event: Event) {
  const target = event.target as HTMLInputElement;
  await dashboardsStore.setIncludeHidden(target.checked);
}

onMounted(() => {
  void Promise.all([
    dashboardsStore.loadDashboards(),
    widgetsStore.loadWidgets(),
  ]);
});

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
</script>

<style scoped lang="scss">
.dashboards-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--app-shell-sidebar-width) minmax(0, 1fr);
  gap: var(--app-shell-gap);
  background: var(--bg);
  padding: var(--app-shell-gap);
  transition: grid-template-columns 220ms ease;
}

.dashboards-shell__sidebar {
  min-height: 0;
  width: var(--app-shell-sidebar-width);
  max-width: 100%;
  transition: width 220ms ease;
}

.dashboards-shell__content {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.dashboards-list-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.dashboards-list-view__panel {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 0 16px;
  box-shadow: var(--shadow-soft);
}

.dashboards-list-view__panel--hero {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.dashboards-list-view__panel--content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dashboards-list-view__panel-content {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dashboards-list-view__eyebrow {
  margin: 0 0 0.15rem;
  color: var(--muted-2);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.dashboards-list-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.dashboards-list-view__header-copy {
  min-width: 0;
}

.dashboards-list-view__header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.dashboards-list-view__hero-note {
  padding-inline-start: 0.9rem;
  border-inline-start: 1px solid
    color-mix(in srgb, var(--accent) 40%, var(--line));
  color: var(--muted-2);
  font-size: 0.84rem;
  line-height: 1.5;
}

.dashboards-list-view__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.78rem;
}

.dashboards-list-view__heading {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--ink-strong);
  margin: 0;
}

.dashboards-list-view__hint {
  color: var(--muted);
  font-size: 0.85rem;
}

.dashboards-list-view__empty {
  flex: 1;
  padding: 48px;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  color: var(--muted);
  font-size: 0.9rem;
  display: grid;
  place-items: center;
  align-content: center;
}

.dashboards-list-view__empty p {
  margin: 0;
}

.dashboards-list-view__hint-sub {
  margin-top: 6px;
  font-size: 0.8rem;
  opacity: 0.7;
}

.dashboards-list-view__grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  align-content: start;
}

.dashboards-list-view__grid--widgets {
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

.dashboards-list-view__card {
  position: relative;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  padding: 16px;
  text-decoration: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background-color: var(--bg);

  &:hover {
    border-color: color-mix(in srgb, var(--accent) 24%, var(--line-strong));
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--accent) 12%, transparent),
        transparent 96px
      ),
      var(--surface);
    transform: translateY(-1px);
  }
}

.dashboards-list-view__card-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}

.dashboards-list-view__card-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.dashboards-list-view__card-badge {
  font-size: 0.68rem;
  color: var(--accent-strong);
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.dashboards-list-view__card-badge--muted {
  color: var(--muted);
  background: var(--line);
}

.dashboards-list-view__card-desc {
  font-size: 0.78rem;
  color: var(--muted);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.dashboards-list-view__card-updated {
  font-size: 0.7rem;
  color: var(--muted);
  margin-top: auto;
}

.wbtn {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.wbtn--primary {
  background: rgba(112, 59, 247, 0.85);
  color: #fff;
  font-weight: 600;
  &:hover {
    background: rgba(112, 59, 247, 1);
  }
}

@media (max-width: 980px) {
  .dashboards-shell {
    grid-template-columns: 1fr;
  }
}
</style>
