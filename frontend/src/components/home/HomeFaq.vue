<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import { ref } from "vue";

import { usePageMeta } from "@/utils/pageMeta";

interface FaqItem {
  q: string;
  a: string;
  link?: { to: string; label: string };
}

const items: FaqItem[] = [
  {
    q: "Сколько стоит занятие и как проходит оплата?",
    a:
      "Цену устанавливает сам репетитор — она указана в каталоге и в анкете, для групп это цена за место. " +
      "Оплата пока происходит вне сайта, напрямую по договорённости с репетитором: цена на сайте нужна, чтобы " +
      "было с чем сравнивать при выборе. Регистрация и пользование сайтом бесплатны и для учеников, и для репетиторов.",
  },
  {
    q: "Где проходят занятия?",
    a:
      "Занятия проходят онлайн на привычных сервисах видеосвязи — Zoom, Яндекс Телемост и других. Ссылку на встречу " +
      "репетитор указывает для каждого занятия, и она видна в вашем кабинете рядом с этим занятием.",
  },
  {
    q: "Можно ли отменить или перенести занятие?",
    a:
      "Да, индивидуальное занятие можно отменить или перенести прямо в кабинете. Сроки (например, не позже чем за " +
      "сутки) и количество отмен в месяц каждый репетитор настраивает под себя — актуальные условия видны в момент " +
      "отмены. Отдельное занятие группы ученик отменить не может, но из группы всегда можно выйти.",
  },
  {
    q: "В каком часовом поясе показывается время?",
    a:
      "Ваш часовой пояс определяется автоматически при регистрации, изменить его можно в настройках. Время занятий " +
      "везде показывается в вашем поясе, а рядом в скобках — московское, чтобы не было расхождений с репетитором.",
  },
  {
    q: "Что нужно, чтобы записаться?",
    a:
      "Зарегистрироваться как ученик и подтвердить почту. После этого можно выбрать репетитора в каталоге, открыть " +
      "его расписание и записаться на любое свободное время — отдельно договариваться заранее не нужно.",
    link: { to: "/register", label: "Зарегистрироваться" },
  },
  {
    q: "Я репетитор. Как разместить анкету?",
    a:
      "Зарегистрируйтесь как репетитор, заполните анкету: фотография, рассказ о себе, предметы и направления, типы " +
      "занятий с ценой и длительностью. Затем отметьте в расписании, когда вы готовы заниматься, — и анкета появится " +
      "в каталоге. Анкету можно в любой момент скрыть из каталога, не удаляя аккаунт.",
    link: { to: "/register?role=tutor", label: "Стать репетитором" },
  },
];

const openIndex = ref<number | null>(null);

function toggle(index: number): void {
  openIndex.value = openIndex.value === index ? null : index;
}

// FAQPage-разметка для поисковиков. Заголовок страницы не трогаем - это лишь секция
// главной; usePageMeta сам уберёт разметку при уходе с маршрута.
usePageMeta(() => ({
  jsonLd: {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  },
}));
</script>

<template>
  <section class="mx-auto w-full max-w-3xl px-4 pt-16">
    <h2 class="text-2xl font-semibold tracking-tight">Частые вопросы</h2>
    <div class="mt-5 flex flex-col gap-3">
      <div v-for="(item, index) in items" :key="item.q" class="surface-card overflow-hidden">
        <button
          :id="`faq-q-${index}`"
          type="button"
          class="flex w-full items-center justify-between gap-4 p-4 text-left text-base font-semibold hover:text-brand-700 dark:hover:text-brand-300"
          :aria-expanded="openIndex === index"
          :aria-controls="`faq-a-${index}`"
          @click="toggle(index)"
        >
          {{ item.q }}
          <ChevronDown
            class="h-5 w-5 shrink-0 text-slate-400 transition-transform duration-300"
            :class="{ 'rotate-180': openIndex === index }"
          />
        </button>
        <Transition name="collapse">
          <div v-show="openIndex === index" :id="`faq-a-${index}`" role="region" :aria-labelledby="`faq-q-${index}`">
            <div class="collapse-inner">
              <p class="px-4 pb-4 text-base leading-relaxed text-slate-600 dark:text-slate-300">
                {{ item.a }}
                <RouterLink
                  v-if="item.link"
                  :to="item.link.to"
                  class="font-medium text-brand-700 underline underline-offset-2 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                >
                  {{ item.link.label }}
                </RouterLink>
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </section>
</template>
