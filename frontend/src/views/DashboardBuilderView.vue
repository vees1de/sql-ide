<template>
  <main class="builder-view">
    <div class="builder-view__header">
      <button
        class="wbtn wbtn--ghost"
        type="button"
        @click="$router.push('/dashboards')"
      >
        Cancel
      </button>
      <div class="builder-view__header-actions">
        <input
          v-model="title"
          class="builder-view__title-input"
          type="text"
          placeholder="Dashboard title..."
        />
        <button
          class="wbtn wbtn--primary"
          type="button"
          :disabled="!title.trim() || !selectedWidgets.length || saving"
          @click="saveDashboard"
        >
          {{ saving ? "Saving..." : "Save dashboard" }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="builder-view__error">{{ errorMsg }}</p>

    <div class="builder-view__body">
      <aside class="builder-view__library">
        <div class="builder-view__library-header">
          <span class="builder-view__section-title">Saved Charts</span>
          <input
            v-model="search"
            class="builder-view__search"
            type="text"
            placeholder="Search..."
          />
        </div>

        <div v-if="widgetsStore.loading" class="builder-view__widget-list">
          <div
            v-for="item in 7"
            :key="`builder-skeleton-${item}`"
            class="builder-view__widget-card builder-view__widget-card--skeleton"
          >
            <AppSkeleton
              class="builder-view__widget-name-skeleton"
              height="0.82rem"
              radius="6px"
            />
            <AppSkeleton width="68px" height="1rem" radius="999px" />
          </div>
        </div>
        <div v-else-if="!filteredWidgets.length" class="builder-view__hint">
          No charts
        </div>

        <div v-else class="builder-view__widget-list">
          <div
            v-for="widget in filteredWidgets"
            :key="widget.id"
            class="builder-view__widget-card"
            :class="{
              'builder-view__widget-card--selected': isSelected(widget.id),
            }"
            @click="toggleWidget(widget)"
          >
            <span class="builder-view__widget-name">{{ widget.title }}</span>
            <span class="builder-view__widget-type">
              {{ translateVisualizationType(widget.visualization_type) }}
            </span>
            <span
              v-if="isSelected(widget.id)"
              class="builder-view__widget-check"
              >вњ“</span
            >
          </div>
        </div>
      </aside>

      <section class="builder-view__grid-area">
        <div
          class="builder-view__section-title builder-view__section-title--pad"
        >
          Preview ({{ selectedWidgets.length }} charts)
        </div>
        <div v-if="!selectedWidgets.length" class="builder-view__grid-empty">
          Choose charts from the list on the left
        </div>
        <div v-else class="builder-view__grid">
          <div
            v-for="(item, idx) in selectedWidgets"
            :key="item.id"
            class="builder-view__grid-tile"
          >
            <div class="builder-view__grid-tile-header">
              <span>{{ item.title }}</span>
              <button
                class="builder-view__remove-btn"
                type="button"
                @click="removeWidget(idx)"
              >
                вњ•
              </button>
            </div>
            <div class="builder-view__grid-tile-body">
              <span class="builder-view__viz-badge">
                {{ translateVisualizationType(item.visualization_type) }}
              </span>
              <span class="builder-view__sql-preview">
                {{ item.sql_text.slice(0, 80) }}вЂ¦
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import AppSkeleton from "@/components/ui/AppSkeleton.vue";
import { useDashboardsStore } from "@/stores/dashboards";
import { useWidgetsStore } from "@/stores/widgets";
import type { ApiWidgetRead } from "@/api/types";

const router = useRouter();
const widgetsStore = useWidgetsStore();
const dashboardsStore = useDashboardsStore();

const title = ref("");
const search = ref("");
const selectedWidgets = ref<ApiWidgetRead[]>([]);
const saving = ref(false);
const errorMsg = ref<string | null>(null);

const filteredWidgets = computed(() =>
  widgetsStore.widgets.filter((w) =>
    w.title.toLowerCase().includes(search.value.toLowerCase()),
  ),
);

function isSelected(widgetId: string) {
  return selectedWidgets.value.some((w) => w.id === widgetId);
}

function toggleWidget(widget: ApiWidgetRead) {
  if (isSelected(widget.id)) {
    selectedWidgets.value = selectedWidgets.value.filter(
      (w) => w.id !== widget.id,
    );
  } else {
    selectedWidgets.value = [...selectedWidgets.value, widget];
  }
}

