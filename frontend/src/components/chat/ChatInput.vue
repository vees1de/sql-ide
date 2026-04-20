<template>
  <form class="chat-input" @submit.prevent="submit">
    <textarea
      :value="modelValue"
      class="chat-input__field"
      rows="3"
      :placeholder="placeholder"
      :disabled="busy"
      @input="onInput"
      @keydown="onKeydown"
    />
    <div class="chat-input__footer">
      <p>Ctrl/Cmd + Enter для отправки.</p>
      <button class="app-button" type="submit" :disabled="busy || !modelValue.trim()">
        {{ busy ? 'Генерирую…' : 'Отправить' }}
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: string;
  busy: boolean;
  placeholder?: string;
}>();

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void;
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
</script>

<style scoped lang="scss">
.chat-input {
  display: grid;
  gap: 0.6rem;
}

.chat-input__field {
  width: 100%;
  min-height: 6.5rem;
  resize: vertical;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--bg-elev);
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.55;
}

.chat-input__field:focus {
  outline: none;
  border-color: rgba(249, 171, 0, 0.45);
  box-shadow: 0 0 0 3px rgba(249, 171, 0, 0.08);
}

.chat-input__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.chat-input__footer p {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
}
</style>

