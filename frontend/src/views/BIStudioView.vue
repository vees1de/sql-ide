<template>
  <main class="bi-studio">
    <aside class="bi-studio__datasets">
      <div class="bi-studio__brand-row">
        <RouterLink to="/chat" class="bi-studio__brand">BimsDash</RouterLink>
        <RouterLink to="/dashboards" class="bi-studio__link">Дашборды</RouterLink>
      </div>

      <header class="bi-studio__datasets-head">
        <div>
          <p class="bi-studio__eyebrow">Datasets</p>
          <h1>BI Studio</h1>
        </div>
        <button class="bi-studio__icon-btn" type="button" :disabled="loading" @click="loadDatasets">
          ↻
        </button>
      </header>

      <p class="bi-studio__hint">
        Любой успешный SQL-запрос из чата уже сохранён как dataset. Здесь из него можно собрать ChartSpec, widget и dashboard.
      </p>

      <div v-if="loading" class="bi-studio__state">Загружаю datasets…</div>
      <div v-else-if="!datasets.length" class="bi-studio__state">
        Пока нет datasets. Выполните SQL в чате, затем вернитесь сюда.
      </div>
      <div v-else class="bi-studio__dataset-list">
        <button
          v-for="dataset in datasets"
          :key="dataset.id"
          class="bi-studio__dataset-card"
          :class="{ 'bi-studio__dataset-card--active': dataset.id === activeDatasetId }"
          type="button"
          @click="selectDataset(dataset.id)"
        >
          <span class="bi-studio__dataset-title">{{ dataset.name }}</span>
          <span class="bi-studio__dataset-meta">
            {{ dataset.row_count }} строк · {{ dataset.fields.length }} полей · {{ dataset.widgets_count }} charts
          </span>
        </button>
      </div>
    </aside>

    <section class="bi-studio__workspace app-route-section">
      <div class="bi-studio__topbar">
        <div>
          <p class="bi-studio__eyebrow">Semantic dataset → ChartSpec → Widget → Dashboard</p>
          <h2>{{ activeDataset?.name ?? 'Выберите dataset' }}</h2>
        </div>
        <div class="bi-studio__top-actions">
          <button
            class="wbtn wbtn--ghost"
            type="button"
            :disabled="!activeDataset || refreshing"
            @click="refreshActiveDataset"
          >
            {{ refreshing ? 'Обновляю…' : 'Refresh dataset' }}
          </button>
          <button
            class="wbtn wbtn--primary"
            type="button"
            :disabled="!activeDataset || creatingDashboard"
            @click="createQuickDashboard"
          >
            {{ creatingDashboard ? 'Создаю…' : 'Auto dashboard' }}
          </button>
        </div>
      </div>

      <p v-if="error" class="bi-studio__error">{{ error }}</p>
      <p v-if="notice" class="bi-studio__notice">{{ notice }}</p>

      <template v-if="activeDataset">
        <section class="bi-studio__panel bi-studio__panel--dataset">
          <div class="bi-studio__panel-head">
            <div>
              <p class="bi-studio__eyebrow">Dataset schema</p>
              <h3>Поля, роли и preview</h3>
            </div>
            <span class="bi-studio__pill">{{ activeDataset.source_type }}</span>
          </div>

          <div class="bi-studio__field-grid">
            <article v-for="field in activeDataset.fields" :key="field.name" class="bi-studio__field-card">
              <strong>{{ field.name }}</strong>
              <div class="bi-studio__chips">
                <span>{{ field.semantic_role }}</span>
                <span>{{ field.data_type }}</span>
                <span v-if="field.default_aggregation">{{ field.default_aggregation }}</span>
              </div>
              <small v-if="field.sample_values.length">{{ field.sample_values.slice(0, 3).join(', ') }}</small>
            </article>
          </div>
        </section>

        <section class="bi-studio__main-grid">
          <div class="bi-studio__left-column">
            <section class="bi-studio__panel">
              <div class="bi-studio__panel-head">
                <div>
                  <p class="bi-studio__eyebrow">Auto chart suggestions</p>
                  <h3>Рекомендации</h3>
                </div>
                <button class="wbtn wbtn--ghost wbtn--sm" type="button" :disabled="recommending" @click="loadRecommendations">
                  {{ recommending ? '…' : 'Обновить' }}
                </button>
              </div>

              <div v-if="!recommendations.length" class="bi-studio__state bi-studio__state--compact">
                Рекомендаций пока нет.
              </div>
              <div v-else class="bi-studio__recommendations">
                <button
                  v-for="recommendation in recommendations"
                  :key="recommendation.title + recommendation.chart_spec.chart_type"
                  class="bi-studio__recommendation"
                  type="button"
                  @click="applyRecommendation(recommendation)"
                >
                  <span>
                    <strong>{{ recommendation.title }}</strong>
                    <small>{{ recommendation.reason }}</small>
                  </span>
                  <b>{{ Math.round(recommendation.score * 100) }}%</b>
                </button>
              </div>
            </section>

            <section class="bi-studio__panel">
              <div class="bi-studio__panel-head">
                <div>
                  <p class="bi-studio__eyebrow">Manual chart builder</p>
                  <h3>ChartSpec</h3>
                </div>
              </div>

              <div class="bi-studio__form-grid">
                <label>
                  <span>Title</span>
                  <input v-model="manualSpec.title" type="text" />
                </label>

                <label>
                  <span>Chart type</span>
                  <select v-model="manualSpec.chart_type">
                    <option value="table">Table</option>
                    <option value="metric_card">KPI card</option>
                    <option value="line">Line</option>
                    <option value="bar">Bar</option>
                    <option value="area">Area</option>
                    <option value="pie">Pie</option>
                  </select>
                </label>

                <label>
                  <span>X axis</span>
                  <select v-model="manualSpec.encoding.x_field" :disabled="manualSpec.chart_type === 'metric_card' || manualSpec.chart_type === 'table'">
                    <option :value="null">—</option>
                    <option v-for="field in xFields" :key="field.name" :value="field.name">{{ field.name }}</option>
                  </select>
                </label>

                <label>
                  <span>Y metric</span>
                  <select v-model="manualSpec.encoding.y_field" :disabled="manualSpec.chart_type === 'table'">
                    <option :value="null">—</option>
                    <option v-for="field in yFields" :key="field.name" :value="field.name">{{ field.name }}</option>
                  </select>
                </label>

                <label>
                  <span>Series / breakdown</span>
                  <select v-model="manualSpec.encoding.series_field" :disabled="manualSpec.chart_type === 'metric_card' || manualSpec.chart_type === 'table' || manualSpec.chart_type === 'pie'">
                    <option :value="null">—</option>
                    <option v-for="field in seriesFields" :key="field.name" :value="field.name">{{ field.name }}</option>
                  </select>
                </label>

                <label>
                  <span>Aggregation</span>
                  <select v-model="manualSpec.encoding.aggregation" :disabled="manualSpec.chart_type === 'table'">
                    <option value="sum">sum</option>
                    <option value="avg">avg</option>
                    <option value="count">count</option>
                    <option value="count_distinct">count distinct</option>
                    <option value="min">min</option>
                    <option value="max">max</option>
                  </select>
                </label>

                <label>
                  <span>Sort</span>
                  <select v-model="manualSpec.encoding.sort" :disabled="manualSpec.chart_type === 'metric_card' || manualSpec.chart_type === 'table'">
                    <option value="x_asc">X asc</option>
                    <option value="x_desc">X desc</option>
                    <option value="y_desc">Y desc</option>
                    <option value="y_asc">Y asc</option>
                    <option value="none">No sort</option>
                  </select>
                </label>

                <label>
                  <span>Limit</span>
                  <input v-model.number="manualSpec.encoding.category_limit" min="1" max="500" type="number" />
                </label>

                <label>
                  <span>Value format</span>
                  <select v-model="manualSpec.encoding.value_format">
                    <option :value="null">Auto</option>
                    <option value="compact">Compact</option>
                    <option value="integer">Integer</option>
                    <option value="currency">Currency</option>
                    <option value="percent">Percent</option>
                  </select>
                </label>

                <label class="bi-studio__wide">
                  <span>Variant</span>
                  <select v-model="manualSpec.variant">
                    <option :value="null">Default</option>
                    <option value="stacked">Stacked</option>
                  </select>
                </label>
              </div>

              <div class="bi-studio__builder-actions">
                <button class="wbtn wbtn--ghost" type="button" :disabled="previewing" @click="previewManualSpec">
                  {{ previewing ? 'Строю…' : 'Preview' }}
                </button>
                <button class="wbtn wbtn--primary" type="button" :disabled="savingChart" @click="saveChart">
                  {{ savingChart ? 'Сохраняю…' : 'Save chart' }}
                </button>
              </div>
            </section>
          </div>

          <section class="bi-studio__panel bi-studio__preview-panel">
            <div class="bi-studio__panel-head">
              <div>
                <p class="bi-studio__eyebrow">Live preview</p>
                <h3>{{ preview?.chart_spec.title ?? manualSpec.title }}</h3>
              </div>
              <span v-if="preview" class="bi-studio__pill">{{ preview.execution_time_ms }} ms · {{ preview.row_count }} rows</span>
            </div>

            <div v-if="previewing" class="bi-studio__state">Строю preview…</div>
            <div v-else-if="!preview" class="bi-studio__empty-preview">
              Выберите рекомендацию или нажмите Preview.
            </div>
            <WidgetResultTable
              v-else-if="preview.chart_spec.chart_type === 'table'"
              :columns="preview.columns"
              :rows="preview.rows"
              :truncated="preview.rows_preview_truncated"
            />
            <ChartCell v-else-if="chartContent" :content="chartContent" />
            <div v-else class="bi-studio__empty-preview">Недостаточно данных для выбранного графика.</div>

            <details v-if="preview" class="bi-studio__sql-details">
              <summary>Compiled SQL</summary>
              <pre>{{ preview.sql }}</pre>
            </details>
          </section>
        </section>
      </template>

      <div v-else-if="!loading" class="bi-studio__empty-screen">
        <h2>Dataset layer пока пуст</h2>
        <p>Выполните любой SQL-запрос в чате. Backend сохранит результат как Dataset, а BI Studio предложит графики и dashboard.</p>
        <RouterLink to="/chat" class="wbtn wbtn--primary">Перейти в чат</RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/api/client';
