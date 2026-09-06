import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FileDropZone from "@/components/FileDropZone.vue";

function imageFile(name = "shot.png"): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type: "image/png" });
}

// jsdom не умеет objectURL - подменяем, иначе превью падает при монтировании.
beforeEach(() => {
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:preview"),
    revokeObjectURL: vi.fn(),
  });
});

describe("FileDropZone", () => {
  it("принимает перетащенный файл", async () => {
    const wrapper = mount(FileDropZone, { props: { modelValue: null } });
    const file = imageFile();

    await wrapper.find('[role="button"]').trigger("drop", { dataTransfer: { files: [file] } });

    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([file]);
  });

  it("принимает картинку из буфера обмена", async () => {
    // Главное ради чего всё затевалось: скриншот лежит в буфере как изображение, а
    // не как ссылка на файл.
    const wrapper = mount(FileDropZone, { props: { modelValue: null } });
    const file = imageFile("image.png");

    await wrapper.find('[role="button"]').trigger("paste", {
      clipboardData: {
        items: [{ kind: "file", type: "image/png", getAsFile: () => file }],
        files: [file],
      },
    });

    const emitted = wrapper.emitted("update:modelValue")?.[0]?.[0] as File;
    expect(emitted).toBeInstanceOf(File);
    expect(emitted.type).toBe("image/png");
    // Безымянному скриншоту из буфера даём осмысленное имя.
    expect(emitted.name).toMatch(/^screenshot-\d+\.png$/);
  });

  it("не реагирует на вставку текста", async () => {
    const wrapper = mount(FileDropZone, { props: { modelValue: null } });

    await wrapper.find('[role="button"]').trigger("paste", {
      clipboardData: { items: [{ kind: "string", type: "text/plain" }], files: [] },
    });

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("показывает выбранный файл и позволяет его убрать", async () => {
    const wrapper = mount(FileDropZone, { props: { modelValue: imageFile("home.png") } });

    expect(wrapper.text()).toContain("home.png");
    expect(wrapper.find("img").attributes("src")).toBe("blob:preview");

    await wrapper.find('button[title="Убрать файл"]').trigger("click");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([null]);
  });

  it("ничего не принимает, когда отключён", async () => {
    const wrapper = mount(FileDropZone, { props: { modelValue: null, disabled: true } });

    await wrapper.find('[role="button"]').trigger("drop", { dataTransfer: { files: [imageFile()] } });

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });
});
