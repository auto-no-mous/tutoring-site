import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import MskTimeNotice from "@/components/MskTimeNotice.vue";
import { useAuthStore } from "@/stores/auth";

function mountNotice(timezone: string) {
  setActivePinia(createPinia());
  useAuthStore().user = { id: "u-1", role: "student", timezone } as never;
  return mount(MskTimeNotice);
}

describe("MskTimeNotice", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("предупреждает о разнице с Москвой", () => {
    // Ученик из МСК+2 переносил занятие "на 14:00", имея в виду своё время, и попадал
    // на 12:00 у репетитора - предупреждение стоит ровно там, где выбирают час.
    const wrapper = mountNotice("Asia/Yekaterinburg");

    expect(wrapper.text()).toContain("Все времена на сайте — московские");
    expect(wrapper.text()).toContain("разница +2 часа");
  });

  it("молчит, когда пояс московский", () => {
    expect(mountNotice("Europe/Moscow").text()).toBe("");
  });

  it("молчит на мусорном значении пояса", () => {
    // Поле годами было свободным текстом, и в базе осело "Chelyabinsk".
    expect(mountNotice("Chelyabinsk").text()).toBe("");
  });
});
