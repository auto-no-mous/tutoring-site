import { mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import FileDropZone from "@/components/FileDropZone.vue";

function imageFile(name = "shot.png"): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type: "image/png" });
}

const mounted: VueWrapper[] = [];

// Вставку зона слушает на документе, поэтому монтируем в настоящий body.
function mountZone(props: Record<string, unknown> = {}) {
  const wrapper = mount(FileDropZone, { props: { modelValue: [], ...props }, attachTo: document.body });
  mounted.push(wrapper);
  return wrapper;
}

// Ctrl+V без клика: событие получает тот элемент, что в фокусе, обычно body.
function pasteImage(target: EventTarget = document.body, file = imageFile("image.png")): Event {
  const event = new Event("paste", { bubbles: true, cancelable: true });
  Object.assign(event, {
    clipboardData: { items: [{ kind: "file", type: "image/png", getAsFile: () => file }], files: [file] },
  });
  target.dispatchEvent(event);
  return event;
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount());
  document.body.innerHTML = "";
});

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
    const wrapper = mountZone();
    const file = imageFile();

    await wrapper.find('[role="button"]').trigger("drop", { dataTransfer: { files: [file] } });

    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([[file]]);
  });

  it("добавляет файлы к уже выбранным, а не заменяет их", async () => {
    const first = imageFile("first.png");
    const wrapper = mountZone({ modelValue: [first] });
    const second = imageFile("second.png");
    const third = imageFile("third.png");

    await wrapper.find('[role="button"]').trigger("drop", { dataTransfer: { files: [second, third] } });

    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([[first, second, third]]);
  });

  it("не даёт набрать больше max и говорит об этом", async () => {
    const wrapper = mountZone({ modelValue: [imageFile("a.png")], max: 2 });

    await wrapper
      .find('[role="button"]')
      .trigger("drop", { dataTransfer: { files: [imageFile("b.png"), imageFile("c.png")] } });

    const emitted = wrapper.emitted("update:modelValue")?.[0]?.[0] as File[];
    expect(emitted.map((f) => f.name)).toEqual(["a.png", "b.png"]);
    expect(wrapper.text()).toContain("не больше 2 файлов");
  });

  it("выбор на диске допускает несколько файлов", () => {
    const wrapper = mountZone();
    expect(wrapper.find('input[type="file"]').attributes("multiple")).toBeDefined();
  });

  it("принимает картинку из буфера обмена", async () => {
    // Главное ради чего всё затевалось: скриншот лежит в буфере как изображение, а
    // не как ссылка на файл.
    const wrapper = mountZone();
    pasteImage(wrapper.find('[role="button"]').element);

    const emitted = (wrapper.emitted("update:modelValue")?.[0]?.[0] as File[])[0];
    expect(emitted).toBeInstanceOf(File);
    expect(emitted.type).toBe("image/png");
    // Безымянному скриншоту из буфера даём осмысленное имя.
    expect(emitted.name).toMatch(/^screenshot-\d+\.png$/);
  });

  it("не реагирует на вставку текста", async () => {
    const wrapper = mountZone();

    await wrapper.find('[role="button"]').trigger("paste", {
      clipboardData: { items: [{ kind: "string", type: "text/plain" }], files: [] },
    });

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("показывает выбранные файлы и позволяет убрать любой", async () => {
    const home = imageFile("home.png");
    const work = imageFile("work.png");
    const wrapper = mountZone({ modelValue: [home, work] });

    expect(wrapper.text()).toContain("home.png");
    expect(wrapper.text()).toContain("work.png");
    expect(wrapper.find("img").attributes("src")).toBe("blob:preview");

    await wrapper.findAll('button[title="Убрать файл"]')[0].trigger("click");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([[work]]);
  });

  it("ничего не принимает, когда отключён", async () => {
    const wrapper = mountZone({ disabled: true });

    await wrapper.find('[role="button"]').trigger("drop", { dataTransfer: { files: [imageFile()] } });

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("принимает Ctrl+V без клика по зоне", () => {
    // Раньше вставка доходила до зоны, только если она была в фокусе, а фокус она
    // получала кликом, который тут же открывал диалог выбора файла.
    const wrapper = mountZone();

    const event = pasteImage();

    expect(wrapper.emitted("update:modelValue")).toHaveLength(1);
    expect(event.defaultPrevented).toBe(true);
  });

  it("из нескольких зон без выбора берёт верхнюю, а под курсором - ту, что под курсором", async () => {
    const first = mountZone();
    const second = mountZone();

    pasteImage();
    expect(first.emitted("update:modelValue")).toHaveLength(1);
    expect(second.emitted("update:modelValue")).toBeUndefined();

    await second.find('[role="button"]').trigger("pointerenter");
    pasteImage();
    expect(first.emitted("update:modelValue")).toHaveLength(1);
    expect(second.emitted("update:modelValue")).toHaveLength(1);
  });

  it("пропускает отключённую зону", () => {
    const disabled = mountZone({ disabled: true });
    const enabled = mountZone();

    pasteImage();

    expect(disabled.emitted("update:modelValue")).toBeUndefined();
    expect(enabled.emitted("update:modelValue")).toHaveLength(1);
  });

  it("не перехватывает вставку в текстовое поле", () => {
    const wrapper = mountZone();
    const textarea = document.createElement("textarea");
    document.body.appendChild(textarea);

    const event = pasteImage(textarea);

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    expect(event.defaultPrevented).toBe(false);
  });

  it("перестаёт слушать вставку после размонтирования", () => {
    const wrapper = mountZone();
    wrapper.unmount();
    mounted.splice(0);

    expect(pasteImage().defaultPrevented).toBe(false);
  });
});
