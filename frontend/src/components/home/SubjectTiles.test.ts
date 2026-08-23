import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import SubjectTiles from "@/components/home/SubjectTiles.vue";
import type { CatalogSubject } from "@/types/subject";

function subject(name: string, tutorsCount: number): CatalogSubject {
  return { id: `id-${name}`, name, directions: [], tutors_count: tutorsCount };
}

describe("SubjectTiles", () => {
  it("hides subjects nobody teaches and puts the busiest first", () => {
    const wrapper = mount(SubjectTiles, {
      props: {
        subjects: [subject("Музыка", 0), subject("Химия", 1), subject("Математика", 3)],
        selectedId: "",
      },
    });

    const tiles = wrapper.findAll("button");
    expect(tiles).toHaveLength(2);
    expect(tiles[0].text()).toContain("Математика");
    expect(tiles[1].text()).toContain("Химия");
    expect(wrapper.text()).not.toContain("Музыка");
  });

  it("renders nothing at all when no subject has tutors", () => {
    const wrapper = mount(SubjectTiles, {
      props: { subjects: [subject("Музыка", 0)], selectedId: "" },
    });
    expect(wrapper.find("section").exists()).toBe(false);
  });

  it("pluralizes the tutor count in Russian", () => {
    const wrapper = mount(SubjectTiles, {
      props: {
        subjects: [subject("A", 1), subject("B", 3), subject("C", 11), subject("D", 21)],
        selectedId: "",
      },
    });
    const text = wrapper.text();
    expect(text).toContain("21 репетитор");
    expect(text).toContain("3 репетитора");
    expect(text).toContain("11 репетиторов");
    // 1 -> singular, and it must not be swallowed by the "21 репетитор" match above.
    expect(wrapper.findAll("button")[3].text()).toContain("1 репетитор");
  });

  it("emits the subject id on click and an empty id when the selected tile is clicked again", async () => {
    const wrapper = mount(SubjectTiles, {
      props: { subjects: [subject("Математика", 2)], selectedId: "" },
    });

    await wrapper.find("button").trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual(["id-Математика"]);

    await wrapper.setProps({ selectedId: "id-Математика" });
    await wrapper.find("button").trigger("click");
    expect(wrapper.emitted("select")?.[1]).toEqual([""]);
  });
});
