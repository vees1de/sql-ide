<template>
  <main class="dashboard-shell">
    <aside class="dashboard-shell__sidebar">
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

    <section class="dashboard-shell__content app-route-section">
      <div class="dashboard-view">
        <template v-if="loading">
          <div class="dashboard-view__skeleton">
            <div class="dashboard-view__panel dashboard-view__panel--hero">
              <div class="dashboard-view__header">
                <div class="dashboard-view__meta dashboard-view__meta--skeleton">
                  <AppSkeleton width="240px" height="1.7rem" radius="8px" />
                  <AppSkeleton width="90px" height="0.78rem" radius="5px" />
                </div>
                <div class="dashboard-view__header-actions dashboard-view__header-actions--skeleton">
                  <AppSkeleton
                    v-for="action in 6"
                    :key="`dashboard-header-skeleton-${action}`"
                    width="110px"
                    height="30px"
                    radius="8px"
                  />
                </div>
              </div>
            </div>

            <div class="dashboard-view__panel">
              <div class="dashboard-view__grid dashboard-view__grid--skeleton">
                <div
                  v-for="tile in 4"
                  :key="`dashboard-grid-skeleton-${tile}`"
                  class="dashboard-view__tile dashboard-view__tile--skeleton"
                >
                  <div class="dashboard-view__tile-header">
                    <AppSkeleton width="26px" height="26px" radius="8px" />
                    <AppSkeleton
                      class="dashboard-view__tile-title-skeleton"
                      height="0.95rem"
                      radius="6px"
                    />
                    <div class="dashboard-view__tile-actions">
                      <AppSkeleton width="22px" height="22px" radius="6px" />
                      <AppSkeleton width="22px" height="22px" radius="6px" />
                    </div>
                  </div>
                  <div class="dashboard-view__tile-body-skeleton">
                    <AppSkeleton height="0.9rem" width="36%" radius="6px" />
                    <AppSkeleton height="0.9rem" width="54%" radius="6px" />
                    <AppSkeleton
                      class="dashboard-view__tile-chart-skeleton"
                      height="100%"
                      radius="14px"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        <template v-else>
        <div v-if="loading" class="dashboard-view__loading">Загрузка…</div>
        <div v-else-if="error" class="dashboard-view__error">{{ error }}</div>

        <template v-else-if="dashboard">
          <div class="dashboard-view__panel dashboard-view__panel--hero">
            <div class="dashboard-view__header">
              <div class="dashboard-view__meta">
                <h1
                  v-if="!editingTitle"
                  class="dashboard-view__title"
                  @dblclick="startEditTitle"
                >
                  {{ dashboard.title }}
                </h1>
                <input
                  v-else
                  ref="titleInput"
                  v-model="titleDraft"
                  class="dashboard-view__title-input"
                  @blur="saveTitle"
                  @keydown.enter="saveTitle"
                  @keydown.esc="editingTitle = false"
                />
                <span class="dashboard-view__updated"
                  >{{ dashboard.widgets.length }} виджетов</span
                >
              </div>

              <div class="dashboard-view__header-actions">
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="copyLink"
                >
                  Копировать ссылку
                </button>
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="togglePublic"
                >
                  {{ dashboard.is_public ? "🔓 Публичный" : "🔒 Закрытый" }}
                </button>
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="toggleHidden"
                >
                  {{ dashboard.is_hidden ? "👁‍🗨 Скрыт" : "👁 Виден" }}
                </button>
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="showScheduleModal = true"
                >
                  Расписание
                </button>
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="downloadPdf"
                >
                  PDF
                </button>
                <button
                  class="wbtn wbtn--ghost"
                  type="button"
                  @click="showAddWidget = true"
                >
                  + Добавить виджет
                </button>
                <button
                  class="wbtn wbtn--danger"
                  type="button"
                  @click="confirmDelete"
                >
                  Удалить
                </button>
              </div>
            </div>
          </div>

          <div class="dashboard-view__panel">
            <div v-if="!dashboard.widgets.length" class="dashboard-view__empty">
              Добавьте виджеты с помощью кнопки «+ Добавить виджет»
            </div>

            <div
              v-else
              class="dashboard-view__grid"
              @dragover.prevent="onGridDragOver"
              @drop.prevent="onGridDrop"
            >
              <div
                v-if="previewLayout"
                class="dashboard-view__drop-preview"
                :style="previewStyle"
              >
                <span class="dashboard-view__drop-preview-label">
                  {{ previewLabel }}
                </span>
              </div>
              <div
                v-for="dw in dashboard.widgets"
                :key="dw.id"
                class="dashboard-view__tile"
                :class="{
                  'dashboard-view__tile--dragging': dragging?.widgetId === dw.id,
                  'dashboard-view__tile--landing': previewOverlapIds.includes(dw.id),
                }"
                :style="tileStyle(dw)"
              >
                <div class="dashboard-view__tile-header">
                  <button
                    class="dashboard-view__tile-drag"
                    type="button"
                    draggable="true"
                    title="Переместить"
                    @dragstart="startDrag(dw, $event)"
                    @dragend="stopInteraction"
                  >
                    ⠿
                  </button>
                  <span class="dashboard-view__tile-title">
                    {{ dw.title_override || dw.widget.title }}
                  </span>
                  <div class="dashboard-view__tile-actions">
                    <router-link
                      :to="`/widget/${dw.widget.id}`"
                      class="dashboard-view__tile-link"
                      title="Открыть виджет"
                      >↗</router-link
                    >
                    <button
                      class="dashboard-view__tile-remove"
                      type="button"
                      title="Убрать из дашборда"
                      @click="removeWidget(dw.id)"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                <DashboardTileContent :dashboard-widget="dw" />
                <button
                  class="dashboard-view__resize-handle dashboard-view__resize-handle--left"
                  type="button"
                  title="Изменить размер слева"
                  @mousedown.prevent="startResize(dw, 'left', $event)"
                />
                <button
                  class="dashboard-view__resize-handle dashboard-view__resize-handle--right"
                  type="button"
                  title="Изменить размер справа"
                  @mousedown.prevent="startResize(dw, 'right', $event)"
                />
                <button
                  class="dashboard-view__resize-handle dashboard-view__resize-handle--top"
                  type="button"
                  title="Изменить размер сверху"
                  @mousedown.prevent="startResize(dw, 'top', $event)"
                />
                <button
                  class="dashboard-view__resize-handle dashboard-view__resize-handle--bottom"
                  type="button"
                  title="Изменить размер снизу"
                  @mousedown.prevent="startResize(dw, 'bottom', $event)"
                />
              </div>
            </div>
          </div>

          <AddWidgetToExistingDashboard
            v-if="showAddWidget"
            :dashboard-id="dashboard.id"
            :already-added-ids="addedWidgetIds"
            @close="showAddWidget = false"
            @added="onWidgetAdded"
          />
          <DashboardScheduleModal
            v-if="showScheduleModal"
            :schedule="dashboard.schedule"
            @close="showScheduleModal = false"
            @delete="deleteSchedule"
            @save="saveSchedule"
          />
        </template>

        <div v-if="linkCopied" class="dashboard-view__toast">
          Ссылка скопирована!
        </div>
        </template>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/api/client";
