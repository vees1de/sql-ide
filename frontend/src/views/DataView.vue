<template>
  <main class="data-shell">
    <aside class="data-shell__sidebar">
      <ChatSidebar
        :active-db-id="selectedDatabaseId"
        :active-session-id="chat.activeSessionId"
        :databases="chat.databases"
        :loading="chat.loadingSessions || chat.loadingMessages"
        :sessions="chat.sessions"
        @create-session="createChatSession"
        @delete-session="deleteChatSession"
        @rename-session="renameChatSession"
        @select-database="selectDatabase"
        @select-session="selectChatSession"
      />
    </aside>

    <div class="data-shell__content">
      <div class="data-view">
        <section class="data-view__panel data-view__panel--hero">
          <header class="data-view__head">
            <div>
              <p class="eyebrow">Database Knowledge Layer</p>
              <h1>Data Control Center</h1>
              <p class="data-view__hint">
                Здесь команда запускает parse БД, следит за scan runs, редактирует table/column semantics и
                смотрит ERD без ручного импорта сырой схемы в словарь.
              </p>
            </div>
            <div class="data-view__actions">
              <select :value="selectedDatabaseId" class="data-view__select" @change="handleDatabaseSelectChange">
                <option v-for="database in store.workspace.databases" :key="database.id" :value="database.id">
                  {{ database.name }}
                </option>
              </select>
              <button class="app-button app-button--ghost" type="button" :disabled="store.isBootstrapping" @click="reload">
                Обновить
              </button>
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="isScanning || !selectedDatabaseId"
                @click="runScan('incremental')"
              >
                {{ isScanning ? 'Скан…' : 'Incremental scan' }}
              </button>
              <button class="app-button" type="button" :disabled="isScanning || !selectedDatabaseId" @click="runScan('full')">
                {{ isScanning ? 'Скан…' : 'Full scan' }}
              </button>
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="isActivatingSemantic || !selectedDatabaseId"
                @click="activateSemantic"
              >
                {{ isActivatingSemantic ? 'Semantic…' : 'Activate semantic' }}
              </button>
          <button
            class="app-button app-button--danger"
            type="button"
            :disabled="isDeletingDatabase || !selectedDatabaseId || selectedDatabase?.isDemo"
            @click="deleteSelectedDatabase"
          >
                {{ isDeletingDatabase ? 'Удаление…' : 'Удалить базу' }}
              </button>
            </div>
          </header>

          <p v-if="knowledgeFeedback" class="data-view__feedback">{{ knowledgeFeedback }}</p>
          <p v-if="semanticFeedback" class="data-view__feedback">{{ semanticFeedback }}</p>

          <div v-if="selectedDatabase" class="data-view__stats">
            <article class="data-view__stat">
              <span>Connection</span>
              <strong>{{ selectedDatabase.engine }}</strong>
              <small>{{ selectedDatabase.mode }}</small>
            </article>
            <article class="data-view__stat">
              <span>Knowledge status</span>
              <strong>{{ knowledgeSummary?.status || selectedDatabase.knowledgeStatus || 'not_scanned' }}</strong>
              <small>{{ formatTimestamp(knowledgeSummary?.last_scan?.finished_at || selectedDatabase.lastScanAt) }}</small>
            </article>
            <article class="data-view__stat">
              <span>Tables</span>
              <strong>{{ knowledgeSummary?.active_table_count ?? 0 }}</strong>
              <small>{{ knowledgeSummary?.active_column_count ?? 0 }} columns</small>
            </article>
            <article class="data-view__stat">
              <span>Relations</span>
              <strong>{{ knowledgeSummary?.active_relationship_count ?? 0 }}</strong>
              <small>FK graph + persisted scan diff</small>
            </article>
            <article class="data-view__stat">
              <span>Semantic</span>
              <strong>{{ semanticCatalog ? 'active' : 'inactive' }}</strong>
              <small>
                {{ semanticCatalog?.tables.length ?? 0 }} tables ·
                {{ semanticCatalog?.relationships.length ?? 0 }} relations
              </small>
            </article>
          </div>
        </section>

    <section class="data-view__panel" v-if="knowledgeSummary">
      <header class="data-view__head data-view__head--compact">
        <div>
          <p class="eyebrow">Scan Runs</p>
          <h2>Последние парсинги</h2>
        </div>
      </header>
      <div v-if="scanRuns.length" class="data-view__scan-list">
        <article v-for="run in scanRuns.slice(0, 6)" :key="run.id" class="data-view__scan-card">
          <div>
            <strong>{{ run.scan_type }}</strong>
            <p>{{ run.status }} · {{ run.stage }}</p>
          </div>
          <small>{{ formatTimestamp(run.finished_at || run.started_at) }}</small>
          <span>
            tables {{ numberFromSummary(run.summary, 'active_tables') }},
            columns {{ numberFromSummary(run.summary, 'active_columns') }},
            rels {{ numberFromSummary(run.summary, 'active_relationships') }}
          </span>
        </article>
      </div>
      <div v-else class="data-view__empty">
        Для этой базы пока нет persisted scan runs. Запустите `Full scan`.
      </div>
    </section>

    <section class="data-view__panel" v-if="knowledgeSummary">
      <div class="data-view__knowledge">
        <aside class="data-view__tables">
          <header class="data-view__head data-view__head--compact">
            <div>
              <p class="eyebrow">Knowledge Tables</p>
              <h2>Сканированная схема</h2>
            </div>
          </header>
          <div v-if="!knowledgeSummary.tables.length" class="data-view__empty">
            База подключена, но knowledge layer ещё не заполнен.
          </div>
          <button
            v-for="table in knowledgeSummary.tables"
            :key="table.id"
            type="button"
            class="data-view__table-pill"
            :class="{ 'is-active': selectedTableId === table.id }"
            @click="selectedTableId = table.id"
          >
            <strong>{{ table.schema_name }}.{{ table.table_name }}</strong>
            <span>{{ table.column_count }} cols · PK {{ table.primary_key.join(', ') || 'none' }}</span>
            <small>{{ table.row_count ?? '—' }} rows · {{ table.object_type }}</small>
          </button>
        </aside>

        <div class="data-view__detail">
          <div v-if="selectedTable" class="data-view__detail-body">
            <header class="data-view__head data-view__head--compact">
              <div>
                <p class="eyebrow">Table Editor</p>
                <h2>{{ selectedTable.schema_name }}.{{ selectedTable.table_name }}</h2>
                <p class="data-view__hint">
                  Manual fields сохраняются между сканами. Auto-поля пересчитываются при каждом parse.
                </p>
              </div>
              <button class="app-button app-button--ghost" type="button" :disabled="loadingTable" @click="loadSelectedTable">
                {{ loadingTable ? 'Загрузка…' : 'Обновить таблицу' }}
              </button>
            </header>

            <div class="data-view__form-grid">
              <label>
                <span>Description</span>
                <textarea v-model="tableDraft.description" rows="3"></textarea>
              </label>
              <label>
                <span>Business meaning</span>
                <textarea v-model="tableDraft.businessMeaning" rows="3"></textarea>
              </label>
              <label>
                <span>Domain</span>
                <input v-model="tableDraft.domain" type="text" placeholder="orders / finance / users" />
              </label>
              <label>
                <span>Tags</span>
                <input v-model="tableDraft.tags" type="text" placeholder="finance, orders, pii" />
              </label>
              <label>
                <span>Sensitivity</span>
                <input v-model="tableDraft.sensitivity" type="text" placeholder="pii / financial / internal" />
              </label>
            </div>

            <div class="data-view__inline-actions">
              <button class="app-button" type="button" :disabled="isSavingTable" @click="saveTable">
                {{ isSavingTable ? 'Сохранение…' : 'Сохранить table overrides' }}
              </button>
              <p class="data-view__auto-copy">
                Auto: {{ selectedTable.description_auto || '—' }}<br />
                Domain auto: {{ selectedTable.domain_auto || '—' }}
              </p>
            </div>

            <section class="data-view__subpanel">
              <header class="data-view__subhead">
                <h3>Columns</h3>
                <p>Manual semantic labels, synonyms и hidden-for-LLM flags.</p>
              </header>
              <div class="data-view__column-list">
                <article v-for="column in selectedTable.columns || []" :key="column.id" class="data-view__column-card">
                  <div class="data-view__column-meta">
                    <strong>{{ column.column_name }}</strong>
                    <span>{{ column.data_type }} · {{ column.is_nullable ? 'nullable' : 'required' }}</span>
                    <small>sample: {{ column.sample_values.join(', ') || '—' }}</small>
                  </div>
                  <div class="data-view__column-edit">
                    <input v-model="getColumnDraft(column).semanticLabel" type="text" placeholder="semantic label" />
                    <input v-model="getColumnDraft(column).synonyms" type="text" placeholder="synonyms через запятую" />
                    <input v-model="getColumnDraft(column).sensitivity" type="text" placeholder="sensitivity" />
                    <label class="data-view__check">
                      <input v-model="getColumnDraft(column).hiddenForLlm" type="checkbox" />
                      <span>Hide from LLM</span>
                    </label>
                    <textarea v-model="getColumnDraft(column).description" rows="2" placeholder="column description"></textarea>
                    <button class="app-button app-button--ghost app-button--tiny" type="button" @click="saveColumn(column.id)">
                      Сохранить column
                    </button>
                  </div>
                </article>
              </div>
            </section>

            <section class="data-view__subpanel">
              <header class="data-view__subhead">
                <h3>Relationships</h3>
                <p>FK edges из scan layer. Можно апрувить и отключать связи вручную.</p>
              </header>
              <div v-if="selectedTable.relationships?.length" class="data-view__relationship-list">
                <article
                  v-for="relationship in selectedTable.relationships"
                  :key="relationship.id"
                  class="data-view__relationship-card"
                >
                  <div>
                    <strong>
                      {{ relationship.from_table_name }}.{{ relationship.from_column_name }}
                      →
                      {{ relationship.to_table_name }}.{{ relationship.to_column_name }}
                    </strong>
                    <p>
                      {{ relationship.relation_type }} · confidence {{ relationship.confidence.toFixed(2) }}
                    </p>
                  </div>
                  <div class="data-view__relationship-edit">
                    <input v-model="getRelationshipDraft(relationship).cardinality" type="text" placeholder="many_to_one" />
                    <input v-model="getRelationshipDraft(relationship).confidence" type="number" min="0" max="1" step="0.1" />
                    <label class="data-view__check">
                      <input v-model="getRelationshipDraft(relationship).approved" type="checkbox" />
                      <span>Approved</span>
                    </label>
                    <label class="data-view__check">
                      <input v-model="getRelationshipDraft(relationship).isDisabled" type="checkbox" />
                      <span>Disabled</span>
                    </label>
                    <input v-model="getRelationshipDraft(relationship).description" type="text" placeholder="comment" />
                    <button
                      class="app-button app-button--ghost app-button--tiny"
                      type="button"
                      @click="saveRelationship(relationship.id)"
                    >
                      Сохранить relation
                    </button>
                  </div>
                </article>
              </div>
              <div v-else class="data-view__empty">Для выбранной таблицы связей пока нет.</div>
            </section>
          </div>
          <div v-else class="data-view__empty">
            Выберите таблицу слева, чтобы править semantics и связи.
          </div>
        </div>
      </div>
    </section>

    <section class="data-view__panel" v-if="erdGraph?.nodes.length">
      <header class="data-view__head data-view__head--compact">
        <div>
          <p class="eyebrow">ERD</p>
          <h2>Graph View</h2>
          <p class="data-view__hint">Physical FK graph по последнему scan snapshot.</p>
        </div>
      </header>
      <VChart class="data-view__erd" :option="erdOption" autoresize />
    </section>

    <section class="data-view__panel" v-if="semanticCatalog">
      <header class="data-view__head data-view__head--compact">
        <div>
          <p class="eyebrow">Semantic Catalog</p>
          <h2>Ontology layer</h2>
          <p class="data-view__hint">
            Rule-based inference plus optional LLM enrichment. Catalog хранится в БД и используется retrieval-слоем.
          </p>
        </div>
        <button class="app-button app-button--ghost" type="button" :disabled="isActivatingSemantic" @click="activateSemantic">
          {{ isActivatingSemantic ? 'Обновляем…' : 'Refresh semantic' }}
        </button>
      </header>
      <p v-if="semanticFeedback" class="data-view__feedback">{{ semanticFeedback }}</p>
      <div class="data-view__semantic-grid">
        <article class="data-view__semantic-stat">
          <span>Tables</span>
          <strong>{{ semanticCatalog.tables.length }}</strong>
        </article>
        <article class="data-view__semantic-stat">
          <span>Relationships</span>
          <strong>{{ semanticCatalog.relationships.length }}</strong>
        </article>
        <article class="data-view__semantic-stat">
          <span>Join paths</span>
          <strong>{{ semanticCatalog.join_paths.length }}</strong>
        </article>
        <article class="data-view__semantic-stat">
          <span>Dialect</span>
          <strong>{{ semanticCatalog.dialect }}</strong>
        </article>
      </div>
      <div v-if="semanticCatalog.tables.length" class="data-view__semantic-list">
        <article v-for="table in semanticCatalog.tables.slice(0, 8)" :key="`${table.schema_name}.${table.table_name}`" class="data-view__semantic-card">
          <div>
            <strong>{{ table.label }}</strong>
            <p>{{ table.schema_name }}.{{ table.table_name }} · {{ table.table_role }}</p>
          </div>
          <small>
            {{ table.columns.length }} columns ·
            {{ table.join_paths.length }} join paths
          </small>
        </article>
      </div>
    </section>

    <section class="data-view__panel">
      <header class="data-view__head">
        <div>
          <p class="eyebrow">Compatibility Layer</p>
          <h2>Dictionary</h2>
          <p class="data-view__hint">
            Semantic dictionary остаётся совместимым со старым NL→SQL pipeline. После scan он может синхронизироваться
            автоматически, а здесь его можно дополнять вручную.
          </p>
        </div>
      </header>
      <form class="data-view__create" @submit.prevent="createTerm">
        <input v-model="draft.term" type="text" placeholder="Термин (например revenue_total)" required />
        <input
          v-model="draft.mappedExpression"
          type="text"
          placeholder="SQL-выражение (например SUM(orders.amount))"
          required
        />
        <input v-model="draft.synonyms" type="text" placeholder="Синонимы через запятую" />
        <button class="app-button" type="submit" :disabled="isCreatingTerm">
          {{ isCreatingTerm ? 'Сохранение…' : 'Добавить термин' }}
        </button>
      </form>
      <p v-if="dictionaryFeedback" class="data-view__feedback">{{ dictionaryFeedback }}</p>

      <div v-if="!store.workspace.dictionary.length" class="data-view__empty">
        Словарь пуст. После scan он может автоматически наполняться table/column terms.
      </div>
      <table v-else class="data-view__table">
        <thead>
          <tr>
            <th>Термин</th>
            <th>Выражение</th>
            <th>Описание</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="term in store.workspace.dictionary" :key="term.id">
            <td>
              <strong>{{ term.term }}</strong>
              <p v-if="term.synonyms.length" class="data-view__syn">{{ term.synonyms.join(', ') }}</p>
            </td>
            <td><code>{{ term.mappedExpression }}</code></td>
            <td>{{ term.description }}</td>
            <td>
              <button class="app-button app-button--link app-button--tiny" type="button" @click="removeTerm(term.id)">
                Удалить
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
  </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import VChart from 'vue-echarts';

