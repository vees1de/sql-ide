import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/api/client';
import type { ApiWidgetCreate, ApiWidgetDetail, ApiWidgetRead, ApiWidgetUpdate } from '@/api/types';

export const useWidgetsStore = defineStore('widgets', () => {
  const widgets = ref<ApiWidgetRead[]>([]);
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);

  function setError(msg: string | null) {
    error.value = msg;
  }

  async function loadWidgets() {
    loading.value = true;
    try {
      widgets.value = await api.listWidgets();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить виджеты.');
    } finally {
      loading.value = false;
    }
  }

  async function createWidget(payload: ApiWidgetCreate): Promise<ApiWidgetDetail> {
    saving.value = true;
    setError(null);
    try {
      const widget = await api.createWidget(payload);
      widgets.value = [widget, ...widgets.value];
      return widget;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Не удалось сохранить виджет.';
      setError(msg);
      throw e;
    } finally {
      saving.value = false;
    }
  }

  async function updateWidget(widgetId: string, payload: ApiWidgetUpdate): Promise<ApiWidgetDetail> {
    saving.value = true;
    setError(null);
    try {
      const updated = await api.updateWidget(widgetId, payload);
      const idx = widgets.value.findIndex((w) => w.id === widgetId);
      if (idx >= 0) widgets.value[idx] = updated;
      return updated;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Не удалось обновить виджет.';
      setError(msg);
      throw e;
    } finally {
      saving.value = false;
    }
  }

  async function deleteWidget(widgetId: string) {
    try {
      await api.deleteWidget(widgetId);
      widgets.value = widgets.value.filter((w) => w.id !== widgetId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить виджет.');
      throw e;
    }
  }

  async function runWidget(widgetId: string): Promise<ApiWidgetDetail> {
    try {
      const detail = await api.runWidget(widgetId);
      const idx = widgets.value.findIndex((w) => w.id === widgetId);
      if (idx >= 0) widgets.value[idx] = detail;
      return detail;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выполнить виджет.');
      throw e;
    }
  }

  return {
    widgets,
    loading,
    saving,
    error,
    loadWidgets,
    createWidget,
    updateWidget,
    deleteWidget,
    runWidget,
    setError
  };
});
