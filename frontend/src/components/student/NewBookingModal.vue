<script setup lang="ts">
import { ArrowLeft, X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { computed, ref } from "vue";

import { getPublicLessonTypes } from "@/api/tutors";
import BookingWizard from "@/components/BookingWizard.vue";
import type { Booking } from "@/types/booking";
import type { LessonType } from "@/types/tutor";
import { formatDate } from "@/utils/time";

// Запись к «своему» репетитору прямо из кабинета, без поиска его заново на главной.
// Репетиторы - те, с кем у ученика уже были занятия; сверху - с кем занимался
// последним. Дальше - тот же мастер записи, что и на странице репетитора.
const props = defineProps<{ bookings: Booking[] }>();
const emit = defineEmits<{ close: []; booked: [] }>();

interface KnownTutor {
  id: string;
  name: string;
  // Последнее состоявшееся (или назначенное, если прошедших ещё нет) занятие.
  lastAt: string;
  isPast: boolean;
}

const tutors = computed<KnownTutor[]>(() => {
  const now = new Date().toISOString();
  const byTutor = new Map<string, KnownTutor>();
  // Сначала - состоявшиеся и назначенные занятия; отменённые и перенесённые
  // учитываются, только если других с этим репетитором не было, чтобы он всё равно
  // попал в список.
  const held = (b: Booking) => b.status === "scheduled" || b.status === "completed";
  const ordered = [...props.bookings].sort((a, b) => Number(held(b)) - Number(held(a)));
  for (const booking of ordered) {
    if (booking.is_manual_block) continue;
    if (byTutor.has(booking.tutor_id) && !held(booking)) continue;
    const isPast = booking.start_at <= now;
    const known = byTutor.get(booking.tutor_id);
    // Прошедшее занятие важнее будущего: «в последнее время занимались» - это про
    // то, что уже было. Среди прошедших берём самое позднее, среди будущих - ближайшее.
    const better =
      !known ||
      (isPast && !known.isPast) ||
      (isPast === known.isPast && (isPast ? booking.start_at > known.lastAt : booking.start_at < known.lastAt));
    if (better) {
      byTutor.set(booking.tutor_id, {
        id: booking.tutor_id,
        name: booking.tutor_display_name ?? known?.name ?? "Репетитор",
        lastAt: booking.start_at,
        isPast,
      });
    }
  }
  return [...byTutor.values()].sort((a, b) => {
    if (a.isPast !== b.isPast) return a.isPast ? -1 : 1;
    return a.isPast ? b.lastAt.localeCompare(a.lastAt) : a.lastAt.localeCompare(b.lastAt);
  });
});

const selected = ref<KnownTutor | null>(null);
const lessonTypes = ref<LessonType[]>([]);
const isLoading = ref(false);
const error = ref("");

async function pick(tutor: KnownTutor): Promise<void> {
  error.value = "";
  isLoading.value = true;
  try {
    lessonTypes.value = await getPublicLessonTypes(tutor.id);
    selected.value = tutor;
  } catch {
    error.value = "Не удалось загрузить занятия репетитора. Попробуйте ещё раз.";
  } finally {
    isLoading.value = false;
  }
}

function back(): void {
  selected.value = null;
  lessonTypes.value = [];
}
</script>

<template>
  <DialogRoot :open="true" @update:open="(open) => !open && emit('close')">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-fade-out data-[state=open]:animate-fade-in"
      />
      <DialogContent
        class="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-y-auto rounded-2xl bg-white shadow-xl
          data-[state=closed]:animate-pop-out data-[state=open]:animate-pop-in dark:bg-slate-900"
        :aria-describedby="undefined"
      >
        <div class="flex items-start justify-between gap-4 rounded-t-2xl bg-brand-50 px-6 pb-4 pt-5 dark:bg-brand-900/30">
          <div>
            <DialogTitle class="text-xl font-semibold">Запись на занятие</DialogTitle>
            <p v-if="selected" class="mt-0.5 text-sm text-slate-500">
              Репетитор <span class="font-medium text-slate-700 dark:text-slate-200">{{ selected.name }}</span>
            </p>
          </div>
          <DialogClose class="rounded-md p-1 text-slate-400 hover:bg-white/60 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200">
            <X class="h-5 w-5" />
          </DialogClose>
        </div>

        <div class="px-6 py-5">
          <template v-if="!selected">
            <p v-if="tutors.length === 0" class="text-base text-slate-500">
              У вас пока не было занятий. Найдите репетитора в
              <RouterLink to="/" class="text-brand-700 underline dark:text-brand-300" @click="emit('close')">каталоге</RouterLink>.
            </p>
            <template v-else>
              <p class="text-sm text-slate-500">Выберите репетитора:</p>
              <div class="mt-3 flex flex-col gap-2" data-tutor-list>
                <button
                  v-for="tutor in tutors"
                  :key="tutor.id"
                  type="button"
                  class="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3 text-left transition-colors hover:border-brand-400 hover:bg-brand-50/60 disabled:opacity-50 dark:border-slate-700 dark:hover:border-brand-500 dark:hover:bg-brand-900/20"
                  :disabled="isLoading"
                  @click="pick(tutor)"
                >
                  <span class="font-medium">{{ tutor.name }}</span>
                  <span class="text-sm text-slate-400">
                    {{ tutor.isPast ? "последнее занятие" : "ближайшее занятие" }} {{ formatDate(tutor.lastAt) }}
                  </span>
                </button>
              </div>
            </template>
            <p v-if="error" class="mt-3 text-sm text-red-600 dark:text-red-400">{{ error }}</p>
          </template>

          <template v-else>
            <button type="button" class="back-link" @click="back"><ArrowLeft class="h-4 w-4" />Другой репетитор</button>
            <BookingWizard
              :key="selected.id"
              class="mt-3"
              :tutor-id="selected.id"
              :tutor-name="selected.name"
              :lesson-types="lessonTypes"
              @booked="emit('booked')"
            />
          </template>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
