<template>
  <div v-if="open" class="semantic-modal__root" @click.self="emit('close')">
    <div class="semantic-modal">
      <header class="semantic-modal__header">
        <div>
          <p class="semantic-modal__eyebrow">Semantic activation</p>
          <h2>Активировать семантику</h2>
          <p class="semantic-modal__lead">
            Опиши базу и при необходимости подпиши таблицы, связи и колонки
            перед сборкой семантического каталога.
          </p>
        </div>
        <button class="semantic-modal__close" type="button" @click="emit('close')">
          ×
        </button>
      </header>

      <form class="semantic-modal__form" @submit.prevent="submit">
        <label class="semantic-modal__field">
          <span>Описание базы</span>
          <textarea
            v-model="state.databaseDescription"
            rows="4"
            placeholder="Что это за предметная область, какие есть ключевые сущности и правила."
          />
        </label>

        <label class="semantic-modal__field">
          <span>Таблицы</span>
          <textarea
            v-model="state.tableDescriptionsText"
            rows="7"
            placeholder="orders: Заказы клиентов\ncustomers: Клиенты и их атрибуты"
          />
          <small>Формат: `table_name: описание` по одной строке.</small>
        </label>

        <label class="semantic-modal__field">
          <span>Связи</span>
          <textarea
            v-model="state.relationshipDescriptionsText"
            rows="7"
            placeholder="orders.customer_id -> customers.id: Заказ принадлежит клиенту"
          />
          <small>
            Формат: `from_table.from_column -> to_table.to_column: описание`.
          </small>
        </label>

        <label class="semantic-modal__field">
          <span>Колонки</span>
          <textarea
            v-model="state.columnDescriptionsText"
            rows="8"
            placeholder="orders.amount: Сумма заказа\ncustomers.city: Город клиента"
          />
          <small>Формат: `table_name.column_name: описание`.</small>
        </label>

        <footer class="semantic-modal__footer">
          <button class="app-button app-button--ghost" type="button" @click="emit('close')">
            Отмена
          </button>
          <button class="app-button" type="submit" :disabled="submitting">
            {{ submitting ? "Активируем…" : "Активировать" }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from "vue";

interface Props {
  open: boolean;
  databaseName?: string;
  databaseDescription?: string;
  tableDescriptionsText?: string;
  relationshipDescriptionsText?: string;
  columnDescriptionsText?: string;
  submitting?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  databaseName: "",
  databaseDescription: "",
  tableDescriptionsText: "",
  relationshipDescriptionsText: "",
  columnDescriptionsText: "",
  submitting: false,
});

const emit = defineEmits<{
  close: [];
  submit: [payload: {
    databaseDescription: string;
    tableDescriptionsText: string;
    relationshipDescriptionsText: string;
    columnDescriptionsText: string;
  }];
}>();

const state = reactive({
  databaseDescription: "",
  tableDescriptionsText: "",
  relationshipDescriptionsText: "",
  columnDescriptionsText: "",
});

function syncFromProps() {
  state.databaseDescription = props.databaseDescription;
  state.tableDescriptionsText = props.tableDescriptionsText;
  state.relationshipDescriptionsText = props.relationshipDescriptionsText;
  state.columnDescriptionsText = props.columnDescriptionsText;
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      syncFromProps();
    }
  },
  { immediate: true },
);

watch(
  () => [props.databaseDescription, props.tableDescriptionsText, props.relationshipDescriptionsText, props.columnDescriptionsText],
  () => {
    if (props.open) {
      syncFromProps();
    }
  },
);

function submit() {
  emit("submit", {
    databaseDescription: state.databaseDescription.trim(),
    tableDescriptionsText: state.tableDescriptionsText.trim(),
    relationshipDescriptionsText: state.relationshipDescriptionsText.trim(),
    columnDescriptionsText: state.columnDescriptionsText.trim(),
  });
}
</script>

<style scoped>
.semantic-modal__root {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(9, 13, 20, 0.7);
  backdrop-filter: blur(12px);
}

.semantic-modal {
  width: min(100%, 920px);
  max-height: min(92vh, 980px);
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(47, 75, 255, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(13, 18, 28, 0.98), rgba(10, 14, 22, 0.98));
  box-shadow: 0 32px 120px rgba(0, 0, 0, 0.45);
  color: #edf2ff;
}

.semantic-modal__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 24px 12px;
}

.semantic-modal__eyebrow {
  margin: 0 0 8px;
  color: #93a4d8;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.semantic-modal__header h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
}

.semantic-modal__lead {
  margin: 10px 0 0;
  max-width: 64ch;
  color: rgba(237, 242, 255, 0.76);
}

.semantic-modal__close {
  flex: none;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}

.semantic-modal__form {
  display: grid;
  gap: 16px;
  padding: 12px 24px 24px;
}

.semantic-modal__field {
  display: grid;
  gap: 8px;
}

.semantic-modal__field > span {
  font-size: 13px;
  color: rgba(237, 242, 255, 0.86);
}

.semantic-modal__field textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  resize: vertical;
  font: inherit;
}

.semantic-modal__field textarea:focus {
  outline: none;
  border-color: rgba(120, 150, 255, 0.7);
  box-shadow: 0 0 0 4px rgba(70, 106, 255, 0.16);
}

.semantic-modal__field small {
  color: rgba(237, 242, 255, 0.62);
}

.semantic-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 4px;
}

@media (max-width: 720px) {
  .semantic-modal__root {
    padding: 12px;
  }

  .semantic-modal__header,
  .semantic-modal__form {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
