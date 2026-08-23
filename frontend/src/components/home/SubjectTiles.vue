<script setup lang="ts">
import { computed } from "vue";

import type { CatalogSubject } from "@/types/subject";

const props = defineProps<{ subjects: CatalogSubject[]; selectedId: string }>();
const emit = defineEmits<{ (e: "select", subjectId: string): void }>();

// Предметы без репетиторов не показываем: плитка, ведущая в пустой каталог, вредит
// сильнее, чем её отсутствие. Порядок - по числу репетиторов, чтобы живые
// направления были сверху.
const visible = computed(() =>
  props.subjects.filter((s) => s.tutors_count > 0).sort((a, b) => b.tutors_count - a.tutors_count),
);

function tutorsLabel(count: number): string {
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 14) return `${count} репетиторов`;
  if (mod10 === 1) return `${count} репетитор`;
  if (mod10 >= 2 && mod10 <= 4) return `${count} репетитора`;
  return `${count} репетиторов`;
}

// Повторный клик по выбранной плитке снимает фильтр - иначе вернуться ко "всем
// предметам" можно только через свёрнутую панель фильтров.
function toggle(subjectId: string): void {
  emit("select", props.selectedId === subjectId ? "" : subjectId);
}
</script>

<template>
  <section v-if="visible.length > 0" class="mx-auto w-full max-w-5xl px-4 pt-12">
    <h2 class="text-2xl font-semibold tracking-tight">Предметы</h2>
    <p class="mt-1.5 text-base text-slate-500 dark:text-slate-400">
      Выберите предмет — каталог ниже отфильтруется.
    </p>
    <div class="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <button
        v-for="(subject, index) in visible"
        :key="subject.id"
        type="button"
        :aria-pressed="selectedId === subject.id"
        :style="{ animationDelay: `${index * 40}ms` }"
        class="surface-card animate-fade-in-up flex flex-col items-start p-4 text-left transition-all duration-200 ease-out hover:-translate-y-1 hover:border-brand-300 hover:shadow-lg dark:hover:border-brand-700"
        :class="
          selectedId === subject.id
            ? 'border-brand-400 ring-2 ring-brand-300 dark:border-brand-600 dark:ring-brand-700'
            : ''
        "
        @click="toggle(subject.id)"
      >
        <span class="text-base font-semibold">{{ subject.name }}</span>
        <span class="mt-1 text-sm text-brand-700 dark:text-brand-300">{{ tutorsLabel(subject.tutors_count) }}</span>
        <span
          v-if="subject.directions.length > 0"
          class="mt-2 line-clamp-2 text-sm leading-snug text-slate-500 dark:text-slate-400"
        >
          {{ subject.directions.map((d) => d.name).join(" · ") }}
        </span>
      </button>
    </div>
  </section>
</template>
