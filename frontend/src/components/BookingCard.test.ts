import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BookingCard from "@/components/BookingCard.vue";
import type { Booking } from "@/types/booking";

const updateBooking = vi.fn(async (_id: string, _payload: Record<string, unknown>) => ({}));

vi.mock("@/api/bookings", () => ({
  cancelBooking: vi.fn(),
  deleteBooking: vi.fn(),
  updateBooking: (id: string, payload: Record<string, unknown>) => updateBooking(id, payload),
}));
vi.mock("@/api/whiteboards", () => ({ markWhiteboardUsed: vi.fn(async () => ({})) }));

function booking(overrides: Partial<Booking> = {}): Booking {
  return {
    id: "bk-1", tutor_id: "t-1", student_id: "s-1", lesson_type_id: "lt-1",
    start_at: "2099-01-05T15:00:00Z", end_at: "2099-01-05T16:00:00Z", status: "scheduled",
    is_manual_block: false, booked_by: "tutor", meeting_link: null, notes: null, recurring_series_id: null,
    cancelled_by: null, cancelled_at: null, cancel_reason: null, rescheduled_from_id: null, outcome: null,
    student_display_name: "Петров Пётр", ...overrides,
  };
}

describe("BookingCard: примечание к занятию", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActivePinia(createPinia());
  });

  it("репетитор добавляет примечание прямо в карточке", async () => {
    const wrapper = mount(BookingCard, { props: { booking: booking(), role: "tutor" } });

    await wrapper.findAll("button").find((b) => b.text().includes("Добавить примечание"))!.trigger("click");
    await wrapper.find("textarea").setValue("начать с проверки ДЗ");
    await wrapper.findAll("button").find((b) => b.text() === "Сохранить")!.trigger("click");
    await flushPromises();

    expect(updateBooking).toHaveBeenCalledWith("bk-1", { notes: "начать с проверки ДЗ" });
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });

  it("ссылка «Добавить примечание» - в строке с «Управление занятием», справа", async () => {
    const wrapper = mount(BookingCard, { props: { booking: booking(), role: "tutor" } });
    const add = wrapper.findAll("button").find((b) => b.text().includes("Добавить примечание"))!;
    const manage = wrapper.findAll("button").find((b) => b.text().includes("Управление занятием"))!;

    expect(add.element.parentElement).toBe(manage.element.parentElement);
    expect(add.element.parentElement!.lastElementChild).toBe(add.element);
    expect(add.element.parentElement!.className).toContain("justify-between");

    // Пока примечание правится, ссылка не нужна; у занятия с примечанием её тоже нет.
    await add.trigger("click");
    expect(wrapper.find("textarea").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("Добавить примечание");

    await wrapper.setProps({ booking: booking({ notes: "есть" }) });
    await wrapper.findAll("button").find((b) => b.text() === "Отмена")!.trigger("click");
    expect(wrapper.text()).not.toContain("Добавить примечание");
    expect(wrapper.text()).toContain("есть");
  });

  it("ученику примечание и редактор не показываются", () => {
    // Сервер ученику примечание не отдаёт; карточка на всякий случай тоже молчит.
    const wrapper = mount(BookingCard, { props: { booking: booking({ notes: "секрет" }), role: "student" } });

    expect(wrapper.text()).not.toContain("секрет");
    expect(wrapper.text()).not.toContain("примечание");
  });
});
