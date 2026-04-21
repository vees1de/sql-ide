<template>
  <form class="chat-input" @submit.prevent="submit">
    <textarea
      :value="modelValue"
      class="chat-input__field"
      rows="2"
      :placeholder="placeholder"
      :disabled="busy"
      @input="onInput"
      @keydown="onKeydown"
    />
    <div class="chat-input__footer">
      <div class="chat-input__controls">
        <button
          class="chat-input__mode chat-input__mode--active"
          type="button"
          :disabled="busy"
          role="switch"
          aria-checked="true"
          aria-label="Thinking режим"
        >
          <span class="chat-input__mode-label">
            Thinking
            <small>on</small>
          </span>
          <span class="chat-input__mode-track" aria-hidden="true">
            <span class="chat-input__mode-thumb" />
          </span>
        </button>
        <select
          class="chat-input__model"
          :value="modelAlias"
          :disabled="busy"
          @change="onModelChange"
        >
          <option
            v-for="alias in modelAliases"
            :key="alias"
            :value="alias"
          >
            {{ alias }}
          </option>
        </select>
      </div>
      <button class="chat-input__send" type="submit" :disabled="busy || !modelValue.trim()">
        <span v-if="busy" class="chat-input__spinner" />
        <span v-else>→</span>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: string;
    busy: boolean;
    queryMode?: 'fast' | 'thinking';
    modelAlias?: string;
    modelAliases?: string[];
    placeholder?: string;
  }>(),
  {
    queryMode: 'fast',
    modelAlias: 'gpt120',
    modelAliases: () => ['gpt120'],
    placeholder: ''
  }
);

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void;
  (event: 'update:queryMode', value: 'fast' | 'thinking'): void;
  (event: 'update:modelAlias', value: string): void;
  (event: 'send'): void;
}>();

emit('update:queryMode', 'thinking');

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  emit('update:modelValue', target.value);
}

function onKeydown(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault();
    submit();
  }
}

function submit() {
  if (props.busy || !props.modelValue.trim()) {
    return;
  }
  emit('send');
}

function onModelChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const next = target.value.trim();
  if (!next || next === props.modelAlias) {
    return;
  }
  emit('update:modelAlias', next);
}
</script>

<style scoped lang="scss">
.chat-input {
  display: grid;
  gap: 8px;
}

.chat-input__field {
  width: 100%;
  min-height: 84px;
  resize: none;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.5;
}

.chat-input__field:focus {
  outline: none;
  border-color: rgba(112, 59, 247, 0.8);
}

.chat-input__footer {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.chat-input__controls {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.chat-input__mode,
.chat-input__model,
.chat-input__send {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--muted);
}

.chat-input__mode {
  min-height: 30px;
  min-width: 112px;
  padding: 0 8px 0 10px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.75rem;
  transition:
    border-color 140ms ease,
    background 140ms ease,
    color 140ms ease;
}

.chat-input__mode-label {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  line-height: 1;
}

.chat-input__mode-label small {
  font-size: 0.64rem;
  color: var(--muted-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chat-input__mode-track {
  width: 28px;
  height: 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 1px;
  display: inline-flex;
  align-items: center;
  transition: background 140ms ease, border-color 140ms ease;
}

.chat-input__mode-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--muted);
  transform: translateX(0);
  transition: transform 140ms ease, background 140ms ease;
}

.chat-input__mode--active {
  border-color: rgba(112, 59, 247, 0.8);
  color: var(--ink-strong);
  background: rgba(112, 59, 247, 0.2);
}

.chat-input__mode--active .chat-input__mode-label small {
  color: rgba(255, 255, 255, 0.7);
}

.chat-input__mode--active .chat-input__mode-track {
  background: rgba(112, 59, 247, 0.3);
  border-color: rgba(112, 59, 247, 0.35);
}

.chat-input__mode--active .chat-input__mode-thumb {
  transform: translateX(12px);
  background: var(--ink-strong);
}

.chat-input__model {
  max-width: 150px;
  color: var(--ink);
}

.chat-input__send {
  width: 34px;
  padding: 0;
  font-size: 1rem;
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

.chat-input__send:disabled,
.chat-input__mode:disabled,
.chat-input__model:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-input__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--ink-strong);
  border-radius: 50%;
  animation: chat-spin 0.7s linear infinite;
}

@keyframes chat-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 940px) {
  .chat-input__footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-input__controls {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
