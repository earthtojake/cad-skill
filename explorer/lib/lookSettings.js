const HEX_COLOR_PATTERN = /^#(?:[0-9a-fA-F]{3}){1,2}$/;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeNumber(value, fallback, min = -Infinity, max = Infinity) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return fallback;
  }
  return clamp(numericValue, min, max);
}

function normalizeColor(value, fallback) {
  const normalized = String(value || "").trim();
  if (!HEX_COLOR_PATTERN.test(normalized)) {
    return fallback;
  }
  return normalized.length === 4
    ? `#${normalized[1]}${normalized[1]}${normalized[2]}${normalized[2]}${normalized[3]}${normalized[3]}`
    : normalized.toLowerCase();
}

function normalizeBoolean(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }
  return fallback;
}

function normalizeBackgroundType(value, fallback = "solid") {
  const normalized = String(value || "").trim().toLowerCase();
  return ["solid", "linear", "radial", "transparent"].includes(normalized)
    ? normalized
    : fallback;
}

export const LOOK_FLOOR_MODES = Object.freeze({
  STAGE: "stage",
  GRID: "grid",
  NONE: "none"
});

function normalizeFloorMode(value, fallback = LOOK_FLOOR_MODES.STAGE) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "glass") {
    return LOOK_FLOOR_MODES.STAGE;
  }
  return Object.values(LOOK_FLOOR_MODES).includes(normalized)
    ? normalized
    : fallback;
}

export const ENVIRONMENT_PRESETS = Object.freeze([
  {
    id: "studio-hdri-43",
    label: "Studio HDRI 43",
    url: "https://static.morflax.com/textures/env/Studio_HDRI_43.jpg"
  },
  {
    id: "studio-hdri-41",
    label: "Studio HDRI 41",
    url: "https://static.morflax.com/textures/env/Studio_HDRI_41.jpg"
  },
  {
    id: "studio-hdri-12",
    label: "Studio HDRI 12",
    url: "https://static.morflax.com/textures/env/Studio_HDRI_12.jpg"
  },
  {
    id: "studio-hdri-17",
    label: "Studio HDRI 17",
    url: "https://static.morflax.com/textures/env/Studio_HDRI_17.jpg"
  },
  {
    id: "studio-hdri-22",
    label: "Studio HDRI 22",
    url: "https://static.morflax.com/textures/env/Studio_HDRI_22.jpg"
  },
  {
    id: "colorful-1",
    label: "Colorful 1",
    url: "https://static.morflax.com/textures/env/colorful-1.jpg"
  },
  {
    id: "colorful-dark-1",
    label: "Colorful Dark 1",
    url: "https://static.morflax.com/textures/env/colorful-dark-1.jpg"
  }
]);

const CAD_WORKSPACE_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#e4e4e7",
    tintStrength: 0.06,
    saturation: 0.94,
    contrast: 1.03,
    brightness: 1,
    roughness: 0.72,
    metalness: 0,
    clearcoat: 0,
    clearcoatRoughness: 0.7,
    opacity: 1,
    envMapIntensity: 0.1
  },
  edges: {
    enabled: true,
    color: "#18181b",
    opacity: 0.46,
    thickness: 1
  },
  background: {
    type: "solid",
    solidColor: "#ffffff",
    linearStart: "#ffffff",
    linearEnd: "#ffffff",
    linearAngle: 180,
    radialInner: "#ffffff",
    radialOuter: "#ffffff"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.STAGE,
    color: "#e4e4e7",
    roughness: 0.88,
    reflectivity: 0.06,
    shadowOpacity: 0.26,
    horizonBlend: 0.08
  },
  environment: {
    enabled: false,
    presetId: "studio-hdri-43",
    intensity: 0,
    rotationY: 0,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.08,
    directional: {
      enabled: true,
      color: "#ffffff",
      intensity: 0.98,
      position: {
        x: -220,
        y: 240,
        z: 160
      }
    },
    spot: {
      enabled: true,
      color: "#ffffff",
      intensity: 0.26,
      angle: 0.62,
      distance: 0,
      position: {
        x: 180,
        y: 170,
        z: 210
      }
    },
    point: {
      enabled: false,
      color: "#ffffff",
      intensity: 0.14,
      distance: 0,
      position: {
        x: 120,
        y: 80,
        z: -210
      }
    },
    ambient: {
      enabled: true,
      color: "#fafafa",
      intensity: 0.42
    },
    hemisphere: {
      enabled: true,
      skyColor: "#ffffff",
      groundColor: "#e4e4e7",
      intensity: 0.84
    }
  }
});

