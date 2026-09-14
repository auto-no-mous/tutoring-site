import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomeworkTab from "@/components/student/HomeworkTab.vue";

const myHomework = vi.fn();
const deleteSubmissionFile = vi.fn(async (_submissionId: string, _fileId: string) => ({}));
const uploadSubmission = vi.fn(async (_submissionId: string, _file: File) => ({}));

vi.mock("@/api/homework", () => ({
  myHomework: () => myHomework(),
  deleteSubmissionFile: (submissionId: string, fileId: string) => deleteSubmissionFile(submissionId, fileId),
  uploadSubmission: (submissionId: string, file: File) => uploadSubmission(submissionId, file),
  markDone: vi.fn(async () => ({})),
}));

vi.mock("@/stores/notifications", () => ({
  useNotificationsStore: () => ({ refresh: vi.fn() }),
}));

function homework(overrides: Record<string, unknown> = {}) {
  return {
    submission_id: "sub-1",
    assignment_id: "a-1",
    tutor_id: "t-1",
    group_id: null,
    title: "Скриншоты",
    content_type: "link",
    content_url: "https://example.com/task",
    content_file_path: null,
    submission_mode: "file_upload",
    due_at: null,
    status: "submitted",
    files: [
      { id: "f-1", file_path: "/files/homework-submissions/first.png", uploaded_at: "2026-09-10T10:00:00Z" },
      { id: "f-2", file_path: "/files/homework-submissions/second.png", uploaded_at: "2026-09-10T11:00:00Z" },
    ],
    comment: null,
    submitted_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

describe("student HomeworkTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    myHomework.mockResolvedValue([homework()]);
  });

  it("показывает все присланные файлы и даёт убрать лишний", async () => {
    // Раньше файл был один: приложив не тот скриншот, ученик уже ничего не мог сделать.
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    expect(wrapper.text()).toContain("first.png");
    expect(wrapper.text()).toContain("second.png");

    await wrapper.findAll('button[title="Убрать файл"]')[0].trigger("click");
    await flushPromises();

    expect(deleteSubmissionFile).toHaveBeenCalledWith("sub-1", "f-1");
  });

  it("даёт добавить ещё один файл к уже отправленным", async () => {
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    expect(wrapper.findAll("button").some((b) => b.text() === "Добавить файл")).toBe(true);
  });

  it("проверенную работу менять нельзя", async () => {
    myHomework.mockResolvedValue([homework({ status: "done" })]);
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    expect(wrapper.find('button[title="Убрать файл"]').exists()).toBe(false);
    expect(wrapper.findAll("button").some((b) => b.text().includes("файл"))).toBe(false);
  });

  it("красит карточку по статусу", async () => {
    myHomework.mockResolvedValue([
      homework({ submission_id: "sub-1", status: "pending", files: [] }),
      homework({ submission_id: "sub-2", status: "submitted" }),
      homework({ submission_id: "sub-3", status: "done" }),
    ]);
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    const cards = wrapper.findAll("[data-status]");
    expect(cards[0].classes()).toContain("border-l-amber-400");
    expect(cards[1].classes()).toContain("border-l-sky-500");
    expect(cards[2].classes()).toContain("border-l-green-500");
  });
});
