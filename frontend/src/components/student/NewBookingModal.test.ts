import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BookingWizard from "@/components/BookingWizard.vue";
import NewBookingModal from "@/components/student/NewBookingModal.vue";

const getPublicLessonTypes = vi.fn(async (_id: string): Promise<unknown[]> => []);
vi.mock("@/api/tutors", () => ({ getPublicLessonTypes: (id: string) => getPublicLessonTypes(id) }));

const DAY = 24 * 3600 * 1000;

function booking(tutorId: string, name: string, offsetDays: number, status = "scheduled") {
  const start = new Date(Date.now() + offsetDays * DAY);
  return {
    id: `${tutorId}-${offsetDays}`,
    tutor_id: tutorId,
    tutor_display_name: name,
    student_id: "s-1",
    status,
    is_manual_block: false,
    start_at: start.toISOString(),
    end_at: new Date(start.getTime() + 3600 * 1000).toISOString(),
  };
}

function mountModal(bookings: unknown[]) {
  setActivePinia(createPinia());
  return mount(NewBookingModal, {
    props: { bookings: bookings as never },
    attachTo: document.body,
    global: { stubs: { BookingWizard: true, RouterLink: { template: "<a><slot /></a>" } } },
  });
}

function tutorButtons(): HTMLButtonElement[] {
  return Array.from(document.body.querySelectorAll<HTMLButtonElement>("[data-tutor-list] button"));
}

describe("NewBookingModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("показывает каждого репетитора один раз, сверху - с кем занимались последним", async () => {
    mountModal([
      booking("t-old", "Давний", -30),
      booking("t-recent", "Недавний", -2),
      booking("t-recent", "Недавний", -9),
      booking("t-future", "Только будущее", 5),
      // Отменённое вчерашнее не делает репетитора «последним».
      booking("t-old", "Давний", -1, "cancelled_by_student"),
    ]);
    await flushPromises();

    expect(tutorButtons().map((b) => b.textContent?.split("последнее")[0].split("ближайшее")[0].trim())).toEqual([
      "Недавний",
      "Давний",
      "Только будущее",
    ]);
  });

  it("после выбора репетитора открывает обычную запись с его типами занятий", async () => {
    getPublicLessonTypes.mockResolvedValue([{ id: "lt-1", format: "individual", is_active: true }]);
    const wrapper = mountModal([booking("t-1", "Иванова Анна", -3)]);
    await flushPromises();

    tutorButtons()[0].click();
    await flushPromises();

    expect(getPublicLessonTypes).toHaveBeenCalledWith("t-1");
    const wizard = wrapper.findComponent(BookingWizard);
    expect(wizard.props("tutorId")).toBe("t-1");
    expect(wizard.props("lessonTypes")).toHaveLength(1);

    wizard.vm.$emit("booked");
    expect(wrapper.emitted("booked")).toHaveLength(1);
    wrapper.unmount();
  });

  it("без занятий предлагает каталог", async () => {
    mountModal([]);
    await flushPromises();
    expect(document.body.textContent).toContain("пока не было занятий");
  });
});