const CINEMATIC_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#aeb9c3",
    tintStrength: 0.28,
    saturation: 0.42,
    contrast: 1.02,
    brightness: 0.94,
    roughness: 0.46,
    metalness: 0.02,
    clearcoat: 0.18,
    clearcoatRoughness: 0.34,
    opacity: 1,
    envMapIntensity: 0.58
  },
  edges: {
    enabled: false,
    color: "#8fa1b5",
    opacity: 0.1,
    thickness: 1
  },
  background: {
    type: "linear",
    solidColor: "#050711",
    linearStart: "#02040b",
    linearEnd: "#252f47",
    linearAngle: 90,
    radialInner: "#171d30",
    radialOuter: "#02040b"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.STAGE,
    color: "#141a29",
    roughness: 0.62,
    reflectivity: 0.22,
    shadowOpacity: 0.24,
    horizonBlend: 0.28
  },
  environment: {
    enabled: true,
    presetId: "studio-hdri-43",
    intensity: 0.46,
    rotationY: -0.35,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.2,
    directional: {
      enabled: true,
      color: "#f1f6fb",
      intensity: 2.45,
      position: {
        x: -190,
        y: 300,
        z: 210
      }
    },
    spot: {
      enabled: true,
      color: "#dbeafe",
      intensity: 1.34,
      angle: 0.72,
      distance: 0,
      position: {
        x: 160,
        y: 245,
        z: 126
      }
    },
    point: {
      enabled: true,
      color: "#8fb6d8",
      intensity: 0.34,
      distance: 0,
      position: {
        x: -260,
        y: 95,
        z: -220
      }
    },
    ambient: {
      enabled: true,
      color: "#1e293b",
      intensity: 0.2
    },
    hemisphere: {
      enabled: true,
      skyColor: "#dbe7f3",
      groundColor: "#070a14",
      intensity: 0.68
    }
  }
});

const BLUE_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#58d6ff",
    tintStrength: 0.72,
    saturation: 1.24,
    contrast: 1.08,
    brightness: 0.96,
    roughness: 0.48,
    metalness: 0.04,
    clearcoat: 0.18,
    clearcoatRoughness: 0.28,
    opacity: 1,
    envMapIntensity: 0.46
  },
  edges: {
    enabled: false,
    color: "#063d61",
    opacity: 0.58,
    thickness: 1.15
  },
  background: {
    type: "radial",
    solidColor: "#04131f",
    linearStart: "#07253a",
    linearEnd: "#0b8edc",
    linearAngle: 128,
    radialInner: "#0b8edc",
    radialOuter: "#02070c"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.STAGE,
    color: "#06324f",
    roughness: 0.58,
    reflectivity: 0.2,
    shadowOpacity: 0.3,
    horizonBlend: 0.18
  },
  environment: {
    enabled: true,
    presetId: "colorful-dark-1",
    intensity: 0.36,
    rotationY: 0.22,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.12,
    directional: {
      enabled: true,
      color: "#c7efff",
      intensity: 1.08,
      position: {
        x: -210,
        y: 260,
        z: 160
      }
    },
    spot: {
      enabled: true,
      color: "#54c8ff",
      intensity: 1.02,
      angle: 0.56,
      distance: 0,
      position: {
        x: 180,
        y: 170,
        z: 220
      }
    },
    point: {
      enabled: true,
      color: "#0485c7",
      intensity: 0.52,
      distance: 0,
      position: {
        x: -220,
        y: 80,
        z: -180
      }
    },
    ambient: {
      enabled: true,
      color: "#082b42",
      intensity: 0.16
    },
    hemisphere: {
      enabled: true,
      skyColor: "#bdeeff",
      groundColor: "#031a2d",
      intensity: 0.64
    }
  }
});

