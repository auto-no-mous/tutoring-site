<script setup lang="ts">
import { CalendarPlus, Users } from "lucide-vue-next";
import { computed } from "vue";

import type { TutorPublicProfile } from "@/types/tutor";

const props = defineProps<{ profile: TutorPublicProfile }>();

// Две кнопки делят ширину блока поровну (сетка в две колонки), одна - просто стоит
// по центру: растянутая на всю ширину одиночная кнопка выглядела бы баннером.
const bothShown = computed(
  () => props.profile.show_individual_booking && props.profile.show_group_booking,
);
</script>

<template>
  <div
    v-if="profile.show_individual_booking || profile.show_group_booking"
    :class="bothShown ? 'grid gap-3 sm:grid-cols-2' : 'flex justify-center'"
  >
    <RouterLink
      v-if="profile.show_individual_booking"
      :to="`/tutors/${profile.id}/book`"
      class="btn-primary text-base"
      :class="bothShown ? 'w-full' : ''"
    >
      <CalendarPlus class="h-4 w-4 shrink-0" />
      Запись на индивидуальное занятие
    </RouterLink>
    <RouterLink
      v-if="profile.show_group_booking"
      :to="`/tutors/${profile.id}/groups`"
      class="btn-outline text-base"
      :class="bothShown ? 'w-full' : ''"
    >
      <Users class="h-4 w-4 shrink-0" />
      Запись на групповое занятие
    </RouterLink>
  </div>
</template>
