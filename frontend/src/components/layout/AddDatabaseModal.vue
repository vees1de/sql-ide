<template>
  <div class="modal-root" @click.self="$emit('close')">
    <div class="modal">
      <header class="modal__header">
        <div>
          <p class="eyebrow">New connection</p>
          <h2>Добавить базу данных</h2>
        </div>
        <button
          class="icon-btn"
          type="button"
          @click="$emit('close')"
          aria-label="Close"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </header>

      <div class="presets">
        <button
          v-for="preset in presets"
          :key="preset.name"
          class="preset"
          type="button"
          @click="applyPreset(preset)"
        >
          <strong>{{ preset.name }}</strong>
          <span
            >{{ preset.host }}:{{ preset.port }} · {{ preset.database }}</span
          >
        </button>
      </div>

      <form class="form" @submit.prevent="submit">
        <label>
          <span>Название</span>
          <input
            v-model="form.name"
            type="text"
            placeholder="dvdrental"
            required
          />
        </label>

        <div class="form__row">
          <label class="form__engine">
            <span>Движок</span>
            <select v-model="form.engine">
              <option>PostgreSQL</option>
              <option>MySQL</option>
              <option>SQLite</option>
              <option>ClickHouse</option>
            </select>
          </label>
          <label class="form__host">
            <span>Host</span>
            <input v-model="form.host" type="text" placeholder="localhost" />
          </label>
          <label class="form__port">
            <span>Port</span>
            <input v-model="form.port" type="text" placeholder="5432" />
          </label>
        </div>

        <label>
          <span>Database</span>
          <input v-model="form.database" type="text" placeholder="dvdrental" />
        </label>

        <div class="form__row">
          <label>
            <span>User</span>
            <input
              v-model="form.user"
              type="text"
              placeholder="postgres"
              autocomplete="off"
            />
          </label>
          <label>
            <span>Password</span>
            <input
              v-model="form.password"
              type="password"
              autocomplete="new-password"
            />
          </label>
        </div>

        <label>
          <span>Таблицы (примерно, опц.)</span>
          <input
            v-model.number="form.tables"
            type="number"
            min="0"
            placeholder="15"
          />
        </label>

        <div class="form__section">
          <p class="form__section-title">Knowledge scan</p>
          <label class="form__check">
            <input v-model="importSchemaToDictionary" type="checkbox" />
            <span
              >Сразу выполнить full scan схемы и синхронизировать
              Dictionary</span
            >
          </label>
          <p class="form__hint">
            После подключения база будет распарсена в knowledge layer: tables,
            columns, FK и persisted scan snapshot.
          </p>
        </div>

        <div class="form__section">
          <p class="form__section-title">Доступ к таблицам</p>
          <div class="form__toolbar">
            <button
              class="app-button app-button--ghost app-button--tiny"
              type="button"
              :disabled="previewLoading"
              @click.prevent="loadPreview"
            >
              {{ previewLoading ? "Загрузка…" : "Загрузить список таблиц" }}
            </button>
            <template v-if="previewTables.length">
              <button
                class="app-button app-button--link app-button--tiny"
                type="button"
                @click.prevent="selectAllTables"
              >
                Выбрать все
              </button>
              <button
                class="app-button app-button--link app-button--tiny"
                type="button"
                @click.prevent="clearTables"
              >
                Снять все
              </button>
            </template>
          </div>
          <p v-if="previewError" class="form__error">{{ previewError }}</p>
          <div v-if="previewTables.length" class="table-pick">
            <label
              v-for="t in previewTables"
              :key="t.name"
              class="table-pick__row"
            >
              <input v-model="selectedTables" type="checkbox" :value="t.name" />
              <span>
                <strong>{{ t.name }}</strong>
                <small
                  >{{ t.columns.slice(0, 8).join(", ")
                  }}{{ t.columns.length > 8 ? "…" : "" }}</small
                >
              </span>
            </label>
          </div>
          <p v-else class="form__hint">
            Нажмите «Загрузить список таблиц», чтобы ограничить whitelist. Иначе
            при подключении будут разрешены все найденные таблицы.
          </p>
        </div>

        <footer class="modal__footer">
          <button
            type="button"
            class="app-button app-button--ghost"
            @click="$emit('close')"
          >
            Отмена
          </button>
          <button type="submit" class="app-button">Подключить</button>
        </footer>
      </form>
    </div>
  </div>
</template>
<script setup lang="ts">
import { reactive, ref } from "vue";
import { api } from "@/api/client";
import AppSkeleton from "@/components/ui/AppSkeleton.vue";
import type { ApiSchemaPreviewTable } from "@/api/types";

const emit = defineEmits<{
  (event: "close"): void;
  (
    event: "submit",
    payload: {
      name: string;
      engine: string;
      host: string;
      port: string;
      database: string;
      user: string;
      password: string;
      tables: number;
      importSchemaToDictionary: boolean;
      allowedTables: string[] | null;
    },
  ): void;
}>();

const form = reactive({
  name: "",
  engine: "PostgreSQL",
  host: "localhost",
  port: "5432",
  database: "",
  user: "postgres",
  password: "",
  tables: 0,
});

