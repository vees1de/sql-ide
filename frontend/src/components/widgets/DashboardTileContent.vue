<template>
  <div class="tile-content">
    <div v-if="running" class="tile-content__loading tile-content__loading--skeleton">
      <AppSkeleton height="1rem" width="42%" radius="6px" />
      <AppSkeleton height="1rem" width="68%" radius="6px" />
      <AppSkeleton class="tile-content__loading-block" height="100%" radius="12px" />
    </div>

    <template v-else-if="widget.source_type === 'text'">
      <div class="tile-content__text">
        <p>{{ widget.description || 'Text widget' }}</p>
      </div>
    </template>

    <template v-else-if="run">
      <div v-if="run.status === 'error'" class="tile-content__error">
        {{ run.error_text }}
      </div>
      <template v-else-if="run.status === 'completed'">
        <WidgetResultTable
          v-if="widget.visualization_type === 'table'"
          :columns="run.columns ?? []"
          :rows="run.rows_preview ?? []"
          :truncated="run.rows_preview_truncated"
        />
        <WidgetResultChart
          v-else
          :run="run"
          :viz-type="widget.visualization_type"
          :viz-config="widget.visualization_config"
          :chart-spec="widget.chart_spec_json"
        />
      </template>
    </template>
    <div v-else class="tile-content__empty">РќРµС‚ РґР°РЅРЅС‹С…</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/api/client';
import AppSkeleton from '@/components/ui/AppSkeleton.vue';
import WidgetResultTable from '@/components/widgets/WidgetResultTable.vue';
import WidgetResultChart from '@/components/widgets/WidgetResultChart.vue';
import type { ApiDashboardWidgetDetail, ApiWidgetRunRead } from '@/api/types';

const props = defineProps<{
  dashboardWidget: ApiDashboardWidgetDetail;
}>();

const widget = props.dashboardWidget.widget;
const run = ref<ApiWidgetRunRead | null>(null);
const running = ref(false);

async function loadRun() {
  running.value = true;
  try {
    const detail = await api.runWidget(widget.id);
    run.value = detail.last_run;
  } catch {
    // ignore, tile just stays empty
  } finally {
    running.value = false;
  }
}

onMounted(() => {
  if (widget.refresh_policy !== 'manual') {
    void loadRun();
  }
});
</script>

<style scoped lang="scss">
.tile-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tile-content__loading,
.tile-content__empty {
  color: var(--muted);
  font-size: 0.82rem;
  padding: 16px 0;
  text-align: center;
}

.tile-content__loading--skeleton {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  padding: 2px 0 0;
  text-align: left;
}

.tile-content__loading-block {
  flex: 1;
  min-height: 96px;
}

.tile-content__text {
  padding: 8px 2px 2px;
  color: var(--ink);
  font-size: 0.88rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.tile-content__error {
  border: 1px solid rgba(255, 107, 107, 0.4);
  border-radius: 6px;
  background: rgba(255, 107, 107, 0.08);
  color: #ffb3b3;
  font-size: 0.78rem;
  padding: 8px 10px;
}
</style>
