import { flushPromises, mount } from "@vue/test-utils";
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
    expect(field("Ссылка").value).toBe("");
  });

  it("название необязательно", async () => {
    getStudentHomeworkForTutor.mockResolvedValue([]);
    mount(StudentHomeworkModal, { props: { studentId: "s-1", studentName: "Пётр" }, attachTo: document.body });
    await flushPromises();

    const title = field("Название");
    expect(title.value).toBe("");
    expect(title.required).toBe(false);

    const link = field("Ссылка") as HTMLInputElement;
    link.value = "https://example.com/new";
    link.dispatchEvent(new Event("input"));
    document.body.querySelector("form")!.dispatchEvent(new Event("submit"));
    await flushPromises();

    expect(createHomework).toHaveBeenCalledWith(
      expect.objectContaining({ title: undefined, submission_mode: "mark_done", content_url: "https://example.com/new" }),
    );
  });
});
