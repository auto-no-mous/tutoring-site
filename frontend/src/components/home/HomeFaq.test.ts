import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";

import HomeFaq from "@/components/home/HomeFaq.vue";

const stubs = { RouterLink: { template: "<a><slot /></a>" } };

function schemaEl(): HTMLScriptElement | null {
  return document.querySelector<HTMLScriptElement>('script[type="application/ld+json"]');
}

describe("HomeFaq", () => {
  afterEach(() => {
    schemaEl()?.remove();
  });

  it("starts with every answer collapsed and opens one at a time", async () => {
    const wrapper = mount(HomeFaq, { global: { stubs } });
    const questions = wrapper.findAll("button");
    expect(questions.length).toBeGreaterThan(1);
    expect(questions.every((q) => q.attributes("aria-expanded") === "false")).toBe(true);

    await questions[0].trigger("click");
    expect(wrapper.findAll("button")[0].attributes("aria-expanded")).toBe("true");

    await wrapper.findAll("button")[1].trigger("click");
    const after = wrapper.findAll("button");
    expect(after[0].attributes("aria-expanded")).toBe("false");
    expect(after[1].attributes("aria-expanded")).toBe("true");
  });

  it("collapses an open answer when its question is clicked again", async () => {
    const wrapper = mount(HomeFaq, { global: { stubs } });
    await wrapper.findAll("button")[0].trigger("click");
    await wrapper.findAll("button")[0].trigger("click");
    expect(wrapper.findAll("button")[0].attributes("aria-expanded")).toBe("false");
  });

  it("publishes FAQPage structured data and cleans it up on unmount", () => {
    const wrapper = mount(HomeFaq, { global: { stubs } });

    const schema = JSON.parse(schemaEl()!.textContent!);
    expect(schema["@type"]).toBe("FAQPage");
    expect(schema.mainEntity).toHaveLength(wrapper.findAll("button").length);
    expect(schema.mainEntity[0].acceptedAnswer.text).toBeTruthy();

    wrapper.unmount();
    expect(schemaEl()).toBeNull();
  });
});