const PINK_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#ff8bd2",
    tintStrength: 0.78,
    saturation: 1.36,
    contrast: 1.14,
    brightness: 1.04,
    roughness: 0.5,
    metalness: 0.05,
    clearcoat: 0.22,
    clearcoatRoughness: 0.24,
    opacity: 1,
    envMapIntensity: 0.42
  },
  edges: {
    enabled: false,
    color: "#ff8ac7",
    opacity: 0.62,
    thickness: 1.18
  },
  background: {
    type: "radial",
    solidColor: "#281323",
    linearStart: "#7a1a52",
    linearEnd: "#301426",
    linearAngle: 140,
    radialInner: "#7f1a55",
    radialOuter: "#25101f"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.STAGE,
    color: "#4a1833",
    roughness: 0.56,
    reflectivity: 0.2,
    shadowOpacity: 0.26,
    horizonBlend: 0.22
  },
  environment: {
    enabled: true,
    presetId: "colorful-dark-1",
    intensity: 0.34,
    rotationY: -0.28,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.08,
    directional: {
      enabled: true,
      color: "#ffd6ea",
      intensity: 1.06,
      position: {
        x: -190,
        y: 250,
        z: 180
      }
    },
    spot: {
      enabled: true,
      color: "#ff4aa8",
      intensity: 1.12,
      angle: 0.54,
      distance: 0,
      position: {
        x: 170,
        y: 180,
        z: 225
      }
    },
    point: {
      enabled: true,
      color: "#ff78c5",
      intensity: 0.62,
      distance: 0,
      position: {
        x: -210,
        y: 82,
        z: -180
      }
    },
    ambient: {
      enabled: true,
      color: "#2a061b",
      intensity: 0.18
    },
    hemisphere: {
      enabled: true,
      skyColor: "#ffd1e8",
      groundColor: "#15000b",
      intensity: 0.52
    }
  }
});

const CLAY_SUNRISE_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#ffd6a8",
    tintStrength: 0.34,
    saturation: 1.08,
    contrast: 1.08,
    brightness: 1.02,
    roughness: 0.7,
    metalness: 0.03,
    clearcoat: 0.08,
    clearcoatRoughness: 0.45,
    opacity: 1,
    envMapIntensity: 0.72
  },
  edges: {
    enabled: false,
    color: "#000000",
    opacity: 1,
    thickness: 1
  },
  background: {
    type: "linear",
    solidColor: "#f3eadc",
    linearStart: "#f7ead8",
    linearEnd: "#c88d5d",
    linearAngle: 162,
    radialInner: "#f7ead8",
    radialOuter: "#b06c43"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.STAGE,
    color: "#d4a070",
    roughness: 0.72,
    reflectivity: 0.14,
    shadowOpacity: 0.34,
    horizonBlend: 0.12
  },
  environment: {
    enabled: true,
    presetId: "studio-hdri-22",
    intensity: 0.62,
    rotationY: -0.46,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.02,
    directional: {
      enabled: true,
      color: "#fff2dc",
      intensity: 1.55,
      position: {
        x: 180,
        y: 250,
        z: 90
      }
    },
    spot: {
      enabled: false,
      color: "#ffffff",
      intensity: 1.6,
      angle: 0.52,
      distance: 0,
      position: {
        x: 160,
        y: 120,
        z: 100
      }
    },
    point: {
      enabled: true,
      color: "#ffc189",
      intensity: 0.55,
      distance: 0,
      position: {
        x: -220,
        y: 120,
        z: 150
      }
    },
    ambient: {
      enabled: true,
      color: "#fff8ef",
      intensity: 0.12
    },
    hemisphere: {
      enabled: true,
      skyColor: "#fff3dd",
      groundColor: "#c49970",
      intensity: 0.52
    }
  }
});

