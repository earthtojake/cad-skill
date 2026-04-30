export const EXPLORER_SCENE_SCALE = Object.freeze({
  CAD: "cad",
  URDF: "urdf"
});

const SCENE_SCALE_SETTINGS = Object.freeze({
  [EXPLORER_SCENE_SCALE.CAD]: Object.freeze({
    minModelRadius: 1,
    minGridSize: 280,
    lightingScopeRadius: 140
  }),
  [EXPLORER_SCENE_SCALE.URDF]: Object.freeze({
    minModelRadius: 0.05,
    minGridSize: 0.5,
    lightingScopeRadius: 0.25
  })
});

export function normalizeSceneScaleMode(value) {
  return value === EXPLORER_SCENE_SCALE.URDF
    ? EXPLORER_SCENE_SCALE.URDF
    : EXPLORER_SCENE_SCALE.CAD;
}

export function getSceneScaleSettings(value) {
  return SCENE_SCALE_SETTINGS[normalizeSceneScaleMode(value)];
}

export function clampSceneModelRadius(radius, value) {
  const numericRadius = Number(radius);
  return Math.max(
    Number.isFinite(numericRadius) ? numericRadius : 0,
    getSceneScaleSettings(value).minModelRadius
  );
}

export function defaultSceneGridRadius(value) {
  return getSceneScaleSettings(value).minGridSize / 2;
}

export function getLightingScopeRadius(value) {
  return getSceneScaleSettings(value).lightingScopeRadius;
}
