<template>
  <div class="data-view">
    <section class="data-view__panel">
      <header class="data-view__head">
        <div>
          <p class="eyebrow">Semantic layer</p>
          <h1>Dictionary</h1>
          <p class="data-view__hint">
            Термины подставляются в семантический слой при генерации SQL. При импорте БД можно
            автоматически добавить таблицы и колонки.
          </p>
        </div>
        <button
          class="app-button app-button--ghost"
          type="button"
          :disabled="store.isBootstrapping"
          @click="reload"
        >
          Обновить
        </button>
      </header>

      <div v-if="!store.workspace.dictionary.length" class="data-view__empty">
        Словарь пуст. Подключите базу с опцией «Заполнить Dictionary из схемы» или добавьте термины через API.
      </div>
      <table v-else class="data-view__table">
        <thead>
          <tr>
            <th>Термин</th>
            <th>Выражение</th>
            <th>Описание</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="term in store.workspace.dictionary" :key="term.id">
            <td>
              <strong>{{ term.term }}</strong>
              <p v-if="term.synonyms.length" class="data-view__syn">
                {{ term.synonyms.join(', ') }}
              </p>
            </td>
            <td><code>{{ term.mappedExpression }}</code></td>
            <td>{{ term.description }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="schema?.tables?.length" class="data-view__panel data-view__panel--schema">
      <header class="data-view__head">
        <div>
          <p class="eyebrow">Текущая аналитическая БД</p>
          <h2>Схема (metadata)</h2>
          <p class="data-view__hint">
            Диалект: {{ schema.dialect }}. Таблицы, доступные оркестратору для SELECT.
          </p>
        </div>
      </header>
      <ul class="data-view__schema-list">
        <li v-for="t in schema.tables" :key="t.name">
          <strong>{{ t.name }}</strong>
          <span class="data-view__cols">{{ t.columns.map((c) => c.name).join(', ') }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '@/api/client';
import type { ApiSchemaMetadataResponse } from '@/api/types';
import { useWorkspaceStore } from '@/stores/workspace';

const store = useWorkspaceStore();
const schema = ref<ApiSchemaMetadataResponse | null>(null);

async function reload() {
  await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
  try {
    schema.value = await api.getSchema();
  } catch {
    schema.value = null;
  }
}

onMounted(() => {
  reload();
});
</script>

<style scoped lang="scss">
.data-view {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 1.25rem 1.25rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.data-view__panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 1.1rem 1.15rem;
  box-shadow: var(--shadow-soft);
}

.data-view__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__head h1 {
  margin: 0.2rem 0 0.35rem;
  font-size: 1.25rem;
  color: var(--ink-strong);
}

.data-view__head h2 {
  margin: 0.2rem 0 0;
  font-size: 1.05rem;
  color: var(--ink-strong);
}

.data-view__hint {
  margin: 0;
  max-width: 720px;
  font-size: 0.86rem;
  color: var(--muted);
  line-height: 1.5;
}

.data-view__empty {
  padding: 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.88rem;
}

.data-view__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

.data-view__table th,
.data-view__table td {
  text-align: left;
  padding: 0.55rem 0.65rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

.data-view__table th {
  color: var(--muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.data-view__table code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--accent-strong);
}

.data-view__syn {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: var(--muted);
}

.data-view__schema-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.data-view__schema-list li {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--line);
}

.data-view__schema-list li:last-child {
  border-bottom: none;
}

.data-view__cols {
  font-size: 0.78rem;
  color: var(--muted);
  font-family: var(--font-mono);
}
</style>
