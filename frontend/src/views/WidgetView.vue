<template>
  <main class="widget-view">
    <template v-if="loading">
      <div class="widget-view__skeleton">
        <div class="widget-view__header">
          <div class="widget-view__meta widget-view__meta--skeleton">
            <AppSkeleton width="220px" height="1.6rem" radius="8px" />
            <AppSkeleton width="130px" height="0.78rem" radius="5px" />
          </div>
          <div class="widget-view__header-actions widget-view__header-actions--skeleton">
            <AppSkeleton
              v-for="action in 3"
              :key="`widget-header-skeleton-${action}`"
              width="126px"
              height="30px"
              radius="8px"
            />
          </div>
        </div>

        <div class="widget-view__body">
          <section class="widget-view__section">
            <div class="widget-view__section-header">
              <AppSkeleton width="108px" height="0.8rem" radius="6px" />
              <AppSkeleton width="96px" height="26px" radius="8px" />
            </div>
            <AppSkeleton height="220px" radius="12px" />
          </section>

          <section class="widget-view__section widget-view__section--result">
            <div class="widget-view__section-header">
              <AppSkeleton width="92px" height="0.8rem" radius="6px" />
              <AppSkeleton width="96px" height="26px" radius="8px" />
            </div>
            <div class="widget-view__result-skeleton">
              <AppSkeleton height="1rem" width="38%" radius="6px" />
              <AppSkeleton height="1rem" width="54%" radius="6px" />
              <AppSkeleton
                class="widget-view__result-skeleton-block"
                height="100%"
                radius="12px"
              />
            </div>
          </section>
        </div>
      </div>
    </template>
    <template v-else>
    <div v-if="loading" class="widget-view__loading">Загрузка…</div>
    <div v-else-if="error" class="widget-view__error">{{ error }}</div>

    <template v-else-if="widget">
      <div class="widget-view__header">
        <div class="widget-view__meta">
          <h1 v-if="!editingTitle" class="widget-view__title" @dblclick="startEditTitle">
            {{ widget.title }}
          </h1>
          <input
            v-else
            ref="titleInput"
            v-model="titleDraft"
            class="widget-view__title-input"
            @blur="saveTitle"
            @keydown.enter="saveTitle"
            @keydown.esc="editingTitle = false"
          />
          <span class="widget-view__updated">Обновлён {{ formatDate(widget.updated_at) }}</span>
        </div>

        <div class="widget-view__header-actions">
          <button class="wbtn wbtn--ghost" type="button" @click="copyLink">Копировать ссылку</button>
          <button class="wbtn wbtn--ghost" type="button" @click="showAddToDashboard = true">+ Добавить в дашборд</button>
          <button class="wbtn wbtn--danger" type="button" @click="confirmDelete">Удалить</button>
        </div>
      </div>

      <div class="widget-view__body">
        <section v-if="widget.source_type === 'text'" class="widget-view__section">
          <div class="widget-view__section-header">
            <span class="widget-view__section-title">Текстовый виджет</span>
            <button
              v-if="!editingText"
              class="wbtn wbtn--ghost wbtn--sm"
              type="button"
              @click="startEditText"
            >
              Редактировать
            </button>
            <div v-else class="widget-view__sql-actions">
              <button class="wbtn wbtn--ghost wbtn--sm" type="button" @click="cancelEditText">
                Отмена
              </button>
              <button class="wbtn wbtn--primary wbtn--sm" type="button" :disabled="savingText" @click="saveText">
                {{ savingText ? '…' : 'Сохранить' }}
              </button>
            </div>
          </div>
          <textarea
            v-model="textDraft"
            class="widget-view__text-editor"
            :readonly="!editingText"
            rows="10"
          />
        </section>

        <!-- SQL section -->
        <section v-else class="widget-view__section">
          <div class="widget-view__section-header">
            <span class="widget-view__section-title">SQL</span>
            <button v-if="!editingSql" class="wbtn wbtn--ghost wbtn--sm" type="button" @click="startEditSql">Редактировать</button>
            <div v-else class="widget-view__sql-actions">
              <button class="wbtn wbtn--ghost wbtn--sm" type="button" @click="editingSql = false">Отмена</button>
              <button class="wbtn wbtn--primary wbtn--sm" type="button" :disabled="savingSql" @click="saveSql">
                {{ savingSql ? '…' : 'Сохранить' }}
              </button>
            </div>
          </div>
          <textarea
            v-model="sqlDraft"
            class="widget-view__sql-editor"
            :readonly="!editingSql"
            rows="6"
          />
        </section>

        <!-- Result section -->
        <section class="widget-view__section widget-view__section--result">
          <div class="widget-view__section-header">
            <span class="widget-view__section-title">Результат</span>
            <div class="widget-view__result-tabs" v-if="lastRun?.status === 'completed'">
              <button
                v-for="opt in vizOptions"
                :key="opt.value"
                class="widget-view__result-tab"
                :class="{ 'widget-view__result-tab--active': resultView === opt.value }"
                type="button"
                @click="resultView = opt.value"
              >{{ opt.label }}</button>
            </div>
            <button
              class="wbtn wbtn--ghost wbtn--sm"
              type="button"
              :disabled="running"
              @click="rerun"
            >
              {{ running ? 'Выполняю…' : 'Обновить' }}
            </button>
          </div>

          <div v-if="running" class="widget-view__result-loading">Выполнение…</div>

          <template v-else-if="lastRun">
            <div v-if="lastRun.status === 'error'" class="widget-view__result-error">
              {{ lastRun.error_text }}
            </div>
            <template v-else-if="lastRun.status === 'completed'">
              <WidgetResultTable
                v-if="resultView === 'table'"
                :columns="lastRun.columns ?? []"
                :rows="lastRun.rows_preview ?? []"
                :truncated="lastRun.rows_preview_truncated"
              />
              <WidgetResultChart
                v-else
                :run="lastRun"
                :viz-type="widget.visualization_type"
                :viz-config="widget.visualization_config"
                :chart-spec="widget.chart_spec_json"
              />
            </template>
          </template>
          <div v-else class="widget-view__result-empty">
            Нажмите «Обновить», чтобы загрузить данные.
          </div>
        </section>
      </div>

      <!-- Add to dashboard modal -->
      <AddToDashboardModal
        v-if="showAddToDashboard"
        :widget-id="widget.id"
        @close="showAddToDashboard = false"
      />
    </template>

    <div v-if="linkCopied" class="widget-view__toast">Ссылка скопирована!</div>
    </template>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api/client';
