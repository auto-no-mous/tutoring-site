import { describe, expect, it } from "vitest";

import {
  clampAxis,
  clampView,
  coverScale,
  cropSourceRect,
  initialView,
  rescaleAroundCenter,
} from "@/utils/cropGeometry";

const VIEWPORT = 256;

describe("coverScale", () => {
  it("scales by the shorter side so the frame is always covered", () => {
    // Широкое фото: по высоте оно короче, её и надо дотянуть до рамки.
    expect(coverScale(800, 400, VIEWPORT)).toBeCloseTo(256 / 400);
    expect(coverScale(400, 800, VIEWPORT)).toBeCloseTo(256 / 400);
  });

  it("upscales an image smaller than the frame", () => {
    expect(coverScale(100, 120, VIEWPORT)).toBeCloseTo(256 / 100);
  });
});

describe("clampAxis", () => {
  it("keeps the image edges outside the frame", () => {
    // Картинка 600px в рамке 256: сдвиг допустим от -344 до 0.
    expect(clampAxis(-100, 600, VIEWPORT)).toBe(-100);
    expect(clampAxis(50, 600, VIEWPORT)).toBe(0);
    expect(clampAxis(-1000, 600, VIEWPORT)).toBe(-344);
  });

  it("centres an image smaller than the frame instead of leaving it against one edge", () => {
    expect(clampAxis(-999, 200, VIEWPORT)).toBe(28);
  });
});

describe("initialView", () => {
  it("centres the image at the smallest scale that still covers the frame", () => {
    const view = initialView(800, 400, VIEWPORT);
    expect(view.scale).toBeCloseTo(0.64);
    // По высоте картинка ровно по рамке, по ширине выступает симметрично.
    expect(view.offsetY).toBeCloseTo(0);
    expect(view.offsetX).toBeCloseTo((256 - 800 * 0.64) / 2);
  });

  it("produces a view that is already within its own limits", () => {
    const view = initialView(1234, 987, VIEWPORT);
    expect(clampView(view, 1234, 987, VIEWPORT)).toEqual(view);
  });
});

describe("clampView", () => {
  it("refuses a scale that would leave empty space in the frame", () => {
    const clamped = clampView({ scale: 0.1, offsetX: 0, offsetY: 0 }, 800, 400, VIEWPORT);
    expect(clamped.scale).toBeCloseTo(coverScale(800, 400, VIEWPORT));
  });
});

describe("rescaleAroundCenter", () => {
  it("keeps whatever is in the middle of the frame in the middle", () => {
    const view = initialView(800, 400, VIEWPORT);
    const zoomed = rescaleAroundCenter(view, view.scale * 2, 800, 400, VIEWPORT);

    // Точка исходника, попадавшая в центр рамки, должна остаться в центре.
    const centreBefore = (VIEWPORT / 2 - view.offsetX) / view.scale;
    const centreAfter = (VIEWPORT / 2 - zoomed.offsetX) / zoomed.scale;
    expect(centreAfter).toBeCloseTo(centreBefore);
  });

  it("still clamps when zooming out pushes the image off the frame", () => {
    const view = { scale: 2, offsetX: -500, offsetY: -500 };
    const zoomed = rescaleAroundCenter(view, 0.5, 800, 400, VIEWPORT);
    expect(zoomed.offsetX).toBeLessThanOrEqual(0);
    expect(zoomed.offsetY).toBeLessThanOrEqual(0);
    expect(zoomed.offsetX).toBeGreaterThanOrEqual(VIEWPORT - 800 * zoomed.scale);
  });
});

describe("cropSourceRect", () => {
  it("maps the frame back onto the original image's pixels", () => {
    // Масштаб 0.5 - в рамку 256 попадает квадрат 512 исходника.
    const rect = cropSourceRect({ scale: 0.5, offsetX: -100, offsetY: -60 }, VIEWPORT);
    expect(rect).toEqual({ sx: 200, sy: 120, size: 512 });
  });

  it("selects the whole image when it exactly fits the frame", () => {
    const view = initialView(500, 500, VIEWPORT);
    const rect = cropSourceRect(view, VIEWPORT);
    expect(rect.sx).toBeCloseTo(0);
    expect(rect.sy).toBeCloseTo(0);
    expect(rect.size).toBeCloseTo(500);
  });

  it("never selects an area outside the original image", () => {
    const imageWidth = 900;
    const imageHeight = 500;
    // Утаскиваем кадр максимально вправо-вниз и проверяем, что не вышли за край.
    const view = clampView(
      { scale: coverScale(imageWidth, imageHeight, VIEWPORT), offsetX: -9999, offsetY: -9999 },
      imageWidth,
      imageHeight,
      VIEWPORT,
    );
    const rect = cropSourceRect(view, VIEWPORT);
    expect(rect.sx).toBeGreaterThanOrEqual(0);
    expect(rect.sy).toBeGreaterThanOrEqual(0);
    expect(rect.sx + rect.size).toBeLessThanOrEqual(imageWidth + 0.001);
    expect(rect.sy + rect.size).toBeLessThanOrEqual(imageHeight + 0.001);
  });
});
