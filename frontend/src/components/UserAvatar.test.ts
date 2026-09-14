import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import UserAvatar from "@/components/UserAvatar.vue";

describe("UserAvatar", () => {
  it("показывает фото, когда оно есть", () => {
    const wrapper = mount(UserAvatar, {
      props: { photoUrl: "/files/user-photos/a.jpg", name: "Пётр" },
    });

    expect(wrapper.find("img").attributes("src")).toBe("/files/user-photos/a.jpg");
  });

  it("без фото рисует кружок с первой буквой имени", () => {
    // Фото есть только у тех, кто вошёл через VK или Яндекс либо загрузил его сам,
    // и без запасного варианта список выглядел рваным.
    const wrapper = mount(UserAvatar, { props: { photoUrl: null, name: "пётр" } });

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toBe("П");
  });

  it("не падает без имени", () => {
    const wrapper = mount(UserAvatar, { props: { photoUrl: null, name: "  " } });
    expect(wrapper.text()).toBe("?");
  });
});