import AppSkeleton from '@/components/ui/AppSkeleton.vue';
import { useWidgetsStore } from '@/stores/widgets';
import WidgetResultTable from '@/components/widgets/WidgetResultTable.vue';
import WidgetResultChart from '@/components/widgets/WidgetResultChart.vue';
import AddToDashboardModal from '@/components/widgets/AddToDashboardModal.vue';
import type { ApiWidgetDetail } from '@/api/types';

const route = useRoute();
const router = useRouter();
const widgetsStore = useWidgetsStore();

const widget = ref<ApiWidgetDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const running = ref(false);

const editingTitle = ref(false);
const titleDraft = ref('');
const titleInput = ref<HTMLInputElement | null>(null);

const editingSql = ref(false);
const sqlDraft = ref('');
const savingSql = ref(false);
const editingText = ref(false);
const textDraft = ref('');
const savingText = ref(false);

const resultView = ref<'table' | 'bar' | 'line' | 'area' | 'pie' | 'metric'>('table');
const showAddToDashboard = ref(false);
const linkCopied = ref(false);

const lastRun = computed(() => widget.value?.last_run ?? null);

const vizOptions = [
  { value: 'table', label: 'Таблица' },
  { value: 'bar', label: 'График' },
] as const;

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

async function loadWidget() {
  loading.value = true;
  error.value = null;
  try {
    widget.value = await api.getWidget(route.params.id as string);
    sqlDraft.value = widget.value.sql_text;
    textDraft.value = widget.value.description ?? '';
    resultView.value = (widget.value.visualization_type as typeof resultView.value) ?? 'table';
    if (widget.value.refresh_policy === 'on_view' && !widget.value.last_run) {
      await rerun();
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось загрузить виджет.';
  } finally {
    loading.value = false;
  }
}

async function rerun() {
  if (!widget.value) return;
  running.value = true;
  try {
    widget.value = await widgetsStore.runWidget(widget.value.id);
  } finally {
    running.value = false;
  }
}

async function startEditTitle() {
  titleDraft.value = widget.value?.title ?? '';
  editingTitle.value = true;
  await nextTick();
  titleInput.value?.focus();
}

async function saveTitle() {
  if (!widget.value || !titleDraft.value.trim()) { editingTitle.value = false; return; }
  editingTitle.value = false;
  widget.value = await widgetsStore.updateWidget(widget.value.id, { title: titleDraft.value.trim() });
}

function startEditSql() {
  sqlDraft.value = widget.value?.sql_text ?? '';
  editingSql.value = true;
}

async function saveSql() {
  if (!widget.value) return;
  savingSql.value = true;
  try {
    widget.value = await widgetsStore.updateWidget(widget.value.id, { sql_text: sqlDraft.value });
    editingSql.value = false;
  } finally {
    savingSql.value = false;
  }
}

function startEditText() {
  textDraft.value = widget.value?.description ?? '';
  editingText.value = true;
}

function cancelEditText() {
  textDraft.value = widget.value?.description ?? '';
  editingText.value = false;
}

async function saveText() {
  if (!widget.value) return;
  savingText.value = true;
  try {
    widget.value = await widgetsStore.updateWidget(widget.value.id, { description: textDraft.value });
    editingText.value = false;
  } finally {
    savingText.value = false;
  }
}

async function confirmDelete() {
  if (!widget.value) return;
  if (!window.confirm(`Удалить виджет «${widget.value.title}»?`)) return;
  await widgetsStore.deleteWidget(widget.value.id);
  void router.push('/widgets');
}

function copyLink() {
  void navigator.clipboard.writeText(window.location.href);
  linkCopied.value = true;
  setTimeout(() => { linkCopied.value = false; }, 2000);
}

onMounted(() => { void loadWidget(); });
</script>

<style scoped lang="scss">
.widget-view {
  padding: 20px 24px;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
  position: relative;
}

.widget-view__loading,
.widget-view__error {
  padding: 40px;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
}

.widget-view__skeleton {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.widget-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.widget-view__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.widget-view__meta--skeleton {
  min-width: min(240px, 100%);
}

.widget-view__title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ink-strong);
  margin: 0;
  cursor: pointer;
}

