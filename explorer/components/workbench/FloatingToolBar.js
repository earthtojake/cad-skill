import {
  Copy,
  Crosshair,
  Download,
  MousePointer2,
  Play,
  PenTool
} from "lucide-react";
import { RENDER_FORMAT } from "../../lib/workbench/constants";
import { TooltipProvider } from "../ui/tooltip";
import DrawingToolbar from "./DrawingToolbar";
import { ToolbarButton, ToolbarTextButton } from "./ToolbarButton";
import {
  CAD_WORKSPACE_TOOLBAR_DESKTOP_WIDTH_CLASS,
  CAD_WORKSPACE_TOOLBAR_MOBILE_WIDTH_CLASS
} from "./ToolbarShell";

const FLOATING_TOOL_BAR_SURFACE_CLASS =
  "cad-glass-surface border border-sidebar-border text-sidebar-foreground shadow-sm";
const MOBILE_TOOL_BUTTON_CLASS =
  "h-10 min-h-10 w-full min-w-0 flex-none flex-col gap-0.5 px-1 text-[10px] leading-none has-[>svg]:px-1 [&_span]:leading-none";

function DesktopFloatingToolBar({
  renderFormat,
  floatingCadToolbarPosition,
  selectionToolActive,
  referenceSelectionPending = false,
  referenceSelectionUnavailable = false,
  urdfPosePickerAvailable = false,
  urdfPosePickerActive = false,
  handleToggleUrdfPosePicker,
  drawToolActive,
  handleSelectTabToolMode,
  explorerLoading,
  selectedMeshData,
  selectedDxfData,
  drawingToolOptions,
  drawingTool,
  handleSelectDrawingTool,
  handleUndoDrawing,
  handleRedoDrawing,
  handleClearDrawings,
  canUndoDrawing,
  canRedoDrawing,
  drawingStrokes,
  handleEnterPreviewMode,
  handleScreenshotCopy,
  handleScreenshotDownload
}) {
  const dxfMode = renderFormat === RENDER_FORMAT.DXF;
  const urdfMode = renderFormat === RENDER_FORMAT.URDF;
  const stlMode = renderFormat === RENDER_FORMAT.STL;
  const meshOnlyMode = stlMode || renderFormat === RENDER_FORMAT.THREE_MF;
  const captureDisabled = explorerLoading || (dxfMode ? !selectedDxfData : !selectedMeshData);
  const selectDisabled = explorerLoading || !selectedMeshData || referenceSelectionPending || referenceSelectionUnavailable;
  const posePickerDisabled = explorerLoading || !selectedMeshData || !urdfPosePickerAvailable;
  const selectLabel = referenceSelectionUnavailable
    ? "Selectable topology unavailable"
    : referenceSelectionPending
      ? "Preparing selectable topology"
      : "Select";

  return (
    <div
      className="absolute z-20 flex flex-col items-end gap-1.5"
      style={floatingCadToolbarPosition}
    >
      <TooltipProvider delayDuration={250}>
        <div className={`pointer-events-auto inline-flex w-fit items-center gap-1 self-end rounded-md p-1 ${FLOATING_TOOL_BAR_SURFACE_CLASS}`}>
          {!dxfMode ? (
            <>
              {!urdfMode && !meshOnlyMode ? (
                <>
                  <ToolbarButton
                    label={selectLabel}
                    active={selectionToolActive}
                    onClick={() => handleSelectTabToolMode("references")}
                    disabled={selectDisabled}
                    aria-pressed={selectionToolActive}
                  >
                    <MousePointer2 className="size-3.5" strokeWidth={2} aria-hidden="true" />
                  </ToolbarButton>

                  <ToolbarButton
                    label="Draw"
                    active={drawToolActive}
                    onClick={() => handleSelectTabToolMode("draw")}
                    disabled={explorerLoading || !selectedMeshData}
                    aria-pressed={drawToolActive}
                  >
                    <PenTool className="size-3.5" strokeWidth={2} aria-hidden="true" />
                  </ToolbarButton>
                </>
              ) : null}

              {urdfMode ? (
                <ToolbarButton
                  label="Select Pose"
                  active={urdfPosePickerActive}
                  onClick={handleToggleUrdfPosePicker}
                  disabled={posePickerDisabled}
                  aria-pressed={urdfPosePickerActive}
                >
                  <Crosshair className="size-3.5" strokeWidth={2} aria-hidden="true" />
                </ToolbarButton>
              ) : null}

              <ToolbarButton
                label="Open orbit preview"
                onClick={handleEnterPreviewMode}
                disabled={explorerLoading || !selectedMeshData}
              >
                <Play className="size-3.5" strokeWidth={2} aria-hidden="true" />
              </ToolbarButton>
            </>
          ) : null}

          <ToolbarButton
            label="Copy screenshot to clipboard"
            onClick={() => {
              void handleScreenshotCopy();
            }}
            disabled={captureDisabled}
          >
            <Copy className="size-3.5" strokeWidth={2} aria-hidden="true" />
          </ToolbarButton>

          <ToolbarButton
            label="Download screenshot"
            onClick={() => {
              void handleScreenshotDownload();
            }}
            disabled={captureDisabled}
          >
            <Download className="size-3.5" strokeWidth={2} aria-hidden="true" />
          </ToolbarButton>
        </div>
      </TooltipProvider>

      {!dxfMode && !meshOnlyMode && drawToolActive ? (
        <DrawingToolbar
          className={CAD_WORKSPACE_TOOLBAR_DESKTOP_WIDTH_CLASS}
          drawingToolOptions={drawingToolOptions}
          drawingTool={drawingTool}
          handleSelectDrawingTool={handleSelectDrawingTool}
          handleUndoDrawing={handleUndoDrawing}
          handleRedoDrawing={handleRedoDrawing}
          handleClearDrawings={handleClearDrawings}
          canUndoDrawing={canUndoDrawing}
          canRedoDrawing={canRedoDrawing}
          drawingStrokes={drawingStrokes}
        />
      ) : null}
    </div>
  );
}

