<script setup lang="ts">
import { Ban, CalendarClock, Users, Video, X } from "lucide-vue-next";
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { listMembers, updateOccurrence } from "@/api/groups";
import type { Whiteboard } from "@/api/whiteboards";
import WhiteboardLinks from "@/components/WhiteboardLinks.vue";
import WhiteboardsModal from "@/components/WhiteboardsModal.vue";
import { useToastStore } from "@/stores/toast";
import type { GroupMembership, TutorGroupOccurrence } from "@/types/group";
import { apiErrorMessage } from "@/utils/apiError";
import { dateInTimeZone } from "@/utils/scheduleGrouping";
import { formatLongDate, formatTime, MSK_TIMEZONE, mskDateTimeToUtcIso } from "@/utils/time";

// Окно занятия группы из недельного вида - устроено как окно индивидуального
// занятия (BookingDetailsModal): та же шапка с датой и временем, крупное «Перейти на
// занятие», доска, управление внизу. Вместо ученика и его ДЗ - состав группы.
// Посещаемость и расписание группы остаются во вкладке «Группы».
const props = defineProps<{ occurrence: TutorGroupOccurrence; whiteboards: Whiteboard[] }>();
const emit = defineEmits<{ close: []; changed: []; "boards-changed": [] }>();

const router = useRouter();
const toast = useToastStore();

const members = ref<GroupMembership[]>([]);
const isBusy = ref(false);
const showWhiteboardsModal = ref(false);
const isRescheduling = ref(false);
const newDate = ref("");
const newTime = ref("");

const durationMinutes = computed(() =>
  Math.round((new Date(props.occurrence.end_at).getTime() - new Date(props.occurrence.start_at).getTime()) / 60000),
);
const isOver = computed(() => new Date(props.occurrence.end_at) < new Date());
const isNow = computed(() => Date.now() >= new Date(props.occurrence.start_at).getTime() && !isOver.value);

onMounted(async () => {
  try {
    members.value = await listMembers(props.occurrence.group_id);
  } catch {
    // Без состава окно всё равно полезно: число участников пришло с занятием.
  }
});

const ACTION =
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-50 dark:border-slate-700";
const DANGER = "border-red-300 text-red-600 dark:border-red-800";
const LABEL = "hidden @min-[30rem]:inline";

function toggleReschedule(): void {
  newDate.value = dateInTimeZone(new Date(props.occurrence.start_at), MSK_TIMEZONE);
  newTime.value = formatTime(props.occurrence.start_at);
  isRescheduling.value = !isRescheduling.value;
}

// Перенос одного занятия: участники получают уведомление (group_service.update_occurrence).
async function saveReschedule(): Promise<void> {
  if (!newDate.value || !newTime.value) return;
  const start = new Date(mskDateTimeToUtcIso(newDate.value, newTime.value));
  const end = new Date(start.getTime() + durationMinutes.value * 60000);
  isBusy.value = true;
  try {
    await updateOccurrence(props.occurrence.group_id, props.occurrence.id, {
      start_at: start.toISOString(),
      end_at: end.toISOString(),
    });
    toast.show("Занятие группы перенесено");
    isRescheduling.value = false;
    emit("changed");
  } catch (err) {
    toast.show(apiErrorMessage(err, "Не удалось перенести занятие"));
  } finally {
    isBusy.value = false;
  }
}

async function cancel(): Promise<void> {
  if (!window.confirm(`Отменить занятие группы «${props.occurrence.group_name}»?`)) return;
  isBusy.value = true;
  try {
    await updateOccurrence(props.occurrence.group_id, props.occurrence.id, { status: "cancelled" });
    toast.show("Занятие группы отменено");
    emit("changed");
    emit("close");
  } catch (err) {
    toast.show(apiErrorMessage(err, "Не удалось отменить занятие"));
  } finally {
    isBusy.value = false;
  }
}