.widget-view__title-input {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ink-strong);
  background: var(--bg);
  border: 1px solid rgba(112, 59, 247, 0.7);
  border-radius: 6px;
  padding: 2px 6px;
  outline: none;
}

.widget-view__updated {
  font-size: 0.72rem;
  color: var(--muted);
}

.widget-view__header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.widget-view__header-actions--skeleton {
  align-items: center;
}

.widget-view__body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.widget-view__section {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.widget-view__section--result {
  min-height: 280px;
}

.widget-view__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.widget-view__section-title {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.widget-view__sql-editor {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  padding: 10px 12px;
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  outline: none;

  &:not([readonly]):focus { border-color: rgba(112, 59, 247, 0.7); }
  &[readonly] { opacity: 0.8; cursor: default; }
}

.widget-view__text-editor {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.6;
  padding: 12px 14px;
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  min-height: 260px;
  outline: none;

  &:not([readonly]):focus { border-color: rgba(112, 59, 247, 0.7); }
  &[readonly] { opacity: 0.8; cursor: default; }
}

.widget-view__sql-actions {
  display: flex;
  gap: 6px;
}

.widget-view__result-tabs {
  display: inline-flex;
  gap: 6px;
}

.widget-view__result-tab {
  min-height: 26px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 0.75rem;
  cursor: pointer;

  &--active {
    border-color: rgba(112, 59, 247, 0.8);
    background: rgba(112, 59, 247, 0.18);
    color: var(--ink-strong);
  }
}

.widget-view__result-loading,
.widget-view__result-empty {
  color: var(--muted);
  font-size: 0.85rem;
  padding: 24px 0;
  text-align: center;
}

.widget-view__result-skeleton {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
}

.widget-view__result-skeleton-block {
  flex: 1;
  min-height: 180px;
}

.widget-view__result-error {
  border: 1px solid rgba(255, 107, 107, 0.5);
  border-radius: 8px;
  background: rgba(255, 107, 107, 0.1);
  color: #ffb3b3;
  font-size: 0.82rem;
  padding: 10px 12px;
}

.widget-view__toast {
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
  &--sm { min-height: 26px; font-size: 0.75rem; padding: 0 8px; }
}

.wbtn--ghost:hover { background: var(--line); }
.wbtn--primary {
  background: rgba(112, 59, 247, 0.85);
  border-color: transparent;
  color: #fff;
  font-weight: 600;
  &:not(:disabled):hover { background: rgba(112, 59, 247, 1); }
}
.wbtn--danger {
  border-color: rgba(255, 80, 80, 0.5);
  color: #ff7070;
  &:hover { background: rgba(255, 80, 80, 0.12); }
}
</style>
