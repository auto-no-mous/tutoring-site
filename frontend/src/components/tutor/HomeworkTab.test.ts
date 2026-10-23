import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createHomework } from "@/api/homework";
import { getMyStudents } from "@/api/tutors";
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

  it("новое задание берёт название и способ сдачи из последнего, но не материал", async () => {
    listMyAssignments.mockResolvedValue([
      assignment({ id: "a-new", title: "Параграф 12", submission_mode: "file_upload" }),
      assignment({ id: "a-old", title: "Старое", submission_mode: "mark_done" }),
    ]);
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "+ ДЗ")!.trigger("click");

    const form = wrapper.find("form");
    const inputs = form.findAll("input:not([type=file])");
    const linkInput = form.find('input[aria-label="Ссылка на материал"]');
    const titleInput = inputs.find((i) => i.element.closest("label")?.textContent?.includes("Название"))!;
    expect((titleInput.element as HTMLInputElement).value).toBe("Параграф 12");
    expect((linkInput.element as HTMLInputElement).value).toBe("");
    const active = form.findAll("button").find((b) => b.classes().includes("bg-brand-500") && b.attributes("type") === "button");
    expect(active?.text()).toBe("Загрузить файл");
  });

  it("показывает последние 5 заданий, остальные - по кнопке; новый фильтр начинает сначала", async () => {
    listMyAssignments.mockResolvedValue(
      Array.from({ length: 12 }, (_, i) => assignment({ id: `a-${i}`, status: i % 2 ? "done" : "submitted" })),
    );
    const wrapper = mount(HomeworkTab);
    await flushPromises();

    expect(wrapper.findAll("[data-status]")).toHaveLength(5);
    await wrapper.findAll("button").find((b) => b.text().includes("Показать ещё 5"))!.trigger("click");
    expect(wrapper.findAll("[data-status]")).toHaveLength(10);

    await wrapper.findAll("button").find((b) => b.text() === "Фильтры")!.trigger("click");
    const statusFilter = wrapper.findAll("select").find((s) => s.findAll("option").some((o) => o.attributes("value") === "all"))!;
    await statusFilter.setValue("done");

    // Выполненных 6: снова видно 5, а не 10.
    expect(wrapper.findAll("[data-status]")).toHaveLength(5);
    expect(wrapper.findAll("button").find((b) => b.text().includes("Показать ещё"))!.text()).toContain("Показать ещё 1");
  });

  it("материал - ссылка или файл: вид как в прошлом задании, в запрос уходит только он", async () => {
    vi.mocked(getMyStudents).mockResolvedValue([
      { id: "s-1", first_name: "Пётр", last_name: "Петров", grade: 7, last_lesson_at: null },
    ]);
    listMyAssignments.mockResolvedValue([assignment({ content_type: "file", content_url: null })]);
    const wrapper = mount(HomeworkTab, { attachTo: document.body });
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text() === "+ ДЗ")!.trigger("click");

    const form = wrapper.find("form");
    expect(form.find('[role="radio"][aria-checked="true"]').text()).toBe("Файл");
    expect(form.find('input[aria-label="Ссылка на материал"]').exists()).toBe(false);

    const fileInput = form.find('input[type="file"]');
    Object.defineProperty(fileInput.element, "files", {
      value: [new File(["d"], "task.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
    });
    await fileInput.trigger("change");
    // Получатель обязателен - выберем ученика через тот же список, что видит репетитор.
    (wrapper.vm as unknown as { createStudentIds: string[] }).createStudentIds = ["s-1"];
    await form.trigger("submit");
    await flushPromises();

    const payload = vi.mocked(createHomework).mock.calls[0][0];
    expect(payload.file?.name).toBe("task.docx");
    expect(payload).not.toHaveProperty("content_url");
    wrapper.unmount();
  });
});
