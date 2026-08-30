<script setup lang="ts">
import { MessageCircle } from "lucide-vue-next";
import { computed } from "vue";
import { useRouter } from "vue-router";

import { openThreadWithTutor } from "@/api/chat";
import SocialLinks from "@/components/tutor/SocialLinks.vue";
import { useAuthStore } from "@/stores/auth";
import type { TutorPublicProfile } from "@/types/tutor";

// Ссылки на соцсети и кнопка "написать" - способы связаться с репетитором, поэтому
// стоят одной строкой и дублируются внизу страницы вместе с кнопками записи.
const props = defineProps<{ profile: TutorPublicProfile }>();

const auth = useAuthStore();
const router = useRouter();

const hasSocialLinks = computed(
  () =>
    !!props.profile.telegram_url ||
    !!props.profile.vk_url ||
    !!props.profile.youtube_url ||
    props.profile.extra_links.length > 0,
);

// Написать можно только ученику: чат заводится парой репетитор-ученик, гостю писать
// не с чего, а второму репетитору - некуда.
const canWrite = computed(() => auth.user?.role === "student");

async function openChat(): Promise<void> {
  const thread = await openThreadWithTutor(props.profile.id);
  await router.push({ path: "/cabinet", query: { tab: "chat", thread: thread.id } });
}
</script>

<template>
  <div
    v-if="hasSocialLinks || canWrite"
    class="flex flex-wrap items-center justify-center gap-2 sm:justify-start"
  >
    <SocialLinks
      v-if="hasSocialLinks"
      :telegram-url="profile.telegram_url"
      :vk-url="profile.vk_url"
      :youtube-url="profile.youtube_url"
      :extra-links="profile.extra_links"
    />
    <button
      v-if="canWrite"
      type="button"
      class="btn-outline h-9 px-3 py-0 text-sm"
      @click="openChat"
    >
      <MessageCircle class="h-4 w-4" />
      Написать личное сообщение
    </button>
  </div>
</template>