import ChatSidebar from "@/components/chat/ChatSidebar.vue";
import AppSkeleton from "@/components/ui/AppSkeleton.vue";
import { useDashboardsStore } from "@/stores/dashboards";
import { useWidgetsStore } from "@/stores/widgets";
import DashboardTileContent from "@/components/widgets/DashboardTileContent.vue";
import AddWidgetToExistingDashboard from "@/components/widgets/AddWidgetToExistingDashboard.vue";
import DashboardScheduleModal from "@/components/widgets/DashboardScheduleModal.vue";
import type {
  ApiDashboardDetail,
  ApiDashboardScheduleUpsert,
  ApiDashboardWidgetDetail,
} from "@/api/types";

const route = useRoute();
const router = useRouter();
const dashboardsStore = useDashboardsStore();
const widgetsStore = useWidgetsStore();

const dashboard = ref<ApiDashboardDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const sidebarMode = ref<"dashboards" | "widgets">("dashboards");

const editingTitle = ref(false);
const titleDraft = ref("");
const titleInput = ref<HTMLInputElement | null>(null);

const showAddWidget = ref(false);
const showScheduleModal = ref(false);
const linkCopied = ref(false);
const dragging = ref<{
  widgetId: string;
  startLayout: { x: number; y: number; w: number; h: number };
} | null>(null);
const previewLayout = ref<{ x: number; y: number; w: number; h: number } | null>(null);
const resizing = ref<{
  widgetId: string;
  edge: ResizeEdge;
  startX: number;
  startY: number;
  startLayout: { x: number; y: number; w: number; h: number };
} | null>(null);