const TERMINAL_LOOK_SETTINGS = Object.freeze({
  materials: {
    defaultColor: "#48ff8b",
    tintStrength: 0.78,
    saturation: 1.34,
    contrast: 1.28,
    brightness: 0.86,
    roughness: 0.52,
    metalness: 0.08,
    clearcoat: 0.18,
    clearcoatRoughness: 0.22,
    opacity: 1,
    envMapIntensity: 0.32
  },
  edges: {
    enabled: false,
    color: "#66ff99",
    opacity: 0.72,
    thickness: 1.4
  },
  background: {
    type: "radial",
    solidColor: "#020403",
    linearStart: "#031109",
    linearEnd: "#000000",
    linearAngle: 180,
    radialInner: "#062414",
    radialOuter: "#000201"
  },
  floor: {
    mode: LOOK_FLOOR_MODES.GRID,
    color: "#020403",
    roughness: 0.58,
    reflectivity: 0.12,
    shadowOpacity: 0.35,
    horizonBlend: 0
  },
  environment: {
    enabled: false,
    presetId: "colorful-dark-1",
    intensity: 0,
    rotationY: 0,
    useAsBackground: false
  },
  lighting: {
    toneMappingExposure: 1.1,
    directional: {
      enabled: true,
      color: "#a6ffbf",
      intensity: 0.65,
      position: {
        x: -200,
        y: 240,
        z: 130
      }
    },
    spot: {
      enabled: true,
      color: "#39ff7d",
      intensity: 0.9,
      angle: 0.45,
      distance: 0,
      position: {
        x: 160,
        y: 180,
        z: 240
      }
    },
    point: {
      enabled: true,
      color: "#00ff66",
      intensity: 0.75,
      distance: 0,
      position: {
        x: -180,
        y: 70,
        z: -160
      }
    },
    ambient: {
      enabled: true,
      color: "#0eff76",
      intensity: 0.18
    },
    hemisphere: {
      enabled: true,
      skyColor: "#5cff9a",
      groundColor: "#000000",
      intensity: 0.45
    }
  }
});

export const LOOK_PRESETS = Object.freeze([
  {
    id: "workbench",
    label: "Workbench",
    description: "Clean Onshape-style CAD editor canvas with white workspace light.",
    preview: {
      background: "linear-gradient(135deg, #ffffff 0%, #f4f4f5 58%, #d4d4d8 100%)",
      modelColor: "#e4e4e7",
      accentColor: "#71717a"
    },
    glassTone: "light",
    settings: CAD_WORKSPACE_LOOK_SETTINGS
  },
  {
    id: "cinematic",
    label: "Cinematic",
    description: "Dark navy studio lighting with cool highlights, soft floor shadows, and cinematic depth.",
    preview: {
      background: "linear-gradient(135deg, #02040b 0%, #141a29 54%, #252f47 100%)",
      modelColor: "#aeb9c3",
      accentColor: "#8fb6d8"
    },
    glassTone: "dark",
    settings: CINEMATIC_LOOK_SETTINGS
  },
  {
    id: "blue",
    label: "Blue",
    description: "Layered cyan and deep-navy CAD lighting inspired by the blue reference.",
    preview: {
      background: "radial-gradient(circle at 28% 24%, #6ec7e9 0%, #0b8edc 42%, #063d61 100%)",
      modelColor: "#58d6ff",
      accentColor: "#6ec7e9"
    },
    glassTone: "dark",
    settings: BLUE_LOOK_SETTINGS
  },
  {
    id: "pink",
    label: "Magenta",
    description: "Bright magenta model glow against a near-black studio backdrop.",
    preview: {
      background: "radial-gradient(circle at 30% 24%, #ff61b2 0%, #ff2f98 44%, #25101f 100%)",
      modelColor: "#ff8bd2",
      accentColor: "#ff8ac7"
    },
    glassTone: "dark",
    settings: PINK_LOOK_SETTINGS
  },
  {
    id: "clay-sunrise",
    label: "Clay",
    description: "Warm sculpting light with a soft presentation clay finish.",
    preview: {
      background: "linear-gradient(135deg, #fff3e2 0%, #e9c199 42%, #94532f 100%)",
      modelColor: "#d8c1a7",
      accentColor: "#ffd59d"
    },
    glassTone: "light",
    settings: CLAY_SUNRISE_LOOK_SETTINGS
  },
  {
    id: "terminal",
    label: "Terminal",
    description: "Neon-green terminal glow with matrix-style linework and a dark grid floor.",
    preview: {
      background: "radial-gradient(circle at 32% 20%, #062414 0%, #020403 56%, #000201 100%)",
      modelColor: "#48ff8b",
      accentColor: "#66ff99"
    },
    glassTone: "dark",
    settings: TERMINAL_LOOK_SETTINGS
  }
]);