function openGroups(): void {
  emit("close");
  router.push({ path: "/cabinet", query: { tab: "groups" } });
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
        <div class="rounded-t-2xl bg-sky-50 px-6 pb-4 pt-5 dark:bg-sky-950/40">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-sm font-medium text-sky-700 dark:text-sky-300">{{ formatLongDate(occurrence.start_at) }}</div>
              <DialogTitle class="mt-0.5 text-3xl font-semibold tabular-nums">
                {{ formatTime(occurrence.start_at) }}–{{ formatTime(occurrence.end_at) }}
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
            <span v-if="occurrence.original_start_at" class="rounded-full bg-white px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              перенесено
            </span>
            <span class="rounded-full bg-white px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              Групповое · {{ durationMinutes }} мин
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-5 px-6 py-5">
          <div>
            <div class="text-xl font-semibold">Группа «{{ occurrence.group_name }}»</div>
            <div class="text-sm text-slate-500">Участников: {{ occurrence.member_count }}</div>
          </div>

          <div class="flex flex-col gap-3">
            <a
              v-if="occurrence.meeting_link"
              :href="occurrence.meeting_link"
              target="_blank"
              class="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 font-medium text-white transition-colors hover:bg-brand-600"
            >
              <Video class="h-5 w-5" />Перейти на занятие
            </a>
            <button
              v-else
              type="button"
              class="inline-flex items-center justify-center gap-2 rounded-lg border border-dashed border-brand-400 px-4 py-2.5 font-medium text-brand-700 transition-colors hover:bg-brand-50 dark:text-brand-300 dark:hover:bg-brand-900/30"
              @click="openGroups"
            >
              <Video class="h-5 w-5" />Указать ссылку в настройках группы
            </button>

            <div class="grid gap-3 sm:grid-cols-2">
              <div class="flex flex-col gap-1.5 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <span class="text-xs font-medium uppercase tracking-wide text-slate-400">Доска</span>
                <WhiteboardLinks :boards="whiteboards" can-manage @manage="showWhiteboardsModal = true" />
              </div>
              <div class="flex flex-col gap-1.5 rounded-lg border border-slate-200 p-3 dark:border-slate-800" data-members>
                <span class="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                  <Users class="h-3.5 w-3.5" />Участники
                </span>
                <p v-if="members.length === 0" class="text-sm text-slate-400">Пока никого</p>
                <ul v-else class="flex flex-col gap-0.5 text-sm">
                  <li v-for="member in members" :key="member.id">{{ member.student_display_name }}</li>
                </ul>
              </div>
            </div>
          </div>

          <div class="border-t border-slate-200 pt-4 dark:border-slate-800">
            <div class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">Управление</div>
            <p v-if="isOver" class="text-sm text-slate-500">
              Занятие уже прошло. Посещаемость отмечается во вкладке
              «<button type="button" class="text-brand-700 underline hover:text-brand-800 dark:text-brand-300" @click="openGroups">Группы</button>».
            </p>
            <div v-else class="@container">
              <div class="flex flex-nowrap items-center gap-2 text-sm">
                <button
                  type="button"
                  :class="[ACTION, isRescheduling ? 'border-brand-400 text-brand-700 dark:text-brand-300' : '']"
                  title="Перенести"
                  aria-label="Перенести"
                  :aria-pressed="isRescheduling"
                  :disabled="isBusy"
                  @click="toggleReschedule"
                >
                  <CalendarClock class="h-4 w-4 shrink-0" /><span :class="LABEL">Перенести</span>
                </button>
                <button type="button" :class="ACTION" title="Открыть группы" aria-label="Открыть группы" @click="openGroups">
                  <Users class="h-4 w-4 shrink-0" /><span :class="LABEL">Открыть группы</span>
                </button>
                <button
                  type="button"
                  :class="[ACTION, DANGER, 'ml-auto']"
                  title="Отменить занятие"
                  aria-label="Отменить занятие"
                  :disabled="isBusy"
                  @click="cancel"
                >
                  <Ban class="h-4 w-4 shrink-0" /><span :class="LABEL">Отменить занятие</span>
                </button>
              </div>
              <!-- Новые дата и время - отдельной строкой, как поле длительности в окне
                   индивидуального занятия. -->
              <div v-if="isRescheduling" class="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span class="text-slate-500">Перенести на</span>
                <input
                  v-model="newDate"
                  type="date"
                  aria-label="Новая дата"
                  class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
                />
                <input
                  v-model="newTime"
                  type="time"
                  aria-label="Новое время, МСК"
                  class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700"
                />
                <span class="text-slate-500">МСК</span>
                <button
                  type="button"
                  class="rounded-md bg-brand-500 px-3 py-1.5 text-white disabled:opacity-50"
                  :disabled="isBusy || !newDate || !newTime"
                  @click="saveReschedule"
                >
                  Сохранить
                </button>
                <button type="button" class="text-slate-500 underline" @click="isRescheduling = false">Отмена</button>
              </div>
            </div>
          </div>
        </div>

        <WhiteboardsModal
          v-if="showWhiteboardsModal"
          :boards="whiteboards"
          :group-id="occurrence.group_id"
          :owner-name="occurrence.group_name"
          @changed="emit('boards-changed')"
          @close="showWhiteboardsModal = false"
        />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
