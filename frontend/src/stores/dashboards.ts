import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/api/client';
import type {
  ApiDashboardCreate,
  ApiDashboardDetail,
  ApiDashboardScheduleRead,
  ApiDashboardScheduleUpsert,
  ApiDashboardRead,
  ApiDashboardUpdate,
  ApiDashboardWidgetAdd,
  ApiDashboardWidgetDetail,
  ApiDashboardWidgetPatch
} from '@/api/types';

export const useDashboardsStore = defineStore('dashboards', () => {
  const dashboards = ref<ApiDashboardRead[]>([]);
  const includeHidden = ref(false);
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  function setError(msg: string | null) {
    error.value = msg;
  }

  async function loadDashboards() {
    loading.value = true;
    try {
      dashboards.value = await api.listDashboards(includeHidden.value);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить дашборды.');
    } finally {
      loading.value = false;
    }
  }

  async function setIncludeHidden(value: boolean) {
    includeHidden.value = value;
    await loadDashboards();
  }

  async function createDashboard(payload: ApiDashboardCreate): Promise<ApiDashboardDetail> {
    saving.value = true;
    setError(null);
    try {
      const dashboard = await api.createDashboard(payload);
      dashboards.value = [dashboard, ...dashboards.value];
      return dashboard;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось создать дашборд.');
      throw e;
    } finally {
      saving.value = false;
    }
  }

  async function updateDashboard(dashboardId: string, payload: ApiDashboardUpdate): Promise<ApiDashboardDetail> {
    saving.value = true;
    setError(null);
    try {
      const updated = await api.updateDashboard(dashboardId, payload);
      const idx = dashboards.value.findIndex((d) => d.id === dashboardId);
      if (idx >= 0) dashboards.value[idx] = updated;
      return updated;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось обновить дашборд.');
      throw e;
    } finally {
      saving.value = false;
    }
  }

  async function deleteDashboard(dashboardId: string) {
    try {
      await api.deleteDashboard(dashboardId);
      dashboards.value = dashboards.value.filter((d) => d.id !== dashboardId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить дашборд.');
      throw e;
    }
  }

  async function addWidget(dashboardId: string, payload: ApiDashboardWidgetAdd): Promise<ApiDashboardWidgetDetail> {
    try {
      return await api.addWidgetToDashboard(dashboardId, payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось добавить виджет.');
      throw e;
    }
  }

  async function updateWidget(
    dashboardId: string,
    dwId: string,
    payload: ApiDashboardWidgetPatch
  ): Promise<ApiDashboardWidgetDetail> {
    try {
      return await api.updateDashboardWidget(dashboardId, dwId, payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось обновить виджет дашборда.');
      throw e;
    }
  }

  async function removeWidget(dashboardId: string, dwId: string) {
    try {
      await api.removeWidgetFromDashboard(dashboardId, dwId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить виджет из дашборда.');
      throw e;
    }
  }

  async function getSchedule(dashboardId: string): Promise<ApiDashboardScheduleRead> {
    try {
      return await api.getDashboardSchedule(dashboardId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить schedule.');
      throw e;
    }
  }

  async function saveSchedule(
    dashboardId: string,
    payload: ApiDashboardScheduleUpsert,
  ): Promise<ApiDashboardScheduleRead> {
    try {
      return await api.upsertDashboardSchedule(dashboardId, payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить schedule.');
      throw e;
    }
  }

  async function deleteSchedule(dashboardId: string) {
    try {
      return await api.deleteDashboardSchedule(dashboardId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить schedule.');
      throw e;
    }
  }

  async function exportPdf(dashboardId: string) {
    try {
      return await api.exportDashboardPdf(dashboardId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выгрузить PDF.');
      throw e;
    }
  }

  return {
    dashboards,
    includeHidden,
    loading,
    saving,
    error,
    setError,
    loadDashboards,
    setIncludeHidden,
    createDashboard,
    updateDashboard,
    deleteDashboard,
    addWidget,
    updateWidget,
    removeWidget,
    getSchedule,
    saveSchedule,
    deleteSchedule,
    exportPdf
  };
});
