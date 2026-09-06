import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BookingCard from "@/components/BookingCard.vue";
import BookingsTab from "@/components/tutor/BookingsTab.vue";

const createManualBooking = vi.fn();
const listTutorBookings = vi.fn(async () => []);
const listMyWhiteboards = vi.fn(async () => []);
const setBookingOutcome = vi.fn(async (_id: string, _outcome: string) => ({}));

vi.mock("@/api/bookings", () => ({
  createManualBooking: (payload: unknown) => createManualBooking(payload),
  listTutorBookings: () => listTutorBookings(),
  setBookingOutcome: (id: string, outcome: string) => setBookingOutcome(id, outcome),
}));

vi.mock("@/api/whiteboards", () => ({
  listMyWhiteboards: () => listMyWhiteboards(),
  markWhiteboardUsed: vi.fn(async () => ({})),
}));

vi.mock("@/api/groups", () => ({
  createOccurrence: vi.fn(async () => ({})),
  listMyGroups: vi.fn(async () => []),
}));

vi.mock("@/api/homework", () => ({
  getMyStudentsHomeworkStatus: vi.fn(async () => ({})),
}));

vi.mock("@/api/tutors", () => ({
  createManagedStudent: vi.fn(async () => ({ id: "s-1" })),
  getManualBookingDates: vi.fn(async () => []),
  getManualBookingSlots: vi.fn(async () => []),
  getMyLessonTypes: vi.fn(async () => [
    {
      id: "lt-1",
      tutor_id: "t-1",
      name: "Занятие",
      format: "individual",
      duration_minutes: 60,
      price: 1000,
      is_active: true,
    },
  ]),
  getMyStudents: vi.fn(async () => []),
}));

// BookingScheduleGroups не заглушается: именно он рендерит слот с карточками, и без
// него до BookingCard дело не доходит.
function mountTab() {
  setActivePinia(createPinia());
  return mount(BookingsTab, {
    global: {
      stubs: {
        BookingCard: true,
        RescheduleModal: true,
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });
}

function bookingAt(offsetHours: number, overrides: Record<string, unknown> = {}) {
  const start = new Date(Date.now() + offsetHours * 3600 * 1000);
  return {
    ...futureBooking(),
    id: `bk-${offsetHours}`,
    start_at: start.toISOString(),
    end_at: new Date(start.getTime() + 3600 * 1000).toISOString(),
    ...overrides,
  };
}

function futureBooking() {
  const start = new Date(Date.now() + 24 * 3600 * 1000);
  return {
    id: "bk-1",
    tutor_id: "t-1",
    student_id: "s-1",
    lesson_type_id: "lt-1",
    start_at: start.toISOString(),
    end_at: new Date(start.getTime() + 3600 * 1000).toISOString(),
    status: "scheduled",
    is_manual_block: false,
    booked_by: "tutor",
    meeting_link: null,
    notes: null,
    recurring_series_id: null,
    cancelled_by: null,
    cancelled_at: null,
    cancel_reason: null,
    rescheduled_from_id: null,
    outcome: null,
    student_display_name: "Петров Пётр",
  };
}

/** Открывает форму и задаёт дату со временем через поля «другая дата/время». */
async function fillForm(wrapper: ReturnType<typeof mountTab>): Promise<void> {
  const button = (text: string) => wrapper.findAll("button").find((b) => b.text().includes(text))!;
  // Кнопки-переключатели панелей называются «Выбрать дату…»/«Выбрать время…», а
  // подтверждение внутри панели - просто «Выбрать»: ищем по точному совпадению,
  // иначе совпадёт переключатель.
  const exactButton = (text: string) =>
    wrapper.findAll("button").find((b) => b.text().trim() === text)!;

  await button("Резерв / запись вручную").trigger("click");
  await button("Выбрать дату").trigger("click");
  await wrapper.find('input[type="date"]').setValue("2099-01-05");
  await exactButton("Выбрать").trigger("click");
  await button("Выбрать время").trigger("click");
  await wrapper.find('input[type="time"]').setValue("18:00");
  await exactButton("Выбрать").trigger("click");
}

describe("BookingsTab: ручная запись", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createManualBooking.mockResolvedValue({});
  });

  it("отправляет allow_overlap булевым, а не событием формы", async () => {
    // Регрессия: обработчик был привязан как @submit.prevent="createBlock", из-за
    // чего первым аргументом приходило событие submit, уезжало в allow_overlap и
    // сервер отвергал любую запись как невалидную.
    const wrapper = mountTab();
    await flushPromises();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(createManualBooking).toHaveBeenCalledTimes(1);
    const payload = createManualBooking.mock.calls[0][0];
    expect(payload.allow_overlap).toBe(false);
    expect(payload.start_at).toMatch(/^2099-01-05T15:00/);
  });

  it("после подтверждения пересечения повторяет запрос с allow_overlap", async () => {
    createManualBooking.mockRejectedValueOnce(
      Object.assign(new Error("conflict"), {
        isAxiosError: true,
        response: { status: 409, data: { detail: "Время пересекается с: 05.01 18:00-19:00 (Иванов Иван)" } },
      }),
    );

    const wrapper = mountTab();
    await flushPromises();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    // Отказ показывается как выбор, а не как ошибка формы.
    expect(wrapper.text()).toContain("Время пересекается с: 05.01 18:00-19:00 (Иванов Иван)");

    const confirm = wrapper.findAll("button").find((b) => b.text() === "Всё равно создать")!;
    await confirm.trigger("click");
    await flushPromises();

    expect(createManualBooking).toHaveBeenCalledTimes(2);
    expect(createManualBooking.mock.calls[1][0].allow_overlap).toBe(true);
  });
});

