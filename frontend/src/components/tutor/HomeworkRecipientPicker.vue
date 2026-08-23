<script setup lang="ts">
import { X } from "lucide-vue-next";
import { computed } from "vue";

import type { Group } from "@/types/group";
import type { TutorStudent } from "@/types/tutor";

// Like addressing an email to several recipients at once - selected students/groups
// show as removable chips, with the full list below to keep adding more.
const props = defineProps<{
  students: TutorStudent[];
  groups: Group[];
  studentIds: string[];
  groupIds: string[];
}>();

const emit = defineEmits<{
  "update:studentIds": [string[]];
  "update:groupIds": [string[]];
}>();

function studentLabel(student: TutorStudent): string {
  const name = `${student.last_name} ${student.first_name}`.trim();
  return student.grade ? `${name}, ${student.grade}-й класс` : name;
}

interface Chip {
  type: "student" | "group";
  id: string;
  label: string;
}

const chips = computed<Chip[]>(() => {
  const studentChips = props.students
    .filter((s) => props.studentIds.includes(s.id))
    .map((s): Chip => ({ type: "student", id: s.id, label: studentLabel(s) }));
  const groupChips = props.groups
    .filter((g) => props.groupIds.includes(g.id))
    .map((g): Chip => ({ type: "group", id: g.id, label: `Группа «${g.name}»` }));
  return [...studentChips, ...groupChips];
});

function isSelected(type: "student" | "group", id: string): boolean {
  return type === "student" ? props.studentIds.includes(id) : props.groupIds.includes(id);
}

function toggle(type: "student" | "group", id: string): void {
  if (type === "student") {
    const next = props.studentIds.includes(id)
      ? props.studentIds.filter((sid) => sid !== id)
      : [...props.studentIds, id];
    emit("update:studentIds", next);
  } else {
    const next = props.groupIds.includes(id) ? props.groupIds.filter((gid) => gid !== id) : [...props.groupIds, id];
    emit("update:groupIds", next);
  }
}

function removeChip(chip: Chip): void {
  toggle(chip.type, chip.id);
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-if="chips.length > 0" class="flex flex-wrap gap-1.5">
      <span
        v-for="chip in chips"
        :key="`${chip.type}-${chip.id}`"
        class="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs dark:bg-slate-800"
      >
        {{ chip.label }}
        <button
          type="button"
          class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          :aria-label="`Убрать ${chip.label}`"
          @click="removeChip(chip)"
        >
          <X class="h-3.5 w-3.5" />
        </button>
      </span>
    </div>
    <p v-else class="text-xs text-slate-400">Получатели не выбраны.</p>

    <div class="max-h-40 overflow-y-auto rounded-md border border-slate-300 p-2 text-sm dark:border-slate-700">
      <p v-if="students.length === 0 && groups.length === 0" class="text-xs text-slate-400">Нет доступных получателей.</p>
      <template v-if="students.length > 0">
        <p class="mb-1 text-xs font-medium text-slate-500">Ученики</p>
        <label
          v-for="student in students"
          :key="student.id"
          class="flex items-center gap-2 rounded-md px-1 py-1 hover:bg-slate-50 dark:hover:bg-slate-800/60"
        >
          <input
            type="checkbox"
            :checked="isSelected('student', student.id)"
            @change="toggle('student', student.id)"
          />
          {{ studentLabel(student) }}
        </label>
      </template>
      <template v-if="groups.length > 0">
        <p class="mb-1 mt-2 text-xs font-medium text-slate-500">Группы</p>
        <label
          v-for="group in groups"
          :key="group.id"
          class="flex items-center gap-2 rounded-md px-1 py-1 hover:bg-slate-50 dark:hover:bg-slate-800/60"
        >
          <input type="checkbox" :checked="isSelected('group', group.id)" @change="toggle('group', group.id)" />
          Группа «{{ group.name }}»
        </label>
      </template>
    </div>
  </div>
</template>