import { api } from '@/api/client';
import ChatSidebar from '@/components/chat/ChatSidebar.vue';
import type {
  ApiERDGraph,
  ApiKnowledgeColumn,
  ApiKnowledgeRelationship,
  ApiKnowledgeSummary,
  ApiKnowledgeTable,
  ApiSemanticCatalog
} from '@/api/types';
import { useChatStore } from '@/stores/chat';
import { useWorkspaceStore } from '@/stores/workspace';

const store = useWorkspaceStore();
const chat = useChatStore();

const selectedDatabaseId = ref('');
const knowledgeSummary = ref<ApiKnowledgeSummary | null>(null);
const semanticCatalog = ref<ApiSemanticCatalog | null>(null);
const selectedTableId = ref<string | null>(null);
const selectedTable = ref<ApiKnowledgeTable | null>(null);
const erdGraph = ref<ApiERDGraph | null>(null);
const scanRuns = ref<Array<{ id: string; scan_type: string; status: string; stage: string; summary: Record<string, unknown>; started_at: string; finished_at?: string | null }>>([]);

const isCreatingTerm = ref(false);
const isScanning = ref(false);
const isSavingTable = ref(false);
const loadingTable = ref(false);
const isActivatingSemantic = ref(false);
const isDeletingDatabase = ref(false);

