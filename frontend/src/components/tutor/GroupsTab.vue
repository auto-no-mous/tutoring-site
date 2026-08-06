<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import {
  acceptApplication,
  createGroup,
  getOccurrenceAttendance,
  listApplications,
  listMembers,
  listMyGroups,
  listOccurrences,
  rejectApplication,
  removeMember,
  replaceSchedule,
  setOccurrenceAttendance,
  updateOccurrence,
} from "@/api/groups";
import { getGroupThread, openThreadWithStudent } from "@/api/chat";
import { getMyLessonTypes } from "@/api/tutors";
import type { Group, GroupApplication, GroupAttendanceEntry, GroupMembership, GroupOccurrence } from "@/types/group";
import type { LessonType } from "@/types/tutor";
import { formatDateTimeWithMsk } from "@/utils/time";

const router = useRouter();

const ATTENDANCE_OPTIONS = [
  { value: "conducted", label: "Присутствовал" },
  { value: "student_no_show", label: "Не явился" },
];

const WEEKDAY_ABBR = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const WEEKDAY_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const isLoading = ref(true);
const groups = ref<Group[]>([]);
const groupLessonTypes = ref<LessonType[]>([]);

const membersByGroup = ref<Record<string, GroupMembership[]>>({});
const pendingApplicationsByGroup = ref<Record<string, GroupApplication[]>>({});
const occurrencesByGroup = ref<Record<string, GroupOccurrence[]>>({});

const showForm = ref(false);
const name = ref("");
const lessonTypeId = ref("");
const capacity = ref(5);
const meetingLink = ref("");
const slots = ref<{ weekday: number; start_time: string }[]>([{ weekday: 1, start_time: "18:00" }]);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    const [groupsData, lessonTypesData] = await Promise.all([listMyGroups(), getMyLessonTypes()]);
    groups.value = groupsData;
    groupLessonTypes.value = lessonTypesData.filter((t) => t.format === "group");
    // Needed up front (not lazily behind the spoiler) so the "Заявки" section only
    // renders for groups that actually have something pending.
    const perGroupApplications = await Promise.all(
      groupsData.map((g) => listApplications(g.id, "pending")),
    );
    pendingApplicationsByGroup.value = Object.fromEntries(
      groupsData.map((g, i) => [g.id, perGroupApplications[i]]),
    );
  } finally {
    isLoading.value = false;
  }
}

function addSlot(): void {
  slots.value.push({ weekday: 1, start_time: "18:00" });
}

async function create(): Promise<void> {
  await createGroup({
    name: name.value,
    lesson_type_id: lessonTypeId.value,
    capacity: capacity.value,
    meeting_link: meetingLink.value || null,
    schedule_slots: slots.value,
  });
  showForm.value = false;
  name.value = "";
  meetingLink.value = "";
  slots.value = [{ weekday: 1, start_time: "18:00" }];
  await load();
}

async function refreshGroup(groupId: string): Promise<void> {
  const [groupsData, pending] = await Promise.all([listMyGroups(), listApplications(groupId, "pending")]);
  groups.value = groupsData;
  pendingApplicationsByGroup.value = { ...pendingApplicationsByGroup.value, [groupId]: pending };
  if (membersByGroup.value[groupId]) {
    membersByGroup.value = { ...membersByGroup.value, [groupId]: await listMembers(groupId) };
  }
}

async function accept(app: GroupApplication): Promise<void> {
  await acceptApplication(app.group_id, app.id);
  await refreshGroup(app.group_id);
}

async function reject(app: GroupApplication): Promise<void> {
  await rejectApplication(app.group_id, app.id);
  await refreshGroup(app.group_id);
}

async function remove(member: GroupMembership): Promise<void> {
  if (!window.confirm(`Исключить ${member.student_display_name} из группы?`)) return;
  await removeMember(member.group_id, member.student_id);
  await refreshGroup(member.group_id);
}

async function loadMembers(groupId: string): Promise<void> {
  membersByGroup.value = { ...membersByGroup.value, [groupId]: await listMembers(groupId) };
}

function onMembersToggle(event: Event, groupId: string): void {
  if ((event.target as HTMLDetailsElement).open) loadMembers(groupId);
}

async function loadOccurrences(groupId: string): Promise<void> {
  occurrencesByGroup.value = { ...occurrencesByGroup.value, [groupId]: await listOccurrences(groupId) };
}

function onOccurrencesToggle(event: Event, groupId: string): void {
  if ((event.target as HTMLDetailsElement).open) loadOccurrences(groupId);
}

async function openStudentChat(studentId: string): Promise<void> {
  const thread = await openThreadWithStudent(studentId);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}

async function openGroupChat(group: Group): Promise<void> {
  const thread = await getGroupThread(group.id);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}

// --- Schedule (periodicity) editing ---------------------------------------------

const scheduleEditGroupId = ref<string | null>(null);
const scheduleEditSlots = ref<{ weekday: number; start_time: string }[]>([]);