const GRID_COLUMNS = 12;
const GRID_ROW_HEIGHT = 56;
const GRID_ROW_GAP = 16;
const MIN_TILE_WIDTH = 2;
const MIN_TILE_HEIGHT = 3;
type ResizeEdge = "left" | "right" | "top" | "bottom";

const addedWidgetIds = computed(
  () => dashboard.value?.widgets.map((dw) => dw.widget.id) ?? [],
);

const previewOverlapIds = computed(() => {
  if (!dashboard.value || !previewLayout.value) return [];
  const activeWidgetId = dragging.value?.widgetId ?? resizing.value?.widgetId ?? null;
  return dashboard.value.widgets
    .filter((item) => item.id !== activeWidgetId)
    .filter((item) => layoutsOverlap(sanitizeLayout(item.layout), previewLayout.value!))
    .map((item) => item.id);
});

const previewStyle = computed(() => {
  if (!previewLayout.value) {
    return {};
  }
  const layout = previewLayout.value;
  return {
    gridColumn: `${layout.x + 1} / span ${layout.w}`,
    gridRow: `${layout.y + 1} / span ${layout.h}`,
  };
});

const previewLabel = computed(() => {
  if (!previewLayout.value) return "";
  const { w, h } = previewLayout.value;
  const overlapCount = previewOverlapIds.value.length;
  return overlapCount
    ? `${w}x${h} • перекрытий: ${overlapCount}`
    : `${w}x${h}`;
});

async function loadDashboard() {
  loading.value = true;
  error.value = null;
  try {
    dashboard.value = await api.getDashboard(route.params.id as string);
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : "Не удалось загрузить дашборд.";
  } finally {
    loading.value = false;
  }
}

async function startEditTitle() {
  titleDraft.value = dashboard.value?.title ?? "";
  editingTitle.value = true;
  await nextTick();
  titleInput.value?.focus();
}

async function saveTitle() {
  if (!dashboard.value || !titleDraft.value.trim()) {
    editingTitle.value = false;
    return;
  }
  editingTitle.value = false;
  const updated = await dashboardsStore.updateDashboard(dashboard.value.id, {
    title: titleDraft.value.trim(),
  });
  dashboard.value = { ...dashboard.value, ...updated };
}

async function togglePublic() {
  if (!dashboard.value) return;
  const updated = await dashboardsStore.updateDashboard(dashboard.value.id, {
    is_public: !dashboard.value.is_public,
  });
  dashboard.value = { ...dashboard.value, ...updated };
}

async function toggleHidden() {
  if (!dashboard.value) return;
  const updated = await dashboardsStore.updateDashboard(dashboard.value.id, {
    is_hidden: !dashboard.value.is_hidden,
  });
  dashboard.value = { ...dashboard.value, ...updated };
}

async function removeWidget(dwId: string) {
  if (!dashboard.value) return;
  await dashboardsStore.removeWidget(dashboard.value.id, dwId);
  dashboard.value = {
    ...dashboard.value,
    widgets: dashboard.value.widgets.filter((dw) => dw.id !== dwId),
  };
}

async function confirmDelete() {
  if (!dashboard.value) return;
  if (!window.confirm(`Удалить дашборд «${dashboard.value.title}»?`)) return;
  await dashboardsStore.deleteDashboard(dashboard.value.id);
  void router.push("/dashboards");
}

