import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SupportTab from "@/components/admin/SupportTab.vue";
import ChatPanel from "@/components/ChatPanel.vue";

const listSupportStaff = vi.fn();
const addSupportStaff = vi.fn(async (_email: string) => ({}));
const removeSupportStaff = vi.fn(async (_id: string) => undefined);

vi.mock("@/api/admin", () => ({
  listSupportStaff: () => listSupportStaff(),
  addSupportStaff: (email: string) => addSupportStaff(email),
  removeSupportStaff: (id: string) => removeSupportStaff(id),
}));

function mountTab() {
  return mount(SupportTab, { global: { stubs: { ChatPanel: true } } });
}

describe("admin SupportTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSupportStaff.mockResolvedValue([
      { id: "u-7", display_name: "Киселёв Александр", email: "alex@example.com", role: "tutor" },
    ]);
  });

  it("показывает назначенных и даёт назначить ещё одного по почте", async () => {
    const wrapper = mountTab();
    await flushPromises();
    expect(wrapper.find("[data-support-staff]").text()).toContain("Киселёв Александр");

    await wrapper.find('input[type="email"]').setValue("helper@example.com");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(addSupportStaff).toHaveBeenCalledWith("helper@example.com");
    expect(listSupportStaff).toHaveBeenCalledTimes(2);
  });

  it("снимает с поддержки после подтверждения", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "Снять")!.trigger("click");
    await flushPromises();
    expect(removeSupportStaff).toHaveBeenCalledWith("u-7");
  });

  it("показывает обращения только из поддержки", async () => {
    const wrapper = mountTab();
    await flushPromises();
    expect(wrapper.findComponent(ChatPanel).props("supportOnly")).toBe(true);
  });
});
