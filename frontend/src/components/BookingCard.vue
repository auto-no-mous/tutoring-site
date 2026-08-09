<script setup lang="ts">
import { computed, ref } from "vue";

import { cancelBooking, deleteBooking, updateBooking } from "@/api/bookings";
import MeetingLinkModal from "@/components/MeetingLinkModal.vue";
import StudentHomeworkModal from "@/components/StudentHomeworkModal.vue";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";
import { formatDateTimeWithMsk } from "@/utils/time";

const props = defineProps<{ booking: Booking; role: "tutor" | "student"; homeworkStatus?: "none" | "pending" | "done" }>();
const emit = defineEmits<{ changed: []; "reschedule-requested": [Booking] }>();

const toast = useToastStore();

const showActions = ref(false);
const isEditingDuration = ref(false);
const showHomeworkModal = ref(false);
const showMeetingLinkModal = ref(false);
const durationMinutes = ref(
  Math.round((new Date(props.booking.end_at).getTime() - new Date(props.booking.start_at).getTime()) / 60000),
);
const isBusy = ref(false);

const isManualBlock = computed(() => props.role === "tutor" && props.booking.is_manual_block);

const FORMAT_LABELS: Record<string, string> = { individual: "Индивидуальное", group: "Групповое" };
const formatLabel = computed(() => (props.booking.lesson_type_format ? FORMAT_LABELS[props.booking.lesson_type_format] : null));
const displayDurationMinutes = computed(() =>
  Math.round((new Date(props.booking.end_at).getTime() - new Date(props.booking.start_at).getTime()) / 60000),
);

const HOMEWORK_BUTTON_STYLE: Record<string, string> = {
  none: "border-slate-300 text-slate-500 dark:border-slate-700",
  pending: "border-amber-400 bg-amber-100 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-400",
  done: "border-green-400 bg-green-100 text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-400",
};

function onHomeworkChanged(): void {
  emit("changed");
}

async function saveMeetingLink(link: string, applyToStudent: boolean): Promise<void> {
  showMeetingLinkModal.value = false;
  isBusy.value = true;
  try {
    await updateBooking(props.booking.id, { meeting_link: link, apply_link_to_student: applyToStudent });
    emit("changed");
  } finally {
    isBusy.value = false;
  }
}

async function cancel(): Promise<void> {
  if (!window.confirm("Отменить это занятие?")) return;
  isBusy.value = true;
  try {
    await cancelBooking(props.booking.id);
    toast.show("Занятие отменено");
    emit("changed");
  } catch {
    toast.show("Не удалось отменить занятие");
  } finally {
    isBusy.value = false;
  }
}

async function removeBlock(): Promise<void> {
  if (!window.confirm("Удалить эту запись?")) return;
  isBusy.value = true;
  try {
    await deleteBooking(props.booking.id);
    emit("changed");
  } finally {
    isBusy.value = false;
  }
}

function openReschedule(): void {
  emit("reschedule-requested", props.booking);
}

function startEditDuration(): void {
  durationMinutes.value = Math.round(
    (new Date(props.booking.end_at).getTime() - new Date(props.booking.start_at).getTime()) / 60000,
  );
  isEditingDuration.value = true;
}

async function saveDuration(): Promise<void> {
  const newEnd = new Date(new Date(props.booking.start_at).getTime() + durationMinutes.value * 60000);
  isBusy.value = true;
  try {
    await updateBooking(props.booking.id, { end_at: newEnd.toISOString() });
    isEditingDuration.value = false;
    emit("changed");
  } finally {
    isBusy.value = false;
  }
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between">
      <div>
        <div class="font-medium">{{ formatDateTimeWithMsk(booking.start_at) }}</div>
        <div v-if="role === 'tutor'" class="text-sm text-slate-500">
          {{ booking.student_display_name ?? (booking.is_manual_block ? "Личная блокировка" : "—") }}
          <span v-if="booking.recurring_series_id"> · еженедельно</span>
        </div>
        <div v-else class="text-sm text-slate-500">
          {{ booking.lesson_type_name }} · Репетитор {{ booking.tutor_display_name }}
          <span v-if="booking.recurring_series_id"> · еженедельно</span>
        </div>
        <div v-if="!booking.is_manual_block" class="text-xs text-slate-400">
          <template v-if="role === 'tutor'">{{ booking.lesson_type_name ?? "Занятие" }} · </template>{{ displayDurationMinutes }} мин<template v-if="formatLabel"> · {{ formatLabel }}</template>
        </div>
        <div v-if="booking.notes" class="mt-1 text-xs text-slate-500">📝 {{ booking.notes }}</div>
      </div>
      <div class="flex items-center gap-2">
        <a v-if="booking.meeting_link" :href="booking.meeting_link" target="_blank" class="text-xs underline">
          Перейти на занятие
        </a>
        <button
          v-if="role === 'tutor' && booking.meeting_link"
          type="button"
          class="text-xs text-slate-400 underline"
          :disabled="isBusy"
          @click="showMeetingLinkModal = true"
        >
          Изменить
        </button>
        <button
          v-else-if="role === 'tutor'"
          type="button"
          class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
          :disabled="isBusy"
          @click="showMeetingLinkModal = true"
        >
          Указать ссылку
        </button>
        <button
          v-if="role === 'tutor' && booking.student_id"
          type="button"
          class="rounded-md border px-2 py-1 text-xs"
          :class="HOMEWORK_BUTTON_STYLE[homeworkStatus ?? 'none']"
          @click="showHomeworkModal = true"
        >
          ДЗ
        </button>
      </div>
    </div>

    <button type="button" class="mt-2 text-xs text-slate-500 underline" @click="showActions = !showActions">
      {{ showActions ? "Скрыть управление" : "Управление занятием" }}
    </button>

    <div v-if="showActions" class="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-2 dark:border-slate-800">
      <template v-if="isManualBlock">
        <button
          type="button"
          class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 disabled:opacity-50 dark:border-red-800"
          :disabled="isBusy"
          @click="removeBlock"
        >
          Удалить
        </button>
      </template>
      <template v-else>
        <button
          type="button"
          class="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-50 dark:border-slate-700"
          :disabled="isBusy"
          @click="openReschedule"
        >
          Перенести
        </button>
        <button
          type="button"
          class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 disabled:opacity-50 dark:border-red-800"
          :disabled="isBusy"
          @click="cancel"
        >
          Отменить
        </button>
        <template v-if="role === 'tutor'">
          <button
            v-if="!isEditingDuration"
            type="button"
            class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
            @click="startEditDuration"
          >
            Изменить длительность
          </button>
          <div v-else class="flex items-center gap-2">
            <input
              v-model.number="durationMinutes"
              type="number"
              min="1"
              class="w-20 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xs dark:border-slate-700"
            />
            <span class="text-xs text-slate-500">мин</span>
            <button
              type="button"
              class="rounded-md bg-slate-900 px-2 py-1 text-xs text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
              :disabled="isBusy"
              @click="saveDuration"
            >
              Сохранить
            </button>
            <button type="button" class="text-xs text-slate-500 underline" @click="isEditingDuration = false">
              Отмена
            </button>
          </div>
        </template>
      </template>
    </div>

    <StudentHomeworkModal
      v-if="showHomeworkModal && booking.student_id"
      :student-id="booking.student_id"
      :student-name="booking.student_display_name ?? '—'"
      @close="showHomeworkModal = false"
      @changed="onHomeworkChanged"
    />

    <MeetingLinkModal
      v-if="showMeetingLinkModal"
      :booking="booking"
      @close="showMeetingLinkModal = false"
      @save="saveMeetingLink"
    />
  </div>
</template>