export const DEFAULT_LOOK_PRESET_ID = "cinematic";

export const DEFAULT_LOOK_PRESET = Object.freeze(
  LOOK_PRESETS.find((preset) => preset.id === DEFAULT_LOOK_PRESET_ID) || LOOK_PRESETS[0]
);

export const DEFAULT_LOOK_SETTINGS = Object.freeze(DEFAULT_LOOK_PRESET.settings);

const PRESET_ID_SET = new Set(ENVIRONMENT_PRESETS.map((preset) => preset.id));

function normalizeEnvironmentPresetId(value) {
  const normalized = String(value || "").trim();
  if (PRESET_ID_SET.has(normalized)) {
    return normalized;
  }
  return DEFAULT_LOOK_SETTINGS.environment.presetId;
}

function normalizePosition(value, fallback) {
  return {
    x: normalizeNumber(value?.x, fallback.x, -5000, 5000),
    y: normalizeNumber(value?.y, fallback.y, -5000, 5000),
    z: normalizeNumber(value?.z, fallback.z, -5000, 5000)
  };
}

function createLookSettingsSignature(value = {}) {
  return JSON.stringify({
    materials: value?.materials || {},
    edges: value?.edges || {},
    background: value?.background || {},
    floor: value?.floor || {},
    environment: value?.environment || {},
    lighting: value?.lighting || {}
  });
}

