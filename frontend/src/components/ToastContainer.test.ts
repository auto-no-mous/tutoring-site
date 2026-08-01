import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import ToastContainer from "@/components/ToastContainer.vue";
import { useToastStore } from "@/stores/toast";

describe("ToastContainer", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders nothing when there are no toasts", () => {
    const wrapper = mount(ToastContainer);
    expect(wrapper.text()).toBe("");
  });

  it("renders a toast's message once shown", async () => {
    const wrapper = mount(ToastContainer);
    const store = useToastStore();
    store.show("Занятие перенесено");
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("Занятие перенесено");
  });
});
