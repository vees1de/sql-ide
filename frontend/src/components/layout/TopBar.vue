<template>
  <header class="topbar">
    <div class="topbar__row topbar__row--main">
      <RouterLink to="/chat" class="topbar__logo" title="Главная">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22">
            <circle cx="8" cy="12" r="5" fill="#f9ab00" />
            <circle cx="16" cy="12" r="5" fill="#fbbc04" opacity="0.92" />
          </svg>
        </span>
        <span class="topbar__logo-text">SQL IDE</span>
      </RouterLink>

      <nav class="topbar__nav" aria-label="Разделы">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="topbar__nav-link"
          :class="{ 'topbar__nav-link--active': isNavActive(item) }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="topbar__right">
        <button
          class="app-button share-btn"
          type="button"
          @click="$emit('share')"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
          Поделиться
        </button>
        <div class="avatar" aria-label="Профиль">{{ initials }}</div>
      </div>
    </div>

    <div class="topbar__row topbar__row--tools">
      <div class="topbar__tools-left">
        <div
          class="status-pill"
          :class="{ 'status-pill--active': isRunning }"
        >
          <span class="status-pill__dot"></span>
          {{ statusLabel }}
        </div>
        <div class="topbar__db">
          <span class="topbar__db-label">DB</span>
          <strong>{{ database.name }}</strong>
          <span class="topbar__db-meta">{{ database.engine }}</span>
        </div>
      </div>
      <div class="topbar__tools-actions">
        <button
          class="icon-btn"
          type="button"
          title="Новый notebook"
          @click="$emit('new-notebook')"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
        <button
          class="icon-btn"
          type="button"
          title="Запустить всё"
          @click="$emit('run-all')"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 4.5v15l13-7.5z"/></svg>
        </button>
        <button
          class="icon-btn"
          type="button"
          title="Сохранить отчёт"
          @click="$emit('save-report')"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
        </button>
      </div>
    </div>
  </header>

  <div v-if="banner" class="topbar-banner">
    <span class="pill pill--accent">●</span>
    <span>{{ banner }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import type { DatabaseConnection } from '@/types/app';

const props = defineProps<{
  banner: string;
  database: DatabaseConnection;
  isRunning: boolean;
  statusLabel: string;
  workspaceName: string;
}>();

defineEmits<{
  (event: 'new-notebook'): void;
  (event: 'run-all'): void;
  (event: 'save-report'): void;
  (event: 'share'): void;
}>();

const route = useRoute();

const navItems = [
  { to: '/chat', label: 'Чат', key: 'chat' as const },
  { to: '/colab', label: 'Колаб', key: 'colab' as const },
  { to: '/data', label: 'Данные', key: 'data' as const }
];

function isNavActive(item: (typeof navItems)[number]): boolean {
  const p = route.path;
  if (item.key === 'data') {
    return p === '/data' || p.startsWith('/data');
  }
  if (item.key === 'colab') {
    return p === '/colab' || p === '/notebook';
  }
  /* chat */
  return p === '/chat' || p.startsWith('/notebooks');
}

const initials = computed(() => {
  const name = props.workspaceName || 'AI';
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? 'A').toUpperCase() + (parts[1]?.[0] ?? '').toUpperCase();
});
</script>

<style scoped lang="scss">
.topbar {
  border-bottom: 1px solid var(--line);
  background: var(--bg-elev);
}

.topbar__row {
  display: flex;
  align-items: center;
  padding: 0 1rem;
}

.topbar__row--main {
  gap: 1rem;
  padding-top: 0.5rem;
  padding-bottom: 0.45rem;
  justify-content: space-between;
}

.topbar__row--tools {
  justify-content: space-between;
  gap: 0.75rem;
  padding-bottom: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.topbar__logo {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: inherit;
  flex-shrink: 0;
}

.topbar__logo-text {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ink-strong);
  letter-spacing: -0.02em;
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(249, 171, 0, 0.08);
}

.topbar__nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.topbar__nav-link {
  padding: 0.45rem 1rem;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: 0.88rem;
  font-weight: 600;
  text-decoration: none;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
}

.topbar__nav-link:hover {
  color: var(--ink);
  background: rgba(255, 255, 255, 0.05);
}

.topbar__nav-link--active {
  color: var(--link-strong);
  background: var(--link-soft);
  border-color: rgba(138, 180, 248, 0.35);
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}

.topbar__tools-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
  min-width: 0;
}

.topbar__tools-actions {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
  font-size: 0.76rem;
  transition: background 180ms ease, color 180ms ease;
}

.status-pill__dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: var(--success);
}

.status-pill--active {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.status-pill--active .status-pill__dot {
  background: var(--accent);
  animation: pulse-dot 1.2s ease infinite;
}

.topbar__db {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.76rem;
  color: var(--ink);
  min-width: 0;
}

.topbar__db strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.topbar__db-label {
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-size: 0.65rem;
}

.topbar__db-meta {
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--ink);
  transition: background 160ms ease, color 160ms ease;
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--accent-strong);
}

.share-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.avatar {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: linear-gradient(135deg, #8ab4f8, #f9ab00);
  color: #1a1d24;
  font-size: 0.76rem;
  font-weight: 700;
}

.topbar-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 1rem;
  background: rgba(249, 171, 0, 0.05);
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.8rem;
}

@keyframes pulse-dot {
  0% { box-shadow: 0 0 0 0 rgba(249, 171, 0, 0.5); }
  70% { box-shadow: 0 0 0 8px rgba(249, 171, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(249, 171, 0, 0); }
}

@media (max-width: 720px) {
  .topbar__nav {
    gap: 0;
  }

  .topbar__nav-link {
    padding: 0.4rem 0.65rem;
    font-size: 0.8rem;
  }

  .topbar__logo-text {
    display: none;
  }
}
</style>
