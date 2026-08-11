import { defineStore } from "pinia";
import { ref, watch } from "vue";

type Theme = "light" | "dark";

const STORAGE_KEY = "my-tutor.theme";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export const useThemeStore = defineStore("theme", () => {
  const theme = ref<Theme>(getInitialTheme());

  function apply(): void {
    document.documentElement.classList.toggle("dark", theme.value === "dark");
    localStorage.setItem(STORAGE_KEY, theme.value);
  }

  function toggle(): void {
    theme.value = theme.value === "dark" ? "light" : "dark";
  }

  watch(theme, apply, { immediate: true });

  return { theme, toggle };
});