import ChartCell from '@/components/cells/ChartCell.vue';
import WidgetResultTable from '@/components/widgets/WidgetResultTable.vue';
import { buildChartCellContentFromSpec } from '@/utils/chartPreview';
import type {
  ApiBiChartSpec,
  ApiBiFieldRead,
  ApiChartPreviewResponse,
  ApiChartRecommendationRead,
  ApiChatChartSpec,
  ApiChatExecutionRead,
  ApiDatasetRead,
} from '@/api/types';
import type { ChartCellContent } from '@/types/app';

const router = useRouter();

const datasets = ref<ApiDatasetRead[]>([]);
const activeDatasetId = ref('');
const activeDataset = ref<ApiDatasetRead | null>(null);
const recommendations = ref<ApiChartRecommendationRead[]>([]);
const preview = ref<ApiChartPreviewResponse | null>(null);
const loading = ref(false);
const refreshing = ref(false);
const recommending = ref(false);
const previewing = ref(false);
const savingChart = ref(false);
const creatingDashboard = ref(false);
const error = ref<string | null>(null);
const notice = ref<string | null>(null);

const manualSpec = ref<ApiBiChartSpec>(emptySpec());

const xFields = computed(() => {
  const fields = activeDataset.value?.fields ?? [];
  return fields.filter((field) => field.semantic_role === 'dimension' || field.semantic_role === 'time');
});

