<script setup lang="ts">
import { Ban, BookOpen, CalendarClock, Link2, Repeat, StickyNote, Timer, Trash2, Video, X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { computed, ref, toRef } from "vue";

import MeetingLinkModal from "@/components/MeetingLinkModal.vue";
import StudentHomeworkModal from "@/components/StudentHomeworkModal.vue";
import WhiteboardLinks from "@/components/WhiteboardLinks.vue";
import WhiteboardsModal from "@/components/WhiteboardsModal.vue";
import type { Whiteboard } from "@/api/whiteboards";
import { bookingDurationMinutes, useBookingActions } from "@/composables/useBookingActions";
import type { Booking } from "@/types/booking";
import { formatLongDate, formatTime } from "@/utils/time";

// Окно занятия из недельного вида: всё, что умеет карточка в списке (BookingCard),
// только крупнее - в ячейке недельной сетки места хватает лишь на время и имя.
const props = defineProps<{
  booking: Booking;
  studentName: string;
  studentGrade: number | null;
  // Общий статус ДЗ ученика у этого репетитора (не по занятию): есть ли невыполненное.
  homeworkStatus: "none" | "pending" | "done";
  whiteboards: Whiteboard[];
}>();
const emit = defineEmits<{ close: []; changed: []; "reschedule-requested": [Booking]; "boards-changed": [] }>();

const { isBusy, cancel, removeBlock, saveMeetingLink, saveDuration } = useBookingActions(
  toRef(props, "booking"),
  () => emit("changed"),
);

const showHomeworkModal = ref(false);
const showMeetingLinkModal = ref(false);
const showWhiteboardsModal = ref(false);
const isEditingDuration = ref(false);
const durationMinutes = ref(bookingDurationMinutes(props.booking));

const hasStudent = computed(() => !!props.booking.student_id && !props.booking.is_manual_block);
const isOver = computed(() => new Date(props.booking.end_at) < new Date());
const isNow = computed(() => {
  const now = Date.now();
  return now >= new Date(props.booking.start_at).getTime() && !isOver.value;
});

const FORMAT_LABELS: Record<string, string> = { individual: "Индивидуальное", group: "Групповое" };

const HOMEWORK: Record<string, { label: string; style: string }> = {
  none: { label: "заданий нет", style: "border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300" },
  pending: {
    label: "есть невыполненное",
    style: "border-amber-400 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
  done: {
    label: "всё выполнено",
    style: "border-green-400 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-950 dark:text-green-300",
  },
};

async function onSaveLink(link: string, applyToStudent: boolean): Promise<void> {
  showMeetingLinkModal.value = false;
  await saveMeetingLink(link, applyToStudent);
}

// Кнопки управления: одинаковая рамка, подпись прячется на узком блоке (см. шаблон).
// Порог - по замеру: ряд из четырёх кнопок с подписями шрифтом сайта занимает
// ~42.5rem, 44rem - с запасом. Порог в rem, как и текст, поэтому при любом масштабе
// и размере шрифта в браузере они меняются вместе. Окно шириной max-w-3xl даёт ряду
// 45rem - на обычном экране подписи видны.
const ACTION =
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-50 dark:border-slate-700";
const DANGER = "border-red-300 text-red-600 dark:border-red-800";
const LABEL = "hidden @min-[44rem]:inline";

function toggleDurationEditor(): void {
  durationMinutes.value = bookingDurationMinutes(props.booking);
  isEditingDuration.value = !isEditingDuration.value;
}

async function onSaveDuration(): Promise<void> {
  if (await saveDuration(durationMinutes.value)) isEditingDuration.value = false;
}

// Отменённое или удалённое занятие из недели пропадает - окно о нём закрываем.
async function onCancel(): Promise<void> {
  if (await cancel()) emit("close");
}

async function onRemove(): Promise<void> {
  if (await removeBlock()) emit("close");
}
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-y-auto rounded-2xl bg-white shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="rounded-t-2xl bg-brand-50 px-6 pb-4 pt-5 dark:bg-brand-900/30">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-sm font-medium text-brand-700 dark:text-brand-300">{{ formatLongDate(booking.start_at) }}</div>
              <DialogTitle class="mt-0.5 text-3xl font-semibold tabular-nums">
                {{ formatTime(booking.start_at) }}–{{ formatTime(booking.end_at) }}
                <span class="text-base font-normal text-slate-500">МСК</span>
              </DialogTitle>
            </div>
            <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-white/60 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
              <X class="h-5 w-5" />
            </DialogClose>
          </div>
          <div class="mt-3 flex flex-wrap gap-1.5 text-xs">
            <span v-if="isNow" class="rounded-full bg-brand-500 px-2 py-0.5 font-medium text-white">Идёт сейчас</span>
            <span v-else-if="isOver" class="rounded-full bg-slate-200 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">Прошло</span>
            <span v-if="booking.recurring_series_id" class="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              <Repeat class="h-3 w-3" />еженедельно
            </span>
            <span v-if="!booking.is_manual_block" class="rounded-full bg-white px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {{ booking.lesson_type_name ?? "Занятие" }} · {{ bookingDurationMinutes(booking) }} мин<template v-if="booking.lesson_type_format">
                · {{ FORMAT_LABELS[booking.lesson_type_format] }}</template>
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-5 px-6 py-5">
          <div>
            <div class="text-xl font-semibold">{{ booking.is_manual_block ? "Личная блокировка" : studentName }}</div>
            <div v-if="hasStudent && studentGrade" class="text-sm text-slate-500">{{ studentGrade }}-й класс</div>
            <div v-if="booking.notes" class="mt-2 flex items-start gap-1.5 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
              <StickyNote class="mt-0.5 h-4 w-4 shrink-0" />{{ booking.notes }}
            </div>
          </div>

          <div v-if="!booking.is_manual_block" class="flex flex-col gap-3">
            <a
              v-if="booking.meeting_link"
              :href="booking.meeting_link"
              target="_blank"
              class="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 font-medium text-white transition-colors hover:bg-brand-600"
            >
              <Video class="h-5 w-5" />Перейти на занятие
            </a>
            <button
              v-else
              type="button"
              class="inline-flex items-center justify-center gap-2 rounded-lg border border-dashed border-brand-400 px-4 py-2.5 font-medium text-brand-700 transition-colors hover:bg-brand-50 dark:text-brand-300 dark:hover:bg-brand-900/30"
              :disabled="isBusy"
              @click="showMeetingLinkModal = true"
            >
              <Video class="h-5 w-5" />Указать ссылку на занятие
            </button>

            <div v-if="hasStudent" class="grid gap-3 sm:grid-cols-2">
              <div class="flex flex-col gap-1.5 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <span class="text-xs font-medium uppercase tracking-wide text-slate-400">Доска</span>
                <WhiteboardLinks :boards="whiteboards" can-manage @manage="showWhiteboardsModal = true" />
              </div>
              <button
                type="button"
                class="flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors hover:brightness-95"
                :class="HOMEWORK[homeworkStatus].style"
                @click="showHomeworkModal = true"
              >
                <span class="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wide opacity-70">
                  <BookOpen class="h-3.5 w-3.5" />Домашнее задание
                </span>
                <span class="font-medium">{{ HOMEWORK[homeworkStatus].label }}</span>
              </button>
            </div>
          </div>

          <div class="border-t border-slate-200 pt-4 dark:border-slate-800">
            <div class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">Управление</div>
            <p v-if="isOver && !booking.is_manual_block" class="text-sm text-slate-500">
              Занятие уже прошло. Отметить, как оно прошло, можно в «Истории занятий».
            </p>
            <!-- Кнопки всегда в один ряд. Хватает ширины окна - с подписями, не хватает
                 (узкий экран, крупный масштаб) - только иконки с подсказкой. Решает
                 container query по ширине самого блока, а не экрана: окно ограничено
                 по ширине, и экран тут ничего не говорит. -->
            <div v-else class="@container">
              <div class="flex flex-nowrap items-center gap-2 text-sm">
                <button
                  v-if="booking.is_manual_block"
                  type="button"
                  :class="[ACTION, DANGER]"
                  title="Удалить"
                  aria-label="Удалить"
                  :disabled="isBusy"
                  @click="onRemove"
                >
                  <Trash2 class="h-4 w-4 shrink-0" /><span :class="LABEL">Удалить</span>
                </button>
                <template v-else>
                  <button
                    type="button"
                    :class="ACTION"
                    title="Перенести"
                    aria-label="Перенести"
                    :disabled="isBusy"
                    @click="emit('reschedule-requested', booking)"
                  >
                    <CalendarClock class="h-4 w-4 shrink-0" /><span :class="LABEL">Перенести</span>
                  </button>
                  <button
                    v-if="booking.meeting_link"
                    type="button"
                    :class="ACTION"
                    title="Изменить ссылку"
                    aria-label="Изменить ссылку"
                    :disabled="isBusy"
                    @click="showMeetingLinkModal = true"
                  >
                    <Link2 class="h-4 w-4 shrink-0" /><span :class="LABEL">Изменить ссылку</span>
                  </button>
                  <button
                    type="button"
                    :class="[ACTION, isEditingDuration ? 'border-brand-400 text-brand-700 dark:text-brand-300' : '']"
                    title="Изменить длительность"
                    aria-label="Изменить длительность"
                    :aria-pressed="isEditingDuration"
                    @click="toggleDurationEditor"
                  >
                    <Timer class="h-4 w-4 shrink-0" /><span :class="LABEL">Изменить длительность</span>
                  </button>
                  <button
                    type="button"
                    :class="[ACTION, DANGER, 'ml-auto']"
                    title="Отменить занятие"
                    aria-label="Отменить занятие"
                    :disabled="isBusy"
                    @click="onCancel"
                  >
                    <Ban class="h-4 w-4 shrink-0" /><span :class="LABEL">Отменить занятие</span>
                  </button>
                </template>
              </div>
              <!-- Поле длительности - отдельной строкой, чтобы не раздвигать ряд кнопок. -->
              <div v-if="isEditingDuration && !booking.is_manual_block" class="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span class="text-slate-500">Длительность</span>
                <input
                  v-model.number="durationMinutes"
                  type="number"
                  min="1"
                  aria-label="Длительность, минут"
                  class="w-20 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
                />
                <span class="text-slate-500">мин</span>
                <button
                  type="button"
                  class="rounded-md bg-brand-500 px-3 py-1.5 text-white disabled:opacity-50"
                  :disabled="isBusy"
                  @click="onSaveDuration"
                >
                  Сохранить
                </button>
                <button type="button" class="text-slate-500 underline" @click="isEditingDuration = false">Отмена</button>
              </div>
            </div>
          </div>
        </div>

        <StudentHomeworkModal
          v-if="showHomeworkModal && booking.student_id"
          :student-id="booking.student_id"
          :student-name="studentName"
          @close="showHomeworkModal = false"
          @changed="emit('changed')"
        />
        <WhiteboardsModal
          v-if="showWhiteboardsModal && booking.student_id"
          :boards="whiteboards"
          :student-id="booking.student_id"
          :owner-name="studentName"
          @changed="emit('boards-changed')"
          @close="showWhiteboardsModal = false"
        />
        <MeetingLinkModal
          v-if="showMeetingLinkModal"
          :booking="booking"
          @close="showMeetingLinkModal = false"
          @save="onSaveLink"
        />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
