import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "../ui/accordion";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "../ui/select";
import { Slider } from "../ui/slider";
import { Switch } from "../ui/switch";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger
} from "../ui/tabs";
import { Textarea } from "../ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "../ui/toggle-group";
import { copyTextToClipboard } from "../../lib/clipboard";
import { cn } from "../../lib/cn";
import {
  DEFAULT_LOOK_PRESET_ID,
  ENVIRONMENT_PRESETS,
  LOOK_FLOOR_MODES,
  LOOK_PRESETS,
  cloneLookPresetSettings,
  getLookPresetIdForSettings
} from "../../lib/lookSettings";
import FileSheet from "./FileSheet";

const CUSTOM_PRESET_VALUE = "__custom";

const BACKGROUND_MODE_OPTIONS = [
  { value: "solid", label: "Solid" },
  { value: "linear", label: "Linear" },
  { value: "radial", label: "Radial" },
  { value: "transparent", label: "Transparent" }
];

const FLOOR_MODE_OPTIONS = [
  { value: LOOK_FLOOR_MODES.STAGE, label: "Stage" },
  { value: LOOK_FLOOR_MODES.GRID, label: "Grid" },
  { value: LOOK_FLOOR_MODES.NONE, label: "None" }
];

const CAD_WORKSPACE_SCENE_TONE_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" }
];

const PRIMARY_LIGHT_OPTIONS = [
  { value: "directional", label: "Directional" },
  { value: "spot", label: "Spot" },
  { value: "point", label: "Point" }
];

const controlRowClasses = "space-y-1.5 px-3 py-2";
const fieldLabelClasses = "block text-xs font-medium text-muted-foreground";
const subsectionHeadingClasses = "px-3 pt-2 pb-1 text-xs font-medium text-muted-foreground";
const valueBadgeClasses = "rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground";
const compactButtonClasses = "h-8 px-2 text-xs";
const HEX_COLOR_PATTERN = /^#(?:[0-9a-fA-F]{3}){1,2}$/;
const COLOR_COMMIT_DELAY_MS = 180;
const SLIDER_COMMIT_DELAY_MS = 120;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function formatNumber(value, digits = 2) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "0";
  }
  return numericValue.toFixed(digits);
}