const knowledgeFeedback = ref('');
const dictionaryFeedback = ref('');
const semanticFeedback = ref('');

const draft = reactive({
  term: '',
  mappedExpression: '',
  synonyms: ''
});

const tableDraft = reactive({
  description: '',
  businessMeaning: '',
  domain: '',
  tags: '',
  sensitivity: ''
});

const columnDrafts = reactive<Record<string, {
  description: string;
  semanticLabel: string;
  synonyms: string;
  sensitivity: string;
  hiddenForLlm: boolean;
}>>({});

const relationshipDrafts = reactive<Record<string, {
  cardinality: string;
  confidence: string;
  approved: boolean;
  isDisabled: boolean;
  description: string;
}>>({});

const selectedDatabase = computed(() =>
  store.workspace.databases.find((database) => database.id === selectedDatabaseId.value) ?? null
);

const erdOption = computed(() => {
  const graph = erdGraph.value;
  if (!graph?.nodes.length) {
    return {
      series: []
    };
  }

  return {
    tooltip: {
      trigger: 'item'
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: {
          repulsion: 180,
          edgeLength: 110
        },
        label: {
          show: true,
          formatter: '{b}',
          color: '#e8eaed',
          fontSize: 11
        },
        lineStyle: {
          color: '#8aa4ff',
          width: 1.4,
          opacity: 0.75
        },
        itemStyle: {
          color: '#2b6fff',
          borderColor: '#dbe5ff',
          borderWidth: 2
        },
        data: graph.nodes.map((node) => ({
          id: node.id,
          name: node.table_name,
          value: node.row_count ?? node.column_count,
          symbolSize: Math.max(34, Math.min(68, 22 + node.column_count * 2)),
          category: node.schema_name
        })),
        links: graph.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.source_label
        }))
      }
    ]
  };
});

