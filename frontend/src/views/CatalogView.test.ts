import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CatalogView from "@/views/CatalogView.vue";

const getCatalog = vi.fn();

vi.mock("@/api/tutors", () => ({ getCatalog: (params: unknown) => getCatalog(params) }));
vi.mock("@/api/subjects", () => ({ listSubjects: vi.fn(async () => []) }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function tutor(id: string, hourly: number) {
  return {
    id,
    slug: null,
    user_id: `u-${id}`,
    display_name: `Репетитор ${id}`,
    name_patronymic: `Репетитор ${id}`,
    photo_url: null,
    hourly_price: hourly,
    subjects: [],
    avg_rating: null,
    reviews_count: 0,
    about_snippet: null,
    show_individual_booking: false,
    show_group_booking: false,
  };
}

function mountCatalog() {
  return mount(CatalogView, {
    global: {
      stubs: {
        HomeHero: true,
        SubjectTiles: true,
        HowItWorks: true,
        PlatformFeatures: true,
        ForTutorsNote: true,
        HomeBlog: true,
        HomeFaq: true,
        RouterLink: { template: "<a><slot /></a>" },
        Transition: false,
        TransitionGroup: false,
      },
    },
  });
}

describe("CatalogView: фильтр цены", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    getCatalog.mockImplementation(async () => ({
      items: [tutor("a", 1000), tutor("b", 1200)],
      total: 2,
      page: 1,
      page_size: 20,
    }));
  });

  it("после выбора цены снова загружает список, а не оставляет его пустым", async () => {
    // Жалоба: выбор цены очищал список и больше ничего не грузил.
    const wrapper = mountCatalog();
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text().includes("Фильтры"))!.trigger("click");

    await wrapper.find('select[aria-label="Цена за час"]').setValue("1000-1499");
    await flushPromises();

    const params = getCatalog.mock.calls.at(-1)![0];
    expect(params.price_min).toBe(1000);
    expect(params.price_max).toBe(1499.99);
    expect(wrapper.text()).toContain("Репетитор a");
    expect(wrapper.text()).toContain("Репетитор b");
    expect(wrapper.text()).not.toContain("Репетиторы не найдены");
  });

  it("кнопка называется «Фильтры и поиск», поиск по имени - в её строке и складывается с ценой", async () => {
    vi.useFakeTimers();
    const wrapper = mountCatalog();
    await flushPromises();
    const toggle = wrapper.findAll("button").find((b) => b.text().includes("Фильтры и поиск"))!;
    expect(wrapper.find('input[aria-label="Поиск по имени"]').exists()).toBe(false);
    await toggle.trigger("click");

    const input = wrapper.find('input[aria-label="Поиск по имени"]');
    expect(input.element.parentElement!.parentElement).toBe(toggle.element.parentElement);

    await wrapper.find('select[aria-label="Цена за час"]').setValue("500-999");
    await flushPromises();
    const callsBefore = getCatalog.mock.calls.length;
    await input.setValue("ива");
    await input.setValue("иван");
    // Пока печатают - запросов нет, после паузы - один.
    expect(getCatalog.mock.calls.length).toBe(callsBefore);
    vi.advanceTimersByTime(300);
    await flushPromises();
    expect(getCatalog.mock.calls.length).toBe(callsBefore + 1);
    const params = getCatalog.mock.calls.at(-1)![0];
    expect(params.q).toBe("иван");
    expect(params.price_min).toBe(500);
    vi.useRealTimers();
  });

  it("одно поле с пятью диапазонами, крайние - открытые", async () => {
    const wrapper = mountCatalog();
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text().includes("Фильтры"))!.trigger("click");

    const select = wrapper.find('select[aria-label="Цена за час"]');
    expect(select.findAll("option").map((o) => o.text())).toEqual([
      "Любая цена",
      "менее 500 ₽",
      "500 – 999 ₽",
      "1000 – 1499 ₽",
      "1500 – 2000 ₽",
      "более 2000 ₽",
    ]);

    await select.setValue("gt2000");
    await flushPromises();
    const params = getCatalog.mock.calls.at(-1)![0];
    expect(params.price_min).toBe(2000.01);
    expect(params.price_max).toBeUndefined();
  });
});
