import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StudentsBlock from "@/components/tutor/StudentsBlock.vue";
import UserAvatar from "@/components/UserAvatar.vue";

const getMyStudentsWithStats = vi.fn();
const listMyWhiteboards = vi.fn();

const setStudentMeetingLink = vi.fn(async (_id: string, _url: string | null) => undefined);

vi.mock("@/api/tutors", () => ({
  getMyStudentsWithStats: () => getMyStudentsWithStats(),
  setStudentMeetingLink: (id: string, url: string | null) => setStudentMeetingLink(id, url),
  createManagedStudent: vi.fn(async () => ({})),
  updateManagedStudent: vi.fn(async () => ({})),
  deleteManagedStudent: vi.fn(async () => undefined),
  setStudentNote: vi.fn(async () => undefined),
  createClaimLink: vi.fn(async () => ({ url: "", expires_at: "" })),
  getMyLessonTypes: vi.fn(async () => []),
}));

vi.mock("@/api/bookings", () => ({
  listTutorRecurringSeries: vi.fn(async () => []),
  createManualBooking: vi.fn(async () => ({})),
  stopSeries: vi.fn(async () => ({})),
}));

vi.mock("@/api/whiteboards", () => ({
  listMyWhiteboards: () => listMyWhiteboards(),
  markWhiteboardUsed: vi.fn(async () => ({})),
  createWhiteboard: vi.fn(async () => ({})),
  updateWhiteboard: vi.fn(async () => ({})),
  deleteWhiteboard: vi.fn(async () => undefined),
}));

function student(overrides: Record<string, unknown> = {}) {
  return {
    id: "s-1",
    first_name: "Пётр",
    last_name: "Петров",
    patronymic: null,
    grade: 9,
    photo_url: null,
    is_managed: false,
    has_login: true,
    note: null,
    meeting_link: null,
    lessons_held: 3,
    no_shows: 0,
    last_lesson_at: "2026-09-01T10:00:00Z",
    next_lesson_at: null,
    homework_done: 0,
    homework_pending: 0,
    ...overrides,
  };
}

function mountBlock() {
  return mount(StudentsBlock, {
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  });
}

async function chooseSort(wrapper: ReturnType<typeof mountBlock>, label: string) {
  const select = wrapper.find("select");
  const option = select.findAll("option").find((o) => o.text().includes(label))!;
  await select.setValue(option.element.value);
}

describe("StudentsBlock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMyWhiteboards.mockResolvedValue([]);
    getMyStudentsWithStats.mockResolvedValue([student()]);
  });

  it("рисует кружок с буквой, когда у ученика нет фото", async () => {
    getMyStudentsWithStats.mockResolvedValue([
      student({ id: "s-1", first_name: "Пётр", photo_url: null }),
      student({ id: "s-2", first_name: "Анна", photo_url: "/files/user-photos/a.jpg" }),
    ]);

    const wrapper = mountBlock();
    await flushPromises();

    const avatars = wrapper.findAllComponents(UserAvatar);
    expect(avatars).toHaveLength(2);
    expect(avatars[0].text()).toBe("П");
    expect(avatars[1].find("img").exists()).toBe(true);
  });

  it("сортирует по ФИО, числу занятий и последнему занятию", async () => {
    getMyStudentsWithStats.mockResolvedValue([
      student({ id: "b", last_name: "Борисов", first_name: "Борис", lessons_held: 1, last_lesson_at: "2026-09-05T10:00:00Z" }),
      student({ id: "a", last_name: "Абрамов", first_name: "Антон", lessons_held: 9, last_lesson_at: "2026-08-01T10:00:00Z" }),
    ]);

    const wrapper = mountBlock();
    await flushPromises();

    await chooseSort(wrapper, "По ФИО");
    let names = wrapper.findAllComponents(UserAvatar).map((a) => a.props("name"));
    expect(names).toEqual(["Антон", "Борис"]);

    await chooseSort(wrapper, "По числу занятий");
    names = wrapper.findAllComponents(UserAvatar).map((a) => a.props("name"));
    expect(names).toEqual(["Антон", "Борис"]);

    await chooseSort(wrapper, "По последнему занятию");
    names = wrapper.findAllComponents(UserAvatar).map((a) => a.props("name"));
    expect(names).toEqual(["Борис", "Антон"]);
  });

  it("даёт поменять постоянную ссылку прямо в списке", async () => {
    getMyStudentsWithStats.mockResolvedValue([
      student({ meeting_link: "https://meet.example.com/old" }),
    ]);

    const wrapper = mountBlock();
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "изменить")!.trigger("click");
    await wrapper.find('input[type="url"]').setValue("https://meet.example.com/new");
    await wrapper.findAll("button").find((b) => b.text() === "Сохранить")!.trigger("click");
    await flushPromises();

    expect(setStudentMeetingLink).toHaveBeenCalledWith("s-1", "https://meet.example.com/new");
  });

  it("пустым полем снимает постоянную ссылку", async () => {
    getMyStudentsWithStats.mockResolvedValue([
      student({ meeting_link: "https://meet.example.com/old" }),
    ]);

    const wrapper = mountBlock();
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "изменить")!.trigger("click");
    await wrapper.find('input[type="url"]').setValue("   ");
    await wrapper.findAll("button").find((b) => b.text() === "Сохранить")!.trigger("click");
    await flushPromises();

    expect(setStudentMeetingLink).toHaveBeenCalledWith("s-1", null);
  });

  it("показывает постоянную ссылку на занятие и доски ученика", async () => {
    getMyStudentsWithStats.mockResolvedValue([
      student({ meeting_link: "https://meet.example.com/room" }),
    ]);
    listMyWhiteboards.mockResolvedValue([
      {
        id: "wb-1",
        tutor_id: "t-1",
        student_id: "s-1",
        group_id: null,
        url: "https://miro.com/app/board/1",
        title: "Алгебра",
        last_used_at: "2026-09-01T10:00:00Z",
      },
      // Чужая доска в карточку попадать не должна.
      {
        id: "wb-2",
        tutor_id: "t-1",
        student_id: "s-9",
        group_id: null,
        url: "https://miro.com/app/board/2",
        title: "Чужая",
        last_used_at: "2026-09-01T10:00:00Z",
      },
    ]);

    const wrapper = mountBlock();
    await flushPromises();

    // Ссылка показана текстом, а не кнопкой: её надо видеть целиком.
    const link = wrapper.find('a[href="https://meet.example.com/room"]');
    expect(link.exists()).toBe(true);
    expect(link.text()).toBe("https://meet.example.com/room");
    expect(wrapper.text()).toContain("Постоянная ссылка на занятие:");
    expect(wrapper.text()).toContain("Алгебра");
    expect(wrapper.text()).not.toContain("Чужая");
  });
});
