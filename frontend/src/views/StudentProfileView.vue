<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { listTutorBookings } from "@/api/bookings";
import { openThreadWithStudent } from "@/api/chat";
import { getMyStudentDetail } from "@/api/tutors";
import StudentHomeworkModal from "@/components/StudentHomeworkModal.vue";
import type { Booking } from "@/types/booking";
import type { TutorStudentDetail } from "@/types/tutor";
import { formatDateTimeWithMsk } from "@/utils/time";

const route = useRoute();
const router = useRouter();
const studentId = route.params.id as string;

const student = ref<TutorStudentDetail | null>(null);
const bookings = ref<Booking[]>([]);
const isLoading = ref(true);
const notFound = ref(false);
const showHomework = ref(false);

const GROUP_STATUS_LABELS: Record<string, string> = { active: "состоит", left: "покинул(а)" };
const BOOKING_STATUS_LABELS: Record<string, string> = {
  cancelled_by_student: "Отменено учеником",
  cancelled_by_tutor: "Отменено репетитором",
  rescheduled: "Перенесено",
};

function pastStatusLabel(booking: Booking): string {
  return BOOKING_STATUS_LABELS[booking.status] ?? "";
}

const fullName = computed(() => {
  if (!student.value) return "";
  const { last_name, first_name, patronymic } = student.value;
  return [last_name, first_name, patronymic].filter(Boolean).join(" ");
});

const upcomingBookings = computed(() =>
  bookings.value
    .filter((b) => b.status === "scheduled" && new Date(b.start_at) >= new Date())
    .sort((a, b) => a.start_at.localeCompare(b.start_at)),
);
const pastBookings = computed(() =>
  bookings.value
    .filter((b) => b.status !== "scheduled" || new Date(b.start_at) < new Date())
    .sort((a, b) => b.start_at.localeCompare(a.start_at))
    .slice(0, 20),
);

async function load(): Promise<void> {
  isLoading.value = true;
  try {
    const [studentData, allBookings] = await Promise.all([getMyStudentDetail(studentId), listTutorBookings()]);
    student.value = studentData;
    bookings.value = allBookings.filter((b) => b.student_id === studentId);
  } catch {
    notFound.value = true;
  } finally {
    isLoading.value = false;
  }
}

async function openChat(): Promise<void> {
  const thread = await openThreadWithStudent(studentId);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}

onMounted(load);
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-10">
    <RouterLink to="/cabinet?tab=groups" class="text-sm text-slate-500 hover:underline">← Группы</RouterLink>

    <p v-if="isLoading" class="mt-4 text-slate-400">Загрузка…</p>
    <p v-else-if="notFound" class="mt-4 text-sm text-red-600 dark:text-red-400">
      Ученик не найден, либо вы никогда с ним не работали.
    </p>
    <template v-else-if="student">
      <div class="mt-2 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold">{{ fullName }}</h1>
          <p class="mt-1 text-sm text-slate-500">
            <span v-if="student.grade">{{ student.grade }}-й класс</span>
            <span v-if="student.grade && student.email"> · </span>
            <span v-if="student.email">{{ student.email }}</span>
          </p>
        </div>
        <button type="button" class="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700" @click="openChat">
          Написать сообщение
        </button>
      </div>

      <section v-if="student.groups.length > 0" class="mt-6">
        <h2 class="text-lg font-medium">Группы</h2>
        <div class="mt-2 flex flex-col gap-1.5 text-sm">
          <div v-for="g in student.groups" :key="g.group_id">
            «{{ g.group_name }}» — {{ GROUP_STATUS_LABELS[g.status] ?? g.status }}
          </div>
        </div>
      </section>

      <section class="mt-6">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-medium">Домашние задания</h2>
          <button type="button" class="text-sm text-slate-500 underline" @click="showHomework = true">Открыть</button>
        </div>
      </section>

      <section class="mt-6">
        <h2 class="text-lg font-medium">Ближайшие занятия</h2>
        <p v-if="upcomingBookings.length === 0" class="mt-2 text-sm text-slate-400">Занятий не запланировано.</p>
        <div v-for="b in upcomingBookings" :key="b.id" class="mt-2 rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
          {{ formatDateTimeWithMsk(b.start_at) }}
        </div>
      </section>

      <section class="mt-6">
        <h2 class="text-lg font-medium">История занятий</h2>
        <p v-if="pastBookings.length === 0" class="mt-2 text-sm text-slate-400">Занятий пока не было.</p>
        <div v-for="b in pastBookings" :key="b.id" class="mt-2 flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-500 dark:border-slate-800">
          <span>{{ formatDateTimeWithMsk(b.start_at) }}</span>
          <span v-if="pastStatusLabel(b)">{{ pastStatusLabel(b) }}</span>
        </div>
      </section>

      <StudentHomeworkModal v-if="showHomework" :student-id="studentId" :student-name="fullName" @close="showHomework = false" />
    </template>
  </div>
</template>
