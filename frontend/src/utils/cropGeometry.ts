/**
 * Геометрия квадратного кадрирования фото профиля.
 *
 * Вынесено из компонента (components/PhotoCropModal.vue) отдельно, потому что вся
 * содержательная часть кадрирования - это арифметика: где лежит картинка
 * относительно рамки, насколько её можно двигать и какой кусок исходника в итоге
 * попадёт в файл. В компоненте остаются только события мыши и отрисовка.
 *
 * Система координат: рамка - квадрат со стороной `viewport` (CSS-пиксели), её левый
 * верхний угол это (0, 0). `offsetX/offsetY` - положение левого верхнего угла
 * картинки относительно этого угла, поэтому они отрицательны, когда картинка
 * выступает за рамку (обычный случай). `scale` - во сколько раз картинка показана
 * относительно своего натурального размера.
 */

export interface CropView {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface CropSourceRect {
  /** Координаты и сторона квадрата в пикселях ИСХОДНОГО изображения. */
  sx: number;
  sy: number;
  size: number;
}

/**
 * Наименьший масштаб, при котором картинка ещё закрывает рамку целиком. Меньше него
 * опускаться нельзя - в кадре появились бы пустые поля.
 */
export function coverScale(imageWidth: number, imageHeight: number, viewport: number): number {
  return Math.max(viewport / imageWidth, viewport / imageHeight);
}

/**
 * Зажимает смещение по одной оси так, чтобы картинка не отъехала от края рамки.
 *
 * Если картинка почему-то оказалась меньше рамки (масштаб ниже coverScale - через
 * интерфейс так не сделать, но функция не должна врать при любых входных данных),
 * центрируем её: это единственное положение, где пустые поля симметричны.
 */
export function clampAxis(offset: number, displayedSize: number, viewport: number): number {
  if (displayedSize <= viewport) return (viewport - displayedSize) / 2;
  return Math.min(0, Math.max(viewport - displayedSize, offset));
}

export function clampView(
  view: CropView,
  imageWidth: number,
  imageHeight: number,
  viewport: number,
): CropView {
  const scale = Math.max(view.scale, coverScale(imageWidth, imageHeight, viewport));
  return {
    scale,
    offsetX: clampAxis(view.offsetX, imageWidth * scale, viewport),
    offsetY: clampAxis(view.offsetY, imageHeight * scale, viewport),
  };
}

/** Начальное положение: минимальный масштаб, картинка по центру рамки. */
export function initialView(imageWidth: number, imageHeight: number, viewport: number): CropView {
  const scale = coverScale(imageWidth, imageHeight, viewport);
  return {
    scale,
    offsetX: (viewport - imageWidth * scale) / 2,
    offsetY: (viewport - imageHeight * scale) / 2,
  };
}

/**
 * Меняет масштаб, оставляя на месте ту точку картинки, что была в центре рамки.
 * Без этого зум «уводит» кадр: увеличение тянуло бы изображение к левому верхнему
 * углу, и наведённое лицо пришлось бы ловить заново.
 */
export function rescaleAroundCenter(
  view: CropView,
  nextScale: number,
  imageWidth: number,
  imageHeight: number,
  viewport: number,
): CropView {
  const ratio = nextScale / view.scale;
  const half = viewport / 2;
  return clampView(
    {
      scale: nextScale,
      offsetX: half - (half - view.offsetX) * ratio,
      offsetY: half - (half - view.offsetY) * ratio,
    },
    imageWidth,
    imageHeight,
    viewport,
  );
}

/**
 * Какой квадрат исходного изображения видно в рамке - именно его компонент рисует
 * на canvas и отправляет на сервер.
 */
export function cropSourceRect(view: CropView, viewport: number): CropSourceRect {
  return {
    sx: -view.offsetX / view.scale,
    sy: -view.offsetY / view.scale,
    size: viewport / view.scale,
  };
}
