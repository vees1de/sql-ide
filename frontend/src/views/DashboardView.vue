<template>
  <main class="dashboard-view">
    <div v-if="loading" class="dashboard-view__loading">Загрузка…</div>
    <div v-else-if="error" class="dashboard-view__error">{{ error }}</div>

    <template v-else-if="dashboard">
      <div class="dashboard-view__header">
        <div class="dashboard-view__meta">
          <h1 v-if="!editingTitle" class="dashboard-view__title" @dblclick="startEditTitle">
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
          <span class="dashboard-view__updated">{{ dashboard.widgets.length }} виджетов</span>
        </div>

        <div class="dashboard-view__header-actions">
          <button class="wbtn wbtn--ghost" type="button" @click="copyLink">Копировать ссылку</button>
          <button class="wbtn wbtn--ghost" type="button" @click="togglePublic">
            {{ dashboard.is_public ? '🔓 Публичный' : '🔒 Приватный' }}
          </button>
          <button class="wbtn wbtn--ghost" type="button" @click="showAddWidget = true">+ Добавить виджет</button>
          <button class="wbtn wbtn--danger" type="button" @click="confirmDelete">Удалить</button>
        </div>
      </div>

      <div v-if="!dashboard.widgets.length" class="dashboard-view__empty">
        Добавьте виджеты с помощью кнопки «+ Добавить виджет»
      </div>

      <div v-else class="dashboard-view__grid">
        <div
          v-for="dw in dashboard.widgets"
          :key="dw.id"
          class="dashboard-view__tile"
        >
          <div class="dashboard-view__tile-header">
            <span class="dashboard-view__tile-title">
              {{ dw.title_override || dw.widget.title }}
            </span>
            <div class="dashboard-view__tile-actions">
              <router-link
                :to="`/widget/${dw.widget.id}`"
                class="dashboard-view__tile-link"
                title="Открыть виджет"
              >↗</router-link>
              <button
                class="dashboard-view__tile-remove"
                type="button"
                title="Убрать из дашборда"
                @click="removeWidget(dw.id)"
              >✕</button>
            </div>
          </div>

          <DashboardTileContent :dashboard-widget="dw" />
        </div>
      </div>

      <!-- Add widget modal -->
      <AddWidgetToExistingDashboard
        v-if="showAddWidget"
        :dashboard-id="dashboard.id"
        :already-added-ids="addedWidgetIds"
        @close="showAddWidget = false"
        @added="onWidgetAdded"
      />
    </template>

    <div v-if="linkCopied" class="dashboard-view__toast">Ссылка скопирована!</div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api/client';
import { useDashboardsStore } from '@/stores/dashboards';
import DashboardTileContent from '@/components/widgets/DashboardTileContent.vue';
import AddWidgetToExistingDashboard from '@/components/widgets/AddWidgetToExistingDashboard.vue';
import type { ApiDashboardDetail } from '@/api/types';

const route = useRoute();
const router = useRouter();
const dashboardsStore = useDashboardsStore();

const dashboard = ref<ApiDashboardDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

const editingTitle = ref(false);
const titleDraft = ref('');
const titleInput = ref<HTMLInputElement | null>(null);

const showAddWidget = ref(false);
const linkCopied = ref(false);

const addedWidgetIds = computed(() =>
  dashboard.value?.widgets.map((dw) => dw.widget.id) ?? []
);

async function loadDashboard() {
  loading.value = true;
  error.value = null;
  try {
    dashboard.value = await api.getDashboard(route.params.id as string);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось загрузить дашборд.';
  } finally {
    loading.value = false;
  }
}

async function startEditTitle() {
  titleDraft.value = dashboard.value?.title ?? '';
  editingTitle.value = true;
  await nextTick();
  titleInput.value?.focus();
}

async function saveTitle() {
  if (!dashboard.value || !titleDraft.value.trim()) { editingTitle.value = false; return; }
  editingTitle.value = false;
  const updated = await dashboardsStore.updateDashboard(dashboard.value.id, { title: titleDraft.value.trim() });
  dashboard.value = { ...dashboard.value, ...updated };
}

async function togglePublic() {
  if (!dashboard.value) return;
  const updated = await dashboardsStore.updateDashboard(dashboard.value.id, { is_public: !dashboard.value.is_public });
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
  void router.push('/dashboards');
}

function copyLink() {
  void navigator.clipboard.writeText(window.location.href);
  linkCopied.value = true;
  setTimeout(() => { linkCopied.value = false; }, 2000);
}

async function onWidgetAdded() {
  showAddWidget.value = false;
  await loadDashboard();
}

onMounted(() => { void loadDashboard(); });
</script>

<style scoped lang="scss">
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

.dashboard-view__loading,
.dashboard-view__error {
  padding: 40px;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
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
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;

  @media (max-width: 760px) {
    grid-template-columns: 1fr;
  }
}

.dashboard-view__tile {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 240px;
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
  &:hover { background: var(--line); color: var(--ink); }
}

.dashboard-view__tile-remove {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 2px 5px;
  border-radius: 4px;
  &:hover { background: rgba(255,80,80,0.15); color: #ff7070; }
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
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}
.wbtn--ghost:hover { background: var(--line); }
.wbtn--danger {
  border-color: rgba(255, 80, 80, 0.5);
  color: #ff7070;
  &:hover { background: rgba(255, 80, 80, 0.12); }
}
</style>
