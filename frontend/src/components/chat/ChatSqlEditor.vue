<template>
  <section class="chat-sql-editor">
    <header class="chat-sql-editor__head">
      <div>
        <p class="eyebrow">Редактор SQL</p>
        <h2>Подготовленный запрос</h2>
      </div>
      <div class="chat-sql-editor__status">
        <span class="pill" :class="statusClass">{{ statusLabel }}</span>
      </div>
    </header>

    <div class="chat-sql-editor__toolbar">
      <div class="chat-sql-editor__meta">
        <span class="pill pill--ghost">Версия {{ version }}</span>
        <span class="pill pill--ghost">{{ autoApplySql ? 'Автоподстановка включена' : 'Автоподстановка выключена' }}</span>
      </div>
      <div class="chat-sql-editor__actions">
        <button class="app-button app-button--ghost app-button--tiny" type="button" @click="copy">
          Копировать
        </button>
        <button class="app-button app-button--tiny" type="button" :disabled="!canRun" @click="$emit('run')">
          {{ busy ? 'Выполняю…' : 'Выполнить' }}
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
      placeholder="SQL появится здесь после ответа ассистента"
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
  version: number;
  autoApplySql: boolean;
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
      return 'pill--soft';
    case 'error':
      return 'pill--accent';
    case 'generating':
      return 'pill--soft';
    default:
      return 'pill--ghost';
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
  gap: 0.75rem;
  min-height: 0;
}

.chat-sql-editor__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.chat-sql-editor__head h2 {
  margin: 0.3rem 0 0;
  font-size: 1.05rem;
}

.chat-sql-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.chat-sql-editor__meta,
.chat-sql-editor__actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.chat-sql-editor__field {
  width: 100%;
  min-height: 16rem;
  resize: vertical;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01)),
    var(--canvas);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 0.87rem;
  line-height: 1.65;
  box-shadow: var(--shadow-soft);
}

.chat-sql-editor__field:focus {
  outline: none;
  border-color: rgba(249, 171, 0, 0.45);
  box-shadow: 0 0 0 3px rgba(249, 171, 0, 0.08), var(--shadow-soft);
}
</style>