export function normalizeLookSettings(value = {}) {
  const source = value && typeof value === "object" ? value : {};
  const materials = source.materials && typeof source.materials === "object"
    ? source.materials
    : {};
  const background = source.background && typeof source.background === "object"
    ? source.background
    : {};
  const environment = source.environment && typeof source.environment === "object"
    ? source.environment
    : {};
  const floor = source.floor && typeof source.floor === "object"
    ? source.floor
    : {};
  const edges = source.edges && typeof source.edges === "object"
    ? source.edges
    : {};
  const lighting = source.lighting && typeof source.lighting === "object"
    ? source.lighting
    : {};

  const normalized = {
    materials: {
      defaultColor: normalizeColor(
        materials.defaultColor || materials.tintColor,
        DEFAULT_LOOK_SETTINGS.materials.defaultColor
      ),
      tintStrength: normalizeNumber(materials.tintStrength, DEFAULT_LOOK_SETTINGS.materials.tintStrength, 0, 1),
      saturation: normalizeNumber(materials.saturation, DEFAULT_LOOK_SETTINGS.materials.saturation, 0, 2.5),
      contrast: normalizeNumber(materials.contrast, DEFAULT_LOOK_SETTINGS.materials.contrast, 0, 2.5),
      brightness: normalizeNumber(materials.brightness, DEFAULT_LOOK_SETTINGS.materials.brightness, 0, 2),
      roughness: normalizeNumber(materials.roughness, DEFAULT_LOOK_SETTINGS.materials.roughness, 0, 1),
      metalness: normalizeNumber(materials.metalness, DEFAULT_LOOK_SETTINGS.materials.metalness, 0, 1),
      clearcoat: normalizeNumber(materials.clearcoat, DEFAULT_LOOK_SETTINGS.materials.clearcoat, 0, 1),
      clearcoatRoughness: normalizeNumber(
        materials.clearcoatRoughness,
        DEFAULT_LOOK_SETTINGS.materials.clearcoatRoughness,
        0,
        1
      ),
      opacity: normalizeNumber(materials.opacity, DEFAULT_LOOK_SETTINGS.materials.opacity, 0, 1),
      envMapIntensity: normalizeNumber(materials.envMapIntensity, DEFAULT_LOOK_SETTINGS.materials.envMapIntensity, 0, 4)
    },
    edges: {
      enabled: normalizeBoolean(edges.enabled, DEFAULT_LOOK_SETTINGS.edges.enabled),
      color: normalizeColor(edges.color, DEFAULT_LOOK_SETTINGS.edges.color),
      opacity: normalizeNumber(edges.opacity, DEFAULT_LOOK_SETTINGS.edges.opacity, 0, 1),
      thickness: normalizeNumber(edges.thickness, DEFAULT_LOOK_SETTINGS.edges.thickness, 0.5, 6)
    },
    background: {
      type: normalizeBackgroundType(background.type, DEFAULT_LOOK_SETTINGS.background.type),
      solidColor: normalizeColor(background.solidColor, DEFAULT_LOOK_SETTINGS.background.solidColor),
      linearStart: normalizeColor(background.linearStart, DEFAULT_LOOK_SETTINGS.background.linearStart),
      linearEnd: normalizeColor(background.linearEnd, DEFAULT_LOOK_SETTINGS.background.linearEnd),
      linearAngle: normalizeNumber(background.linearAngle, DEFAULT_LOOK_SETTINGS.background.linearAngle, -360, 360),
      radialInner: normalizeColor(background.radialInner, DEFAULT_LOOK_SETTINGS.background.radialInner),
      radialOuter: normalizeColor(background.radialOuter, DEFAULT_LOOK_SETTINGS.background.radialOuter)
    },
    floor: {
      mode: normalizeFloorMode(floor.mode, DEFAULT_LOOK_SETTINGS.floor?.mode || LOOK_FLOOR_MODES.STAGE),
      color: normalizeColor(floor.color, DEFAULT_LOOK_SETTINGS.floor?.color || "#141416"),
      roughness: normalizeNumber(floor.roughness, DEFAULT_LOOK_SETTINGS.floor?.roughness ?? 0.72, 0, 1),
      reflectivity: normalizeNumber(floor.reflectivity, DEFAULT_LOOK_SETTINGS.floor?.reflectivity ?? 0.12, 0, 1),
      shadowOpacity: normalizeNumber(floor.shadowOpacity, DEFAULT_LOOK_SETTINGS.floor?.shadowOpacity ?? 0.45, 0, 1),
      horizonBlend: normalizeNumber(floor.horizonBlend, DEFAULT_LOOK_SETTINGS.floor?.horizonBlend ?? 0, 0, 1)
    },
    environment: {
      enabled: normalizeBoolean(environment.enabled, DEFAULT_LOOK_SETTINGS.environment.enabled),
      presetId: normalizeEnvironmentPresetId(environment.presetId),
      intensity: normalizeNumber(environment.intensity, DEFAULT_LOOK_SETTINGS.environment.intensity, 0, 4),
      rotationY: normalizeNumber(environment.rotationY, DEFAULT_LOOK_SETTINGS.environment.rotationY, -Math.PI * 2, Math.PI * 2),
      useAsBackground: normalizeBoolean(environment.useAsBackground, DEFAULT_LOOK_SETTINGS.environment.useAsBackground)
    },
    lighting: {
      toneMappingExposure: normalizeNumber(
        lighting.toneMappingExposure,
        DEFAULT_LOOK_SETTINGS.lighting.toneMappingExposure,
        0.05,
        6
      ),
      directional: {
        enabled: normalizeBoolean(lighting.directional?.enabled, DEFAULT_LOOK_SETTINGS.lighting.directional.enabled),
        color: normalizeColor(lighting.directional?.color, DEFAULT_LOOK_SETTINGS.lighting.directional.color),
        intensity: normalizeNumber(lighting.directional?.intensity, DEFAULT_LOOK_SETTINGS.lighting.directional.intensity, 0, 20),
        position: normalizePosition(lighting.directional?.position, DEFAULT_LOOK_SETTINGS.lighting.directional.position)
      },
      spot: {
        enabled: normalizeBoolean(lighting.spot?.enabled, DEFAULT_LOOK_SETTINGS.lighting.spot.enabled),
        color: normalizeColor(lighting.spot?.color, DEFAULT_LOOK_SETTINGS.lighting.spot.color),
        intensity: normalizeNumber(lighting.spot?.intensity, DEFAULT_LOOK_SETTINGS.lighting.spot.intensity, 0, 20),
        angle: normalizeNumber(lighting.spot?.angle, DEFAULT_LOOK_SETTINGS.lighting.spot.angle, 0.01, Math.PI / 2),
        distance: normalizeNumber(lighting.spot?.distance, DEFAULT_LOOK_SETTINGS.lighting.spot.distance, 0, 5000),
        position: normalizePosition(lighting.spot?.position, DEFAULT_LOOK_SETTINGS.lighting.spot.position)
      },
      point: {
        enabled: normalizeBoolean(lighting.point?.enabled, DEFAULT_LOOK_SETTINGS.lighting.point.enabled),
        color: normalizeColor(lighting.point?.color, DEFAULT_LOOK_SETTINGS.lighting.point.color),
        intensity: normalizeNumber(lighting.point?.intensity, DEFAULT_LOOK_SETTINGS.lighting.point.intensity, 0, 20),
        distance: normalizeNumber(lighting.point?.distance, DEFAULT_LOOK_SETTINGS.lighting.point.distance, 0, 5000),
        position: normalizePosition(lighting.point?.position, DEFAULT_LOOK_SETTINGS.lighting.point.position)
      },
      ambient: {
        enabled: normalizeBoolean(lighting.ambient?.enabled, DEFAULT_LOOK_SETTINGS.lighting.ambient.enabled),
        color: normalizeColor(lighting.ambient?.color, DEFAULT_LOOK_SETTINGS.lighting.ambient.color),
        intensity: normalizeNumber(lighting.ambient?.intensity, DEFAULT_LOOK_SETTINGS.lighting.ambient.intensity, 0, 20)
      },
      hemisphere: {
        enabled: normalizeBoolean(lighting.hemisphere?.enabled, DEFAULT_LOOK_SETTINGS.lighting.hemisphere.enabled),
        skyColor: normalizeColor(lighting.hemisphere?.skyColor, DEFAULT_LOOK_SETTINGS.lighting.hemisphere.skyColor),
        groundColor: normalizeColor(lighting.hemisphere?.groundColor, DEFAULT_LOOK_SETTINGS.lighting.hemisphere.groundColor),
        intensity: normalizeNumber(lighting.hemisphere?.intensity, DEFAULT_LOOK_SETTINGS.lighting.hemisphere.intensity, 0, 20)
      }
    }
  };

  return normalized;
}

export function cloneLookSettings(value = DEFAULT_LOOK_SETTINGS) {
  return normalizeLookSettings(JSON.parse(JSON.stringify(value)));
}

export function getLookPresetById(presetId) {
  return LOOK_PRESETS.find((preset) => preset.id === presetId) || DEFAULT_LOOK_PRESET;
}

export function cloneLookPresetSettings(presetId) {
  return cloneLookSettings(getLookPresetById(presetId).settings);
}

export function getLookPresetIdForSettings(lookSettings) {
  const currentSignature = createLookSettingsSignature(normalizeLookSettings(lookSettings));
  for (const preset of LOOK_PRESETS) {
    const presetSignature = createLookSettingsSignature(normalizeLookSettings(preset.settings));
    if (presetSignature === currentSignature) {
      return preset.id;
    }
  }
  return null;
}

export function getEnvironmentPresetById(presetId) {
  return ENVIRONMENT_PRESETS.find((preset) => preset.id === presetId) || ENVIRONMENT_PRESETS[0];
}
