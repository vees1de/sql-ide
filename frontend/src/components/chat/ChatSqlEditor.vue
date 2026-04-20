<template>
  <section class="chat-sql-editor">
    <div class="chat-sql-editor__toolbar">
      <span class="chat-sql-editor__status" :class="statusClass">{{ statusLabel }}</span>
      <div class="chat-sql-editor__actions">
        <button class="chat-sql-editor__btn" type="button" @click="copy">
          Копировать
        </button>
        <button class="chat-sql-editor__btn chat-sql-editor__btn--accent" type="button" :disabled="!canRun" @click="$emit('run')">
          {{ busy ? 'Выполняю…' : 'Запустить' }}
        </button>
      </div>
    </div>

    <textarea
      :value="modelValue"
      class="chat-sql-editor__field"
      spellcheck="false"
      autocomplete="off"
      autocapitalize="off"
      :disabled="busy"
      placeholder="SQL"
      @input="onInput"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  modelValue: string;
  busy: boolean;
  status: 'idle' | 'executing' | 'error' | 'generating';
}>();

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void;
  (event: 'run'): void;
}>();

const statusLabel = computed(() => {
  switch (props.status) {
    case 'executing':
      return 'Выполняю';
    case 'error':
      return 'Ошибка';
    case 'generating':
      return 'Генерирую';
    default:
      return 'Готов';
  }
});

const statusClass = computed(() => {
  switch (props.status) {
    case 'executing':
      return 'chat-sql-editor__status--info';
    case 'error':
      return 'chat-sql-editor__status--error';
    case 'generating':
      return 'chat-sql-editor__status--info';
    default:
      return '';
  }
});

const canRun = computed(() => props.modelValue.trim().length > 0 && !props.busy);

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  emit('update:modelValue', target.value);
}

async function copy() {
  if (!props.modelValue.trim()) {
    return;
  }
  try {
    await navigator.clipboard.writeText(props.modelValue);
  } catch {
    /* ignore clipboard failures */
  }
}
</script>

<style scoped lang="scss">
.chat-sql-editor {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
}

.chat-sql-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-sql-editor__status {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  font-size: 0.76rem;
  color: var(--muted);
}

.chat-sql-editor__status--info {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.7);
  background: rgba(112, 59, 247, 0.2);
}

.chat-sql-editor__status--error {
  border-color: rgba(255, 107, 107, 0.6);
  background: rgba(255, 107, 107, 0.15);
  color: #ffb3b3;
}

.chat-sql-editor__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-sql-editor__btn {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  font-size: 0.78rem;
}

.chat-sql-editor__btn--accent {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

.chat-sql-editor__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-sql-editor__field {
  width: 100%;
  min-height: 0;
  resize: none;
  padding: 12px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: rgba(0, 0, 0, 0.2);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 0.86rem;
  line-height: 1.55;
}

.chat-sql-editor__field:focus {
  outline: none;
  border-color: rgba(112, 59, 247, 0.8);
}
</style>