function Field({ label, value, children, className }) {
  return (
    <div className={cn(controlRowClasses, className)}>
      <div className="flex items-center justify-between gap-3">
        <span className={fieldLabelClasses}>{label}</span>
        {value != null ? (
          <span className={valueBadgeClasses}>{value}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function Section({ title, value, children }) {
  return (
    <AccordionItem value={value} className="border-border">
      <AccordionTrigger>{title}</AccordionTrigger>
      <AccordionContent className="py-1">{children}</AccordionContent>
    </AccordionItem>
  );
}

function Subsection({ title, children }) {
  return (
    <div className="border-t border-border first:border-t-0">
      <div className={subsectionHeadingClasses}>{title}</div>
      <div className="pb-1">{children}</div>
    </div>
  );
}

function SwitchRow({ label, checked, onChange }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2">
      <span className={fieldLabelClasses}>{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function SliderInput({ value, min, max, step = 0.01, onChange }) {
  const numericValue = Number.isFinite(Number(value)) ? Number(value) : min;
  const [draftValue, setDraftValue] = useState(numericValue);
  const commitTimerRef = useRef(null);

  useEffect(() => {
    setDraftValue(numericValue);
  }, [numericValue]);

  useEffect(() => () => {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
  }, []);

  const resolveNextValue = (nextValue) => {
    const numericNextValue = Number(nextValue);
    return Number.isFinite(numericNextValue) ? clamp(numericNextValue, min, max) : numericValue;
  };

  const commitValue = (nextValue) => {
    const resolvedNextValue = resolveNextValue(nextValue);
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    if (Math.abs(resolvedNextValue - numericValue) > 1e-9) {
      onChange(resolvedNextValue);
    }
  };

  const scheduleCommitValue = (nextValue) => {
    const resolvedNextValue = resolveNextValue(nextValue);
    setDraftValue(resolvedNextValue);
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    commitTimerRef.current = setTimeout(() => {
      commitValue(resolvedNextValue);
    }, SLIDER_COMMIT_DELAY_MS);
  };

  return (
    <Slider
      value={[draftValue]}
      min={min}
      max={max}
      step={step}
      onValueChange={(nextValue) => scheduleCommitValue(nextValue[0] ?? draftValue)}
      onValueCommit={(nextValue) => commitValue(nextValue[0] ?? draftValue)}
      className="h-8"
    />
  );
}

function ColorInput({ value, onChange }) {
  const normalizedValue = String(value || "#ffffff");
  const [draftValue, setDraftValue] = useState(normalizedValue);
  const commitTimerRef = useRef(null);

  useEffect(() => {
    setDraftValue(normalizedValue);
  }, [normalizedValue]);

  useEffect(() => () => {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
  }, []);

  const commitValue = (nextValue) => {
    const normalizedNextValue = String(nextValue || normalizedValue).toLowerCase();
    if (!HEX_COLOR_PATTERN.test(normalizedNextValue)) {
      return;
    }
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    if (normalizedNextValue !== normalizedValue.toLowerCase()) {
      onChange(normalizedNextValue);
    }
  };

  const scheduleCommitValue = (nextValue) => {
    const normalizedNextValue = String(nextValue || normalizedValue).toLowerCase();
    setDraftValue(normalizedNextValue);
    if (!HEX_COLOR_PATTERN.test(normalizedNextValue)) {
      return;
    }
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    commitTimerRef.current = setTimeout(() => {
      commitValue(normalizedNextValue);
    }, COLOR_COMMIT_DELAY_MS);
  };

  return (
    <label className="flex h-8 items-center gap-2 rounded-md border bg-background px-2">
      <Input
        type="color"
        className="h-5 w-8 cursor-pointer border-0 bg-transparent p-0 shadow-none"
        value={draftValue}
        onInput={(event) => scheduleCommitValue(event.currentTarget.value)}
        onChange={(event) => scheduleCommitValue(event.currentTarget.value)}
        onBlur={(event) => commitValue(event.currentTarget.value)}
        aria-label="Color"
      />
      <span className="text-xs font-medium text-muted-foreground">{draftValue}</span>
    </label>
  );
}

function SegmentedControl({ value, onChange, options }) {
  const templateColumns = `repeat(${Math.max(options.length, 1)}, minmax(0, 1fr))`;
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      size="sm"
      value={value}
      onValueChange={(nextValue) => {
        if (!nextValue) {
          return;
        }
        onChange(nextValue);
      }}
      className="grid h-8 w-full min-w-0"
      style={{ gridTemplateColumns: templateColumns }}
    >
      {options.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          className="text-xs data-[state=on]:font-semibold data-[state=on]:ring-1 data-[state=on]:ring-inset data-[state=on]:ring-primary"
        >
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

function SelectInput({ value, onChange, options }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" className="text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value} className="text-xs">
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function PresetSwatch({ preset = null }) {
  if (!preset) {
    return (
      <span
        className="h-4 w-8 shrink-0 rounded-md border border-dashed bg-muted"
        aria-hidden="true"
      />
    );
  }

  return (
    <span
      className="relative h-4 w-8 shrink-0 overflow-hidden rounded-md border shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]"
      style={{ backgroundImage: preset.preview.background }}
      aria-hidden="true"
    >
      <span
        className="absolute inset-y-0 right-0 w-3"
        style={{ backgroundColor: preset.preview.accentColor, opacity: 0.9 }}
      />
    </span>
  );
}

function LookPresetSelect({ activePresetId, onChange }) {
  const activePreset = LOOK_PRESETS.find((preset) => preset.id === activePresetId) || null;
  const selectValue = activePresetId || CUSTOM_PRESET_VALUE;

  return (
    <Select
      value={selectValue}
      onValueChange={(nextValue) => {
        if (nextValue === CUSTOM_PRESET_VALUE) {
          return;
        }
        onChange(nextValue);
      }}
    >
      <SelectTrigger size="sm" className="text-xs">
        <span className="flex min-w-0 items-center gap-2">
          <PresetSwatch preset={activePreset} />
          <span className="truncate">{activePreset?.label || "Custom"}</span>
        </span>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={CUSTOM_PRESET_VALUE} disabled className="text-xs" textValue="Custom">
          <span className="flex min-w-0 items-center gap-2">
            <PresetSwatch />
            <span>Custom</span>
          </span>
        </SelectItem>
        {LOOK_PRESETS.map((preset) => (
          <SelectItem key={preset.id} value={preset.id} className="text-xs" textValue={preset.label}>
            <span className="flex min-w-0 items-center gap-2">
              <PresetSwatch preset={preset} />
              <span className="truncate">{preset.label}</span>
              {preset.id === DEFAULT_LOOK_PRESET_ID ? (
                <span className="rounded-full border px-1.5 py-0.5 text-[9px] uppercase tracking-[0.08em] text-muted-foreground">
                  Default
                </span>
              ) : null}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function PositionPad({ value, onChange }) {
  const resolvedX = Number.isFinite(Number(value?.x)) ? Number(value.x) : 0;
  const resolvedZ = Number.isFinite(Number(value?.z)) ? Number(value.z) : 0;
  const [draftPosition, setDraftPosition] = useState({ x: resolvedX, z: resolvedZ });
  const draftPositionRef = useRef(draftPosition);
  const commitTimerRef = useRef(null);
  const x = draftPosition.x;
  const z = draftPosition.z;

  useEffect(() => {
    const nextPosition = { x: resolvedX, z: resolvedZ };
    draftPositionRef.current = nextPosition;
    setDraftPosition(nextPosition);
  }, [resolvedX, resolvedZ]);

  useEffect(() => () => {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
  }, []);

  const extent = useMemo(() => {
    const magnitude = Math.max(Math.abs(x), Math.abs(z), 220);
    return Math.min(5000, Math.ceil((magnitude * 1.2) / 20) * 20);
  }, [x, z]);

  const markerLeft = ((x + extent) / (extent * 2)) * 100;
  const markerTop = ((extent - z) / (extent * 2)) * 100;

  const commitPosition = (nextX, nextZ) => {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    if (nextX !== resolvedX) {
      onChange("x", nextX);
    }
    if (nextZ !== resolvedZ) {
      onChange("z", nextZ);
    }
  };

  const scheduleCommitPosition = (nextX, nextZ) => {
    const nextPosition = { x: nextX, z: nextZ };
    draftPositionRef.current = nextPosition;
    setDraftPosition(nextPosition);
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
    }
    commitTimerRef.current = setTimeout(() => {
      commitPosition(nextX, nextZ);
    }, SLIDER_COMMIT_DELAY_MS);
  };

  const updateFromPointer = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }
    const ratioX = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    const ratioY = clamp((event.clientY - rect.top) / rect.height, 0, 1);
    const nextX = Math.round((ratioX * 2 - 1) * extent);
    const nextZ = Math.round((1 - ratioY * 2) * extent);
    scheduleCommitPosition(nextX, nextZ);
  };

  return (
    <div className="space-y-2">
      <div
        className="relative h-36 w-full touch-none overflow-hidden rounded-md border bg-background"
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          updateFromPointer(event);
        }}
        onPointerMove={(event) => {
          if (!event.currentTarget.hasPointerCapture(event.pointerId)) {
            return;
          }
          updateFromPointer(event);
        }}
        onPointerUp={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
          }
          commitPosition(draftPositionRef.current.x, draftPositionRef.current.z);
        }}
      >
        <div
          className="absolute inset-0 opacity-45"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(154, 169, 188, 0.65) 1.5px, transparent 1.5px)",
            backgroundSize: "22px 22px"
          }}
          aria-hidden="true"
        />
        <div className="absolute inset-x-0 top-1/2 h-px bg-border" aria-hidden="true" />
        <div className="absolute inset-y-0 left-1/2 w-px bg-border" aria-hidden="true" />
        <div
          className="absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary bg-foreground shadow-xs"
          style={{ left: `${markerLeft}%`, top: `${markerTop}%` }}
          aria-hidden="true"
        />
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>X {Math.round(x)}</span>
        <span>Z {Math.round(z)}</span>
        <span>range +/-{extent}</span>
      </div>
    </div>
  );
}

function LookSettingsDebugExport({ lookSettings }) {
  const [copyStatus, setCopyStatus] = useState("idle");
  const statusTimerRef = useRef(null);
  const lookSettingsJson = useMemo(() => JSON.stringify(lookSettings, null, 2), [lookSettings]);

  useEffect(() => () => {
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current);
    }
  }, []);

  const handleCopy = async () => {
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current);
    }
    try {
      await copyTextToClipboard(lookSettingsJson);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
    statusTimerRef.current = setTimeout(() => {
      setCopyStatus("idle");
    }, 1600);
  };

  return (
    <div className="space-y-2 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={compactButtonClasses}
          onClick={handleCopy}
        >
          {copyStatus === "copied" ? (
            <Check className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
          )}
          <span>{copyStatus === "copied" ? "Copied" : "Copy JSON"}</span>
        </Button>
        {copyStatus === "failed" ? (
          <span className="text-[10px] font-medium text-destructive">Copy failed</span>
        ) : null}
      </div>
      <Textarea
        readOnly
        value={lookSettingsJson}
        onFocus={(event) => event.currentTarget.select()}
        className="h-44 resize-none bg-muted/30 px-2 py-1.5 font-mono text-[10px] leading-4 text-muted-foreground"
      />
    </div>
  );
}

