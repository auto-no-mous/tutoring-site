/**
 * Разбивает текст на обычные куски и ссылки.
 *
 * Нужно для тел системных уведомлений (components/ChatPanel.vue): они приходят
 * простым текстом, но в некоторых шаблонах есть адреса, по которым логично кликнуть
 * (например, каталог репетиторов в приветственном сообщении).
 *
 * Возвращается массив кусков, а не готовая HTML-строка, именно чтобы не появилось
 * v-html: тексты шаблонов редактируются админом в интерфейсе, и превращать их в
 * разметку значило бы открыть путь для внедрения произвольного HTML. Кусок с типом
 * "link" компонент отрисовывает тегом <a>, всё остальное - как текст, который Vue
 * экранирует сам.
 */

export interface TextSegment {
  type: "text";
  value: string;
}

export interface LinkSegment {
  type: "link";
  value: string;
}

export type LinkifySegment = TextSegment | LinkSegment;

// Только http(s) и до первого пробела. Хвостовые знаки препинания отрезаются ниже:
// в "загляните на https://my-tutor.ru/." точка принадлежит предложению, а не адресу.
const URL_PATTERN = /https?:\/\/[^\s<>"']+/g;
const TRAILING_PUNCTUATION = /[.,;:!?)\]}»"']+$/;

export function linkifySegments(text: string): LinkifySegment[] {
  const segments: LinkifySegment[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(URL_PATTERN)) {
    const start = match.index ?? 0;
    let url = match[0];

    // Закрывающая скобка отрезается, только если в самом адресе не было открывающей -
    // иначе сломались бы ссылки вида .../wiki/Foo_(bar).
    const trailing = url.match(TRAILING_PUNCTUATION);
    if (trailing) {
      const stripped = url.slice(0, url.length - trailing[0].length);
      const balanced = (url.match(/\(/g) ?? []).length === (url.match(/\)/g) ?? []).length;
      if (!(trailing[0] === ")" && balanced)) url = stripped;
    }

    if (start > lastIndex) segments.push({ type: "text", value: text.slice(lastIndex, start) });
    segments.push({ type: "link", value: url });
    lastIndex = start + url.length;
  }

  if (lastIndex < text.length) segments.push({ type: "text", value: text.slice(lastIndex) });
  return segments;
}
