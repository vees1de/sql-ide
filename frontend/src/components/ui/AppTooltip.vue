<template>
  <span class="app-tooltip">
    <button
      aria-label="Показать подсказку"
      class="app-tooltip__trigger"
      type="button"
    >
      ?
    </button>
    <span class="app-tooltip__content" role="tooltip">
      <slot />
    </span>
  </span>
</template>

<style scoped lang="scss">
.app-tooltip {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.app-tooltip__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  background: rgba(18, 20, 27, 0.92);
  color: var(--muted);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1;
  cursor: help;
  transition:
    border-color 0.18s ease,
    color 0.18s ease,
    background-color 0.18s ease;
}

.app-tooltip__trigger:hover,
.app-tooltip__trigger:focus-visible {
  border-color: rgba(138, 180, 248, 0.5);
  color: var(--ink-strong);
  background: rgba(26, 39, 64, 0.94);
  outline: none;
}

.app-tooltip__content {
  position: absolute;
  top: calc(100% + 0.65rem);
  left: 50%;
  z-index: 20;
  min-width: 220px;
  max-width: 320px;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(18, 20, 27, 0.98);
  box-shadow: var(--shadow-soft);
  color: var(--ink);
  font-size: 0.8rem;
  line-height: 1.45;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateX(-50%) translateY(-6px);
  transition:
    opacity 0.18s ease,
    visibility 0.18s ease,
    transform 0.18s ease;
}

.app-tooltip__content::before {
  content: "";
  position: absolute;
  top: -0.35rem;
  left: 50%;
  width: 0.7rem;
  height: 0.7rem;
  border-top: 1px solid var(--line);
  border-left: 1px solid var(--line);
  background: rgba(18, 20, 27, 0.98);
  transform: translateX(-50%) rotate(45deg);
}

.app-tooltip:hover .app-tooltip__content,
.app-tooltip:focus-within .app-tooltip__content {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}
</style>
