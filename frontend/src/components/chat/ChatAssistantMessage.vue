<template>
  <article class="chat-assistant-message">
    <section v-if="hasReasoning" class="chat-assistant-message__reasoning">
      <button
        class="chat-assistant-message__reasoning-toggle"
        type="button"
        :aria-expanded="!reasoningCollapsed"
        @click="reasoningCollapsed = !reasoningCollapsed"
      >
        <span class="chat-assistant-message__reasoning-label">
          Логика ответа
          <small>{{ reasoningCollapsed ? "показать" : "скрыть" }}</small>
        </span>
        <span class="chat-assistant-message__reasoning-icon" aria-hidden="true">
          {{ reasoningCollapsed ? "▾" : "▴" }}
        </span>
      </button>

      <div
        v-show="!reasoningCollapsed"
        class="chat-assistant-message__reasoning-body"
      >
        <div
          v-if="reasoningLines.length"
          class="chat-assistant-message__reasoning-lines"
        >
          <p v-for="line in reasoningLines" :key="line">{{ line }}</p>
        </div>
      </div>
    </section>

    <p class="chat-assistant-message__text">{{ message.text }}</p>

    <div
      v-if="payload?.clarification_question"
      class="chat-assistant-message__clarification"
    >
      <p>{{ payload.clarification_question }}</p>
      <div
        v-if="payload.clarification_options?.length"
        class="chat-assistant-message__chips"
      >
        <button
          v-for="option in payload.clarification_options"
          :key="option.id"
          class="chat-assistant-message__btn"
          type="button"
          @click="$emit('clarification', option.label)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <section v-if="payload?.sql" class="chat-assistant-message__sql">
      <SQLCell :content="sqlCellContent" :collapsed="sqlCollapsed" />
      <div
        class="chat-assistant-message__actions chat-assistant-message__actions--below"
      >
        <button
          class="chat-assistant-message__btn"
          type="button"
          @click="$emit('apply-sql', payload.sql!)"
        >
          Подставить SQL
        </button>
        <button
          class="chat-assistant-message__btn chat-assistant-message__btn--secondary"
          type="button"
          @click="sqlCollapsed = !sqlCollapsed"
        >
          {{ sqlCollapsed ? "Показать SQL" : "Скрыть SQL" }}
        </button>
        <button
          v-if="payload?.mode_suggestion && payload.mode_suggestion_reason"
          class="chat-assistant-message__btn"
          type="button"
          @click="$emit('switch-mode', payload.mode_suggestion)"
        >
          {{
            payload.mode_suggestion === "thinking" ? "Deep thinking" : "Быстро"
          }}
        </button>
      </div>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import SQLCell from "@/components/cells/SQLCell.vue";
import type {
  ApiChatMessageRead,
  ApiChatStructuredPayload,
  ApiQueryMode,
} from "@/api/types";

const props = defineProps<{
  message: ApiChatMessageRead;
}>();

defineEmits<{
  (event: "apply-sql", sql: string): void;
  (event: "clarification", answer: string): void;
  (event: "switch-mode", mode: ApiQueryMode): void;
}>();

const payload = computed<ApiChatStructuredPayload | null>(
  () => props.message.structured_payload,
);
const sqlCollapsed = ref(false);
const reasoningCollapsed = ref(true);

watch(
  () => payload.value?.sql,
  () => {
    sqlCollapsed.value = false;
  },
);

watch(
  () => props.message.id,
  () => {
    reasoningCollapsed.value = true;
  },
);

const warnings = computed(() => [
  ...(payload.value?.warnings ?? []),
  ...(payload.value?.interpretation.ambiguities ?? []).map(
    (item) => `Неоднозначность: ${item.replaceAll("_", " ")}`,
  ),
]);

const confidenceLabel = computed(() => {
  switch (payload.value?.confidence_level) {
    case 'high':
      return 'Высокая';
    case 'low':
      return 'Низкая';
    default:
      return 'Средняя';
  }
});