function tileStyle(dw: ApiDashboardWidgetDetail) {
  const layout = dw.layout;
  return {
    gridColumn: `${layout.x + 1} / span ${layout.w}`,
    gridRow: `${layout.y + 1} / span ${layout.h}`,
    zIndex: dragging.value?.widgetId === dw.id ? 2 : 1,
  };
}

function sanitizeLayout(layout: { x: number; y: number; w: number; h: number }) {
  const w = Math.min(GRID_COLUMNS, Math.max(MIN_TILE_WIDTH, Math.round(layout.w)));
  const h = Math.max(MIN_TILE_HEIGHT, Math.round(layout.h));
  const x = Math.min(Math.max(0, Math.round(layout.x)), GRID_COLUMNS - w);
  const y = Math.max(0, Math.round(layout.y));
  return { x, y, w, h };
}

function layoutsOverlap(
  left: { x: number; y: number; w: number; h: number },
  right: { x: number; y: number; w: number; h: number },
) {
  return !(
    left.x + left.w <= right.x ||
    right.x + right.w <= left.x ||
    left.y + left.h <= right.y ||
    right.y + right.h <= left.y
  );
}

function resolveLayout(
  desired: { x: number; y: number; w: number; h: number },
  widgetId: string,
) {
  if (!dashboard.value) {
    return sanitizeLayout(desired);
  }
  let layout = sanitizeLayout(desired);
  const occupied = dashboard.value.widgets
    .filter((item) => item.id !== widgetId)
    .map((item) => sanitizeLayout(item.layout));

  while (occupied.some((other) => layoutsOverlap(layout, other))) {
    layout = { ...layout, y: layout.y + 1 };
  }
  return layout;
}

async function commitLayout(widgetId: string, desiredLayout: { x: number; y: number; w: number; h: number }) {
  if (!dashboard.value) return;
  const resolved = resolveLayout(desiredLayout, widgetId);
  const updated = await dashboardsStore.updateWidget(dashboard.value.id, widgetId, {
    layout: resolved,
  });
  const idx = dashboard.value.widgets.findIndex((item) => item.id === widgetId);
  if (idx >= 0) {
    dashboard.value.widgets[idx] = {
      ...dashboard.value.widgets[idx],
      ...updated,
    };
  }
}

function startDrag(dw: ApiDashboardWidgetDetail, event: DragEvent) {
  if (!dashboard.value) return;
  resizing.value = null;
  dragging.value = {
    widgetId: dw.id,
    startLayout: { ...dw.layout },
  };
  previewLayout.value = sanitizeLayout(dw.layout);
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", dw.id);
  }
}

function onGridDragOver(event: DragEvent) {
  if (!dragging.value) return;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
  const grid = document.querySelector(".dashboard-view__grid") as HTMLElement | null;
  if (!grid) return;
  const rect = grid.getBoundingClientRect();
  const colWidth = rect.width / GRID_COLUMNS;
  const rowHeight = GRID_ROW_HEIGHT + GRID_ROW_GAP;
  const x = Math.round((event.clientX - rect.left) / colWidth - dragging.value.startLayout.w / 2);
  const y = Math.round((event.clientY - rect.top) / rowHeight - dragging.value.startLayout.h / 2);
  previewLayout.value = resolveLayout({
    ...dragging.value.startLayout,
    x,
    y,
  }, dragging.value.widgetId);
}

function onGridDrop(event: DragEvent) {
  if (!dashboard.value || !dragging.value) return;
  const grid = document.querySelector(".dashboard-view__grid") as HTMLElement | null;
  if (!grid) {
    stopInteraction();
    return;
  }

  const widget = dashboard.value.widgets.find((item) => item.id === dragging.value?.widgetId);
  if (!widget) {
    stopInteraction();
    return;
  }

  const rect = grid.getBoundingClientRect();
  const colWidth = rect.width / GRID_COLUMNS;
  const rowHeight = GRID_ROW_HEIGHT + GRID_ROW_GAP;
  const x = Math.round((event.clientX - rect.left) / colWidth - dragging.value.startLayout.w / 2);
  const y = Math.round((event.clientY - rect.top) / rowHeight - dragging.value.startLayout.h / 2);
  const nextLayout = previewLayout.value ?? resolveLayout({
    ...dragging.value.startLayout,
    x,
    y,
  }, dragging.value.widgetId);
  void moveWidget(widget.id, {
    ...nextLayout,
  });
}

