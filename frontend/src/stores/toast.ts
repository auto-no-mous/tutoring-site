import { defineStore } from "pinia";
import { ref } from "vue";

interface Toast {
  id: number;
  message: string;
}

let nextId = 1;

export const useToastStore = defineStore("toast", () => {
  const toasts = ref<Toast[]>([]);

  function show(message: string, durationMs = 3000): void {
    const id = nextId++;
    toasts.value.push({ id, message });
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id);
    }, durationMs);
  }

  return { toasts, show };
});
