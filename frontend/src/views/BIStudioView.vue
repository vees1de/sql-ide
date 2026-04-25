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
        Любой успешный SQL-запрос из чата уже сохранён как dataset. Здесь можно собрать несколько вариантов ChartSpec и быстро превратить их в widget или dashboard.
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
        <section class="bi-studio__panel">
          <div class="bi-studio__panel-head">
            <div>
              <p class="bi-studio__eyebrow">Manual chart builder</p>
              <h3>ChartSpec</h3>
            </div>
            <span class="bi-studio__pill">10 visual variants</span>
          </div>

          <div class="bi-studio__visual-grid">
            <button
              v-for="option in visualizationOptions"
              :key="option.key"
              class="bi-studio__visual-card"
              :class="{ 'bi-studio__visual-card--active': selectedVisualPreset === option.key }"
              type="button"
              @click="selectedVisualPreset = option.key"
            >
              <strong>{{ option.label }}</strong>
              <small>{{ option.description }}</small>
            </button>
          </div>

          <div class="bi-studio__form-grid">
            <label class="bi-studio__wide">
              <span>Title</span>
              <input v-model="manualSpec.title" type="text" />
            </label>

            <label>
              <span>X axis</span>
              <select v-model="manualSpec.encoding.x_field" :disabled="isMetricChart || isTableChart">
                <option :value="null">—</option>
                <option v-for="field in xFields" :key="field.name" :value="field.name">{{ field.name }}</option>
              </select>
            </label>

            <label>
              <span>Y metric</span>
              <select v-model="manualSpec.encoding.y_field" :disabled="isTableChart">
                <option :value="null">—</option>
                <option v-for="field in yFields" :key="field.name" :value="field.name">{{ field.name }}</option>
              </select>
            </label>

            <label>
              <span>Series / breakdown</span>
              <select v-model="manualSpec.encoding.series_field" :disabled="!supportsSeriesField">
                <option :value="null">—</option>
                <option v-for="field in seriesFields" :key="field.name" :value="field.name">{{ field.name }}</option>
              </select>
            </label>

            <label>
              <span>Aggregation</span>
              <select v-model="manualSpec.encoding.aggregation" :disabled="isTableChart">
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
              <select v-model="manualSpec.encoding.sort" :disabled="isMetricChart || isTableChart">
                <option value="x_asc">X asc</option>
                <option value="x_desc">X desc</option>
                <option value="y_desc">Y desc</option>
                <option value="y_asc">Y asc</option>
                <option value="none">No sort</option>
              </select>
            </label>

            <label>
              <span>Category limit</span>
              <input v-model.number="manualSpec.encoding.category_limit" min="1" max="500" type="number" />
            </label>

            <label>
              <span>Series limit</span>
              <input v-model.number="manualSpec.encoding.series_limit" min="1" max="50" type="number" :disabled="!supportsSeriesField" />
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

            <label>
              <span>Variant</span>
              <input :value="manualSpec.variant ?? 'default'" disabled type="text" />
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

        <section class="bi-studio__content-grid">
          <section class="bi-studio__panel bi-studio__data-panel">
            <div class="bi-studio__panel-head">
              <div>
                <p class="bi-studio__eyebrow">Dataset preview</p>
                <h3>Таблица данных</h3>
              </div>
              <span class="bi-studio__pill">{{ datasetColumns.length }} cols · {{ activeDataset.row_count }} rows</span>
            </div>

            <WidgetResultTable
              :columns="datasetColumns"
              :rows="activeDataset.preview_rows"
              :truncated="activeDataset.row_count > activeDataset.preview_rows.length"
            />
          </section>

          <section class="bi-studio__panel bi-studio__preview-panel">
            <div class="bi-studio__panel-head">
              <div>
                <p class="bi-studio__eyebrow">Chart preview</p>
                <h3>{{ preview?.chart_spec.title ?? manualSpec.title }}</h3>
              </div>
              <span v-if="preview" class="bi-studio__pill">{{ preview.execution_time_ms }} ms · {{ preview.row_count }} rows</span>
            </div>

            <div v-if="previewing" class="bi-studio__state">Строю preview…</div>
            <div v-else-if="!preview" class="bi-studio__empty-preview">
              Выберите визуальный вариант и нажмите Preview.
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

        <section class="bi-studio__bottom-grid">
          <section class="bi-studio__panel bi-studio__panel--dataset">
            <div class="bi-studio__panel-head">
              <div>
                <p class="bi-studio__eyebrow">Dataset schema</p>
                <h3>Поля и роли</h3>
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
                :key="recommendation.title + recommendation.chart_spec.chart_type + (recommendation.chart_spec.variant ?? '')"
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
  ApiChartPreviewResponse,
  ApiChartRecommendationRead,
  ApiChatChartSpec,
  ApiChatExecutionRead,
  ApiDatasetRead,
} from '@/api/types';
import type { ChartCellContent } from '@/types/app';

