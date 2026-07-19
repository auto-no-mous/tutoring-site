<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  acceptApplication,
  createGroup,
  listApplications,
  listMembers,
  listMyGroups,
  listOccurrences,
  rejectApplication,
  removeMember,
  updateOccurrence,
} from "@/api/groups";
import { getMyLessonTypes } from "@/api/tutors";
import type { GroupApplication, GroupMembership, GroupOccurrence } from "@/types/group";
import type { Group } from "@/types/group";
import type { LessonType } from "@/types/tutor";
import { formatDateTimeWithMsk } from "@/utils/time";

const groups = ref<Group[]>([]);
const groupLessonTypes = ref<LessonType[]>([]);
const selectedGroupId = ref<string | null>(null);
const applications = ref<GroupApplication[]>([]);
const members = ref<GroupMembership[]>([]);
const occurrences = ref<GroupOccurrence[]>([]);

const showForm = ref(false);
const name = ref("");
const lessonTypeId = ref("");
const capacity = ref(5);
const meetingLink = ref("");
const slots = ref<{ weekday: number; start_time: string }[]>([{ weekday: 1, start_time: "18:00" }]);

const weekdayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const selectedGroup = computed(() => groups.value.find((g) => g.id === selectedGroupId.value) ?? null);

async function load(): Promise<void> {
  const [groupsData, lessonTypesData] = await Promise.all([listMyGroups(), getMyLessonTypes()]);
  groups.value = groupsData;
  groupLessonTypes.value = lessonTypesData.filter((t) => t.format === "group");
  if (groups.value.length > 0 && !selectedGroupId.value) {
    await selectGroup(groups.value[0].id);
  }
}

async function selectGroup(id: string): Promise<void> {
  selectedGroupId.value = id;
  [applications.value, members.value, occurrences.value] = await Promise.all([
    listApplications(id),
    listMembers(id),
    listOccurrences(id),
  ]);
}

function addSlot(): void {
  slots.value.push({ weekday: 1, start_time: "18:00" });
}

async function create(): Promise<void> {
  const group = await createGroup({
    name: name.value,
    lesson_type_id: lessonTypeId.value,
    capacity: capacity.value,
    meeting_link: meetingLink.value || null,
    schedule_slots: slots.value,
  });
  showForm.value = false;
  name.value = "";
  await load();
  await selectGroup(group.id);
}

async function accept(app: GroupApplication): Promise<void> {
  await acceptApplication(app.group_id, app.id);
  await selectGroup(app.group_id);
}

async function reject(app: GroupApplication): Promise<void> {
  await rejectApplication(app.group_id, app.id);
  await selectGroup(app.group_id);
}

async function remove(member: GroupMembership): Promise<void> {
  await removeMember(member.group_id, member.student_id);
  await selectGroup(member.group_id);
}

async function cancelOccurrence(occurrence: GroupOccurrence): Promise<void> {
  await updateOccurrence(occurrence.group_id, occurrence.id, { status: "cancelled" });
  await selectGroup(occurrence.group_id);
}

const pendingApplications = computed(() => applications.value.filter((a) => a.status === "pending"));

onMounted(load);
</script>

<template>
  <div class="flex max-w-3xl flex-col gap-6">
    <div>
      <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="showForm = !showForm">
        {{ showForm ? "Отмена" : "+ Новая группа" }}
      </button>

      <form v-if="showForm" class="mt-3 flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800" @submit.prevent="create">
        <p v-if="groupLessonTypes.length === 0" class="text-sm text-amber-600 dark:text-amber-400">
          Сначала создайте тип занятия с форматом «групповое» на вкладке «Типы занятий».
        </p>
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
              <option v-for="(wd, idx) in weekdayNames" :key="idx" :value="idx">{{ wd }}</option>
            </select>
            <input v-model="slot.start_time" type="time" class="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700" />
          </div>
          <button type="button" class="mt-1 text-xs text-slate-500 underline" @click="addSlot">+ день</button>
        </div>
        <button type="submit" class="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-slate-900">Создать группу</button>
      </form>
    </div>

    <div v-if="groups.length > 0" class="flex flex-wrap gap-2">
      <button
        v-for="group in groups"
        :key="group.id"
        type="button"
        class="rounded-md border px-3 py-1.5 text-sm"
        :class="selectedGroupId === group.id ? 'border-slate-900 dark:border-white' : 'border-slate-300 dark:border-slate-700'"
        @click="selectGroup(group.id)"
      >
        {{ group.name }} ({{ group.member_count }}/{{ group.capacity }})
      </button>
    </div>

    <template v-if="selectedGroup">
      <section v-if="pendingApplications.length > 0">
        <h2 class="text-lg font-medium">Заявки</h2>
        <div v-for="app in pendingApplications" :key="app.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
          <span>Ученик {{ app.student_id }}</span>
          <div class="flex gap-2">
            <button type="button" class="rounded-md border border-green-300 px-2 py-1 text-xs text-green-700 dark:border-green-800" @click="accept(app)">Принять</button>
            <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="reject(app)">Отклонить</button>
          </div>
        </div>
      </section>

      <section>
        <h2 class="text-lg font-medium">Участники</h2>
        <p v-if="members.length === 0" class="mt-2 text-sm text-slate-400">Пока никого нет.</p>
        <div v-for="member in members" :key="member.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
          <span>{{ member.student_id }}</span>
          <button type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="remove(member)">Исключить</button>
        </div>
      </section>

      <section>
        <h2 class="text-lg font-medium">Занятия группы</h2>
        <div v-for="occ in occurrences.slice(0, 12)" :key="occ.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
          <span :class="occ.status === 'cancelled' ? 'text-slate-400 line-through' : ''">{{ formatDateTimeWithMsk(occ.start_at) }}</span>
          <button v-if="occ.status === 'scheduled'" type="button" class="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 dark:border-red-800" @click="cancelOccurrence(occ)">
            Отменить
          </button>
        </div>
      </section>
    </template>
  </div>
</template>