describe("BookingsTab: доски на карточках", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listTutorBookings.mockResolvedValue([futureBooking()] as never);
    listMyWhiteboards.mockResolvedValue([] as never);
  });

  it("отдаёт карточке доски ученика сразу при открытии вкладки", async () => {
    // Регрессия: список досок грузился только после их правки, поэтому после
    // перезагрузки страницы карточка оставалась без ссылок.
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
    ] as never);

    const wrapper = mountTab();
    await flushPromises();

    expect(listMyWhiteboards).toHaveBeenCalled();
    const card = wrapper.findComponent(BookingCard);
    expect(card.exists()).toBe(true);
    const boards = card.props("whiteboards") ?? [];
    expect(boards).toHaveLength(1);
    expect(boards[0].title).toBe("Алгебра");
  });

  it("не отдаёт карточке чужие доски", async () => {
    listMyWhiteboards.mockResolvedValue([
      {
        id: "wb-2",
        tutor_id: "t-1",
        student_id: "s-2",
        group_id: null,
        url: "https://miro.com/app/board/2",
        title: null,
        last_used_at: "2026-09-01T10:00:00Z",
      },
    ] as never);

    const wrapper = mountTab();
    await flushPromises();

    expect(wrapper.findComponent(BookingCard).props("whiteboards")).toEqual([]);
  });
});

describe("BookingsTab: история занятий", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMyWhiteboards.mockResolvedValue([] as never);
  });

  async function openHistory() {
    const wrapper = mountTab();
    await flushPromises();
    const button = wrapper.findAll("button").find((b) => b.text() === "История занятий")!;
    await button.trigger("click");
    return wrapper;
  }

  it("показывает только прошедшие состоявшиеся занятия, свежие сверху", async () => {
    listTutorBookings.mockResolvedValue([
      bookingAt(-24, { id: "вчера", student_display_name: "Вчерашний" }),
      bookingAt(-24 * 7, { id: "неделю назад", student_display_name: "Давний" }),
      bookingAt(48, { id: "будущее", student_display_name: "Будущий" }),
      // Ровно случай из жалобы: отмена занятия, которое было бы через два месяца,
      // не должна оказываться в истории, да ещё и сверху.
      bookingAt(24 * 60, {
        id: "отменённое будущее",
        status: "cancelled_by_student",
        student_display_name: "Отменивший",
      }),
    ] as never);

    const wrapper = await openHistory();
    const text = wrapper.text();

    expect(text).toContain("Вчерашний");
    expect(text).toContain("Давний");
    expect(text).not.toContain("Будущий");
    expect(text).not.toContain("Отменивший");
    expect(text.indexOf("Вчерашний")).toBeLessThan(text.indexOf("Давний"));
  });

  it("прячет расписание, пока открыта история, и возвращает обратно", async () => {
    listTutorBookings.mockResolvedValue([bookingAt(48, { student_display_name: "Будущий" })] as never);

    const wrapper = await openHistory();
    expect(wrapper.findComponent(BookingCard).exists()).toBe(false);

    const back = wrapper.findAll("button").find((b) => b.text().includes("К расписанию"))!;
    await back.trigger("click");
    expect(wrapper.findComponent(BookingCard).exists()).toBe(true);
  });

  it("по фильтру показывает отменённые", async () => {
    listTutorBookings.mockResolvedValue([
      bookingAt(-24, { id: "состоялось", student_display_name: "Пришедший" }),
      bookingAt(-48, {
        id: "отменено",
        status: "cancelled_by_tutor",
        student_display_name: "Отменённый",
      }),
    ] as never);

    const wrapper = await openHistory();
    expect(wrapper.text()).not.toContain("Отменённый");

    const filter = wrapper.findAll("button").find((b) => b.text().includes("Отменённые"))!;
    await filter.trigger("click");

    expect(wrapper.text()).toContain("Отменённый");
    expect(wrapper.text()).not.toContain("Пришедший");
  });

  it("позволяет отметить, что ученик не явился", async () => {
    listTutorBookings.mockResolvedValue([
      bookingAt(-24, { id: "bk-past", student_display_name: "Прогульщик" }),
    ] as never);

    const wrapper = await openHistory();
    const select = wrapper.find("select");
    expect(select.exists()).toBe(true);

    await select.setValue("student_no_show");
    await flushPromises();

    expect(setBookingOutcome).toHaveBeenCalledWith("bk-past", "student_no_show");
  });
});