type VisualPresetKey =
  | 'table'
  | 'metric_card'
  | 'line'
  | 'area'
  | 'bar'
  | 'horizontal_bar'
  | 'stacked_bar'
  | 'stacked_area'
  | 'pie'
  | 'donut';

const router = useRouter();

const visualizationOptions: Array<{ key: VisualPresetKey; label: string; description: string }> = [
  { key: 'table', label: 'Table', description: 'Raw rows for drill-through and QA' },
  { key: 'metric_card', label: 'KPI card', description: 'Single headline metric' },
  { key: 'line', label: 'Line', description: 'Trend over time or ordered categories' },
  { key: 'area', label: 'Area', description: 'Trend with volume emphasis' },
  { key: 'bar', label: 'Bar', description: 'Category comparison' },
  { key: 'horizontal_bar', label: 'Horizontal bar', description: 'Ranking with long labels' },
  { key: 'stacked_bar', label: 'Stacked bar', description: 'Breakdown inside each category' },
  { key: 'stacked_area', label: 'Stacked area', description: 'Accumulated trend by segment' },
  { key: 'pie', label: 'Pie', description: 'Small segment distribution' },
  { key: 'donut', label: 'Donut', description: 'Compact share breakdown' },
];

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

const datasetColumns = computed(() =>
  (activeDataset.value?.columns_schema ?? []).map((column) => ({
    name: String(column.name ?? column['name'] ?? ''),
    type: String(column.type ?? column['type'] ?? 'unknown'),
  })).filter((column) => column.name),
);

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

const isTableChart = computed(() => manualSpec.value.chart_type === 'table');
const isMetricChart = computed(() => manualSpec.value.chart_type === 'metric_card');
const supportsSeriesField = computed(() => !isTableChart.value && !isMetricChart.value && manualSpec.value.chart_type !== 'pie');

