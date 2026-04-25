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
          aria-label="Thinking mode"
        >
          <span class="chat-input__mode-label">Deep thinking</span>
          <span class="chat-input__mode-track" aria-hidden="true">
            <span class="chat-input__mode-thumb" />
          </span>
        </button>

        <div
          ref="modelSelectEl"
          class="chat-input__model-select"
          :class="{ 'chat-input__model-select--open': isModelMenuOpen }"
          @focusout="onModelFocusOut"
        >
          <button
            ref="modelTriggerEl"
            class="chat-input__model-trigger"
            type="button"
            :disabled="busy || !modelAliases.length"
            aria-haspopup="listbox"
            :aria-expanded="isModelMenuOpen"
            aria-label="Select model"
            @click="toggleModelMenu"
            @keydown="onModelTriggerKeydown"
          >
            <span class="chat-input__model-trigger-copy">
              <span class="chat-input__model-trigger-label">Model </span>
              <span class="chat-input__model-trigger-value">
                {{ currentModelAlias }}
              </span>
            </span>
            <span class="chat-input__model-trigger-icon" aria-hidden="true">
              <svg viewBox="0 0 10 6" width="10" height="6" fill="none">
                <path
                  d="M1 1L5 5L9 1"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </span>
          </button>

          <Transition name="chat-input__model-menu">
            <div
              v-if="isModelMenuOpen"
              class="chat-input__model-menu"
              role="listbox"
              aria-label="Model options"
              @keydown="onModelMenuKeydown"
            >
              <button
                v-for="alias in modelAliases"
                :key="alias"
                class="chat-input__model-option"
                :class="{
                  'chat-input__model-option--selected':
                    alias === currentModelAlias,
                }"
                type="button"
                role="option"
                :aria-selected="alias === currentModelAlias"
                :data-model-alias="alias"
                data-model-option="true"
                @click="selectModelAlias(alias)"
              >
                <span class="chat-input__model-option-value">{{ alias }}</span>
                <span
                  v-if="alias === currentModelAlias"
                  class="chat-input__model-option-check"
                  aria-hidden="true"
                >
                  <svg viewBox="0 0 14 14" width="14" height="14" fill="none">
                    <path
                      d="M3 7.5L5.5 10L11 4.5"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </span>
              </button>
            </div>
          </Transition>
        </div>
      </div>

      <button
        class="chat-input__send"
        type="submit"
        :disabled="busy || !modelValue.trim()"
      >
        <span v-if="busy" class="chat-input__spinner" />
        <span v-else>&rarr;</span>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

const props = withDefaults(
  defineProps<{
    modelValue: string;
    busy: boolean;
    queryMode?: "fast" | "thinking";
    modelAlias?: string;
    modelAliases?: string[];
    placeholder?: string;
  }>(),
  {
    queryMode: "fast",
    modelAlias: "gpt120",
    modelAliases: () => ["gpt120"],
    placeholder: "",
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
  (event: "update:queryMode", value: "fast" | "thinking"): void;
  (event: "update:modelAlias", value: string): void;
  (event: "send"): void;
}>();

const isModelMenuOpen = ref(false);
const modelSelectEl = ref<HTMLElement | null>(null);
const modelTriggerEl = ref<HTMLButtonElement | null>(null);

emit("update:queryMode", "thinking");

const currentModelAlias = computed(() => {
  const current = props.modelAlias?.trim();
  if (current && props.modelAliases.includes(current)) {
    return current;
  }
  return props.modelAliases[0] ?? "";
});

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  emit("update:modelValue", target.value);
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function submit() {
  if (props.busy || !props.modelValue.trim()) {
    return;
  }
  emit("send");
}

function getModelOptionElements() {
  return Array.from(
    modelSelectEl.value?.querySelectorAll<HTMLButtonElement>(
      "[data-model-option]",
    ) ?? [],
  );
}

function focusModelOption(
  alias: string = currentModelAlias.value,
  fallback: "first" | "last" = "first",
) {
  const options = getModelOptionElements();
  if (!options.length) {
    return;
  }

  const fallbackOption =
    fallback === "last" ? options[options.length - 1] : options[0];
  const target =
    options.find((option) => option.dataset.modelAlias === alias) ??
    fallbackOption;

  target?.focus();
}

function openModelMenu({ focusSelected = true } = {}) {
  if (props.busy || !props.modelAliases.length) {
    return;
  }

  isModelMenuOpen.value = true;

  if (!focusSelected) {
    return;
  }

  void nextTick(() => {
    focusModelOption();
  });
}

function closeModelMenu({ focusTrigger = false } = {}) {
  if (!isModelMenuOpen.value) {
    return;
  }

  isModelMenuOpen.value = false;

  if (focusTrigger) {
    void nextTick(() => {
      modelTriggerEl.value?.focus();
    });
  }
}

function toggleModelMenu() {
  if (isModelMenuOpen.value) {
    closeModelMenu();
    return;
  }
  openModelMenu();
}

function selectModelAlias(alias: string) {
  if (!alias) {
    closeModelMenu({ focusTrigger: true });
    return;
  }

  if (alias !== currentModelAlias.value) {
    emit("update:modelAlias", alias);
  }

  closeModelMenu({ focusTrigger: true });
}

function moveModelFocus(step: 1 | -1) {
  const options = getModelOptionElements();
  if (!options.length) {
    return;
  }

  const activeIndex = options.findIndex(
    (option) => option === document.activeElement,
  );
  const selectedIndex = options.findIndex(
    (option) => option.dataset.modelAlias === currentModelAlias.value,
  );
  const startIndex = activeIndex === -1 ? selectedIndex : activeIndex;
  const nextIndex =
    startIndex === -1
      ? step === 1
        ? 0
        : options.length - 1
      : (startIndex + step + options.length) % options.length;

  options[nextIndex]?.focus();
}

function onModelTriggerKeydown(event: KeyboardEvent) {
  if (props.busy) {
    return;
  }

  switch (event.key) {
    case "ArrowDown":
    case "Enter":
    case " ":
      event.preventDefault();
      openModelMenu();
      break;
    case "ArrowUp":
      event.preventDefault();
      openModelMenu({ focusSelected: false });
      void nextTick(() => {
        focusModelOption(currentModelAlias.value, "last");
      });
      break;
    case "Escape":
      closeModelMenu();
      break;
    default:
      break;
  }
}

function onModelMenuKeydown(event: KeyboardEvent) {
  if (!isModelMenuOpen.value) {
    return;
  }

  switch (event.key) {
    case "ArrowDown":
      event.preventDefault();
      moveModelFocus(1);
      break;
    case "ArrowUp":
      event.preventDefault();
      moveModelFocus(-1);
      break;
    case "Home":
      event.preventDefault();
      focusModelOption(undefined, "first");
      break;
    case "End":
      event.preventDefault();
      focusModelOption(undefined, "last");
      break;
    case "Escape":
      event.preventDefault();
      closeModelMenu({ focusTrigger: true });
      break;
    case "Tab":
      closeModelMenu();
      break;
    default:
      break;
  }
}

function onModelFocusOut(event: FocusEvent) {
  const nextTarget = event.relatedTarget;
  if (nextTarget instanceof Node && modelSelectEl.value?.contains(nextTarget)) {
    return;
  }
  closeModelMenu();
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }

  if (modelSelectEl.value?.contains(target)) {
    return;
  }

  closeModelMenu();
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
});
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
  align-items: stretch;
  gap: 8px;
  min-width: 0;
}

