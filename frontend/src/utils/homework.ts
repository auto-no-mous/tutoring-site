import { computed, ref, type Ref } from "vue";

// Статус домашки показывают три разных места - вкладка ученика, вкладка репетитора и
// окно «ДЗ · ученик», - и раньше каждое называло и красило его по-своему.

export const HOMEWORK_STATUS_OPTIONS = [
  { value: "pending", label: "Не выполнено" },
  { value: "submitted", label: "Отправлено" },
  { value: "done", label: "Выполнено" },
] as const;

export function homeworkStatusLabel(status: string): string {
  return HOMEWORK_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status;
}

// Цвет полосы и фона карточки. Разные оттенки, а не разная насыщенность одного:
// репетитору важнее всего заметить «отправлено, но не проверено» (синий), ученику -
// «не выполнено» (янтарный).
const CARD_CLASSES: Record<string, string> = {
  pending: "border-l-4 border-l-amber-400 bg-amber-50/50 dark:bg-amber-950/20",
  submitted: "border-l-4 border-l-sky-500 bg-sky-50/50 dark:bg-sky-950/20",
  done: "border-l-4 border-l-green-500 bg-green-50/40 dark:bg-green-950/20",
};

export function homeworkCardClass(status: string): string {
  return CARD_CLASSES[status] ?? "";
}

const TEXT_CLASSES: Record<string, string> = {
  pending: "text-amber-600 dark:text-amber-400",
  submitted: "text-sky-600 dark:text-sky-400",
  done: "text-green-600 dark:text-green-400",
};

export function homeworkStatusTextClass(status: string): string {
  return TEXT_CLASSES[status] ?? "text-slate-500";
}

/** Имя файла из пути вида /files/homework/2026/abc-screenshot.png. */
export function homeworkFileName(path: string): string {
  const name = path.split("/").pop() ?? path;
  return name.length > 40 ? `${name.slice(0, 37)}…` : name;
}

// У учеников копятся десятки заданий, и свежие тонули под старыми. Показываем
// последние HOMEWORK_PAGE_SIZE (списки приходят от новых к старым), остальные
// догружаются кнопкой. Сколько раскрыто - помним при перезагрузке списка после сдачи
// или смены статуса, иначе карточка, с которой только что работали, пропадала бы.
export const HOMEWORK_PAGE_SIZE = 5;

export function useHomeworkPage<T>(items: Ref<T[]>) {
  const limit = ref(HOMEWORK_PAGE_SIZE);
  const visible = computed(() => items.value.slice(0, limit.value));
  const remaining = computed(() => Math.max(0, items.value.length - limit.value));
  return {
    visible,
    remaining,
    showMore: () => {
      limit.value += HOMEWORK_PAGE_SIZE;
    },
    reset: () => {
      limit.value = HOMEWORK_PAGE_SIZE;
    },
  };
}