const selectedVisualPreset = computed<VisualPresetKey>({
  get() {
    return detectVisualPreset(manualSpec.value);
  },
  set(next) {
    applyVisualPreset(next);
  },
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

function detectVisualPreset(spec: ApiBiChartSpec): VisualPresetKey {
  if (spec.chart_type === 'table') return 'table';
  if (spec.chart_type === 'metric_card') return 'metric_card';
  if (spec.chart_type === 'pie' && spec.variant === 'donut') return 'donut';
  if (spec.chart_type === 'pie') return 'pie';
  if (spec.chart_type === 'area' && spec.variant === 'stacked') return 'stacked_area';
  if (spec.chart_type === 'area') return 'area';
  if (spec.chart_type === 'bar' && spec.variant === 'horizontal') return 'horizontal_bar';
  if (spec.chart_type === 'bar' && spec.variant === 'stacked') return 'stacked_bar';
  if (spec.chart_type === 'bar') return 'bar';
  return 'line';
}

function applyVisualPreset(preset: VisualPresetKey) {
  const next: ApiBiChartSpec = JSON.parse(JSON.stringify(manualSpec.value));
  next.options = { ...(next.options ?? {}) };

  if (preset === 'table') {
    next.chart_type = 'table';
    next.variant = null;
    next.encoding.aggregation = 'none';
    next.encoding.series_field = null;
  } else if (preset === 'metric_card') {
    next.chart_type = 'metric_card';
    next.variant = null;
    next.encoding.x_field = null;
    next.encoding.series_field = null;
    next.encoding.sort = null;
    next.encoding.category_limit = 1;
  } else if (preset === 'line') {
    next.chart_type = 'line';
    next.variant = null;
  } else if (preset === 'area') {
    next.chart_type = 'area';
    next.variant = null;
  } else if (preset === 'bar') {
    next.chart_type = 'bar';
    next.variant = null;
  } else if (preset === 'horizontal_bar') {
    next.chart_type = 'bar';
    next.variant = 'horizontal';
  } else if (preset === 'stacked_bar') {
    next.chart_type = 'bar';
    next.variant = 'stacked';
  } else if (preset === 'stacked_area') {
    next.chart_type = 'area';
    next.variant = 'stacked';
  } else if (preset === 'pie') {
    next.chart_type = 'pie';
    next.variant = null;
    next.encoding.series_field = null;
  } else if (preset === 'donut') {
    next.chart_type = 'pie';
    next.variant = 'donut';
    next.encoding.series_field = null;
  }

  if (next.chart_type !== 'table' && next.encoding.aggregation === 'none') {
    next.encoding.aggregation = 'sum';
  }
  manualSpec.value = next;
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
      max_widgets: 6,
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
.bi-studio__recommendation,
.bi-studio__visual-card {
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

.bi-studio__dataset-card--active,
.bi-studio__visual-card--active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.bi-studio__dataset-title,
.bi-studio__visual-card strong {
  font-weight: 700;
}

.bi-studio__dataset-meta,
.bi-studio__recommendation small,
.bi-studio__field-card small,
.bi-studio__visual-card small {
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

.bi-studio__visual-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
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

.bi-studio__content-grid,
.bi-studio__bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 18px;
  align-items: start;
}

.bi-studio__data-panel :deep(.widget-table__scroll) {
  max-height: 560px;
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
  grid-template-columns: repeat(5, minmax(0, 1fr));
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

.bi-studio__preview-panel :deep(.chart-cell__plot),
.bi-studio__preview-panel :deep(.chart-cell__metric) {
  min-height: 420px;
  height: 420px;
}

.bi-studio__sql-details {
  margin-top: 14px;
}

.bi-studio__sql-details summary {
  cursor: pointer;
  color: var(--muted-2);
  font-size: 0.8rem;
}

.bi-studio__sql-details pre {
  margin: 10px 0 0;
  padding: 12px;
  border-radius: 10px;
  background: var(--canvas);
  color: var(--ink);
  font-size: 0.75rem;
  line-height: 1.45;
  overflow: auto;
}

.bi-studio__error,
.bi-studio__notice {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 0.82rem;
}

.bi-studio__error {
  border: 1px solid rgba(255, 107, 107, 0.35);
  background: rgba(255, 107, 107, 0.08);
  color: #ffb4b4;
}

.bi-studio__notice {
  border: 1px solid rgba(77, 208, 141, 0.28);
  background: rgba(77, 208, 141, 0.08);
  color: #9ee1b8;
}

.bi-studio__empty-screen {
  display: grid;
  gap: 10px;
  place-items: start;
}

@media (max-width: 1320px) {
  .bi-studio__visual-grid,
  .bi-studio__form-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .bi-studio {
    grid-template-columns: 1fr;
  }

  .bi-studio__datasets {
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .bi-studio__content-grid,
  .bi-studio__bottom-grid,
  .bi-studio__visual-grid,
  .bi-studio__form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
