<script setup lang="ts">
import { ChevronDown, PencilLine, Presentation } from "lucide-vue-next";
import { computed, ref } from "vue";

import { markWhiteboardUsed, type Whiteboard } from "@/api/whiteboards";

// Доски приходят от родителя уже отобранными для этого занятия: они привязаны к паре
// репетитор-ученик или к группе, и запрашивать их на каждую карточку значило бы
// повторять один и тот же ответ.
const props = defineProps<{ boards: Whiteboard[]; canManage?: boolean }>();
const emit = defineEmits<{ manage: [] }>();

const expanded = ref(false);

// Сервер отдаёт список уже отсортированным по «последней открытой», но полагаться на
// порядок в пропсе нельзя: родитель мог отфильтровать его как угодно.
const sorted = computed(() =>
  [...props.boards].sort((a, b) => b.last_used_at.localeCompare(a.last_used_at)),
);
const current = computed(() => sorted.value[0] ?? null);
const rest = computed(() => sorted.value.slice(1));

function boardLabel(board: Whiteboard): string {
  return board.title?.trim() || "Доска";
}

/** Отмечаем открытие и не мешаем переходу: ссылка открывается в новой вкладке сама,
 * а если отметка не дойдёт - потеряется только порядок в списке. */
function onOpen(board: Whiteboard): void {
  markWhiteboardUsed(board.id).catch(() => {});
}
</script>

<template>
  <div v-if="current || canManage" class="flex flex-col gap-1">
    <div class="flex items-center gap-1">
      <a
        v-if="current"
        :href="current.url"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1 rounded-md border border-brand-200 px-2 py-1 text-xs text-brand-800 transition-colors hover:bg-brand-50 dark:border-brand-800 dark:text-brand-200 dark:hover:bg-brand-900/30"
        @click="onOpen(current)"
      >
        <Presentation class="h-3.5 w-3.5" />
        {{ boardLabel(current) }}
      </a>

      <!-- Досок обычно одна; кнопка появляется, только когда есть что разворачивать. -->
      <button
        v-if="rest.length > 0"
        type="button"
        class="inline-flex items-center gap-0.5 rounded-md border border-slate-300 px-1.5 py-1 text-xs text-slate-500 dark:border-slate-700"
        :title="expanded ? 'Скрыть остальные доски' : `Ещё досок: ${rest.length}`"
        @click="expanded = !expanded"
      >
        +{{ rest.length }}
        <ChevronDown class="h-3 w-3 transition-transform duration-200" :class="{ 'rotate-180': expanded }" />
      </button>

      <button
        v-if="canManage"
        type="button"
        class="inline-flex items-center gap-1 rounded-md border border-slate-300 px-1.5 py-1 text-xs text-slate-500 dark:border-slate-700"
        :title="current ? 'Изменить доски' : 'Добавить доску'"
        @click="emit('manage')"
      >
        <PencilLine class="h-3.5 w-3.5" />
        <span v-if="!current">Доска</span>
      </button>
    </div>

    <div v-if="expanded && rest.length > 0" class="flex flex-wrap gap-1">
      <a
        v-for="board in rest"
        :key="board.id"
        :href="board.url"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 transition-colors hover:border-brand-400 dark:border-slate-700 dark:text-slate-300"
        @click="onOpen(board)"
      >
        <Presentation class="h-3.5 w-3.5" />
        {{ boardLabel(board) }}
      </a>
    </div>
  </div>
</template>
