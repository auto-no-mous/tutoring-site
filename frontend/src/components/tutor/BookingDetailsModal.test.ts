import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BookingDetailsModal from "@/components/tutor/BookingDetailsModal.vue";
import type { Booking } from "@/types/booking";

const cancelBooking = vi.fn(async (_id: string) => ({}));
const deleteBooking = vi.fn(async (_id: string) => ({}));
const updateBooking = vi.fn(async (_id: string, _payload: Record<string, unknown>) => ({}));

vi.mock("@/api/bookings", () => ({
  cancelBooking: (id: string) => cancelBooking(id),
  deleteBooking: (id: string) => deleteBooking(id),
  updateBooking: (id: string, payload: Record<string, unknown>) => updateBooking(id, payload),
}));
vi.mock("@/api/whiteboards", () => ({ markWhiteboardUsed: vi.fn(async () => ({})) }));

function booking(overrides: Partial<Booking> = {}): Booking {
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
    meeting_link: "https://meet.example.com/abc",
    notes: null,
    recurring_series_id: null,
    cancelled_by: null,
    cancelled_at: null,
    cancel_reason: null,
    rescheduled_from_id: null,
    outcome: null,
    student_display_name: "Петров Пётр",
    lesson_type_name: "Математика",
    ...overrides,
  };
}

function mountModal(overrides: Partial<Booking> = {}, homeworkStatus: "none" | "pending" | "done" = "pending") {
  return mount(BookingDetailsModal, {
    props: { booking: booking(overrides), studentName: "Петров Пётр", studentGrade: 7, homeworkStatus, whiteboards: [] },
    attachTo: document.body,
    global: { stubs: { StudentHomeworkModal: true, WhiteboardsModal: true, MeetingLinkModal: true } },
  });
}

const body = () => document.body;
const button = (text: string) =>
  Array.from(body().querySelectorAll("button")).find((b) => b.textContent?.trim().includes(text)) as HTMLButtonElement | undefined;

describe("BookingDetailsModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActivePinia(createPinia());
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("показывает ученика, класс, ссылку на занятие и статус ДЗ", async () => {
    mountModal();
    await flushPromises();

    expect(body().textContent).toContain("Петров Пётр");
    expect(body().textContent).toContain("7-й класс");
    expect(body().textContent).toContain("Математика · 60 мин");
    const link = body().querySelector('a[href="https://meet.example.com/abc"]');
    expect(link?.textContent).toContain("Перейти на занятие");
    expect(body().textContent).toContain("есть невыполненное");
  });

  it("у кнопок управления есть подпись и без текста - на узком окне остаются иконки", async () => {
    mountModal();
    await flushPromises();

    for (const label of ["Перенести", "Изменить ссылку", "Изменить длительность", "Отменить занятие"]) {
      const el = body().querySelector(`button[aria-label="${label}"]`);
      expect(el, label).not.toBeNull();
      expect(el!.getAttribute("title")).toBe(label);
    }
  });

  it("без ссылки предлагает её указать", async () => {
    mountModal({ meeting_link: null });
    await flushPromises();

    expect(button("Указать ссылку на занятие")).toBeDefined();
    expect(body().textContent).not.toContain("Перейти на занятие");
  });

  it("отменяет занятие и закрывается", async () => {
    const wrapper = mountModal();
    await flushPromises();

    button("Отменить занятие")!.click();
    await flushPromises();

    expect(cancelBooking).toHaveBeenCalledWith("bk-1");
    expect(wrapper.emitted("changed")).toHaveLength(1);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("передумал отменять - ничего не происходит", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    const wrapper = mountModal();
    await flushPromises();

    button("Отменить занятие")!.click();
    await flushPromises();

    expect(cancelBooking).not.toHaveBeenCalled();
    expect(wrapper.emitted("close")).toBeUndefined();
  });

  it("просит перенос у родителя", async () => {
    const wrapper = mountModal();
    await flushPromises();

    button("Перенести")!.click();

    expect(wrapper.emitted("reschedule-requested")?.[0]?.[0]).toMatchObject({ id: "bk-1" });
  });

  it("меняет длительность", async () => {
    const start = "2099-01-05T15:00:00.000Z";
    mountModal({ start_at: start, end_at: "2099-01-05T16:00:00.000Z" });
    await flushPromises();

    button("Изменить длительность")!.click();
    await flushPromises();
    const input = body().querySelector('input[aria-label="Длительность, минут"]') as HTMLInputElement;
    input.value = "90";
    input.dispatchEvent(new Event("input"));
    button("Сохранить")!.click();
    await flushPromises();

    const [id, payload] = updateBooking.mock.calls[0];
    expect(id).toBe("bk-1");
    expect(payload).toEqual({ end_at: "2099-01-05T16:30:00.000Z" });
  });

  it("у прошедшего занятия нет переноса и отмены", async () => {
    const past = new Date(Date.now() - 3 * 3600 * 1000);
    mountModal({ start_at: past.toISOString(), end_at: new Date(past.getTime() + 3600 * 1000).toISOString() });
    await flushPromises();

    expect(button("Перенести")).toBeUndefined();
    expect(button("Отменить занятие")).toBeUndefined();
    expect(body().textContent).toContain("Занятие уже прошло");
  });

  it("личную блокировку можно только удалить", async () => {
    const wrapper = mountModal({ is_manual_block: true, student_id: null });
    await flushPromises();

    expect(body().textContent).toContain("Личная блокировка");
    expect(button("Перенести")).toBeUndefined();
    button("Удалить")!.click();
    await flushPromises();

    expect(deleteBooking).toHaveBeenCalledWith("bk-1");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });
});
