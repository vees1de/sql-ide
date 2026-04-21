<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal__header">
          <span class="modal__title">Schedule dashboard</span>
          <button class="modal__close" type="button" @click="$emit('close')">✕</button>
        </div>

        <div class="modal__body">
          <div class="form-field">
            <label class="form-field__label">E-mail recipients</label>
            <textarea
              v-model="recipientsText"
              class="form-field__input form-field__input--textarea"
              rows="3"
              placeholder="anna@company.com, team@company.com"
            />
          </div>

          <div class="form-field">
            <label class="form-field__label">Days</label>
            <div class="days-grid">
              <label v-for="day in dayOptions" :key="day.value" class="days-grid__item">
                <input v-model="selectedDays" type="checkbox" :value="day.value" />
                <span>{{ day.label }}</span>
              </label>
            </div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label class="form-field__label">Time</label>
              <input v-model="sendTime" class="form-field__input" type="time" />
            </div>
            <div class="form-field">
              <label class="form-field__label">Timezone</label>
              <input v-model="timezone" class="form-field__input" type="text" />
            </div>
          </div>

          <div class="form-field">
            <label class="form-field__label">Subject</label>
            <input v-model="subject" class="form-field__input" type="text" />
          </div>

          <label class="toggle">
            <input v-model="enabled" type="checkbox" />
            <span>Enable scheduled delivery</span>
          </label>
        </div>

        <div class="modal__footer">
          <button class="btn btn--ghost" type="button" @click="$emit('delete')">Delete</button>
          <button class="btn btn--ghost" type="button" @click="$emit('close')">Cancel</button>
          <button class="btn btn--primary" type="button" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>

        <p v-if="errorMsg" class="modal__error">{{ errorMsg }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ApiDashboardScheduleRead, ApiDashboardScheduleUpsert } from '@/api/types';

const props = defineProps<{
  schedule: ApiDashboardScheduleRead | null;
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'save', payload: ApiDashboardScheduleUpsert): void;
  (event: 'delete'): void;
}>();

const dayOptions = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
];

const recipientsText = ref('');
const selectedDays = ref<string[]>([]);
const sendTime = ref('09:00');
const timezone = ref('Asia/Yakutsk');
const subject = ref('Dashboard digest');
const enabled = ref(false);
const saving = ref(false);
const errorMsg = ref<string | null>(null);

watch(
  () => props.schedule,
  () => {
    recipientsText.value = props.schedule?.recipient_emails.join(', ') ?? '';
    selectedDays.value = props.schedule?.weekdays?.length ? [...props.schedule.weekdays] : ['mon'];
    sendTime.value = props.schedule?.send_time ?? '09:00';
    timezone.value = props.schedule?.timezone ?? 'Asia/Yakutsk';
    subject.value = props.schedule?.subject ?? 'Dashboard digest';
    enabled.value = props.schedule?.enabled ?? false;
  },
  { immediate: true }
);

async function save() {
  saving.value = true;
  errorMsg.value = null;
  try {
    const emails = recipientsText.value
      .split(',')
      .map((email) => email.trim())
      .filter(Boolean);
    emit('save', {
      recipient_emails: emails,
      weekdays: selectedDays.value,
      send_time: sendTime.value || '09:00',
      timezone: timezone.value || 'Asia/Yakutsk',
      enabled: enabled.value,
      subject: subject.value || 'Dashboard digest'
    });
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Failed to save schedule.';
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  width: 520px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
}

.modal__header,
.modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px;
}

.modal__header {
  border-bottom: 1px solid var(--line);
}

.modal__footer {
  border-top: 1px solid var(--line);
  justify-content: flex-end;
}

.modal__title {
  font-weight: 600;
  color: var(--ink-strong);
}

.modal__close {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
}

.modal__body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 600;
}

.form-field__input {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  padding: 8px 10px;
}

.form-field__input--textarea {
  resize: vertical;
  min-height: 84px;
}

.days-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.days-grid__item,
.toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
  font-size: 0.82rem;
}

.toggle {
  padding: 6px 0;
}

.modal__error {
  margin: 0;
  padding: 0 16px 12px;
  color: #ff7b7b;
  font-size: 0.78rem;
}

.btn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 0.82rem;
  cursor: pointer;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
}

.btn--primary {
  background: rgba(112, 59, 247, 0.9);
  color: #fff;
  border-color: transparent;
}

.btn--ghost:hover {
  background: var(--line);
}
</style>