function startScheduleEdit(group: Group): void {
  scheduleEditGroupId.value = group.id;
  scheduleEditSlots.value = group.schedule_slots.map((s) => ({ weekday: s.weekday, start_time: s.start_time.slice(0, 5) }));
}

function addScheduleEditSlot(): void {
  scheduleEditSlots.value.push({ weekday: 1, start_time: "18:00" });
}

function removeScheduleEditSlot(i: number): void {
  scheduleEditSlots.value.splice(i, 1);
}

async function saveSchedule(): Promise<void> {
  if (!scheduleEditGroupId.value) return;
  const updated = await replaceSchedule(scheduleEditGroupId.value, scheduleEditSlots.value);
  const idx = groups.value.findIndex((g) => g.id === updated.id);
  if (idx !== -1) groups.value[idx] = updated;
  scheduleEditGroupId.value = null;
}

// --- Occurrences / attendance ----------------------------------------------------

async function cancelOccurrence(occurrence: GroupOccurrence): Promise<void> {
  await updateOccurrence(occurrence.group_id, occurrence.id, { status: "cancelled" });
  await loadOccurrences(occurrence.group_id);
}

function isPastLiveOccurrence(occ: GroupOccurrence): boolean {
  return (occ.status === "scheduled" || occ.status === "completed") && new Date(occ.end_at) < new Date();
}

const openAttendanceOccurrenceId = ref<string | null>(null);
const attendance = ref<GroupAttendanceEntry[]>([]);
const isSavingAttendance = ref(false);
const attendanceSavedMessage = ref("");

async function toggleAttendance(occ: GroupOccurrence): Promise<void> {
  if (openAttendanceOccurrenceId.value === occ.id) {
    openAttendanceOccurrenceId.value = null;
    return;
  }
  attendanceSavedMessage.value = "";
  attendance.value = await getOccurrenceAttendance(occ.group_id, occ.id);
  openAttendanceOccurrenceId.value = occ.id;
}