const yFields = computed(() => {
  const fields = activeDataset.value?.fields ?? [];
  const measures = fields.filter((field) => field.semantic_role === 'measure');
  return measures.length ? measures : fields.filter((field) => field.data_type === 'number');
});

const seriesFields = computed(() => {
  const fields = activeDataset.value?.fields ?? [];
  return fields.filter((field) => field.semantic_role === 'dimension' && field.name !== manualSpec.value.encoding.x_field);
});

const adaptedExecution = computed<ApiChatExecutionRead | null>(() => {
  if (!preview.value) return null;
  return {
    id: 'bi-preview',
    session_id: '',
    sql_text: preview.value.sql,
    columns: preview.value.columns,
    rows_preview: preview.value.rows,
    rows_preview_truncated: preview.value.rows_preview_truncated,
    row_count: preview.value.row_count,
    execution_time_ms: preview.value.execution_time_ms,
    dataset: null,
    chart_recommendation: null,
    error_message: null,
    created_at: new Date().toISOString(),
  };
});

const chartContent = computed<ChartCellContent | null>(() => {
  if (!preview.value || preview.value.chart_spec.chart_type === 'table') return null;
  return buildChartCellContentFromSpec(
    preview.value.chart_spec as unknown as ApiChatChartSpec,
    adaptedExecution.value,
  );
});

function emptySpec(): ApiBiChartSpec {
  return {
    chart_type: 'bar',
    title: 'Новый график',
    dataset_id: null,
    encoding: {
      x_field: null,
      y_field: null,
      series_field: null,
      aggregation: 'sum',
      sort: 'y_desc',
      series_limit: 8,
      category_limit: 20,
      top_n_strategy: 'top_only',
      value_format: 'compact',
    },
    filters: [],
    options: {},
    variant: null,
  };
}

