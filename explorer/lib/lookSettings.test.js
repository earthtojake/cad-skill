import assert from "node:assert/strict";
import test from "node:test";

import {
  cloneLookPresetSettings,
  DEFAULT_LOOK_PRESET_ID,
  DEFAULT_LOOK_SETTINGS,
  getLookPresetIdForSettings,
  LOOK_PRESETS,
  normalizeLookSettings
} from "./lookSettings.js";

test("look presets expose a default material color", () => {
  const blue = cloneLookPresetSettings("blue");
  const pink = cloneLookPresetSettings("pink");

  assert.equal(LOOK_PRESETS.find((preset) => preset.id === "pink")?.label, "Magenta");
  assert.equal(blue.materials.defaultColor, "#58d6ff");
  assert.equal(pink.materials.defaultColor, "#ff8bd2");
  assert.equal(getLookPresetIdForSettings(blue), "blue");
  assert.equal(getLookPresetIdForSettings(pink), "pink");
});

test("cinematic is the default look preset", () => {
  assert.equal(DEFAULT_LOOK_PRESET_ID, "cinematic");
  assert.equal(LOOK_PRESETS[0]?.id, "cinematic");
  assert.equal(getLookPresetIdForSettings(DEFAULT_LOOK_SETTINGS), "cinematic");
});

test("normalizeLookSettings migrates legacy tint color into default color", () => {
  const normalized = normalizeLookSettings({
    materials: {
      tintColor: "#abc123"
    }
  });

  assert.equal(normalized.materials.defaultColor, "#abc123");
  assert.equal(Object.hasOwn(normalized.materials, "tintColor"), false);
});

test("only the workbench preset enables edges by default", () => {
  assert.equal(LOOK_PRESETS.find((preset) => preset.id === "clay-sunrise")?.label, "Clay");

  for (const preset of LOOK_PRESETS) {
    assert.equal(
      preset.settings.edges.enabled,
      preset.id === "workbench",
      `${preset.id} edge default`
    );
  }
});
