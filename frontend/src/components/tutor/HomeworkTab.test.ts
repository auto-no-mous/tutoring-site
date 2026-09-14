import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomeworkTab from "@/components/tutor/HomeworkTab.vue";

const listMyAssignments = vi.fn();
const setSubmissionStatus = vi.fn(async (_submissionId: string, _status: string) => ({}));
const deleteAssignment = vi.fn(async (_assignmentId: string) => undefined);

vi.mock("@/api/homework", () => ({
  listMyAssignments: () => listMyAssignments(),
  setSubmissionStatus: (submissionId: string, status: string) => setSubmissionStatus(submissionId, status),
  deleteAssignment: (assignmentId: string) => deleteAssignment(assignmentId),
  createHomework: vi.fn(async () => []),
  duplicateHomework: vi.fn(async () => []),
  updateHomework: vi.fn(async () => ({})),
}));

vi.mock("@/api/groups", () => ({ listMyGroups: vi.fn(async () => []) }));
vi.mock("@/api/tutors", () => ({ getMyStudents: vi.fn(async () => []) }));
vi.mock("@/stores/notifications", () => ({
  useNotificationsStore: () => ({ refresh: vi.fn() }),
}));

function assignment(overrides: Record<string, unknown> = {}) {
  return {
    id: "a-1",
    tutor_id: "t-1",
    student_id: "s-1",
    group_id: null,
    title: "Скриншоты",
    content_type: "link",
    content_url: "https://example.com/task",
    content_file_path: null,
    submission_mode: "file_upload",
    due_at: null,
    created_at: "2026-09-10T09:00:00Z",
    status: "submitted",
    student_display_name: "Пётр Петров",
    group_name: null,
    submissions: [
      {
        id: "sub-1",
        assignment_id: "a-1",
        student_id: "s-1",
        status: "submitted",
        files: [{ id: "f-1", file_path: "/files/homework-submissions/shot.png", uploaded_at: "2026-09-10T10:00:00Z" }],
        comment: null,
        submitted_at: "2026-09-10T10:00:00Z",
        student_display_name: "Пётр Петров",
      },
    ],
    ...overrides,
  };
}

describe("tutor HomeworkTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMyAssignments.mockResolvedValue([assignment()]);
  });

  it("показывает сдачу с файлом ученика прямо в карточке", async () => {
    // Раньше карточка ничего не умела: чтобы увидеть присланное, нужно было раскрыть
    // «Сдачи», и там был голый идентификатор ученика.
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    expect(wrapper.text()).toContain("Пётр Петров");
    expect(wrapper.text()).toContain("shot.png");
    expect(wrapper.text()).toContain("Выдано 10.09");
  });

  it("меняет статус сдачи прямо из карточки", async () => {
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    const select = wrapper.findAll("select").find((s) => (s.element as HTMLSelectElement).value === "submitted")!;
    await select.setValue("done");
    await flushPromises();

    expect(setSubmissionStatus).toHaveBeenCalledWith("sub-1", "done");
  });

  it("отличает присланное на проверку от проверенного", async () => {
    listMyAssignments.mockResolvedValue([
      assignment({ id: "a-1", status: "submitted" }),
      assignment({ id: "a-2", status: "done" }),
      assignment({ id: "a-3", status: "pending" }),
    ]);
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    const cards = wrapper.findAll("[data-status]");
    expect(cards[0].classes()).toContain("border-l-sky-500");
    expect(cards[1].classes()).toContain("border-l-green-500");
    expect(cards[2].classes()).toContain("border-l-amber-400");
  });
});