function startResize(dw: ApiDashboardWidgetDetail, edge: ResizeEdge, event: MouseEvent) {
  if (!dashboard.value) return;
  dragging.value = null;
  resizing.value = {
    widgetId: dw.id,
    edge,
    startX: event.clientX,
    startY: event.clientY,
    startLayout: { ...dw.layout },
  };
  previewLayout.value = sanitizeLayout(dw.layout);
  document.addEventListener("mousemove", onResizeMove);
  document.addEventListener("mouseup", stopResize);
  document.body.style.userSelect = "none";
  document.body.style.cursor =
    edge === "left" || edge === "right" ? "ew-resize" : "ns-resize";
}

function onResizeMove(event: MouseEvent) {
  if (!resizing.value || !dashboard.value) return;
  const widget = dashboard.value.widgets.find((item) => item.id === resizing.value?.widgetId);
  if (!widget) return;

  const grid = document.querySelector(".dashboard-view__grid") as HTMLElement | null;
  if (!grid) return;
  const rect = grid.getBoundingClientRect();
  const colWidth = rect.width / GRID_COLUMNS;
  const rowHeight = GRID_ROW_HEIGHT + GRID_ROW_GAP;
  const deltaX = event.clientX - resizing.value.startX;
  const deltaY = event.clientY - resizing.value.startY;
  const nextLayout = resolveLayout(
    getResizedLayout(
      resizing.value.startLayout,
      resizing.value.edge,
      deltaX,
      deltaY,
      colWidth,
      rowHeight,
    ),
    widget.id,
  );
  widget.layout = nextLayout;
  previewLayout.value = nextLayout;
}

function stopResize() {
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", stopResize);
  document.body.style.userSelect = "";
  document.body.style.cursor = "";
  if (!dashboard.value || !resizing.value) {
    resizing.value = null;
    return;
  }

  const widget = dashboard.value.widgets.find((item) => item.id === resizing.value?.widgetId);
  if (widget) {
    void resizeWidget(widget.id, widget.layout);
  }
  resizing.value = null;
}

function stopInteraction() {
  dragging.value = null;
  previewLayout.value = null;
  resizing.value = null;
}

function getResizedLayout(
  start: { x: number; y: number; w: number; h: number },
  edge: ResizeEdge,
  deltaX: number,
  deltaY: number,
  colWidth: number,
  rowHeight: number,
) {
  const dx = Math.round(deltaX / colWidth);
  const dy = Math.round(deltaY / rowHeight);
  let next = { ...start };

  if (edge === "right") {
    next.w = start.w + dx;
  } else if (edge === "left") {
    next.x = start.x + dx;
    next.w = start.w - dx;
  } else if (edge === "bottom") {
    next.h = start.h + dy;
  } else if (edge === "top") {
    next.y = start.y + dy;
    next.h = start.h - dy;
  }

  return sanitizeResizedLayout(next, edge);
}

function sanitizeResizedLayout(
  layout: { x: number; y: number; w: number; h: number },
  edge: ResizeEdge,
) {
  let x = Math.round(layout.x);
  let y = Math.round(layout.y);
  let w = Math.round(layout.w);
  let h = Math.round(layout.h);

  if (w < MIN_TILE_WIDTH) {
    if (edge === "left") {
      x -= MIN_TILE_WIDTH - w;
    }
    w = MIN_TILE_WIDTH;
  }
  if (h < MIN_TILE_HEIGHT) {
    if (edge === "top") {
      y -= MIN_TILE_HEIGHT - h;
    }
    h = MIN_TILE_HEIGHT;
  }

  if (x < 0) {
    if (edge === "left") {
      w += x;
    }
    x = 0;
  }
  if (y < 0) {
    if (edge === "top") {
      h += y;
    }
    y = 0;
  }

  if (w > GRID_COLUMNS) w = GRID_COLUMNS;
  if (h < MIN_TILE_HEIGHT) h = MIN_TILE_HEIGHT;
  if (x + w > GRID_COLUMNS) {
    if (edge === "left") {
      x = GRID_COLUMNS - w;
    } else {
      w = GRID_COLUMNS - x;
    }
  }

  return sanitizeLayout({ x, y, w, h });
}

