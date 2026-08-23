import { onBeforeUnmount, watchEffect } from "vue";

// Сайт - SPA без SSR, поэтому <title>, description и structured data приходится
// проставлять из компонента и возвращать на место при уходе с маршрута: иначе
// заголовок статьи останется висеть на каталоге. Поисковики, исполняющие JS, это
// видят; для остальных нужен пререндер - см. README, «Известные ограничения».
const SITE_NAME = "my-tutor.ru";

export interface PageMeta {
  /** Без названия сайта - оно добавляется автоматически. */
  title?: string;
  description?: string;
  /** Любой JSON-LD-объект (Article, FAQPage, …). */
  jsonLd?: unknown;
}

/**
 * Принимает геттер, а не готовый объект: на страницах вроде статьи блога мета
 * известна только после загрузки данных, и watchEffect подхватит её сам.
 */
export function usePageMeta(source: () => PageMeta): void {
  const defaultTitle = document.title;
  const descriptionEl = document.querySelector<HTMLMetaElement>('meta[name="description"]');
  const defaultDescription = descriptionEl?.content ?? "";

  // Каждый вызов владеет своим <script>, а не общим по id: так две секции с
  // разметкой на одной странице не затирают друг друга.
  let scriptEl: HTMLScriptElement | null = null;

  function removeJsonLd(): void {
    scriptEl?.remove();
    scriptEl = null;
  }

  watchEffect(() => {
    const meta = source();
    document.title = meta.title ? `${meta.title} — ${SITE_NAME}` : defaultTitle;
    if (descriptionEl) descriptionEl.content = meta.description || defaultDescription;

    removeJsonLd();
    if (meta.jsonLd) {
      scriptEl = document.createElement("script");
      scriptEl.type = "application/ld+json";
      scriptEl.textContent = JSON.stringify(meta.jsonLd);
      document.head.appendChild(scriptEl);
    }
  });

  onBeforeUnmount(() => {
    document.title = defaultTitle;
    if (descriptionEl) descriptionEl.content = defaultDescription;
    removeJsonLd();
  });
}