function formatTimestamp(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

function numberFromSummary(summary: Record<string, unknown>, key: string) {
  const value = summary[key];
  return typeof value === 'number' ? value : 0;
}

function splitCsv(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function syncTableDraft(table: ApiKnowledgeTable | null) {
  tableDraft.description = table?.description_manual ?? '';
  tableDraft.businessMeaning = table?.business_meaning_manual ?? '';
  tableDraft.domain = table?.domain_manual ?? '';
  tableDraft.tags = (table?.tags ?? []).join(', ');
  tableDraft.sensitivity = table?.sensitivity ?? '';

  Object.keys(columnDrafts).forEach((key) => delete columnDrafts[key]);
  Object.keys(relationshipDrafts).forEach((key) => delete relationshipDrafts[key]);

  for (const column of table?.columns ?? []) {
    columnDrafts[column.id] = {
      description: column.description_manual ?? '',
      semanticLabel: column.semantic_label_manual ?? column.semantic_label_auto ?? '',
      synonyms: column.synonyms.join(', '),
      sensitivity: column.sensitivity ?? '',
      hiddenForLlm: Boolean(column.hidden_for_llm)
    };
  }

  for (const relationship of table?.relationships ?? []) {
    relationshipDrafts[relationship.id] = {
      cardinality: relationship.cardinality ?? '',
      confidence: String(relationship.confidence ?? 1),
      approved: Boolean(relationship.approved),
      isDisabled: Boolean(relationship.is_disabled),
      description: relationship.description_manual ?? ''
    };
  }
}

function getColumnDraft(column: ApiKnowledgeColumn) {
  if (!columnDrafts[column.id]) {
    columnDrafts[column.id] = {
      description: column.description_manual ?? '',
      semanticLabel: column.semantic_label_manual ?? column.semantic_label_auto ?? '',
      synonyms: column.synonyms.join(', '),
      sensitivity: column.sensitivity ?? '',
      hiddenForLlm: Boolean(column.hidden_for_llm)
    };
  }
  return columnDrafts[column.id];
}

function getRelationshipDraft(relationship: ApiKnowledgeRelationship) {
  if (!relationshipDrafts[relationship.id]) {
    relationshipDrafts[relationship.id] = {
      cardinality: relationship.cardinality ?? '',
      confidence: String(relationship.confidence ?? 1),
      approved: Boolean(relationship.approved),
      isDisabled: Boolean(relationship.is_disabled),
      description: relationship.description_manual ?? ''
    };
  }
  return relationshipDrafts[relationship.id];
}

function mergeTableIntoSummary(table: ApiKnowledgeTable) {
  selectedTable.value = table;
  syncTableDraft(table);
  if (!knowledgeSummary.value) return;
  knowledgeSummary.value.tables = knowledgeSummary.value.tables.map((item) =>
    item.id === table.id
      ? {
          ...item,
          description_manual: table.description_manual,
          business_meaning_manual: table.business_meaning_manual,
          domain_manual: table.domain_manual,
          tags: table.tags,
          sensitivity: table.sensitivity,
          column_count: table.column_count,
          row_count: table.row_count,
          primary_key: table.primary_key
        }
      : item
  );
}

async function loadSelectedTable() {
  if (!selectedTableId.value) {
    selectedTable.value = null;
    return;
  }
  loadingTable.value = true;
  try {
    const table = await api.getKnowledgeTable(selectedTableId.value);
    selectedTable.value = table;
    syncTableDraft(table);
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось загрузить детали таблицы.';
    selectedTable.value = null;
  } finally {
    loadingTable.value = false;
  }
}

async function loadKnowledge() {
  if (!selectedDatabaseId.value) {
    knowledgeSummary.value = null;
    selectedTable.value = null;
    scanRuns.value = [];
    erdGraph.value = null;
    semanticCatalog.value = null;
    return;
  }

  knowledgeFeedback.value = '';
  try {
    const [summary, runs, graph] = await Promise.all([
      api.getKnowledge(selectedDatabaseId.value),
      api.getKnowledgeScanRuns(selectedDatabaseId.value),
      api.getERD(selectedDatabaseId.value)
    ]);
    knowledgeSummary.value = summary;
    scanRuns.value = runs;
    erdGraph.value = graph;

    const stillExists = summary.tables.find((table) => table.id === selectedTableId.value);
    if (!stillExists) {
      selectedTableId.value = summary.tables[0]?.id ?? null;
    }

    if (selectedTableId.value) {
      await loadSelectedTable();
    } else {
      selectedTable.value = null;
    }
    await loadSemanticCatalog();
  } catch (error) {
    knowledgeSummary.value = null;
    selectedTable.value = null;
    scanRuns.value = [];
    erdGraph.value = null;
    semanticCatalog.value = null;
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось загрузить knowledge layer.';
  }
}

async function loadSemanticCatalog() {
  if (!selectedDatabaseId.value) {
    semanticCatalog.value = null;
    return;
  }

  semanticFeedback.value = '';
  try {
    semanticCatalog.value = await api.getSemanticCatalog(selectedDatabaseId.value);
  } catch (error) {
    semanticCatalog.value = null;
    semanticFeedback.value = error instanceof Error ? error.message : 'Не удалось загрузить semantic catalog.';
  }
}

async function reload() {
  await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
  await chat.loadDatabases();
  if (!selectedDatabaseId.value) {
    selectedDatabaseId.value = store.workspace.databases[0]?.id ?? '';
    if (selectedDatabaseId.value) {
      await selectDatabase(selectedDatabaseId.value);
      return;
    }
  }
  if (selectedDatabaseId.value) {
    await chat.loadSessions(selectedDatabaseId.value);
  }
  await loadKnowledge();
}

async function runScan(mode: 'full' | 'incremental') {
  if (!selectedDatabaseId.value) return;
  isScanning.value = true;
  knowledgeFeedback.value = '';
  try {
    if (mode === 'full') {
      await api.runKnowledgeFullScan(selectedDatabaseId.value);
    } else {
      await api.runKnowledgeIncrementalScan(selectedDatabaseId.value);
    }
    await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
    await chat.loadDatabases();
    await loadKnowledge();
    knowledgeFeedback.value = `${mode === 'full' ? 'Full' : 'Incremental'} scan завершён.`;
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось выполнить scan.';
  } finally {
    isScanning.value = false;
  }
}

async function activateSemantic() {
  if (!selectedDatabaseId.value) return;
  isActivatingSemantic.value = true;
  semanticFeedback.value = '';
  try {
    semanticCatalog.value = await api.activateSemanticCatalog({
      database_id: selectedDatabaseId.value,
      refresh: true
    });
    semanticFeedback.value = 'Semantic catalog activated.';
  } catch (error) {
    semanticFeedback.value = error instanceof Error ? error.message : 'Не удалось активировать semantic.';
  } finally {
    isActivatingSemantic.value = false;
  }
}

async function deleteSelectedDatabase() {
  if (!selectedDatabase.value || selectedDatabase.value.isDemo || !selectedDatabaseId.value) {
    return;
  }
  const confirmed = window.confirm(`Удалить базу данных «${selectedDatabase.value.name}»?`);
  if (!confirmed) {
    return;
  }
  isDeletingDatabase.value = true;
  try {
    await api.deleteDatabase(selectedDatabaseId.value);
    await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
    await chat.loadDatabases();
    const nextDatabase = store.workspace.databases[0]?.id ?? '';
    selectedDatabaseId.value = nextDatabase;
    if (nextDatabase) {
      await chat.selectDatabase(nextDatabase);
    } else {
      semanticCatalog.value = null;
      knowledgeSummary.value = null;
      selectedTable.value = null;
      scanRuns.value = [];
      erdGraph.value = null;
    }
    knowledgeFeedback.value = 'Database deleted.';
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось удалить базу.';
  } finally {
    isDeletingDatabase.value = false;
  }
}

async function selectDatabase(databaseId: string) {
  if (!databaseId) {
    return;
  }
  if (databaseId === selectedDatabaseId.value) {
    await chat.selectDatabase(databaseId);
    return;
  }
  selectedDatabaseId.value = databaseId;
  await chat.selectDatabase(databaseId);
}

function handleDatabaseSelectChange(event: Event) {
  const target = event.target as HTMLSelectElement | null;
  if (!target) {
    return;
  }
  void selectDatabase(target.value);
}

function selectChatSession(sessionId: string) {
  void chat.selectSession(sessionId);
}

function createChatSession() {
  void chat.createSession(selectedDatabaseId.value || undefined);
}

function renameChatSession(sessionId: string, title: string) {
  void chat.renameSession(sessionId, title);
}

function deleteChatSession(sessionId: string) {
  void chat.deleteSession(sessionId);
}

async function saveTable() {
  if (!selectedTable.value) return;
  isSavingTable.value = true;
  try {
    const table = await api.updateKnowledgeTable(selectedTable.value.id, {
      description_manual: tableDraft.description || null,
      business_meaning_manual: tableDraft.businessMeaning || null,
      domain_manual: tableDraft.domain || null,
      tags: splitCsv(tableDraft.tags),
      sensitivity: tableDraft.sensitivity || null
    });
    mergeTableIntoSummary(table);
    erdGraph.value = await api.getERD(selectedDatabaseId.value);
    knowledgeFeedback.value = 'Table overrides сохранены.';
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось сохранить таблицу.';
  } finally {
    isSavingTable.value = false;
  }
}

async function saveColumn(columnId: string) {
  const draftState = columnDrafts[columnId];
  if (!draftState) return;
  try {
    const table = await api.updateKnowledgeColumn(columnId, {
      description_manual: draftState.description || null,
      semantic_label_manual: draftState.semanticLabel || null,
      synonyms: splitCsv(draftState.synonyms),
      sensitivity: draftState.sensitivity || null,
      hidden_for_llm: draftState.hiddenForLlm
    });
    mergeTableIntoSummary(table);
    knowledgeFeedback.value = 'Column overrides сохранены.';
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось сохранить колонку.';
  }
}

async function saveRelationship(relationshipId: string) {
  const draftState = relationshipDrafts[relationshipId];
  if (!draftState) return;
  try {
    const table = await api.updateKnowledgeRelationship(relationshipId, {
      cardinality: draftState.cardinality || null,
      confidence: Number.parseFloat(draftState.confidence) || 0,
      approved: draftState.approved,
      is_disabled: draftState.isDisabled,
      description_manual: draftState.description || null
    });
    mergeTableIntoSummary(table);
    erdGraph.value = await api.getERD(selectedDatabaseId.value);
    knowledgeFeedback.value = 'Relationship overrides сохранены.';
  } catch (error) {
    knowledgeFeedback.value = error instanceof Error ? error.message : 'Не удалось сохранить связь.';
  }
}

async function createTerm() {
  isCreatingTerm.value = true;
  dictionaryFeedback.value = '';
  try {
    const synonyms = splitCsv(draft.synonyms);
    await api.createDictionaryEntry({
      term: draft.term.trim(),
      synonyms,
      mapped_expression: draft.mappedExpression.trim(),
      description: 'Добавлено вручную из Data View',
      object_type: 'manual'
    });
    draft.term = '';
    draft.mappedExpression = '';
    draft.synonyms = '';
    dictionaryFeedback.value = 'Термин добавлен.';
    await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
  } finally {
    isCreatingTerm.value = false;
  }
}

async function removeTerm(id: string) {
  await api.deleteDictionaryEntry(id);
  await store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep');
}

watch(
  selectedDatabaseId,
  async (value, previousValue) => {
    if (!value || value === previousValue) return;
    selectedTableId.value = null;
    selectedTable.value = null;
    await loadKnowledge();
  }
);

watch(
  selectedTableId,
  async (value, previousValue) => {
    if (!value || value === previousValue) return;
    await loadSelectedTable();
  }
);

onMounted(async () => {
  await Promise.allSettled([
    store.refreshWorkspace(store.selectedNotebookId || undefined, 'keep'),
    chat.initialize()
  ]);
  selectedDatabaseId.value = chat.activeDbId || store.workspace.databases[0]?.id || '';
  if (selectedDatabaseId.value && chat.activeDbId !== selectedDatabaseId.value) {
    await chat.selectDatabase(selectedDatabaseId.value);
  }
});
</script>

<style scoped lang="scss">
.data-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 300px) minmax(0, 1fr);
  gap: 1rem;
  padding: 1rem;
  background: var(--bg);
}

