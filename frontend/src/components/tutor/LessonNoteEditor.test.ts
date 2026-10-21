import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import LessonNoteEditor from "@/components/tutor/LessonNoteEditor.vue";

const buttonByText = (wrapper: ReturnType<typeof mount>, text: string) =>
  wrapper.findAll("button").find((b) => b.text().includes(text))!;

describe("LessonNoteEditor", () => {
  it("без примечания предлагает его добавить и сохраняет обрезанный текст", async () => {
    const wrapper = mount(LessonNoteEditor, { props: { note: null } });

    await buttonByText(wrapper, "Добавить примечание").trigger("click");
    await wrapper.find("textarea").setValue("  начать с дробей  ");
    await buttonByText(wrapper, "Сохранить").trigger("click");

    expect(wrapper.emitted("save")).toEqual([["начать с дробей"]]);
    expect(wrapper.find("textarea").exists()).toBe(false);
  });

  it("показывает примечание и правит его по клику", async () => {
    const wrapper = mount(LessonNoteEditor, { props: { note: "повторить степени" } });
    expect(wrapper.text()).toContain("повторить степени");

    await wrapper.find('button[title="Изменить примечание"]').trigger("click");
    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe("повторить степени");
    expect(wrapper.text()).toContain("Видно только вам");
  });

  it("пустое примечание снимает его", async () => {
    const wrapper = mount(LessonNoteEditor, { props: { note: "было" } });

    await wrapper.find('button[title="Изменить примечание"]').trigger("click");
    await wrapper.find("textarea").setValue("   ");
    await buttonByText(wrapper, "Сохранить").trigger("click");

    expect(wrapper.emitted("save")).toEqual([[null]]);
  });

  it("отмена ничего не сохраняет", async () => {
    const wrapper = mount(LessonNoteEditor, { props: { note: "было" } });

    await wrapper.find('button[title="Изменить примечание"]').trigger("click");
    await wrapper.find("textarea").setValue("стало");
    await buttonByText(wrapper, "Отмена").trigger("click");

    expect(wrapper.emitted("save")).toBeUndefined();
    expect(wrapper.text()).toContain("было");
  });
});
