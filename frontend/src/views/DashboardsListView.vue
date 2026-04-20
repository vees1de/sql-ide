<template>
  <main class="dashboards-list-view">
    <div class="dashboards-list-view__header">
      <h1 class="dashboards-list-view__heading">Дашборды</h1>
      <router-link to="/dashboards/new" class="wbtn wbtn--primary">+ Новый дашборд</router-link>
    </div>

    <div v-if="dashboardsStore.loading" class="dashboards-list-view__hint">Загрузка…</div>
    <div v-else-if="!dashboardsStore.dashboards.length" class="dashboards-list-view__empty">
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
          <span class="dashboards-list-view__card-title">{{ dashboard.title }}</span>
          <span v-if="dashboard.is_public" class="dashboards-list-view__card-badge">публичный</span>
        </div>
        <p v-if="dashboard.description" class="dashboards-list-view__card-desc">{{ dashboard.description }}</p>
        <span class="dashboards-list-view__card-updated">{{ formatDate(dashboard.updated_at) }}</span>
      </router-link>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useDashboardsStore } from '@/stores/dashboards';

const dashboardsStore = useDashboardsStore();

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

onMounted(() => { void dashboardsStore.loadDashboards(); });
</script>

<style scoped lang="scss">
.dashboards-list-view {
  padding: 20px 24px;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}

.dashboards-list-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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
  padding: 48px;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  color: var(--muted);
  font-size: 0.9rem;
}

.dashboards-list-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.dashboards-list-view__card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 14px;
  text-decoration: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 0.15s;

  &:hover { border-color: rgba(112, 59, 247, 0.5); }
}

.dashboards-list-view__card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dashboards-list-view__card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.dashboards-list-view__card-badge {
  font-size: 0.68rem;
  color: rgba(112, 59, 247, 0.9);
  background: rgba(112, 59, 247, 0.15);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
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
  &:hover { background: rgba(112, 59, 247, 1); }
}
</style>
