<template>
  <main class="widgets-list-view">
    <div class="widgets-list-view__header">
      <h1 class="widgets-list-view__heading">Отчёты</h1>
      <div class="widgets-list-view__header-actions">
        <router-link to="/dashboards/new" class="wbtn wbtn--ghost">+ Новый дашборд</router-link>
      </div>
    </div>

    <div v-if="widgetsStore.loading" class="widgets-list-view__hint">Загрузка…</div>
    <div v-else-if="!widgetsStore.widgets.length" class="widgets-list-view__empty">
      <p>Здесь будут ваши сохранённые отчёты.</p>
      <p class="widgets-list-view__hint-sub">Нажмите «Сохранить отчёт» после выполнения SQL в чате.</p>
    </div>

    <div v-else class="widgets-list-view__grid">
      <router-link
        v-for="widget in widgetsStore.widgets"
        :key="widget.id"
        :to="`/widget/${widget.id}`"
        class="widgets-list-view__card"
      >
        <div class="widgets-list-view__card-header">
          <span class="widgets-list-view__card-title">{{ widget.title }}</span>
          <span class="widgets-list-view__card-viz">{{ widget.visualization_type }}</span>
        </div>
        <p v-if="widget.description" class="widgets-list-view__card-desc">{{ widget.description }}</p>
        <span class="widgets-list-view__card-updated">{{ formatDate(widget.updated_at) }}</span>
      </router-link>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useWidgetsStore } from '@/stores/widgets';

const widgetsStore = useWidgetsStore();

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

onMounted(() => { void widgetsStore.loadWidgets(); });
</script>

<style scoped lang="scss">
.widgets-list-view {
  padding: 20px 24px;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}

.widgets-list-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.widgets-list-view__heading {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--ink-strong);
  margin: 0;
}

.widgets-list-view__hint {
  color: var(--muted);
  font-size: 0.85rem;
}

.widgets-list-view__empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 48px;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  color: var(--muted);
  font-size: 0.9rem;
}

.widgets-list-view__hint-sub {
  font-size: 0.8rem;
  opacity: 0.7;
}

.widgets-list-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.widgets-list-view__card {
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

.widgets-list-view__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.widgets-list-view__card-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.widgets-list-view__card-viz {
  font-size: 0.68rem;
  color: var(--muted);
  background: var(--line);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.widgets-list-view__card-desc {
  font-size: 0.78rem;
  color: var(--muted);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.widgets-list-view__card-updated {
  font-size: 0.7rem;
  color: var(--muted);
  margin-top: auto;
}

.wbtn {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}
.wbtn--ghost:hover { background: var(--line); }
</style>