.data-shell__sidebar {
  min-height: 0;
}

.data-shell__content {
  min-height: 0;
  overflow: auto;
}

.data-view {
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-view__panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at top right, rgba(138, 180, 248, 0.08), transparent 28%),
    linear-gradient(180deg, rgba(26, 29, 36, 0.96), rgba(18, 20, 27, 0.98));
  padding: 1.1rem 1.15rem;
  box-shadow: var(--shadow-soft);
}

.data-view__panel--hero {
  background:
    radial-gradient(circle at top right, rgba(129, 201, 149, 0.08), transparent 24%),
    radial-gradient(circle at top left, rgba(138, 180, 248, 0.14), transparent 28%),
    linear-gradient(180deg, rgba(21, 24, 34, 0.98), rgba(15, 17, 23, 0.99));
}

.data-view__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__head--compact {
  margin-bottom: 0.8rem;
}

.data-view__head h1,
.data-view__head h2 {
  margin: 0.2rem 0 0.25rem;
  color: var(--ink-strong);
}

.data-view__head h1 {
  font-size: 1.28rem;
}

.data-view__head h2 {
  font-size: 1.04rem;
}

.data-view__hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.86rem;
  line-height: 1.45;
  max-width: 760px;
}

.data-view__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
}

.data-view__select,
.data-view__form-grid input,
.data-view__form-grid textarea,
.data-view__create input,
.data-view__column-edit input,
.data-view__column-edit textarea,
.data-view__relationship-edit input {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: rgba(18, 20, 27, 0.92);
  color: var(--ink);
}