function MobileFloatingToolBar({
  renderFormat,
  mobileCadBottomBarPosition,
  drawToolActive,
  drawingToolOptions,
  drawingTool,
  handleSelectDrawingTool,
  handleUndoDrawing,
  canUndoDrawing,
  handleRedoDrawing,
  canRedoDrawing,
  handleClearDrawings,
  drawingStrokes,
  selectionToolActive,
  referenceSelectionPending = false,
  referenceSelectionUnavailable = false,
  urdfPosePickerAvailable = false,
  urdfPosePickerActive = false,
  handleToggleUrdfPosePicker,
  handleSelectTabToolMode,
  explorerLoading,
  selectedMeshData,
  selectedDxfData,
  handleEnterPreviewMode,
  handleScreenshotCopy
}) {
  const dxfMode = renderFormat === RENDER_FORMAT.DXF;
  const urdfMode = renderFormat === RENDER_FORMAT.URDF;
  const stlMode = renderFormat === RENDER_FORMAT.STL;
  const meshOnlyMode = stlMode || renderFormat === RENDER_FORMAT.THREE_MF;
  const captureDisabled = explorerLoading || (dxfMode ? !selectedDxfData : !selectedMeshData);
  const selectDisabled = explorerLoading || !selectedMeshData || referenceSelectionPending || referenceSelectionUnavailable;
  const posePickerDisabled = explorerLoading || !selectedMeshData || !urdfPosePickerAvailable;
  const selectLabel = referenceSelectionUnavailable
    ? "Selectable topology unavailable"
    : referenceSelectionPending
      ? "Preparing selectable topology"
      : "Select";

  return (
    <TooltipProvider delayDuration={250}>
      <div
        className="absolute z-20 flex flex-col gap-1.5"
        style={mobileCadBottomBarPosition}
      >
        {!dxfMode && !meshOnlyMode && drawToolActive ? (
          <DrawingToolbar
            className={CAD_WORKSPACE_TOOLBAR_MOBILE_WIDTH_CLASS}
            layout="scroll"
            drawingToolOptions={drawingToolOptions}
            drawingTool={drawingTool}
            handleSelectDrawingTool={handleSelectDrawingTool}
            handleUndoDrawing={handleUndoDrawing}
            handleRedoDrawing={handleRedoDrawing}
            handleClearDrawings={handleClearDrawings}
            canUndoDrawing={canUndoDrawing}
            canRedoDrawing={canRedoDrawing}
            drawingStrokes={drawingStrokes}
          />
        ) : null}

        <div className={`pointer-events-auto flex w-full items-center rounded-md p-2 ${FLOATING_TOOL_BAR_SURFACE_CLASS}`}>
          <div
            className="grid w-full min-w-0 auto-cols-fr grid-flow-col gap-1"
          >
            {!dxfMode ? (
              <>
                {urdfMode || meshOnlyMode ? null : (
                  <>
                    <ToolbarTextButton
                      label={selectLabel}
                      active={selectionToolActive}
                      onClick={() => {
                        handleSelectTabToolMode("references");
                      }}
                      disabled={selectDisabled}
                      className={MOBILE_TOOL_BUTTON_CLASS}
                      aria-pressed={selectionToolActive}
                    >
                      <MousePointer2 className="size-4" strokeWidth={2} aria-hidden="true" />
                      <span>Select</span>
                    </ToolbarTextButton>

                    <ToolbarTextButton
                      label="Draw"
                      active={drawToolActive}
                      onClick={() => {
                        handleSelectTabToolMode("draw");
                      }}
                      disabled={explorerLoading || !selectedMeshData}
                      className={MOBILE_TOOL_BUTTON_CLASS}
                      aria-pressed={drawToolActive}
                    >
                      <PenTool className="size-4" strokeWidth={2} aria-hidden="true" />
                      <span>Draw</span>
                    </ToolbarTextButton>
                  </>
                )}
                {urdfMode ? (
                  <ToolbarTextButton
                    label="Select Pose"
                    active={urdfPosePickerActive}
                    onClick={handleToggleUrdfPosePicker}
                    disabled={posePickerDisabled}
                    className={MOBILE_TOOL_BUTTON_CLASS}
                    aria-pressed={urdfPosePickerActive}
                  >
                    <Crosshair className="size-4" strokeWidth={2} aria-hidden="true" />
                    <span>Pose</span>
                  </ToolbarTextButton>
                ) : null}
              </>
            ) : null}

            {!dxfMode ? (
              <ToolbarTextButton
                label="Play"
                onClick={handleEnterPreviewMode}
                disabled={explorerLoading || !selectedMeshData}
                className={MOBILE_TOOL_BUTTON_CLASS}
              >
                <Play className="size-4" strokeWidth={2} aria-hidden="true" />
                <span>Play</span>
              </ToolbarTextButton>
            ) : null}

            <ToolbarTextButton
              label="Copy"
              onClick={() => {
                void handleScreenshotCopy();
              }}
              disabled={captureDisabled}
              className={MOBILE_TOOL_BUTTON_CLASS}
            >
              <Copy className="size-4" strokeWidth={2} aria-hidden="true" />
              <span>Copy</span>
            </ToolbarTextButton>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

export default function FloatingToolBar({
  previewMode,
  selectedEntry,
  isDesktop,
  sidebarOpen,
  ...toolbarProps
}) {
  if (previewMode || !selectedEntry) {
    return null;
  }

  if (isDesktop) {
    return <DesktopFloatingToolBar {...toolbarProps} />;
  }

  if (sidebarOpen) {
    return null;
  }

  return <MobileFloatingToolBar {...toolbarProps} />;
}
