<template>
  <section class="chat-sql-editor">
    <div class="chat-sql-editor__toolbar">
      <div class="chat-sql-editor__actions">
        <button class="chat-sql-editor__btn" type="button" @click="copy">
          Копировать
        </button>
        <button class="chat-sql-editor__btn chat-sql-editor__btn--accent" type="button" :disabled="!canRun" @click="$emit('run')">
          {{ busy ? 'Выполняю…' : 'Запустить' }}
        </button>
        <button
          class="chat-sql-editor__help"
          type="button"
          :disabled="busy"
          aria-label="Объяснить SQL код"
          @click="$emit('explain')"
        >
          ?
          <span class="chat-sql-editor__help-tooltip">При нажатии ИИ объяснит SQL код</span>
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
  state?: 'CLARIFYING' | 'SQL_DRAFTING' | 'SQL_READY' | 'ERROR';
}>();

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void;
  (event: 'run'): void;
  (event: 'explain'): void;
}>();

const canRun = computed(() => props.modelValue.trim().length > 0 && !props.busy && props.state !== 'CLARIFYING');

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
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
}

.chat-sql-editor__help {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(112, 59, 247, 0.7);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.34), rgba(112, 59, 247, 0.2));
  color: #efe9ff;
  font-size: 1rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(112, 59, 247, 0.18);
  animation: chat-sql-editor-float 3.2s ease-in-out infinite;
}

.chat-sql-editor__help:hover:not(:disabled),
.chat-sql-editor__help:focus-visible:not(:disabled) {
  border-color: rgba(164, 126, 255, 0.92);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.42), rgba(112, 59, 247, 0.26));
}

.chat-sql-editor__help:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  animation: none;
}

.chat-sql-editor__help-tooltip {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  min-width: 220px;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(8, 12, 20, 0.96);
  color: var(--ink);
  font-size: 0.76rem;
  line-height: 1.35;
  white-space: normal;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.chat-sql-editor__help:hover .chat-sql-editor__help-tooltip,
.chat-sql-editor__help:focus-visible .chat-sql-editor__help-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.chat-sql-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1.1;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.chat-sql-editor__btn:hover:not(:disabled) {
  color: var(--ink-strong);
  border-color: rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
}

.chat-sql-editor__btn--accent {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

.chat-sql-editor__btn--accent:hover:not(:disabled) {
  border-color: rgba(112, 59, 247, 0.92);
  background: rgba(112, 59, 247, 0.32);
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

@keyframes chat-sql-editor-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
</style>
