import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Component } from "vue";

import TutorBookingButtons from "@/components/tutor/TutorBookingButtons.vue";
import TutorContactRow from "@/components/tutor/TutorContactRow.vue";
import { useAuthStore } from "@/stores/auth";
import type { TutorPublicProfile } from "@/types/tutor";

const push = vi.fn();
const openThreadWithTutor = vi.fn(async (_tutorId: string) => ({ id: "thread-1" }));

vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/api/chat", () => ({
  openThreadWithTutor: (tutorId: string) => openThreadWithTutor(tutorId),
}));

function makeProfile(overrides: Partial<TutorPublicProfile> = {}): TutorPublicProfile {
  return {
    id: "t-1",
    display_name: "Петров Пётр",
    telegram_url: null,
    vk_url: null,
    youtube_url: null,
    extra_links: [],
    show_individual_booking: true,
    show_group_booking: true,
    subjects: [],
    ...overrides,
  } as TutorPublicProfile;
}

// Оба компонента принимают один и тот же проп, поэтому монтируются общим хелпером;
// точный тип компонента здесь не нужен, а generic-сигнатура mount его не выводит.
function mountAs(component: Component, profile: TutorPublicProfile, role?: "student" | "tutor") {
  setActivePinia(createPinia());
  useAuthStore().user = role ? ({ id: "u-1", role } as never) : null;
  return mount(component, {
    props: { profile },
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  } as never);
}

describe("TutorBookingButtons", () => {
  it("показывает только разрешённые репетитором способы записи", () => {
    const both = mountAs(TutorBookingButtons, makeProfile());
    expect(both.text()).toContain("Запись на индивидуальное занятие");
    expect(both.text()).toContain("Запись на групповое занятие");

    const individualOnly = mountAs(
      TutorBookingButtons,
      makeProfile({ show_group_booking: false }),
    );
    expect(individualOnly.text()).toContain("Запись на индивидуальное занятие");
    expect(individualOnly.text()).not.toContain("Запись на групповое занятие");
  });

  it("не рисует пустой блок, когда запись выключена целиком", () => {
    const wrapper = mountAs(
      TutorBookingButtons,
      makeProfile({ show_individual_booking: false, show_group_booking: false }),
    );
    // Блок оформлен как карточка на странице профиля - пустая выглядела бы ошибкой.
    expect(wrapper.find("div").exists()).toBe(false);
  });
});

describe("TutorContactRow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("предлагает написать только ученику", () => {
    const forStudent = mountAs(TutorContactRow, makeProfile(), "student");
    expect(forStudent.text()).toContain("Написать личное сообщение");

    const forGuest = mountAs(TutorContactRow, makeProfile());
    expect(forGuest.find("button").exists()).toBe(false);
  });

  it("открывает чат с репетитором и уводит в кабинет", async () => {
    const wrapper = mountAs(TutorContactRow, makeProfile(), "student");
    await wrapper.find("button").trigger("click");
    await vi.waitFor(() => expect(push).toHaveBeenCalled());

    expect(openThreadWithTutor).toHaveBeenCalledWith("t-1");
    expect(push).toHaveBeenCalledWith({
      path: "/cabinet",
      query: { tab: "chat", thread: "thread-1" },
    });
  });

  it("исчезает целиком, когда нет ни ссылок, ни кнопки", () => {
    const wrapper = mountAs(TutorContactRow, makeProfile(), "tutor");
    expect(wrapper.find("div").exists()).toBe(false);
  });

  it("показывает ссылки на соцсети гостю", () => {
    const wrapper = mountAs(TutorContactRow, makeProfile({ vk_url: "https://vk.com/tutor" }));
    expect(wrapper.find('a[href="https://vk.com/tutor"]').exists()).toBe(true);
  });
});
