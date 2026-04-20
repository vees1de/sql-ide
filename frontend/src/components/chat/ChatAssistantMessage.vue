<template>
  <article class="chat-assistant-message">
    <p class="chat-assistant-message__text">{{ message.text }}</p>

    <div v-if="payload?.sql" class="chat-assistant-message__actions">
      <button
        class="chat-assistant-message__btn"
        type="button"
        @click="$emit('apply-sql', payload.sql!)"
      >
        Подставить SQL
      </button>
      <button
        v-if="payload?.mode_suggestion && payload.mode_suggestion_reason"
        class="chat-assistant-message__btn"
        type="button"
        @click="$emit('switch-mode', payload.mode_suggestion)"
      >
        {{ payload.mode_suggestion === 'thinking' ? 'Thinking' : 'Fast' }}
      </button>
    </div>

    <div v-if="payload?.clarification_question" class="chat-assistant-message__clarification">
      <p>{{ payload.clarification_question }}</p>
      <div v-if="payload.clarification_options?.length" class="chat-assistant-message__chips">
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
      <SQLCell :content="sqlCellContent" />
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import SQLCell from '@/components/cells/SQLCell.vue';
import type {
  ApiChatMessageRead,
  ApiChatStructuredPayload,
  ApiQueryMode
} from '@/api/types';

const props = defineProps<{
  message: ApiChatMessageRead;
}>();

defineEmits<{
  (event: 'apply-sql', sql: string): void;
  (event: 'clarification', answer: string): void;
  (event: 'switch-mode', mode: ApiQueryMode): void;
}>();

const payload = computed<ApiChatStructuredPayload | null>(() => props.message.structured_payload);

const warnings = computed(() => [
  ...(payload.value?.warnings ?? []),
  ...(payload.value?.interpretation.ambiguities ?? []).map((item) => `Неоднозначность: ${item.replaceAll('_', ' ')}`)
]);

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? '',
  explanation:
    payload.value?.query_mode === 'thinking'
      ? 'Thinking режим, автоисполнение выключено.'
      : 'Fast режим, автоисполнение выключено.',
  warnings: warnings.value
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

.chat-assistant-message__btn {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
  font-size: 0.74rem;
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
