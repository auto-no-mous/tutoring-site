import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BookingsTab from "@/components/tutor/BookingsTab.vue";

const createManualBooking = vi.fn();

vi.mock("@/api/bookings", () => ({
  createManualBooking: (payload: unknown) => createManualBooking(payload),
  listTutorBookings: vi.fn(async () => []),
  setBookingOutcome: vi.fn(async () => ({})),
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

function mountTab() {
  setActivePinia(createPinia());
  return mount(BookingsTab, {
    global: {
      stubs: {
        BookingCard: true,
        BookingScheduleGroups: true,
        RescheduleModal: true,
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });
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
