import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BookingCard from "@/components/BookingCard.vue";
import GroupOccurrenceCard from "@/components/GroupOccurrenceCard.vue";
import BookingsTab from "@/components/student/BookingsTab.vue";
import ScheduleItemModal from "@/components/student/ScheduleItemModal.vue";

const listMyBookings = vi.fn(async (): Promise<unknown[]> => []);
const myOccurrences = vi.fn(async (): Promise<unknown[]> => []);

vi.mock("@/api/bookings", () => ({ listMyBookings: () => listMyBookings() }));
vi.mock("@/api/groups", () => ({ myOccurrences: () => myOccurrences(), markOwnNoShow: vi.fn() }));
vi.mock("@/api/whiteboards", () => ({ listMyWhiteboards: vi.fn(async () => []) }));

function at(offsetHours: number): { start_at: string; end_at: string } {
  const start = new Date(Date.now() + offsetHours * 3600 * 1000);
  return { start_at: start.toISOString(), end_at: new Date(start.getTime() + 3600 * 1000).toISOString() };
}

function booking(offsetHours: number, overrides: Record<string, unknown> = {}) {
  return {
    id: `bk-${offsetHours}`,
    tutor_id: "t-1",
    student_id: "s-1",
    lesson_type_id: "lt-1",
    status: "scheduled",
    is_manual_block: false,
    booked_by: "student",
    meeting_link: null,
    notes: null,
    recurring_series_id: null,
    cancelled_by: null,
    cancelled_at: null,
    cancel_reason: null,
    rescheduled_from_id: null,
    outcome: null,
    lesson_type_name: "Математика",
    tutor_display_name: "Иванова Анна",
    ...at(offsetHours),
    ...overrides,
  };
}

function occurrence(offsetHours: number, overrides: Record<string, unknown> = {}) {
  return {
    id: `occ-${offsetHours}`,
    group_id: "g-1",
    status: "scheduled",
    original_start_at: null,
    group_name: "ЕГЭ-11",
    tutor_display_name: "Иванова Анна",
    meeting_link: null,
    my_attendance_outcome: null,
    ...at(offsetHours),
    ...overrides,
  };
}

function mountTab() {
  setActivePinia(createPinia());
  return mount(BookingsTab, {
    global: { stubs: { BookingCard: true, GroupOccurrenceCard: true, ScheduleItemModal: { props: ["startAt", "endAt", "isGroup"], template: "<div><slot /></div>" }, RescheduleModal: true } },
  });
}

const toggle = (wrapper: ReturnType<typeof mountTab>, label: string) =>
  wrapper.find('[aria-label="Вид расписания"]').findAll("button").find((b) => b.text() === label)!;

describe("student BookingsTab: недельный вид", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    listMyBookings.mockResolvedValue([booking(2)]);
    myOccurrences.mockResolvedValue([occurrence(3), occurrence(4, { id: "occ-cancelled", status: "cancelled", group_name: "Отменённая" })]);
  });

  it("по умолчанию - список, переключается на неделю и запоминает выбор", async () => {
    const wrapper = mountTab();
    await flushPromises();
    expect(wrapper.find("[data-week]").exists()).toBe(false);

    await toggle(wrapper, "Неделя").trigger("click");
    expect(wrapper.findAll("[data-week]").length).toBeGreaterThan(0);
    expect(wrapper.find("[data-day]").exists()).toBe(true);
    expect(localStorage.getItem("student-bookings-layout")).toBe("week");
  });

  it("в сетке и индивидуальные занятия, и занятия групп, без отменённых", async () => {
    localStorage.setItem("student-bookings-layout", "week");
    const wrapper = mountTab();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("Иванова Анна");
    expect(text).toContain("Группа «ЕГЭ-11»");
    expect(text).not.toContain("Отменённая");
    expect(wrapper.findAll("[data-group-occurrence]")).toHaveLength(1);
  });

  it("по клику открывает окно с карточкой занятия", async () => {
    localStorage.setItem("student-bookings-layout", "week");
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.find("[data-group-occurrence]").trigger("click");
    expect(wrapper.findComponent(ScheduleItemModal).props("isGroup")).toBe(true);
    expect(wrapper.findComponent(GroupOccurrenceCard).props("occurrence").id).toBe("occ-3");

    wrapper.findComponent(ScheduleItemModal).vm.$emit("close");
    await flushPromises();
    expect(wrapper.findComponent(ScheduleItemModal).exists()).toBe(false);

    const bookingRow = wrapper.findAll("[data-day] button").find((b) => b.text().includes("Математика"))!;
    await bookingRow.trigger("click");
    expect(wrapper.findComponent(BookingCard).props("booking").id).toBe("bk-2");
  });
});