.data-view__select {
  min-width: 240px;
}

.data-view__feedback {
  margin: 0;
  color: var(--muted);
  font-size: 0.84rem;
}

.data-view__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.data-view__stat {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__stat span,
.data-view__stat small {
  display: block;
  color: var(--muted);
}

.data-view__stat strong {
  display: block;
  margin: 0.2rem 0;
  color: var(--ink-strong);
}

.data-view__scan-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
}

.data-view__scan-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(21, 24, 34, 0.94);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__scan-card p,
.data-view__scan-card span,
.data-view__scan-card small {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.data-view__knowledge {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 1rem;
}

.data-view__tables {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.data-view__table-pill {
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(21, 24, 34, 0.88);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.data-view__table-pill strong,
.data-view__table-pill span,
.data-view__table-pill small {
  display: block;
}

.data-view__table-pill span,
.data-view__table-pill small {
  color: var(--muted);
  font-size: 0.8rem;
}

.data-view__table-pill.is-active {
  border-color: rgba(138, 180, 248, 0.34);
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.12);
  background: rgba(26, 39, 64, 0.92);
}

.data-view__detail {
  min-width: 0;
}

.data-view__detail-body,
.data-view__subpanel {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.data-view__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.data-view__form-grid label,
.data-view__column-edit,
.data-view__relationship-edit {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__form-grid span {
  font-size: 0.78rem;
  color: var(--muted);
}

.data-view__form-grid textarea {
  resize: vertical;
}

.data-view__inline-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.data-view__auto-copy {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.data-view__subpanel {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.85rem;
}

.data-view__subhead h3 {
  margin: 0;
  font-size: 0.98rem;
  color: var(--ink-strong);
}

.data-view__subhead p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.data-view__column-list,
.data-view__relationship-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.data-view__column-card,
.data-view__relationship-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(18, 20, 27, 0.9);
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  gap: 0.75rem;
}

.data-view__column-meta,
.data-view__relationship-card > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.data-view__column-meta span,
.data-view__column-meta small,
.data-view__relationship-card p {
  color: var(--muted);
  font-size: 0.8rem;
  margin: 0;
}

.data-view__relationship-edit {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.55rem;
  align-items: center;
}

.data-view__check {
  display: inline-flex;
  gap: 0.4rem;
  align-items: center;
  font-size: 0.78rem;
  color: var(--muted);
}

.data-view__erd {
  width: 100%;
  height: 480px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background:
    radial-gradient(circle at top, rgba(138, 180, 248, 0.06), transparent 32%),
    rgba(18, 20, 27, 0.92);
}

.data-view__semantic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.data-view__semantic-stat {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__semantic-stat span {
  display: block;
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__semantic-stat strong {
  display: block;
  margin-top: 0.25rem;
  color: var(--ink-strong);
}

.data-view__semantic-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.65rem;
}

.data-view__semantic-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(21, 24, 34, 0.9);
}

.data-view__semantic-card strong,
.data-view__semantic-card p,
.data-view__semantic-card small {
  display: block;
  margin: 0;
}

.data-view__semantic-card p,
.data-view__semantic-card small {
  color: var(--muted);
  font-size: 0.8rem;
}

.data-view__create {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 0.55rem;
  margin-bottom: 0.9rem;
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
}

.data-view__syn {
  margin: 0.25rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__empty {
  padding: 1rem;
  color: var(--muted);
  text-align: center;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  background: rgba(21, 24, 34, 0.72);
}

@media (max-width: 1100px) {
  .data-shell {
    grid-template-columns: 1fr;
  }

  .data-view__knowledge,
  .data-view__stats,
  .data-view__semantic-grid,
  .data-view__form-grid,
  .data-view__column-card,
  .data-view__relationship-card,
  .data-view__relationship-edit,
  .data-view__create {
    grid-template-columns: 1fr;
  }

  .data-view__inline-actions,
  .data-view__head {
    flex-direction: column;
    align-items: stretch;
  }

  .data-view__select {
    min-width: 0;
  }
}
</style>