async function saveSchedule(payload: ApiDashboardScheduleUpsert) {
  if (!dashboard.value) return;
  try {
    const schedule = await dashboardsStore.saveSchedule(dashboard.value.id, payload);
    dashboard.value = { ...dashboard.value, schedule };
    showScheduleModal.value = false;
  } catch {
    // store surfaces the error banner
  }
}

async function deleteSchedule() {
  if (!dashboard.value) return;
  try {
    await dashboardsStore.deleteSchedule(dashboard.value.id);
    dashboard.value = { ...dashboard.value, schedule: null };
    showScheduleModal.value = false;
  } catch {
    // store surfaces the error banner
  }
}

async function downloadPdf() {
  if (!dashboard.value) return;
  try {
    const response = await dashboardsStore.exportPdf(dashboard.value.id);
    if (!response.ok) {
      throw new Error("Не удалось выгрузить PDF.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${dashboard.value.slug || dashboard.value.title}.pdf`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Не удалось выгрузить PDF.";
  }
}

async function moveWidget(widgetId: string, desiredLayout: { x: number; y: number; w: number; h: number }) {
  if (!dashboard.value) return;
  try {
    await commitLayout(widgetId, desiredLayout);
  } catch {
    error.value = "Не удалось переместить виджет.";
    await loadDashboard();
  } finally {
    dragging.value = null;
    previewLayout.value = null;
  }
}

async function resizeWidget(widgetId: string, desiredLayout: { x: number; y: number; w: number; h: number }) {
  if (!dashboard.value) return;
  try {
    await commitLayout(widgetId, desiredLayout);
  } catch {
    error.value = "Не удалось сохранить размер виджета.";
    await loadDashboard();
  } finally {
    resizing.value = null;
    previewLayout.value = null;
  }
}

function copyLink() {
  void navigator.clipboard.writeText(window.location.href);
  linkCopied.value = true;
  setTimeout(() => {
    linkCopied.value = false;
  }, 2000);
}

async function onWidgetAdded() {
  showAddWidget.value = false;
  await loadDashboard();
}

onMounted(() => {
  void loadDashboard();
  void Promise.all([
    dashboardsStore.loadDashboards(),
    widgetsStore.loadWidgets(),
  ]);
});

onBeforeUnmount(() => {
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", stopResize);
  document.body.style.userSelect = "";
  document.body.style.cursor = "";
  previewLayout.value = null;
});
</script>

<style scoped lang="scss">
.dashboard-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--app-shell-sidebar-width) minmax(0, 1fr);
  gap: var(--app-shell-gap);
  background: var(--bg);
  padding: var(--app-shell-gap);
}

.dashboard-shell__sidebar {
  min-height: 0;
  width: var(--app-shell-sidebar-width);
  max-width: 100%;
}

.dashboard-shell__content {
  min-height: 0;
  overflow: auto;
}

.dashboard-view {
  padding: 20px 24px;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
  position: relative;
}

.dashboard-view__panel {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 12px;
  box-shadow: var(--shadow-soft);
}

.dashboard-view__panel--hero {
  background:
    radial-gradient(
      circle at top right,
      rgba(138, 180, 248, 0.08),
      transparent 28%
    ),
    linear-gradient(180deg, rgba(26, 29, 36, 0.96), rgba(18, 20, 27, 0.98));
}

.dashboard-view__loading,
.dashboard-view__error {
  padding: 40px;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
}

.dashboard-view__skeleton {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.dashboard-view__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dashboard-view__meta--skeleton {
  min-width: min(280px, 100%);
}

.dashboard-view__title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ink-strong);
  margin: 0;
  cursor: pointer;
}

.dashboard-view__title-input {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ink-strong);
  background: var(--bg);
  border: 1px solid rgba(112, 59, 247, 0.7);
  border-radius: 6px;
  padding: 2px 6px;
  outline: none;
}

.dashboard-view__updated {
  font-size: 0.72rem;
  color: var(--muted);
}

