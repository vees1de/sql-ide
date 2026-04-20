<template>
  <article class="chat-assistant-message">
    <header class="chat-assistant-message__head">
      <div>
        <p class="chat-assistant-message__label">Ответ модели</p>
        <p class="chat-assistant-message__lead">{{ message.text }}</p>
      </div>
      <button
        v-if="payload?.sql"
        class="app-button app-button--ghost app-button--tiny"
        type="button"
        @click="$emit('apply-sql', payload.sql!)"
      >
        Подставить в редактор
      </button>
    </header>

    <section v-if="payload" class="chat-assistant-message__section">
      <h4>Как я понял запрос</h4>
      <div class="chat-assistant-message__summary">
        <div v-if="payload.interpretation.metric" class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Метрика</span>
          <span class="pill pill--ghost">{{ humanize(payload.interpretation.metric) }}</span>
        </div>

        <div v-if="payload.interpretation.dimensions.length" class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Измерения</span>
          <div class="chat-assistant-message__chips">
            <span
              v-for="dimension in payload.interpretation.dimensions"
              :key="dimension"
              class="pill pill--soft"
            >
              {{ humanize(dimension) }}
            </span>
          </div>
        </div>

        <div v-if="payload.interpretation.date_range" class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Период</span>
          <span class="chat-assistant-message__text">{{ formatDateRange(payload.interpretation.date_range) }}</span>
        </div>

        <div v-if="payload.interpretation.filters.length" class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Фильтры</span>
          <div class="chat-assistant-message__chips">
            <span
              v-for="filter in payload.interpretation.filters"
              :key="`${filter.field}:${String(filter.value)}`"
              class="pill pill--ghost"
            >
              {{ humanize(filter.field) }} {{ filter.operator }} {{ String(filter.value) }}
            </span>
          </div>
        </div>

        <div v-if="payload.interpretation.comparison" class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Сравнение</span>
          <span class="chat-assistant-message__text">{{ humanize(payload.interpretation.comparison) }}</span>
        </div>

        <div class="chat-assistant-message__row">
          <span class="chat-assistant-message__key">Уверенность</span>
          <span class="chat-assistant-message__text">{{ formatConfidence(payload.interpretation.confidence) }}</span>
        </div>
      </div>
    </section>

    <section v-if="payload?.tables_used.length" class="chat-assistant-message__section">
      <h4>Использованные таблицы</h4>
      <ul class="chat-assistant-message__table-list">
        <li
          v-for="item in payload.tables_used"
          :key="item.table"
        >
          <strong>{{ item.table }}</strong>
          <span>{{ item.reason }}</span>
        </li>
      </ul>
    </section>

    <section v-if="warnings.length" class="chat-assistant-message__section">
      <h4>Допущения</h4>
      <div class="chat-assistant-message__warnings">
        <span
          v-for="warning in warnings"
          :key="warning"
          class="pill pill--ghost"
        >
          {{ warning }}
        </span>
      </div>
    </section>

    <section v-if="payload?.clarification_question" class="chat-assistant-message__section">
      <h4>Нужны уточнения</h4>
      <p class="chat-assistant-message__question">{{ payload.clarification_question }}</p>
      <div v-if="payload.clarification_options?.length" class="chat-assistant-message__chips">
        <button
          v-for="option in payload.clarification_options"
          :key="option.id"
          class="app-button app-button--ghost app-button--tiny"
          type="button"
          @click="$emit('clarification', option.label)"
        >
          {{ option.label }}
        </button>
      </div>
    </section>

    <section v-if="payload?.sql" class="chat-assistant-message__section">
      <h4>SQL</h4>
      <SQLCell :content="sqlCellContent" />
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import SQLCell from '@/components/cells/SQLCell.vue';
import type { ApiChatMessageRead, ApiChatStructuredPayload, ApiChatDateRange } from '@/api/types';

const props = defineProps<{
  message: ApiChatMessageRead;
  autoApplySql: boolean;
}>();

defineEmits<{
  (event: 'apply-sql', sql: string): void;
  (event: 'clarification', answer: string): void;
}>();

const payload = computed<ApiChatStructuredPayload | null>(() => props.message.structured_payload);

const warnings = computed(() => [
  ...(payload.value?.warnings ?? []),
  ...(payload.value?.interpretation.ambiguities ?? []).map((item) => `Неоднозначность: ${humanize(item)}`)
]);

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? '',
  explanation: 'SQL готов к ручному запуску. Автоисполнение отключено.',
  warnings: warnings.value
}));

function humanize(value: string) {
  const labels: Record<string, string> = {
    revenue: 'выручка',
    order_count: 'количество заказов',
    avg_order_value: 'средний чек',
    month: 'по месяцам',
    week: 'по неделям',
    day: 'по дням',
    region: 'по регионам',
    city: 'по городам',
    segment: 'по сегментам',
    channel: 'по каналам',
    campaign: 'по кампаниям',
    previous_year: 'с прошлым годом',
    previous_period: 'с предыдущим периодом'
  };
  return labels[value] ?? value.replaceAll('_', ' ');
}

function formatDateRange(range: ApiChatDateRange) {
  if (range.kind === 'relative' && range.lookback_value && range.lookback_unit) {
    const unitMap: Record<string, string> = {
      days: 'дней',
      day: 'день',
      weeks: 'недель',
      week: 'неделю',
      months: 'месяцев',
      month: 'месяц',
      years: 'лет',
      year: 'год'
    };
    return `за последние ${range.lookback_value} ${unitMap[range.lookback_unit] ?? range.lookback_unit}`;
  }

  const start = range.start ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(range.start)) : '';
  const end = range.end ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(range.end)) : '';
  if (start && end) {
    return `${start} — ${end}`;
  }
  return start || end || 'Период не указан';
}

function formatConfidence(value: number) {
  return `${Math.round(value * 100)}%`;
}
</script>

<style scoped lang="scss">
.chat-assistant-message {
  display: grid;
  gap: 1rem;
}

.chat-assistant-message__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.chat-assistant-message__label {
  margin: 0;
  color: var(--muted);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chat-assistant-message__lead {
  margin: 0.35rem 0 0;
  color: var(--ink);
  font-size: 0.95rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.chat-assistant-message__section {
  display: grid;
  gap: 0.55rem;
}

.chat-assistant-message__section h4 {
  margin: 0;
  color: var(--ink-strong);
  font-size: 0.86rem;
}

.chat-assistant-message__summary,
.chat-assistant-message__row {
  display: grid;
  gap: 0.45rem;
}

.chat-assistant-message__row {
  grid-template-columns: minmax(7rem, 9rem) minmax(0, 1fr);
  align-items: start;
}

.chat-assistant-message__key {
  color: var(--muted);
  font-size: 0.8rem;
}

.chat-assistant-message__text {
  color: var(--ink);
  font-size: 0.82rem;
  line-height: 1.5;
}

.chat-assistant-message__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chat-assistant-message__table-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.chat-assistant-message__table-list li {
  display: grid;
  gap: 0.15rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.02);
}

.chat-assistant-message__table-list strong {
  font-size: 0.82rem;
  color: var(--ink);
}

.chat-assistant-message__table-list span,
.chat-assistant-message__question {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.5;
}

.chat-assistant-message__warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

@media (max-width: 720px) {
  .chat-assistant-message__row {
    grid-template-columns: 1fr;
  }
}
</style>