function removeWidget(idx: number) {
  selectedWidgets.value = selectedWidgets.value.filter((_, i) => i !== idx);
}

function translateVisualizationType(value: string) {
  switch (value) {
    case "table":
      return "Table";
    case "bar":
      return "Bar";
    case "line":
      return "Line";
    case "area":
      return "Area";
    case "pie":
      return "Pie";
    case "metric":
      return "Metric";
    default:
      return value;
  }
}

async function saveDashboard() {
  if (!title.value.trim() || !selectedWidgets.value.length) return;
  saving.value = true;
  errorMsg.value = null;
  try {
    const dashboard = await dashboardsStore.createDashboard({
      title: title.value.trim(),
      widgets: selectedWidgets.value.map((w, idx) => ({
        widget_id: w.id,
        layout: {
          x: (idx % 2) * 6,
          y: Math.floor(idx / 2) * 4,
          w: 6,
          h: 4,
        },
      })),
    });
    void router.push(`/dashboards/${dashboard.id}`);
  } catch (e) {
    errorMsg.value =
      e instanceof Error ? e.message : "Failed to create dashboard.";
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void widgetsStore.loadWidgets();
});
</script>

<style scoped lang="scss">
.builder-view {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.builder-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.builder-view__title-input {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--ink-strong);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 12px;
  outline: none;
  flex: 1;
  max-width: 420px;

  &:focus {
    border-color: rgba(112, 59, 247, 0.7);
  }
}

.builder-view__header-actions {
  display: flex;
  gap: 8px;
}

.builder-view__error {
  color: #ff7070;
  font-size: 0.82rem;
  margin: 0;
}

.builder-view__body {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.builder-view__library {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.builder-view__library-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.builder-view__section-title {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;

  &--pad {
    padding: 0 2px;
  }
}

.builder-view__search {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink);
  font-size: 0.82rem;
  padding: 5px 8px;
  outline: none;

  &:focus {
    border-color: rgba(112, 59, 247, 0.6);
  }
}

.builder-view__hint {
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
  padding: 12px 0;
}

.builder-view__widget-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  flex: 1;
}

.builder-view__widget-card {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.15s;
  user-select: none;

  &:hover {
    border-color: rgba(112, 59, 247, 0.4);
  }

  &--selected {
    border-color: rgba(112, 59, 247, 0.8);
    background: rgba(112, 59, 247, 0.08);
  }
}

.builder-view__widget-card--skeleton {
  pointer-events: none;
}

.builder-view__widget-name {
  font-size: 0.82rem;
  color: var(--ink);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.builder-view__widget-name-skeleton {
  flex: 1;
}

.builder-view__widget-type {
  font-size: 0.7rem;
  color: var(--muted);
  background: var(--line);
  padding: 1px 5px;
  border-radius: 4px;
  flex-shrink: 0;
}

.builder-view__widget-check {
  color: rgba(112, 59, 247, 0.9);
  font-size: 0.85rem;
  flex-shrink: 0;
}

.builder-view__grid-area {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.builder-view__grid-empty {
  color: var(--muted);
  font-size: 0.85rem;
  text-align: center;
  padding: 40px 0;
  border: 1px dashed var(--line);
  border-radius: 8px;
}

.builder-view__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.builder-view__grid-tile {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.builder-view__grid-tile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink-strong);
}

.builder-view__remove-btn {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 2px 4px;
  border-radius: 4px;

  &:hover {
    background: rgba(255, 80, 80, 0.15);
    color: #ff7070;
  }
}

.builder-view__grid-tile-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.builder-view__viz-badge {
  font-size: 0.7rem;
  color: var(--muted);
  background: var(--line);
  padding: 1px 6px;
  border-radius: 4px;
  align-self: flex-start;
}

.builder-view__sql-preview {
  font-size: 0.72rem;
  color: var(--muted);
  font-family: "JetBrains Mono", monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wbtn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 0.82rem;
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

.wbtn--primary {
  background: rgba(112, 59, 247, 0.85);
  border-color: transparent;
  color: #fff;
  font-weight: 600;

  &:not(:disabled):hover {
    background: rgba(112, 59, 247, 1);
  }
}
</style>