const importSchemaToDictionary = ref(true);
const previewLoading = ref(false);
const previewError = ref("");
const previewTables = ref<ApiSchemaPreviewTable[]>([]);
const selectedTables = ref<string[]>([]);
const previewLoaded = ref(false);

const presets = [
  {
    name: "dvdrental",
    engine: "PostgreSQL",
    host: "localhost",
    port: "5432",
    database: "dvdrental",
    user: "postgres",
    password: "postgres",
    tables: 15,
  },
];

function applyPreset(preset: (typeof presets)[number]) {
  form.name = preset.name;
  form.engine = preset.engine;
  form.host = preset.host;
  form.port = preset.port;
  form.database = preset.database;
  form.user = preset.user;
  form.password = preset.password;
  form.tables = preset.tables;
  previewTables.value = [];
  selectedTables.value = [];
  previewLoaded.value = false;
  previewError.value = "";
}

function buildPreviewPayload() {
  const portNumber =
    typeof form.port === "string" && form.port.trim()
      ? Number.parseInt(form.port, 10) || null
      : null;
  return {
    name: form.name.trim() || "preview",
    dialect: form.engine.toLowerCase(),
    host: form.host.trim() || null,
    port: portNumber,
    database: form.database.trim() || null,
    username: form.user.trim() || null,
    password: form.password || null,
    read_only: true,
    table_count: form.tables || 0,
  };
}

async function loadPreview() {
  previewError.value = "";
  previewLoading.value = true;
  try {
    const res = await api.previewDatabaseSchema(buildPreviewPayload());
    previewTables.value = res.tables;
    selectedTables.value = [...res.table_names];
    previewLoaded.value = true;
  } catch (e) {
    previewTables.value = [];
    selectedTables.value = [];
    previewLoaded.value = false;
    previewError.value =
      e instanceof Error ? e.message : "Не удалось прочитать схему.";
  } finally {
    previewLoading.value = false;
  }
}

function selectAllTables() {
  selectedTables.value = previewTables.value.map((t) => t.name);
}

function clearTables() {
  selectedTables.value = [];
}

function submit() {
  if (!form.name.trim()) return;
  if (
    previewLoaded.value &&
    previewTables.value.length &&
    selectedTables.value.length === 0
  ) {
    previewError.value =
      "Выберите хотя бы одну таблицу для доступа или очистите превью (закройте и откройте форму).";
    return;
  }
  let allowed: string[] | null = null;
  if (previewLoaded.value && previewTables.value.length) {
    allowed = [...selectedTables.value];
  }
  emit("submit", {
    ...form,
    importSchemaToDictionary: importSchemaToDictionary.value,
    allowedTables: allowed,
  });
}
</script>

<style scoped lang="scss">
.modal-root {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(5, 7, 12, 0.7);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  padding: 1.5rem;
}

.modal {
  width: fit-content;
  max-height: calc(100vh - 3rem);
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hover);
  padding: 1.25rem 1.25rem 1rem;
}

.modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.modal__header h2 {
  margin: 0.2rem 0 0;
  font-size: 1.15rem;
  color: var(--ink-strong);
}

.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--ink);
}

.presets {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.preset {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--bg-elev);
  color: var(--ink);
  text-align: left;
  transition:
    border-color 160ms ease,
    background 160ms ease;
}

.preset:hover {
  border-color: var(--accent);
}

.preset strong {
  font-size: 0.88rem;
}

.preset span {
  font-size: 0.72rem;
  color: var(--muted);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.form label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--muted);
}

.form input,
.form select {
  padding: 0.55rem 0.7rem;
  background: var(--bg-elev);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: 0.88rem;
  color: var(--ink);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.form input:focus,
.form select:focus {
  outline: none;
  border-color: var(--accent);
}

.form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.7rem;
}

.form__row:has(.form__engine) {
  grid-template-columns: 1.1fr 1.2fr 0.8fr;
}

.form__section {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.02);
}

.form__section-title {
  margin: 0 0 0.45rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.form__check {
  flex-direction: row !important;
  align-items: flex-start;
  gap: 0.5rem !important;
  cursor: pointer;
  font-size: 0.86rem !important;
  color: var(--ink) !important;
}

.form__check input {
  margin-top: 0.2rem;
}

.form__hint {
  margin: 0.35rem 0 0;
  font-size: 0.76rem;
  color: var(--muted);
  line-height: 1.45;
}

.form__error {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #f28b82;
}

.form__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.45rem;
}

.table-pick {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.35rem;
}

.table-pick__row {
  display: flex;
  flex-direction: row !important;
  align-items: flex-start;
  gap: 0.5rem !important;
  font-size: 0.82rem !important;
  color: var(--ink) !important;
  cursor: pointer;
}

.table-pick__row--skeleton {
  cursor: default;
  pointer-events: none;
}

.table-pick__row input {
  margin-top: 0.2rem;
}

.table-pick__row strong {
  display: block;
  font-size: 0.84rem;
}

.table-pick__row small {
  display: block;
  color: var(--muted);
  font-size: 0.72rem;
  margin-top: 0.15rem;
}

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
</style>
