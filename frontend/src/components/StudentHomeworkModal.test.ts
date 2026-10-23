import { flushPromises, mount } from "@vue/test-utils";
import { AxiosError, type AxiosResponse } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StudentHomeworkModal from "@/components/StudentHomeworkModal.vue";

const getStudentHomeworkForTutor = vi.fn();
const createHomework = vi.fn(async (_payload: Record<string, unknown>) => []);

vi.mock("@/api/homework", () => ({
  getStudentHomeworkForTutor: () => getStudentHomeworkForTutor(),
  createHomework: (payload: Record<string, unknown>) => createHomework(payload),
  setSubmissionStatus: vi.fn(async () => ({})),
}));

function homework(overrides: Record<string, unknown> = {}) {
  return {
    submission_id: "sub-1",
    assignment_id: "a-1",
    tutor_id: "t-1",
    group_id: null,
    title: "Параграф 12",
    content_type: "link",
    content_url: "https://example.com/task",
    content_file_path: null,
    submission_mode: "file_upload",
    due_at: null,
    status: "pending",
    files: [],
    comment: null,
    submitted_at: null,
    ...overrides,
  };
}

function field(label: string): HTMLInputElement | HTMLSelectElement {
  const el = Array.from(document.body.querySelectorAll("form label")).find((l) => l.textContent?.includes(label));
  return el!.querySelector("input, select")!;
}

const linkInput = () => document.body.querySelector('input[aria-label="Ссылка на материал"]') as HTMLInputElement | null;
const kindButton = (label: string) =>
  Array.from(document.body.querySelectorAll('[role="radio"]')).find((b) => b.textContent?.includes(label)) as HTMLButtonElement;

async function chooseFile(name: string, type: string): Promise<void> {
  const input = document.body.querySelector('input[type="file"]') as HTMLInputElement;
  Object.defineProperty(input, "files", { value: [new File(["data"], name, { type })], configurable: true });
  input.dispatchEvent(new Event("change"));
  await flushPromises();
}

async function submit(): Promise<void> {
  document.body.querySelector("form")!.dispatchEvent(new Event("submit"));
  await flushPromises();
}

async function openForm(): Promise<void> {
  const button = Array.from(document.body.querySelectorAll("button")).find((b) => b.textContent?.includes("Новое задание"));
  button!.click();
  await flushPromises();
}

describe("StudentHomeworkModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("новое задание берёт название и способ сдачи из последнего, но не материал", async () => {
    getStudentHomeworkForTutor.mockResolvedValue([
      homework({ submission_id: "sub-2", title: "Параграф 12", submission_mode: "file_upload" }),
      homework({ submission_id: "sub-1", title: "Старое", submission_mode: "mark_done" }),
    ]);
    mount(StudentHomeworkModal, { props: { studentId: "s-1", studentName: "Пётр" }, attachTo: document.body });
    await flushPromises();
    await openForm();

    expect(field("Название").value).toBe("Параграф 12");
    expect(field("Что должен сделать").value).toBe("file_upload");
    expect(linkInput()!.value).toBe("");
  });

  it("название необязательно", async () => {
    getStudentHomeworkForTutor.mockResolvedValue([]);
    mount(StudentHomeworkModal, { props: { studentId: "s-1", studentName: "Пётр" }, attachTo: document.body });
    await flushPromises();

    const title = field("Название");
    expect(title.value).toBe("");
    expect(title.required).toBe(false);

    const link = linkInput()!;
    link.value = "https://example.com/new";
    link.dispatchEvent(new Event("input"));
    await submit();

    expect(createHomework).toHaveBeenCalledWith(
      expect.objectContaining({ title: undefined, submission_mode: "mark_done", content_url: "https://example.com/new" }),
    );
  });

  it("показывает последние 5 заданий, остальные - по кнопке", async () => {
    getStudentHomeworkForTutor.mockResolvedValue(
      Array.from({ length: 7 }, (_, i) => homework({ submission_id: `sub-${i}`, title: `Задание ${i + 1}` })),
    );
    mount(StudentHomeworkModal, { props: { studentId: "s-1", studentName: "Пётр" }, attachTo: document.body });
    await flushPromises();

    expect(document.body.textContent).toContain("Задание 5");
    expect(document.body.textContent).not.toContain("Задание 6");

    const more = Array.from(document.body.querySelectorAll("button")).find((b) => b.textContent?.includes("Показать ещё"));
    expect(more!.textContent).toContain("Показать ещё 2");
    more!.click();
    await flushPromises();

    expect(document.body.textContent).toContain("Задание 7");
    expect(Array.from(document.body.querySelectorAll("button")).some((b) => b.textContent?.includes("Показать ещё"))).toBe(false);
  });

  describe("материал: ссылка или файл", () => {
    async function mountWithLast(contentType: "link" | "file") {
      getStudentHomeworkForTutor.mockResolvedValue([homework({ content_type: contentType })]);
      mount(StudentHomeworkModal, { props: { studentId: "s-1", studentName: "Пётр" }, attachTo: document.body });
      await flushPromises();
      await openForm();
    }

    it("на экране только одно поле, вид - как в прошлом задании", async () => {
      await mountWithLast("file");

      expect(kindButton("Файл").getAttribute("aria-checked")).toBe("true");
      expect(linkInput()).toBeNull();
      expect(document.body.querySelector('input[type="file"]')).not.toBeNull();
    });

    it("с файлом отправляется только файл, без пустой ссылки", async () => {
      await mountWithLast("file");
      await chooseFile("task.pdf", "application/pdf");
      await submit();

      const payload = createHomework.mock.calls[0][0];
      expect((payload.file as File).name).toBe("task.pdf");
      expect(payload).not.toHaveProperty("content_url");
    });

    it("переключение вида очищает введённое", async () => {
      await mountWithLast("link");
      const link = linkInput()!;
      link.value = "https://example.com/x";
      link.dispatchEvent(new Event("input"));
      await flushPromises();

      kindButton("Файл").click();
      await flushPromises();
      kindButton("Ссылка").click();
      await flushPromises();

      expect(linkInput()!.value).toBe("");
    });

    it("неподходящий файл отсеивается до отправки, с понятной причиной", async () => {
      await mountWithLast("file");
      await chooseFile("tasks.rar", "application/vnd.rar");

      expect(document.body.textContent).toContain("Такой файл не подойдёт (.rar)");
      await submit();
      expect(createHomework).not.toHaveBeenCalled();
    });

    it("без материала не отправляет", async () => {
      await mountWithLast("file");
      await submit();

      expect(createHomework).not.toHaveBeenCalled();
      expect(document.body.textContent).toContain("Выберите файл с материалом.");
    });

    it("показывает настоящую причину отказа сервера", async () => {
      createHomework.mockRejectedValueOnce(
        new AxiosError("Bad Request", "ERR_BAD_REQUEST", undefined, undefined, {
          status: 400,
          data: { detail: "Файл больше 20 МБ" },
        } as AxiosResponse),
      );
      await mountWithLast("file");
      await chooseFile("task.pdf", "application/pdf");
      await submit();

      expect(document.body.textContent).toContain("Файл больше 20 МБ");
      expect(document.body.textContent).not.toContain("укажите ссылку или файл");
    });
  });
});