.chat-input__mode,
.chat-input__model-trigger,
.chat-input__send {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  color: var(--muted);
  line-height: 1;
  transition:
    border-color 140ms ease,
    background 140ms ease,
    color 140ms ease,
    opacity 140ms ease;
}

.chat-input__mode {
  display: none;
}

.chat-input__mode-label {
  display: inline-flex;
  align-items: center;
  line-height: 1;
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
  transition:
    background 140ms ease,
    border-color 140ms ease;
}

.chat-input__mode-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--muted);
  transform: translateX(0);
  transition:
    transform 140ms ease,
    background 140ms ease;
}

.chat-input__mode--active {
  border-color: rgba(112, 59, 247, 0.8);
  color: var(--ink-strong);
  background: rgba(112, 59, 247, 0.2);
}

.chat-input__mode--active .chat-input__mode-track {
  background: rgba(112, 59, 247, 0.3);
  border-color: rgba(112, 59, 247, 0.35);
}

.chat-input__mode--active .chat-input__mode-thumb {
  transform: translateX(12px);
  background: var(--ink-strong);
}

.chat-input__model-select {
  position: relative;
  flex: 0 0 auto;
  min-width: 0;
}

.chat-input__model-trigger {
  width: min(180px, 42vw);
  min-width: 132px;
  max-width: 180px;
  height: 36px;
  padding: 0 10px 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--ink);
}

.chat-input__model-trigger-copy {
  min-width: 0;
}

.chat-input__model-trigger-label {
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted-2);
}

.chat-input__model-trigger-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-strong);
  font-size: 0.76rem;
  font-weight: 600;
}

.chat-input__model-trigger-icon {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted-2);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  transition:
    transform 140ms ease,
    background 140ms ease,
    color 140ms ease;
}

.chat-input__model-trigger:hover:not(:disabled),
.chat-input__model-select--open .chat-input__model-trigger {
  border-color: rgba(112, 59, 247, 0.45);
  background: rgba(112, 59, 247, 0.12);
}

.chat-input__model-trigger:hover:not(:disabled) .chat-input__model-trigger-icon,
.chat-input__model-select--open .chat-input__model-trigger-icon {
  background: rgba(112, 59, 247, 0.22);
  color: var(--ink-strong);
}

.chat-input__model-select--open .chat-input__model-trigger-icon {
  transform: rotate(180deg);
}

.chat-input__model-trigger:focus-visible,
.chat-input__mode:focus-visible,
.chat-input__send:focus-visible,
.chat-input__model-option:focus-visible {
  outline: none;
  border-color: rgba(112, 59, 247, 0.8);
}

.chat-input__model-menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  min-width: 100%;
  width: max-content;
  max-width: min(260px, 70vw);
  padding: 6px;
  display: grid;
  gap: 4px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: rgba(36, 36, 36, 0.98);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.32);
  z-index: 12;
}

.chat-input__model-menu-enter-active,
.chat-input__model-menu-leave-active {
  transform-origin: bottom right;
  transition:
    opacity 140ms ease,
    transform 140ms ease;
}

.chat-input__model-menu-enter-from,
.chat-input__model-menu-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.chat-input__model-option {
  width: 100%;
  min-height: 36px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  transition:
    border-color 140ms ease,
    background 140ms ease,
    color 140ms ease;
}

.chat-input__model-option:hover {
  border-color: rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.05);
}

.chat-input__model-option--selected {
  border-color: rgba(112, 59, 247, 0.3);
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
}

.chat-input__model-option-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
}

.chat-input__model-option-check {
  color: var(--accent-strong);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
}

.chat-input__send {
  width: 34px;
  height: 36px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
}

.chat-input__send:disabled,
.chat-input__mode:disabled,
.chat-input__model-trigger:disabled {
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
  to {
    transform: rotate(360deg);
  }
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

  .chat-input__model-trigger {
    width: min(180px, 48vw);
  }
}
</style>