async function saveAttendance(occ: GroupOccurrence): Promise<void> {
  isSavingAttendance.value = true;
  attendanceSavedMessage.value = "";
  try {
    attendance.value = await setOccurrenceAttendance(
      occ.group_id,
      occ.id,
      attendance.value.map((a) => ({ student_id: a.student_id, outcome: a.outcome })),
    );
    attendanceSavedMessage.value = "Сохранено";
  } finally {
    isSavingAttendance.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex max-w-3xl flex-col gap-6">
    <p v-if="isLoading" class="text-sm text-slate-400">Загрузка…</p>

    <div v-else-if="groupLessonTypes.length === 0" class="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
      Чтобы создавать группы, сначала добавьте тип занятия с форматом «групповое».
      <RouterLink to="/cabinet?tab=schedule" class="underline">Перейти к типам занятий</RouterLink>
    </div>

    <template v-else>
      <div class="flex justify-end">
        <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="showForm = !showForm">
          {{ showForm ? "Отмена" : "+ Новая группа" }}
        </button>
      </div>

      <form v-if="showForm" class="flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="create">
        <label class="flex flex-col gap-1 text-sm">
          Название группы
          <input v-model="name" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Тип занятия
          <select v-model="lessonTypeId" required class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700">
            <option v-for="type in groupLessonTypes" :key="type.id" :value="type.id">{{ type.name }} ({{ type.price }} ₽/место)</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Вместимость
          <input v-model.number="capacity" type="number" min="1" class="w-24 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <label class="flex flex-col gap-1 text-sm">
          Ссылка на занятие
          <input v-model="meetingLink" class="rounded-md border border-slate-300 bg-transparent px-2 py-1.5 dark:border-slate-700" />
        </label>
        <div>
          <span class="text-sm">Расписание (МСК)</span>
          <div v-for="(slot, i) in slots" :key="i" class="mt-1 flex items-center gap-2">
            <select v-model.number="slot.weekday" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700">
              <option v-for="(wd, idx) in WEEKDAY_ABBR" :key="idx" :value="idx">{{ wd }}</option>
            </select>
            <input v-model="slot.start_time" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700" />
          </div>
          <button type="button" class="mt-1 text-xs text-slate-500 underline" @click="addSlot">+ день</button>
        </div>
        <button type="submit" class="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-slate-900">Создать группу</button>
      </form>

      <p v-if="groups.length === 0" class="text-sm text-slate-400">У вас пока нет групп.</p>

      <div v-for="group in groups" :key="group.id" class="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-lg font-medium">{{ group.name }}</h3>
          <span class="shrink-0 text-sm text-slate-500">{{ group.member_count }}/{{ group.capacity }}</span>
        </div>

        <div class="mt-2 text-sm text-slate-600 dark:text-slate-300">
          <div v-for="slot in group.schedule_slots" :key="slot.id">
            {{ WEEKDAY_FULL[slot.weekday] }} {{ slot.start_time.slice(0, 5) }}, {{ group.duration_minutes }} мин
          </div>
          <button type="button" class="mt-0.5 text-xs text-slate-500 underline" @click="startScheduleEdit(group)">
            Изменить периодичность
          </button>
        </div>

        <div v-if="scheduleEditGroupId === group.id" class="mt-2 rounded-md border border-slate-200 p-3 dark:border-slate-800">
          <div v-for="(slot, i) in scheduleEditSlots" :key="i" class="mt-1 flex items-center gap-2">
            <select v-model.number="slot.weekday" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700">
              <option v-for="(wd, idx) in WEEKDAY_ABBR" :key="idx" :value="idx">{{ wd }}</option>
            </select>
            <input v-model="slot.start_time" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700" />
            <button type="button" class="text-xs text-red-600 underline dark:text-red-400" @click="removeScheduleEditSlot(i)">✕</button>
          </div>
          <div class="mt-2 flex items-center gap-3">
            <button type="button" class="text-xs text-slate-500 underline" @click="addScheduleEditSlot">+ день</button>
            <button type="button" class="rounded-md bg-slate-900 px-3 py-1 text-xs text-white dark:bg-white dark:text-slate-900" @click="saveSchedule">
              Сохранить
            </button>
            <button type="button" class="text-xs text-slate-500 underline" @click="scheduleEditGroupId = null">Отмена</button>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-3 text-sm">
          <a v-if="group.meeting_link" :href="group.meeting_link" target="_blank" class="underline">Ссылка на занятие</a>
          <button type="button" class="underline" @click="openGroupChat(group)">Чат группы</button>
        </div>

        <details class="mt-3" @toggle="onMembersToggle($event, group.id)">
          <summary class="cursor-pointer text-sm text-slate-500">Участники ({{ group.member_count }})</summary>
          <div class="mt-2 flex flex-col gap-2">
            <p v-if="(membersByGroup[group.id] ?? []).length === 0" class="text-xs text-slate-400">Пока никого нет.</p>
            <div
              v-for="member in membersByGroup[group.id] ?? []"
              :key="member.id"
              class="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
            >
              <RouterLink :to="`/students/${member.student_id}`" class="hover:underline">{{ member.student_display_name }}</RouterLink>
              <div class="flex gap-2">
                <button type="button" class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700" @click="openStudentChat(member.student_id)">
                  Написать
                </button>
                <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(member)">
                  Исключить
                </button>
              </div>
            </div>
          </div>
        </details>

        <details v-if="(pendingApplicationsByGroup[group.id] ?? []).length > 0" class="mt-3">
          <summary class="cursor-pointer text-sm text-slate-500">
            Заявки ({{ pendingApplicationsByGroup[group.id].length }})
          </summary>
          <div class="mt-2 flex flex-col gap-2">
            <div
              v-for="app in pendingApplicationsByGroup[group.id]"
              :key="app.id"
              class="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
            >
              <span>{{ app.student_display_name }}</span>
              <div class="flex gap-2">
                <button type="button" class="rounded-md border border-green-300 px-2 py-1 text-xs text-green-700 dark:border-green-800" @click="accept(app)">Принять</button>
                <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="reject(app)">Отклонить</button>
              </div>
            </div>
          </div>
        </details>

        <details class="mt-3" @toggle="onOccurrencesToggle($event, group.id)">
          <summary class="cursor-pointer text-sm text-slate-500">Занятия группы</summary>
          <div v-for="occ in (occurrencesByGroup[group.id] ?? []).slice(0, 12)" :key="occ.id" class="mt-2 rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <div class="flex items-center justify-between">
              <span :class="occ.status === 'cancelled' ? 'text-slate-400 line-through' : ''">{{ formatDateTimeWithMsk(occ.start_at) }}</span>
              <div class="flex gap-2">
                <button
                  v-if="isPastLiveOccurrence(occ)"
                  type="button"
                  class="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700"
                  @click="toggleAttendance(occ)"
                >
                  {{ openAttendanceOccurrenceId === occ.id ? "Скрыть" : "Посещаемость" }}
                </button>
                <button v-if="occ.status === 'scheduled'" type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="cancelOccurrence(occ)">
                  Отменить
                </button>
              </div>
            </div>
            <div v-if="openAttendanceOccurrenceId === occ.id" class="mt-2 flex flex-col gap-2 border-t border-slate-200 pt-2 dark:border-slate-800">
              <p v-if="attendance.length === 0" class="text-xs text-slate-400">На тот момент в группе никого не было.</p>
              <div v-for="entry in attendance" :key="entry.student_id" class="flex items-center justify-between text-xs">
                <span>{{ entry.student_display_name }}</span>
                <select v-model="entry.outcome" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700">
                  <option v-for="opt in ATTENDANCE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <div v-if="attendance.length > 0" class="flex items-center gap-3">
                <button
                  type="button"
                  :disabled="isSavingAttendance"
                  class="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-xs text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"
                  @click="saveAttendance(occ)"
                >
                  Сохранить
                </button>
                <span v-if="attendanceSavedMessage" class="text-xs text-green-600 dark:text-green-400">{{ attendanceSavedMessage }}</span>
              </div>
            </div>
          </div>
        </details>
      </div>
    </template>
  </div>
</template>
