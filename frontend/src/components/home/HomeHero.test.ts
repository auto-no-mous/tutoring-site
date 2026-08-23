import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomeHero from "@/components/home/HomeHero.vue";

const stubs = { RouterLink: { template: "<a><slot /></a>" } };

function mountHero() {
  return mount(HomeHero, { global: { stubs } });
}

// Точки-переключатели идут после кнопок CTA, поэтому берём их по aria-label.
function dots(wrapper: ReturnType<typeof mountHero>) {
  return wrapper.findAll("button[aria-label]");
}

describe("HomeHero", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders both slides at once so the block keeps the taller one's height", () => {
    const wrapper = mountHero();
    const slides = wrapper.findAll("p");
    expect(slides).toHaveLength(2);
    expect(slides[0].text()).toContain("Выберите преподавателя");
    expect(slides[1].text()).toContain("Репетитор может настроить своё расписание");
    // Только активная реплика видима и доступна скринридеру.
    expect(slides[0].attributes("aria-hidden")).toBe("false");
    expect(slides[1].attributes("aria-hidden")).toBe("true");
  });

  it("rotates to the next slide on a timer and wraps around", async () => {
    const wrapper = mountHero();

    vi.advanceTimersByTime(7000);
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll("p")[1].attributes("aria-hidden")).toBe("false");

    vi.advanceTimersByTime(7000);
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll("p")[0].attributes("aria-hidden")).toBe("false");
  });

  it("switches on a dot click and restarts the countdown from that moment", async () => {
    const wrapper = mountHero();

    vi.advanceTimersByTime(5000);
    await dots(wrapper)[1].trigger("click");
    expect(wrapper.findAll("p")[1].attributes("aria-hidden")).toBe("false");

    // Осталось бы 2 с от прежнего таймера - после клика он должен идти заново.
    vi.advanceTimersByTime(2000);
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll("p")[1].attributes("aria-hidden")).toBe("false");
  });

  it("pauses rotation while the block is hovered", async () => {
    const wrapper = mountHero();

    await wrapper.find("div.grid").trigger("mouseenter");
    vi.advanceTimersByTime(21000);
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll("p")[0].attributes("aria-hidden")).toBe("false");

    await wrapper.find("div.grid").trigger("mouseleave");
    vi.advanceTimersByTime(7000);
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll("p")[1].attributes("aria-hidden")).toBe("false");
  });

  it("stops the timer when unmounted", () => {
    const clearSpy = vi.spyOn(window, "clearInterval");
    mountHero().unmount();
    expect(clearSpy).toHaveBeenCalled();
  });
});
