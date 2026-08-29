import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RescheduleModal from "@/components/RescheduleModal.vue";
import { useAuthStore } from "@/stores/auth";
import type { Booking } from "@/types/booking";

const SLOTS = [
  { start_at: "2026-09-02T07:00:00Z", end_at: "2026-09-02T08:00:00Z", available: true, busy: false },
  { start_at: "2026-09-02T09:00:00Z", end_at: "2026-09-02T10:00:00Z", available: true, busy: true },
];

vi.mock("@/api/bookings", () => ({
  getRescheduleDates: vi.fn(async () => ["2026-09-02"]),
  getRescheduleSlots: vi.fn(async () => SLOTS),
  rescheduleBooking: vi.fn(async () => ({})),
}));

vi.mock("@/api/tutors", () => ({
  getMyLessonTypes: vi.fn(async () => [
    { id: "lt-1", tutor_id: "t-1", name: "Занятие", format: "individual", duration_minutes: 60, price: 1000, is_active: true },
  ]),
}));

const booking = {
  id: "b-1",
  lesson_type_id: "lt-1",
  start_at: "2026-09-02T07:00:00Z",
  end_at: "2026-09-02T08:00:00Z",
} as Booking;

function mountAs(role: "tutor" | "student") {
  setActivePinia(createPinia());
  useAuthStore().user = { id: "u-1", role } as never;
  return mount(RescheduleModal, {
    props: { booking },
    // Календарь подменяем кнопкой: дата выбирается так же, как пользователем -
    // через событие компонента, а не вызовом внутренней функции.
    global: {
      stubs: {
        BookingCalendar: {
          template: `<button class="pick-date" @click="$emit('select', '2026-09-02')" />`,
        },
      },
    },
    attachTo: document.body,
  });
}

async function pickDate(): Promise<void> {
  document.body.querySelector<HTMLButtonElement>(".pick-date")!.click();
  await flushPromises();
}

describe("RescheduleModal", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  // Регрессия: пояснение для репетитора было вставлено в цепочку v-if/v-else-if, и
  // сетка слотов оказалась в ветке v-else - то есть переставала рисоваться именно у
  // репетитора. Внешне это выглядело как пустой список времени после выбора даты.
  it("renders the slot grid for a tutor, alongside the explanatory note", async () => {
    mountAs("tutor");
    await flushPromises();
    await pickDate();

    const slotButtons = document.body.querySelectorAll(".grid button");
    expect(slotButtons).toHaveLength(SLOTS.length);
    expect(document.body.textContent).toContain("Показаны все отрезки дня");
  });

  it("marks a busy slot differently but still lets the tutor pick it", async () => {
    mountAs("tutor");
    await flushPromises();
    await pickDate();

    const buttons = [...document.body.querySelectorAll<HTMLButtonElement>(".grid button")];
    const busy = buttons[1];
    expect(busy.className).toContain("border-red-300");
    expect(busy.disabled).toBe(false);
  });

  it("shows the plain grid without the tutor note for a student", async () => {
    mountAs("student");
    await flushPromises();
    await pickDate();

    expect(document.body.querySelectorAll(".grid button")).toHaveLength(SLOTS.length);
    expect(document.body.textContent).not.toContain("Показаны все отрезки дня");
  });
});
