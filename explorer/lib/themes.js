export const SYSTEM_THEME_ID = "system";
export const LIGHT_THEME_ID = "light";
export const DARK_THEME_ID = "dark";
export const DEFAULT_THEME_ID = SYSTEM_THEME_ID;
export const THEME_STORAGE_KEY = "cad-explorer-theme";

const THEME_ALIASES = Object.freeze({
  "studio-light": LIGHT_THEME_ID,
  ivory: LIGHT_THEME_ID,
  graphite: DARK_THEME_ID,
  blueprint: DARK_THEME_ID,
  solarized: DARK_THEME_ID,
  terminal: DARK_THEME_ID,
  "candy-core": DARK_THEME_ID
});

const THEME_OPTIONS = Object.freeze([
  {
    id: SYSTEM_THEME_ID,
    label: "System"
  },
  {
    id: LIGHT_THEME_ID,
    label: "Light"
  },
  {
    id: DARK_THEME_ID,
    label: "Dark"
  }
]);

const THEME_REGISTRY = Object.freeze(
  Object.fromEntries(THEME_OPTIONS.map((themeOption) => [themeOption.id, themeOption]))
);

export const THEMES = THEME_OPTIONS;

export function normalizeThemeId(themeId) {
  const normalizedThemeId = String(themeId || "").trim().toLowerCase();
  const canonicalThemeId = THEME_ALIASES[normalizedThemeId] || normalizedThemeId;
  return THEME_REGISTRY[canonicalThemeId] ? canonicalThemeId : DEFAULT_THEME_ID;
}

export function getThemeOption(themeId) {
  return THEME_REGISTRY[normalizeThemeId(themeId)];
}

export function resolveThemeMode(themeId, { prefersDark = false } = {}) {
  const normalizedThemeId = normalizeThemeId(themeId);
  return normalizedThemeId === SYSTEM_THEME_ID
    ? (prefersDark ? DARK_THEME_ID : LIGHT_THEME_ID)
    : normalizedThemeId;
}

export function getThemeControlLabel(themeId, { prefersDark = false } = {}) {
  const themeOption = getThemeOption(themeId);
  if (themeOption.id !== SYSTEM_THEME_ID) {
    return themeOption.label;
  }
  const resolvedMode = resolveThemeMode(themeId, { prefersDark });
  return `${themeOption.label} (${getThemeOption(resolvedMode).label})`;
}

export function applyThemeToDocument(themeId, root = document.documentElement, { prefersDark = false } = {}) {
  if (!root) {
    return;
  }

  const normalizedThemeId = normalizeThemeId(themeId);
  const resolvedThemeMode = resolveThemeMode(normalizedThemeId, { prefersDark });

  root.dataset.themePreference = normalizedThemeId;
  root.dataset.theme = resolvedThemeMode;
  root.classList.toggle("dark", resolvedThemeMode === DARK_THEME_ID);
  root.style.colorScheme = resolvedThemeMode;
}
