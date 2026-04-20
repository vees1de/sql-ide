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
        <div class="chat-input__mode" role="group" aria-label="Query mode">
          <button
            class="chat-input__mode-btn"
            :class="{ 'chat-input__mode-btn--active': queryMode === 'fast' }"
            type="button"
            :disabled="busy"
            @click="setMode('fast')"
          >
            Fast
          </button>
          <button
            class="chat-input__mode-btn"
            :class="{ 'chat-input__mode-btn--active': queryMode === 'thinking' }"
            type="button"
            :disabled="busy"
            @click="setMode('thinking')"
          >
            Thinking
          </button>
        </div>
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
        {{ busy ? '...' : '→' }}
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

function setMode(mode: 'fast' | 'thinking') {
  if (props.busy || props.queryMode === mode) {
    return;
  }
  emit('update:queryMode', mode);
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

.chat-input__mode {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.chat-input__mode-btn,
.chat-input__model,
.chat-input__send {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--muted);
  font-size: 0.75rem;
  min-height: 30px;
  padding: 0 10px;
}

.chat-input__mode-btn--active {
  border-color: rgba(112, 59, 247, 0.8);
  color: var(--ink-strong);
  background: rgba(112, 59, 247, 0.2);
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
.chat-input__mode-btn:disabled,
.chat-input__model:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