export default function LookSettingsPopover({
  open,
  isDesktop,
  width,
  onStartResize,
  lookSettings,
  cadWorkspaceGlassTone = "light",
  updateLookSettings,
  updateCadWorkspaceGlassTone,
  handleResetLookSettings
}) {
  const [activePrimaryLight, setActivePrimaryLight] = useState("directional");
  const activeLookPresetId = useMemo(() => getLookPresetIdForSettings(lookSettings), [lookSettings]);

  const setMaterials = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      materials: {
        ...current.materials,
        ...patch
      }
    }));
  };

  const setBackground = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      background: {
        ...current.background,
        ...patch
      }
    }));
  };

  const setFloor = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      floor: {
        ...current.floor,
        ...patch
      }
    }));
  };

  const setEdges = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      edges: {
        ...current.edges,
        ...patch
      }
    }));
  };

  const setEnvironment = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      environment: {
        ...current.environment,
        ...patch
      }
    }));
  };

  const setLighting = (patch) => {
    updateLookSettings((current) => ({
      ...current,
      lighting: {
        ...current.lighting,
        ...patch
      }
    }));
  };

  const setLightConfig = (lightKey, patch) => {
    updateLookSettings((current) => ({
      ...current,
      lighting: {
        ...current.lighting,
        [lightKey]: {
          ...current.lighting[lightKey],
          ...patch
        }
      }
    }));
  };

  const setLightPosition = (lightKey, axis, nextValue) => {
    updateLookSettings((current) => ({
      ...current,
      lighting: {
        ...current.lighting,
        [lightKey]: {
          ...current.lighting[lightKey],
          position: {
            ...current.lighting[lightKey].position,
            [axis]: nextValue
          }
        }
      }
    }));
  };

  const applyLookPreset = (presetId) => {
    updateLookSettings(cloneLookPresetSettings(presetId));
    const preset = LOOK_PRESETS.find((lookPreset) => lookPreset.id === presetId);
    if (preset?.glassTone && typeof updateCadWorkspaceGlassTone === "function") {
      updateCadWorkspaceGlassTone(preset.glassTone);
    }
  };

  return (
    <FileSheet
      open={open}
      title="CAD explorer settings"
      isDesktop={isDesktop}
      width={width}
      onStartResize={onStartResize}
    >
      <Accordion type="multiple" defaultValue={["presets"]} className="text-sm">
        <Section title="Presets" value="presets">
          <Field label="Scene preset" value={activeLookPresetId ? null : "Custom"}>
            <LookPresetSelect activePresetId={activeLookPresetId} onChange={applyLookPreset} />
          </Field>
          <Field label="Scene tone">
            <SegmentedControl
              value={cadWorkspaceGlassTone}
              onChange={(nextTone) => updateCadWorkspaceGlassTone?.(nextTone)}
              options={CAD_WORKSPACE_SCENE_TONE_OPTIONS}
            />
          </Field>
          <div className="px-3 py-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={compactButtonClasses}
              onClick={handleResetLookSettings}
              aria-label="Reset explorer settings"
              title="Reset explorer settings"
            >
              <RotateCcw className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
              <span>Reset</span>
            </Button>
          </div>
        </Section>

        <Section title="Surface" value="surface">
          <Field label="Default Color">
            <ColorInput value={lookSettings.materials.defaultColor} onChange={(nextValue) => setMaterials({ defaultColor: nextValue })} />
          </Field>

          <Field label="Tint strength" value={formatNumber(lookSettings.materials.tintStrength)}>
            <SliderInput
              value={lookSettings.materials.tintStrength}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ tintStrength: nextValue })}
            />
          </Field>

          <Field label="Saturation" value={formatNumber(lookSettings.materials.saturation)}>
            <SliderInput
              value={lookSettings.materials.saturation}
              min={0}
              max={2.5}
              step={0.01}
              onChange={(nextValue) => setMaterials({ saturation: nextValue })}
            />
          </Field>

          <Field label="Contrast" value={formatNumber(lookSettings.materials.contrast)}>
            <SliderInput
              value={lookSettings.materials.contrast}
              min={0}
              max={2.5}
              step={0.01}
              onChange={(nextValue) => setMaterials({ contrast: nextValue })}
            />
          </Field>

          <Field label="Brightness" value={formatNumber(lookSettings.materials.brightness)}>
            <SliderInput
              value={lookSettings.materials.brightness}
              min={0}
              max={2}
              step={0.01}
              onChange={(nextValue) => setMaterials({ brightness: nextValue })}
            />
          </Field>
        </Section>

        <Section title="Finish" value="finish">
          <Field label="Roughness" value={formatNumber(lookSettings.materials.roughness)}>
            <SliderInput
              value={lookSettings.materials.roughness}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ roughness: nextValue })}
            />
          </Field>

          <Field label="Metalness" value={formatNumber(lookSettings.materials.metalness)}>
            <SliderInput
              value={lookSettings.materials.metalness}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ metalness: nextValue })}
            />
          </Field>

          <Field label="Env reflection" value={formatNumber(lookSettings.materials.envMapIntensity)}>
            <SliderInput
              value={lookSettings.materials.envMapIntensity}
              min={0}
              max={4}
              step={0.01}
              onChange={(nextValue) => setMaterials({ envMapIntensity: nextValue })}
            />
          </Field>

          <Field label="Clearcoat" value={formatNumber(lookSettings.materials.clearcoat)}>
            <SliderInput
              value={lookSettings.materials.clearcoat}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ clearcoat: nextValue })}
            />
          </Field>

          <Field label="Clearcoat roughness" value={formatNumber(lookSettings.materials.clearcoatRoughness)}>
            <SliderInput
              value={lookSettings.materials.clearcoatRoughness}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ clearcoatRoughness: nextValue })}
            />
          </Field>

          <Field label="Opacity" value={formatNumber(lookSettings.materials.opacity)}>
            <SliderInput
              value={lookSettings.materials.opacity}
              min={0}
              max={1}
              step={0.01}
              onChange={(nextValue) => setMaterials({ opacity: nextValue })}
            />
          </Field>
        </Section>

        <Section title="Edges" value="edges">
          <SwitchRow label="Show edges" checked={lookSettings.edges.enabled} onChange={(nextValue) => setEdges({ enabled: nextValue })} />
          {lookSettings.edges.enabled ? (
            <>
              <Field label="Edge color">
                <ColorInput value={lookSettings.edges.color} onChange={(nextValue) => setEdges({ color: nextValue })} />
              </Field>
              <Field label="Thickness" value={`${formatNumber(lookSettings.edges.thickness, 1)} px`}>
                <SliderInput
                  value={lookSettings.edges.thickness}
                  min={0.5}
                  max={6}
                  step={0.1}
                  onChange={(nextValue) => setEdges({ thickness: nextValue })}
                />
              </Field>
              <Field label="Edge opacity" value={formatNumber(lookSettings.edges.opacity)}>
                <SliderInput
                  value={lookSettings.edges.opacity}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(nextValue) => setEdges({ opacity: nextValue })}
                />
              </Field>
            </>
          ) : null}
        </Section>

        <Section title="Backdrop" value="backdrop">
          <Field label="Style">
            <SegmentedControl
              value={lookSettings.background.type}
              onChange={(nextValue) => setBackground({ type: nextValue })}
              options={BACKGROUND_MODE_OPTIONS}
            />
          </Field>

          {lookSettings.background.type === "solid" ? (
            <Field label="Color">
              <ColorInput value={lookSettings.background.solidColor} onChange={(nextValue) => setBackground({ solidColor: nextValue })} />
            </Field>
          ) : null}

          {lookSettings.background.type === "linear" ? (
            <>
              <Field label="Start color">
                <ColorInput value={lookSettings.background.linearStart} onChange={(nextValue) => setBackground({ linearStart: nextValue })} />
              </Field>
              <Field label="End color">
                <ColorInput value={lookSettings.background.linearEnd} onChange={(nextValue) => setBackground({ linearEnd: nextValue })} />
              </Field>
              <Field label="Angle" value={`${formatNumber(lookSettings.background.linearAngle, 0)} deg`}>
                <SliderInput
                  value={lookSettings.background.linearAngle}
                  min={-360}
                  max={360}
                  step={1}
                  onChange={(nextValue) => setBackground({ linearAngle: nextValue })}
                />
              </Field>
            </>
          ) : null}

          {lookSettings.background.type === "radial" ? (
            <>
              <Field label="Inner color">
                <ColorInput value={lookSettings.background.radialInner} onChange={(nextValue) => setBackground({ radialInner: nextValue })} />
              </Field>
              <Field label="Outer color">
                <ColorInput value={lookSettings.background.radialOuter} onChange={(nextValue) => setBackground({ radialOuter: nextValue })} />
              </Field>
            </>
          ) : null}
        </Section>

        <Section title="Floor" value="floor">
          <Field label="Mode">
            <SegmentedControl
              value={lookSettings.floor?.mode || LOOK_FLOOR_MODES.STAGE}
              onChange={(nextValue) => setFloor({ mode: nextValue })}
              options={FLOOR_MODE_OPTIONS}
            />
          </Field>
          {(lookSettings.floor?.mode || LOOK_FLOOR_MODES.STAGE) === LOOK_FLOOR_MODES.STAGE ? (
            <>
              <Field label="Color">
                <ColorInput
                  value={lookSettings.floor?.color || "#141416"}
                  onChange={(nextValue) => setFloor({ color: nextValue })}
                />
              </Field>
              <Field label="Roughness" value={formatNumber(lookSettings.floor?.roughness ?? 0.72)}>
                <SliderInput
                  value={lookSettings.floor?.roughness ?? 0.72}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(nextValue) => setFloor({ roughness: nextValue })}
                />
              </Field>
              <Field label="Reflectivity" value={formatNumber(lookSettings.floor?.reflectivity ?? 0.12)}>
                <SliderInput
                  value={lookSettings.floor?.reflectivity ?? 0.12}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(nextValue) => setFloor({ reflectivity: nextValue })}
                />
              </Field>
              <Field label="Shadow" value={formatNumber(lookSettings.floor?.shadowOpacity ?? 0.45)}>
                <SliderInput
                  value={lookSettings.floor?.shadowOpacity ?? 0.45}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(nextValue) => setFloor({ shadowOpacity: nextValue })}
                />
              </Field>
              <Field label="Backdrop blend" value={formatNumber(lookSettings.floor?.horizonBlend ?? 0)}>
                <SliderInput
                  value={lookSettings.floor?.horizonBlend ?? 0}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(nextValue) => setFloor({ horizonBlend: nextValue })}
                />
              </Field>
            </>
          ) : null}
        </Section>

        <Section title="Environment" value="environment">
          <SwitchRow label="Enable environment light" checked={lookSettings.environment.enabled} onChange={(nextValue) => setEnvironment({ enabled: nextValue })} />
          <Field label="Preset">
            <SelectInput
              value={lookSettings.environment.presetId}
              onChange={(nextValue) => setEnvironment({ presetId: nextValue })}
              options={ENVIRONMENT_PRESETS.map((preset) => ({ value: preset.id, label: preset.label }))}
            />
          </Field>
          <Field label="Intensity" value={formatNumber(lookSettings.environment.intensity)}>
            <SliderInput
              value={lookSettings.environment.intensity}
              min={0}
              max={4}
              step={0.01}
              onChange={(nextValue) => setEnvironment({ intensity: nextValue })}
            />
          </Field>
          <Field label="Rotation Y" value={formatNumber(lookSettings.environment.rotationY)}>
            <SliderInput
              value={lookSettings.environment.rotationY}
              min={-6.2832}
              max={6.2832}
              step={0.01}
              onChange={(nextValue) => setEnvironment({ rotationY: nextValue })}
            />
          </Field>
          <SwitchRow
            label="Use env as background"
            checked={lookSettings.environment.useAsBackground}
            onChange={(nextValue) => setEnvironment({ useAsBackground: nextValue })}
          />
        </Section>

        <Section title="Exposure" value="exposure">
          <Field label="Tone mapping" value={formatNumber(lookSettings.lighting.toneMappingExposure)}>
            <SliderInput
              value={lookSettings.lighting.toneMappingExposure}
              min={0.05}
              max={6}
              step={0.01}
              onChange={(nextValue) => setLighting({ toneMappingExposure: nextValue })}
            />
          </Field>
        </Section>

        <Section title="Primary Lights" value="primaryLights">
          <Tabs value={activePrimaryLight} onValueChange={setActivePrimaryLight} className="gap-0">
            <div className="px-3 py-2">
              <TabsList className="grid h-8 w-full grid-cols-3">
                {PRIMARY_LIGHT_OPTIONS.map((option) => (
                  <TabsTrigger key={option.value} value={option.value} className="text-xs">
                    {option.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            {PRIMARY_LIGHT_OPTIONS.map((option) => {
              const light = lookSettings.lighting[option.value];
              const supportsDistance = option.value !== "directional";
              return (
                <TabsContent key={option.value} value={option.value} className="mt-0">
                  <SwitchRow
                    label={`Enable ${option.label.toLowerCase()} light`}
                    checked={light.enabled}
                    onChange={(nextValue) => setLightConfig(option.value, { enabled: nextValue })}
                  />
                  <Field label="Color">
                    <ColorInput value={light.color} onChange={(nextValue) => setLightConfig(option.value, { color: nextValue })} />
                  </Field>
                  <Field label="Intensity" value={formatNumber(light.intensity)}>
                    <SliderInput
                      value={light.intensity}
                      min={0}
                      max={20}
                      step={0.01}
                      onChange={(nextValue) => setLightConfig(option.value, { intensity: nextValue })}
                    />
                  </Field>
                  {option.value === "spot" ? (
                    <Field label="Angle" value={formatNumber(light.angle)}>
                      <SliderInput
                        value={light.angle}
                        min={0.01}
                        max={1.57}
                        step={0.01}
                        onChange={(nextValue) => setLightConfig(option.value, { angle: nextValue })}
                      />
                    </Field>
                  ) : null}
                  {supportsDistance ? (
                    <Field label="Distance" value={formatNumber(light.distance, 0)}>
                      <SliderInput
                        value={light.distance}
                        min={0}
                        max={5000}
                        step={1}
                        onChange={(nextValue) => setLightConfig(option.value, { distance: nextValue })}
                      />
                    </Field>
                  ) : null}
                  <Field label="Position (X/Z plane)">
                    <PositionPad
                      value={light.position}
                      onChange={(axis, nextValue) => setLightPosition(option.value, axis, nextValue)}
                    />
                  </Field>
                  <Field label="Height (Y)" value={formatNumber(light.position.y, 0)}>
                    <SliderInput
                      value={light.position.y}
                      min={-5000}
                      max={5000}
                      step={1}
                      onChange={(nextValue) => setLightPosition(option.value, "y", nextValue)}
                    />
                  </Field>
                </TabsContent>
              );
            })}
          </Tabs>
        </Section>

        <Section title="Ambient Light" value="ambientLight">
          <SwitchRow
            label="Enable ambient"
            checked={lookSettings.lighting.ambient.enabled}
            onChange={(nextValue) => setLightConfig("ambient", { enabled: nextValue })}
          />
          <Field label="Color">
            <ColorInput value={lookSettings.lighting.ambient.color} onChange={(nextValue) => setLightConfig("ambient", { color: nextValue })} />
          </Field>
          <Field label="Intensity" value={formatNumber(lookSettings.lighting.ambient.intensity)}>
            <SliderInput
              value={lookSettings.lighting.ambient.intensity}
              min={0}
              max={20}
              step={0.01}
              onChange={(nextValue) => setLightConfig("ambient", { intensity: nextValue })}
            />
          </Field>
        </Section>

        <Section title="Hemisphere Light" value="hemisphereLight">
          <SwitchRow
            label="Enable hemisphere"
            checked={lookSettings.lighting.hemisphere.enabled}
            onChange={(nextValue) => setLightConfig("hemisphere", { enabled: nextValue })}
          />
          <Field label="Sky color">
            <ColorInput
              value={lookSettings.lighting.hemisphere.skyColor}
              onChange={(nextValue) => setLightConfig("hemisphere", { skyColor: nextValue })}
            />
          </Field>
          <Field label="Ground color">
            <ColorInput
              value={lookSettings.lighting.hemisphere.groundColor}
              onChange={(nextValue) => setLightConfig("hemisphere", { groundColor: nextValue })}
            />
          </Field>
          <Field label="Intensity" value={formatNumber(lookSettings.lighting.hemisphere.intensity)}>
            <SliderInput
              value={lookSettings.lighting.hemisphere.intensity}
              min={0}
              max={20}
              step={0.01}
              onChange={(nextValue) => setLightConfig("hemisphere", { intensity: nextValue })}
            />
          </Field>
        </Section>
        <Section title="Debug" value="debug">
          <LookSettingsDebugExport lookSettings={lookSettings} />
        </Section>
        </Accordion>
    </FileSheet>
  );
}