function buildDefaultSpec(dataset: ApiDatasetRead): ApiBiChartSpec {
  const fields = dataset.fields;
  const measure = fields.find((field) => field.semantic_role === 'measure') ?? fields.find((field) => field.data_type === 'number') ?? null;
  const time = fields.find((field) => field.semantic_role === 'time') ?? null;
  const dimension = fields.find((field) => field.semantic_role === 'dimension') ?? null;
  const spec = emptySpec();
  spec.dataset_id = dataset.id;
  spec.title = measure && (time || dimension)
    ? `${measure.name} по ${(time ?? dimension)?.name}`
    : `График: ${dataset.name}`;
  spec.chart_type = time ? 'line' : 'bar';
  spec.encoding.x_field = (time ?? dimension)?.name ?? null;
  spec.encoding.y_field = measure?.name ?? null;
  spec.encoding.sort = time ? 'x_asc' : 'y_desc';
  spec.encoding.value_format = guessValueFormat(measure?.name ?? '');
  return spec;
}

function guessValueFormat(fieldName: string) {
  const lowered = fieldName.toLowerCase();
  if (/(revenue|amount|price|cost|profit|gmv|выруч|доход|сумм)/.test(lowered)) return 'currency';
  if (/(count|orders|qty|quantity|колич)/.test(lowered)) return 'integer';
  if (/(percent|ratio|share|rate|доля|процент)/.test(lowered)) return 'percent';
  return 'compact';
}