.dashboard-view__header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dashboard-view__header-actions--skeleton {
  align-items: center;
}

.dashboard-view__empty {
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  padding: 48px;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
}

.dashboard-view__grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-rows: 56px;
  gap: 16px;
  position: relative;
}

.dashboard-view__grid--skeleton {
  margin-top: 0;
}

.dashboard-view__drop-preview {
  pointer-events: none;
  border: 2px dashed rgba(112, 59, 247, 0.95);
  border-radius: var(--radius-lg);
  background: rgba(112, 59, 247, 0.12);
  box-shadow: inset 0 0 0 1px rgba(112, 59, 247, 0.25);
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 8px;
  z-index: 5;
}

.dashboard-view__drop-preview-label {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(18, 20, 27, 0.9);
  color: rgba(238, 232, 255, 0.95);
  font-size: 0.68rem;
  letter-spacing: 0.02em;
}

.dashboard-view__tile {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  height: 100%;
}

.dashboard-view__tile--skeleton {
  grid-column: span 6;
  grid-row: span 5;
  pointer-events: none;
}

.dashboard-view__tile-title-skeleton {
  flex: 1;
}

.dashboard-view__tile-body-skeleton {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
}

.dashboard-view__tile-chart-skeleton {
  flex: 1;
  min-height: 140px;
}

.dashboard-view__tile--dragging {
  border-color: rgba(112, 59, 247, 0.8);
  box-shadow: 0 12px 28px rgba(112, 59, 247, 0.18);
  opacity: 0.92;
}

.dashboard-view__tile--landing {
  border-color: rgba(112, 59, 247, 0.9);
  box-shadow: inset 0 0 0 1px rgba(112, 59, 247, 0.22);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.12), rgba(112, 59, 247, 0.04));
}

.dashboard-view__tile-drag {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: rgba(112, 59, 247, 0.12);
  color: var(--ink-strong);
  cursor: grab;
  font-size: 0.95rem;
  line-height: 1;
  flex-shrink: 0;
}

.dashboard-view__tile-drag:active {
  cursor: grabbing;
}

.dashboard-view__resize-handle {
  position: absolute;
  border: none;
  background: rgba(112, 59, 247, 0.02);
  padding: 0;
  z-index: 3;
}

.dashboard-view__resize-handle:hover {
  background: rgba(112, 59, 247, 0.12);
}

.dashboard-view__resize-handle--left,
.dashboard-view__resize-handle--right {
  top: 10px;
  bottom: 10px;
  width: 14px;
  cursor: ew-resize;
}

.dashboard-view__resize-handle--left {
  left: -3px;
}

.dashboard-view__resize-handle--right {
  right: -3px;
}

.dashboard-view__resize-handle--top,
.dashboard-view__resize-handle--bottom {
  left: 10px;
  right: 10px;
  height: 14px;
  cursor: ns-resize;
}

.dashboard-view__resize-handle--top {
  top: -3px;
}

.dashboard-view__resize-handle--bottom {
  bottom: -3px;
}

.dashboard-view__tile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.dashboard-view__tile-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-view__tile-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.dashboard-view__tile-link {
  color: var(--muted);
  font-size: 0.85rem;
  text-decoration: none;
  padding: 2px 5px;
  border-radius: 4px;
  &:hover {
    background: var(--line);
    color: var(--ink);
  }
}

.dashboard-view__tile-remove {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 2px 5px;
  border-radius: 4px;
  &:hover {
    background: rgba(255, 80, 80, 0.15);
    color: #ff7070;
  }
}

.dashboard-view__toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(112, 59, 247, 0.9);
  color: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.82rem;
  pointer-events: none;
}

@media (max-width: 980px) {
  .dashboard-shell {
    grid-template-columns: 1fr;
  }
}

/* --- shared button styles --- */
.wbtn {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}
.wbtn--ghost:hover {
  background: var(--line);
}
.wbtn--danger {
  border-color: rgba(255, 80, 80, 0.5);
  color: #ff7070;
  &:hover {
    background: rgba(255, 80, 80, 0.12);
  }
}
</style>
