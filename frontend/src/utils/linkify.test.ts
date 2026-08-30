import { describe, expect, it } from "vitest";

import { internalPath, linkifySegments } from "@/utils/linkify";

describe("linkifySegments", () => {
  it("returns a single text segment when there is nothing to link", () => {
    expect(linkifySegments("Занятие перенесено на завтра")).toEqual([
      { type: "text", value: "Занятие перенесено на завтра" },
    ]);
  });

  it("splits the surrounding text away from the link", () => {
    expect(linkifySegments("Каталог: https://my-tutor.ru/ — выбирайте")).toEqual([
      { type: "text", value: "Каталог: " },
      { type: "link", value: "https://my-tutor.ru/" },
      { type: "text", value: " — выбирайте" },
    ]);
  });

  it("leaves sentence punctuation out of the link", () => {
    expect(linkifySegments("Загляните на https://my-tutor.ru/.")).toEqual([
      { type: "text", value: "Загляните на " },
      { type: "link", value: "https://my-tutor.ru/" },
      { type: "text", value: "." },
    ]);
  });

  it("keeps a closing bracket that belongs to the address itself", () => {
    const segments = linkifySegments("см. https://ru.wikipedia.org/wiki/Foo_(bar)");
    expect(segments[1]).toEqual({ type: "link", value: "https://ru.wikipedia.org/wiki/Foo_(bar)" });
  });

  it("handles several links in one message", () => {
    const segments = linkifySegments("http://a.example и https://b.example");
    expect(segments.filter((s) => s.type === "link").map((s) => s.value)).toEqual([
      "http://a.example",
      "https://b.example",
    ]);
  });

  it("does not treat other schemes as links", () => {
    // Тела уведомлений рисуются как ссылки без всякой очистки, поэтому ничего кроме
    // http(s) распознавать нельзя - javascript: в шаблоне не должен стать кликабельным.
    const text = "javascript:alert(1) и mailto:a@b.c";
    expect(linkifySegments(text)).toEqual([{ type: "text", value: text }]);
  });

  it("reassembles into the original text", () => {
    const text = "Начало https://my-tutor.ru/, середина http://x.example конец";
    expect(linkifySegments(text).map((s) => s.value).join("")).toBe(text);
  });
});

describe("internalPath", () => {
  it("возвращает путь для ссылки на наш же сайт", () => {
    // Уведомления собираются на бэкенде из FRONTEND_BASE_URL, поэтому адрес вкладки
    // кабинета приходит абсолютным - и должен открываться без перезагрузки.
    expect(internalPath(`${window.location.origin}/cabinet?tab=groups`)).toBe("/cabinet?tab=groups");
    expect(internalPath(`${window.location.origin}/blog/post#top`)).toBe("/blog/post#top");
  });

  it("не трогает внешние адреса и мусор", () => {
    expect(internalPath("https://vk.com/tutor")).toBeNull();
    expect(internalPath("not a url")).toBeNull();
  });
});