async function loadDatasets() {
  loading.value = true;
  error.value = null;
  try {
    datasets.value = await api.listDatasets();
    if (!activeDatasetId.value && datasets.value.length) {
      await selectDataset(datasets.value[0].id);
    } else if (activeDatasetId.value) {
      await selectDataset(activeDatasetId.value);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось загрузить datasets.';
  } finally {
    loading.value = false;
  }
}

async function selectDataset(datasetId: string) {
  activeDatasetId.value = datasetId;
  error.value = null;
  notice.value = null;
  preview.value = null;
  try {
    activeDataset.value = await api.getDataset(datasetId);
    manualSpec.value = buildDefaultSpec(activeDataset.value);
    await loadRecommendations();
    if (recommendations.value.length) {
      applyRecommendation(recommendations.value[0], false);
      await previewManualSpec();
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось открыть dataset.';
  }
}

async function loadRecommendations() {
  if (!activeDatasetId.value) return;
  recommending.value = true;
  try {
    recommendations.value = await api.recommendDatasetCharts(activeDatasetId.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось получить рекомендации.';
  } finally {
    recommending.value = false;
  }
}

function applyRecommendation(recommendation: ApiChartRecommendationRead, clearPreview = true) {
  manualSpec.value = JSON.parse(JSON.stringify(recommendation.chart_spec)) as ApiBiChartSpec;
  if (clearPreview) preview.value = null;
}

async function previewManualSpec() {
  if (!activeDataset.value) return;
  previewing.value = true;
  error.value = null;
  notice.value = null;
  try {
    manualSpec.value.dataset_id = activeDataset.value.id;
    preview.value = await api.previewBiChart(activeDataset.value.id, manualSpec.value);
    if (preview.value.warnings.length) {
      notice.value = preview.value.warnings.join(' ');
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось построить preview.';
  } finally {
    previewing.value = false;
  }
}

async function saveChart() {
  if (!activeDataset.value) return;
  savingChart.value = true;
  error.value = null;
  try {
    const response = await api.saveBiChart({
      dataset_id: activeDataset.value.id,
      chart_spec: manualSpec.value,
      title: manualSpec.value.title,
      description: manualSpec.value.reason ?? null,
      run_immediately: true,
    });
    notice.value = 'Chart сохранён как widget.';
    void router.push(`/widget/${response.widget.id}`);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось сохранить chart.';
  } finally {
    savingChart.value = false;
  }
}

async function createQuickDashboard() {
  if (!activeDataset.value) return;
  creatingDashboard.value = true;
  error.value = null;
  try {
    const response = await api.createQuickDashboard(activeDataset.value.id, {
      title: `BI dashboard: ${activeDataset.value.name}`,
      max_widgets: 4,
    });
    void router.push(`/dashboards/${response.dashboard.id}`);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось создать dashboard.';
  } finally {
    creatingDashboard.value = false;
  }
}

async function refreshActiveDataset() {
  if (!activeDataset.value) return;
  refreshing.value = true;
  try {
    const refreshed = await api.refreshDataset(activeDataset.value.id);
    activeDataset.value = refreshed;
    const index = datasets.value.findIndex((item) => item.id === refreshed.id);
    if (index >= 0) datasets.value[index] = refreshed;
    notice.value = 'Dataset обновлён.';
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Не удалось обновить dataset.';
  } finally {
    refreshing.value = false;
  }
}

onMounted(() => {
  void loadDatasets();
});
</script>

<style scoped lang="scss">
.bi-studio {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  background: var(--bg);
}

.bi-studio__datasets {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  padding: 18px;
  border-right: 1px solid var(--line);
  background: var(--surface);
}

.bi-studio__brand-row,
.bi-studio__datasets-head,
.bi-studio__topbar,
.bi-studio__panel-head,
.bi-studio__builder-actions,
.bi-studio__top-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.bi-studio__brand {
  color: var(--ink-strong);
  font-weight: 800;
  text-decoration: none;
}

.bi-studio__link {
  color: var(--muted-2);
  font-size: 0.8rem;
  text-decoration: none;
}

.bi-studio__datasets-head h1,
.bi-studio__topbar h2,
.bi-studio__panel-head h3 {
  margin: 0;
  color: var(--ink-strong);
}

.bi-studio__eyebrow {
  margin: 0 0 4px;
  color: var(--accent-strong);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.bi-studio__hint,
.bi-studio__state,
.bi-studio__empty-preview,
.bi-studio__empty-screen p {
  color: var(--muted-2);
  font-size: 0.84rem;
}

.bi-studio__dataset-list,
.bi-studio__recommendations {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow: auto;
}

.bi-studio__dataset-card,
.bi-studio__recommendation {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--canvas);
  color: var(--ink);
  text-align: left;
}

.bi-studio__dataset-card--active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.bi-studio__dataset-title {
  font-weight: 700;
}

.bi-studio__dataset-meta,
.bi-studio__recommendation small,
.bi-studio__field-card small {
  color: var(--muted-2);
  font-size: 0.76rem;
}

.bi-studio__workspace {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.bi-studio__panel {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
}

.bi-studio__panel--dataset {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bi-studio__field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 10px;
}

.bi-studio__field-card {
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--canvas);
}

.bi-studio__field-card strong {
  display: block;
  margin-bottom: 7px;
  font-size: 0.84rem;
}

.bi-studio__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 6px;
}

.bi-studio__chips span,
.bi-studio__pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--muted-2);
  font-size: 0.7rem;
}

.bi-studio__main-grid {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.bi-studio__left-column {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.bi-studio__recommendation {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.bi-studio__recommendation strong {
  display: block;
  margin-bottom: 3px;
}

.bi-studio__recommendation b {
  color: var(--accent-strong);
}

.bi-studio__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.bi-studio__form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--muted-2);
  font-size: 0.76rem;
}

.bi-studio__form-grid input,
.bi-studio__form-grid select {
  width: 100%;
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--canvas);
  color: var(--ink);
  padding: 7px 9px;
}

.bi-studio__wide {
  grid-column: 1 / -1;
}

.bi-studio__builder-actions {
  justify-content: flex-end;
  margin-top: 14px;
}

.bi-studio__preview-panel {
  min-height: 520px;
}

.bi-studio__preview-panel :deep(.chart-cell__plot),
.bi-studio__preview-panel :deep(.chart-cell__metric) {
  min-height: 380px;
}

.bi-studio__empty-preview,
.bi-studio__empty-screen {
  min-height: 320px;
  display: grid;
  place-items: center;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  padding: 24px;
}

.bi-studio__sql-details {
  margin-top: 14px;
  color: var(--muted-2);
  font-size: 0.78rem;
}

.bi-studio__sql-details pre {
  overflow: auto;
  padding: 12px;
  border-radius: var(--radius);
  background: var(--canvas);
  color: var(--ink);
}

.bi-studio__icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--canvas);
  color: var(--ink);
}

.bi-studio__error,
.bi-studio__notice {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  font-size: 0.84rem;
}

.bi-studio__error {
  color: var(--danger);
  background: rgba(255, 118, 118, 0.1);
  border: 1px solid rgba(255, 118, 118, 0.25);
}

.bi-studio__notice {
  color: var(--success);
  background: rgba(90, 200, 138, 0.08);
  border: 1px solid rgba(90, 200, 138, 0.2);
}

.bi-studio__state--compact {
  min-height: auto;
}

@media (max-width: 1100px) {
  .bi-studio {
    grid-template-columns: 1fr;
  }

  .bi-studio__datasets {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    max-height: 320px;
  }

  .bi-studio__main-grid {
    grid-template-columns: 1fr;
  }
}
</style>