const reasoningLines = computed(() => {
  const lines: string[] = [];
  const interpretation = payload.value?.interpretation;

  if (interpretation?.metric) {
    lines.push(`Метрика: ${interpretation.metric}`);
  }

  if (interpretation?.dimensions?.length) {
    lines.push(`Измерения: ${interpretation.dimensions.join(", ")}`);
  }

  if (interpretation?.date_range) {
    const parts: string[] = [];
    if (interpretation.date_range.start) {
      parts.push(`с ${interpretation.date_range.start}`);
    }
    if (interpretation.date_range.end) {
      parts.push(`по ${interpretation.date_range.end}`);
    }
    if (parts.length) {
      lines.push(`Период: ${parts.join(" ")}`);
    }
  }

  if (interpretation?.filters?.length) {
    lines.push(
      `Фильтры: ${interpretation.filters
        .map(
          (filter) =>
            `${filter.field} ${filter.operator} ${String(filter.value)}`,
        )
        .join("; ")}`,
    );
  }

  if (typeof interpretation?.confidence === "number") {
    lines.push(`Уверенность: ${Math.round(interpretation.confidence * 100)}%`);
  }

  if (payload.value?.confidence_level) {
    lines.push(`Уверенность SQL: ${confidenceLabel.value}`);
  }

  if (payload.value?.confidence_reasons?.length) {
    lines.push(`Сигналы confidence: ${payload.value.confidence_reasons.join('; ')}`);
  }

  if (payload.value?.tables_used?.length) {
    lines.push(
      `Таблицы: ${payload.value.tables_used.map((item) => `${item.table} (${item.reason})`).join("; ")}`,
    );
  }

  if (payload.value?.mode_suggestion_reason) {
    lines.push(`Подсказка режима: ${payload.value.mode_suggestion_reason}`);
  }

  if (payload.value?.debug_trace?.length) {
    lines.push(
      ...payload.value.debug_trace.map((step) => {
        const code = step.code ? ` [${step.code}]` : '';
        return `${step.stage}${code}: ${step.detail}`;
      }),
    );
  }

  if (warnings.value.length) {
    lines.push(`Предупреждения: ${warnings.value.join("; ")}`);
  }

  return lines;
});

const hasReasoning = computed(() => reasoningLines.value.length > 0);

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? "",
  explanation: "",
  warnings: warnings.value,
}));
</script>

<style scoped lang="scss">
.chat-assistant-message {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.16);
  display: grid;
  gap: 10px;
}

.chat-assistant-message__reasoning {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  overflow: hidden;
}

.chat-assistant-message__reasoning-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  color: var(--ink);
  text-align: left;
}

.chat-assistant-message__reasoning-label {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.82rem;
  font-weight: 600;
}

.chat-assistant-message__reasoning-label small {
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chat-assistant-message__reasoning-icon {
  color: var(--muted);
  font-size: 0.88rem;
}

.chat-assistant-message__reasoning-body {
  padding: 0 10px 10px;
}

.chat-assistant-message__reasoning-lines {
  display: grid;
  gap: 4px;
}

.chat-assistant-message__reasoning-lines p {
  margin: 0;
  color: var(--muted);
  font-size: 0.77rem;
  line-height: 1.5;
}

.chat-assistant-message__text {
  margin: 0;
  color: var(--ink);
  font-size: 0.88rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.chat-assistant-message__actions,
.chat-assistant-message__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chat-assistant-message__actions--below {
  margin-top: 0.15rem;
}

.chat-assistant-message__btn {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
  font-size: 0.74rem;
}

.chat-assistant-message__btn--secondary {
  min-height: 24px;
  padding: 0 8px;
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  font-size: 0.7rem;
}

.chat-assistant-message__btn--secondary:hover {
  color: var(--ink-strong);
  border-color: var(--line);
  background: rgba(255, 255, 255, 0.06);
}

.chat-assistant-message__clarification {
  display: grid;
  gap: 8px;
}

.chat-assistant-message__clarification p {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.45;
}

.chat-assistant-message__sql {
  min-width: 0;
}
</style>
