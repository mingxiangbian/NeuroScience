const COMPACT_PORTRAIT_WIDTH = 720;
const MIN_SAFE_NDC_SPAN = 0.18;

export const HOMEPAGE_VIEWPORT_PRESETS = Object.freeze({
  desktop: Object.freeze({
    cameraZ: 6.7,
    brainScale: 1.16,
    brainY: -0.12,
    expandedBrainScaleReduction: 0.24,
    expandedBrainYShift: 0.02,
    shellScale: Object.freeze([1.28, 0.82, 0.9]),
    pedestalY: -0.08,
    pedestalScale: 1.02,
    pedestalRotationX: -0.018,
  }),
  portrait: Object.freeze({
    cameraZ: 8.45,
    brainScale: 0.82,
    brainY: -0.02,
    expandedBrainScaleReduction: 0.14,
    expandedBrainYShift: 0.015,
    shellScale: Object.freeze([1.08, 0.7, 0.76]),
    pedestalY: -0.02,
    pedestalScale: 0.76,
    pedestalRotationX: -0.012,
  }),
  compact: Object.freeze({
    cameraZ: 8.9,
    brainScale: 0.7,
    brainY: -0.08,
    expandedBrainScaleReduction: 0.08,
    expandedBrainYShift: 0.02,
    shellScale: Object.freeze([0.98, 0.66, 0.7]),
    pedestalY: -0.04,
    pedestalScale: 0.64,
    pedestalRotationX: -0.01,
  }),
});

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function toViewportDimension(value) {
  return Math.max(1, Number.isFinite(value) ? value : 1);
}

export function computeHomepageViewport(width, height) {
  const viewportWidth = toViewportDimension(width);
  const viewportHeight = toViewportDimension(height);
  const isPortrait = viewportHeight >= viewportWidth;
  const isCompact = isPortrait && viewportWidth < COMPACT_PORTRAIT_WIDTH;
  const mode = isCompact ? "compact" : isPortrait ? "portrait" : "desktop";

  return {
    width: viewportWidth,
    height: viewportHeight,
    aspect: viewportWidth / viewportHeight,
    isPortrait,
    isCompact,
    mode,
    preset: HOMEPAGE_VIEWPORT_PRESETS[mode],
  };
}

function getSafeNdcSpan(inset, viewportSize) {
  return clamp(1 - (2 * Math.max(0, inset || 0)) / viewportSize, MIN_SAFE_NDC_SPAN, 1);
}

function isFiniteBounds(bounds) {
  return bounds
    && [bounds.min?.x, bounds.min?.y, bounds.min?.z, bounds.max?.x, bounds.max?.y, bounds.max?.z]
      .every(Number.isFinite);
}

export function fitCameraZToBounds({
  bounds,
  viewportWidth,
  viewportHeight,
  fovDegrees,
  cameraX = 0,
  cameraY = 0,
  baseCameraZ = 0,
  safeInsets = {},
}) {
  const width = toViewportDimension(viewportWidth);
  const height = toViewportDimension(viewportHeight);
  const aspect = width / height;
  const tanHalfFov = Math.tan((Math.max(1, fovDegrees) * Math.PI) / 360);
  const leftSpan = getSafeNdcSpan(safeInsets.left, width);
  const rightSpan = getSafeNdcSpan(safeInsets.right, width);
  const topSpan = getSafeNdcSpan(safeInsets.top, height);
  const bottomSpan = getSafeNdcSpan(safeInsets.bottom, height);
  let fittedCameraZ = baseCameraZ;

  for (const item of bounds ?? []) {
    if (!isFiniteBounds(item)) continue;
    const closestZ = item.max.z;
    const rightExtent = Math.max(0, item.max.x - cameraX);
    const leftExtent = Math.max(0, cameraX - item.min.x);
    const topExtent = Math.max(0, item.max.y - cameraY);
    const bottomExtent = Math.max(0, cameraY - item.min.y);

    fittedCameraZ = Math.max(
      fittedCameraZ,
      closestZ + rightExtent / (tanHalfFov * aspect * rightSpan),
      closestZ + leftExtent / (tanHalfFov * aspect * leftSpan),
      closestZ + topExtent / (tanHalfFov * topSpan),
      closestZ + bottomExtent / (tanHalfFov * bottomSpan),
    );
  }

  return fittedCameraZ;
}
