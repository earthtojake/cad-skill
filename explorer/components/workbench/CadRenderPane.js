import { useEffect } from "react";
import CadExplorer from "../CadExplorer";
import DxfExplorer from "../DxfExplorer";
import { X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Button } from "../ui/button";
import ExplorerAlertCommand from "./ExplorerAlertCommand";
import { RENDER_FORMAT } from "../../lib/workbench/constants";
import { LOOK_FLOOR_MODES } from "../../lib/lookSettings";
import { EXPLORER_SCENE_SCALE } from "../../lib/explorer/sceneScale";
import { EXPLORER_PICK_MODE } from "../../lib/explorer/constants";

const EMPTY_LIST = Object.freeze([]);

export default function CadRenderPane({
  explorerRef,
  renderFormat,
  renderPartsIndividually = false,
  selectedMeshData,
  selectedDxfData,
  selectedDxfMeshData,
  selectedKey,
  selectedDxfKey,
  missingFileRef = "",
  explorerPerspective,
  explorerPerspectiveRef,
  lookSettings,
  previewMode,
  viewportFrameInsets,
  explorerLoading,
  explorerAlert,
  stepUpdateInProgress,
  referenceSelectionPending = false,
  referenceSelectionUnavailable = false,
  viewPlaneOffsetRight = 16,
  explorerMode,
  assemblyParts,
  hiddenPartIds,
  selectedPartIds,
  hoveredPartId,
  hoveredReferenceId,
  selectedReferenceIds,
  selectorRuntime,
  pickableFaces,
  pickableEdges,
  pickableVertices,
  focusedPartIds = "",
  drawToolActive,
  drawingTool,
  drawingStrokes,
  handleDrawingStrokesChange,
  handlePerspectiveChange,
  handleModelHoverChange,
  handleModelReferenceActivate,
  handleModelReferenceDoubleActivate,
  handleExplorerAlertChange,
  selectionCount,
  copyButtonLabel,
  handleCopySelection,
  handleScreenshotCopy,
  partIntroAnimation = null,
  urdfPosePicker = null
}) {
  const explorerAlertVariant = explorerAlert?.severity === "warning" ? "warning" : "destructive";
  const explorerAlertSummaryClasses = explorerAlert?.severity === "warning" ? "text-chart-5" : "text-destructive";
  const compactExplorerAlert = Boolean(explorerAlert?.compact);
  const dxfMode = renderFormat === RENDER_FORMAT.DXF;
  const urdfMode = renderFormat === RENDER_FORMAT.URDF;
  const stlMode = renderFormat === RENDER_FORMAT.STL;
  const meshOnlyMode = stlMode || renderFormat === RENDER_FORMAT.THREE_MF;
  const dxfMeshPreviewReady = dxfMode && !!selectedDxfMeshData;
  const activeMeshData = dxfMeshPreviewReady ? selectedDxfMeshData : selectedMeshData;
  const activeModelKey = dxfMeshPreviewReady ? (selectedDxfKey || selectedKey) : selectedKey;
  const missingFileLabel = String(missingFileRef || "").trim();
  const topologySelectionPending = Boolean(referenceSelectionPending && !dxfMode && !urdfMode && !meshOnlyMode);
  const topologySelectionUnavailable = Boolean(referenceSelectionUnavailable && !dxfMode && !urdfMode && !meshOnlyMode);
  const urdfPosePickerActive = Boolean(urdfPosePicker?.active);
  const urdfPosePickerPrompt = "Select target";
  const posePickerExitStyle = {
    left: `calc(${Math.max(Number(viewportFrameInsets?.left) || 0, 0)}px + 0.75rem)`,
    top: `calc(${Math.max(Number(viewportFrameInsets?.top) || 0, 0)}px + 0.75rem)`
  };
  const ctaMode = !dxfMode && !meshOnlyMode && drawToolActive
    ? "screenshot"
    : selectionCount > 0
      ? "selection"
      : "";
  const bottomOverlayStyle = {
    bottom: "1rem"
  };
  const ctaLabel = ctaMode === "screenshot" ? "Copy Screenshot" : copyButtonLabel;
  const ctaTitle = ctaMode === "screenshot" ? "Copy screenshot to clipboard" : copyButtonLabel;
  const ctaDisabled = ctaMode === "screenshot" ? explorerLoading || !activeMeshData : false;

  useEffect(() => {
    if (!urdfPosePickerActive || typeof window === "undefined" || typeof document === "undefined") {
      return undefined;
    }
    const handleEscape = (event) => {
      if (event.defaultPrevented) {
        return;
      }
      if (event.key !== "Escape" && event.key !== "Esc" && event.code !== "Escape") {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      urdfPosePicker?.onCancel?.();
    };
    window.addEventListener("keydown", handleEscape, true);
    document.addEventListener("keydown", handleEscape, true);
    return () => {
      window.removeEventListener("keydown", handleEscape, true);
      document.removeEventListener("keydown", handleEscape, true);
    };
  }, [urdfPosePicker, urdfPosePickerActive]);

  return (
    <div className="absolute inset-0">
      {dxfMode && !dxfMeshPreviewReady ? (
        <DxfExplorer
          ref={explorerRef}
          dxfData={selectedDxfData}
          modelKey={selectedDxfKey}
          onExplorerAlertChange={handleExplorerAlertChange}
        />
      ) : (
        <CadExplorer
          ref={explorerRef}
          meshData={activeMeshData}
          modelKey={activeModelKey}
          perspective={explorerPerspective}
          perspectiveRef={explorerPerspectiveRef}
          showEdges={true}
          recomputeNormals={false}
          lookSettings={lookSettings}
          previewMode={dxfMode ? false : previewMode}
          showViewPlane={dxfMode ? true : !previewMode}
          floorModeOverride={dxfMode ? LOOK_FLOOR_MODES.GRID : ""}
          sceneScaleMode={urdfMode ? EXPLORER_SCENE_SCALE.URDF : EXPLORER_SCENE_SCALE.CAD}
          viewPlaneOffsetRight={viewPlaneOffsetRight}
          viewPlaneOffsetBottom="1rem"
          compactViewPlane={false}
          viewportFrameInsets={viewportFrameInsets}
          isLoading={explorerLoading}
          pickMode={
            urdfMode || meshOnlyMode || topologySelectionPending || topologySelectionUnavailable
              ? EXPLORER_PICK_MODE.NONE
              : (!dxfMode && explorerMode === "assembly" ? EXPLORER_PICK_MODE.ASSEMBLY : EXPLORER_PICK_MODE.AUTO)
          }
          renderPartsIndividually={urdfMode ? true : renderPartsIndividually}
          pickableParts={dxfMode || urdfMode || meshOnlyMode ? EMPTY_LIST : assemblyParts}
          hiddenPartIds={dxfMode || meshOnlyMode ? [] : hiddenPartIds}
          selectedPartIds={dxfMode || meshOnlyMode ? [] : selectedPartIds}
          hoveredPartId={dxfMode || meshOnlyMode ? "" : hoveredPartId}
          hoveredReferenceId={dxfMode || meshOnlyMode ? "" : hoveredReferenceId}
          selectedReferenceIds={dxfMode || meshOnlyMode ? [] : selectedReferenceIds}
          selectorRuntime={dxfMode || meshOnlyMode ? null : selectorRuntime}
          pickableFaces={dxfMode || meshOnlyMode ? [] : pickableFaces}
          pickableEdges={dxfMode || meshOnlyMode ? [] : pickableEdges}
          pickableVertices={dxfMode || meshOnlyMode ? [] : pickableVertices}
          focusedPartId={dxfMode || meshOnlyMode ? "" : focusedPartIds}
          drawingEnabled={!dxfMode && !meshOnlyMode && drawToolActive}
          drawingTool={drawingTool}
          drawingStrokes={dxfMode || meshOnlyMode ? [] : drawingStrokes}
          onDrawingStrokesChange={handleDrawingStrokesChange}
          onPerspectiveChange={handlePerspectiveChange}
          onHoverReferenceChange={handleModelHoverChange}
          onActivateReference={handleModelReferenceActivate}
          onDoubleActivateReference={handleModelReferenceDoubleActivate}
          onExplorerAlertChange={handleExplorerAlertChange}
          partIntroAnimation={partIntroAnimation}
          urdfPosePicker={urdfPosePicker}
        />
      )}
      {!previewMode && missingFileLabel ? (
        <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center px-4">
          <Alert
            variant="destructive"
            className="cad-glass-popover pointer-events-auto w-full max-w-xl p-5 text-center shadow-lg"
          >
            <p className="col-start-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-destructive">
              File does not exist
            </p>
            <AlertTitle className="col-start-1 mt-1 line-clamp-none text-lg text-foreground">File does not exist</AlertTitle>
            <AlertDescription className="col-start-1 mt-1 text-sm leading-6 text-muted-foreground">
              <code className="rounded-md bg-muted px-2 py-1 text-xs text-foreground">{missingFileLabel}</code>
            </AlertDescription>
          </Alert>
        </div>
      ) : null}
      {!previewMode && explorerAlert ? (
        <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center px-4">
          <Alert
            variant={explorerAlertVariant}
            className={`cad-glass-popover pointer-events-auto w-full shadow-lg ${compactExplorerAlert ? "max-w-lg p-4" : "max-w-xl p-5"}`}
          >
            {compactExplorerAlert ? null : (
              <p className={`col-start-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${explorerAlertSummaryClasses}`}>
                {explorerAlert.summary || "Explorer error"}
              </p>
            )}
            <AlertTitle className={`col-start-1 line-clamp-none text-foreground ${compactExplorerAlert ? "text-base" : "mt-1 text-lg"}`}>{explorerAlert.title}</AlertTitle>
            <AlertDescription className={`col-start-1 mt-1 gap-2 ${compactExplorerAlert ? "text-xs leading-5 whitespace-pre-line" : "text-sm leading-6"}`}>
              <p>{explorerAlert.message}</p>
              {!compactExplorerAlert && explorerAlert.resolution ? (
                <p className="text-muted-foreground/80">{explorerAlert.resolution}</p>
              ) : null}
            </AlertDescription>
            <div className="col-start-1">
              <ExplorerAlertCommand command={explorerAlert.command} />
            </div>
          </Alert>
        </div>
      ) : null}
      {!previewMode && stepUpdateInProgress ? (
        <Alert
          role="status"
          className="cad-glass-popover pointer-events-none absolute left-1/2 z-20 w-auto -translate-x-1/2 px-3 py-1.5 text-[11px] font-medium text-popover-foreground shadow-sm"
          style={bottomOverlayStyle}
        >
          STEP changed. Updating/regenerating references...
        </Alert>
      ) : null}
      {!previewMode && !stepUpdateInProgress && topologySelectionPending ? (
        <Alert
          role="status"
          className="cad-glass-popover pointer-events-none absolute left-1/2 z-20 w-auto -translate-x-1/2 px-3 py-1.5 text-[11px] font-medium text-popover-foreground shadow-sm"
          style={bottomOverlayStyle}
        >
          Preparing selectable topology...
        </Alert>
      ) : null}
      {!previewMode && !stepUpdateInProgress && topologySelectionUnavailable ? (
        <Alert
          role="status"
          variant="warning"
          className="cad-glass-popover pointer-events-none absolute left-1/2 z-20 w-auto -translate-x-1/2 px-3 py-1.5 text-[11px] font-medium text-popover-foreground shadow-sm"
          style={bottomOverlayStyle}
        >
          Selectable topology unavailable.
        </Alert>
      ) : null}
      {!previewMode && urdfPosePickerActive ? (
        <Button
          type="button"
          variant="outline"
          size="icon-xs"
          className="cad-glass-popover pointer-events-auto absolute z-30 size-6 rounded-md border-sidebar-border p-0 text-popover-foreground shadow-sm"
          style={posePickerExitStyle}
          onClick={() => {
            urdfPosePicker?.onCancel?.();
          }}
          aria-label="Exit Select Pose"
          title="Exit Select Pose"
        >
          <X className="size-3.5" strokeWidth={2} aria-hidden="true" />
        </Button>
      ) : null}
      {!previewMode && urdfPosePickerActive ? (
        <Alert
          role="status"
          className="cad-glass-popover pointer-events-none absolute left-1/2 z-20 w-auto -translate-x-1/2 px-3 py-1.5 text-[11px] font-medium text-popover-foreground shadow-sm"
          style={bottomOverlayStyle}
        >
          {urdfPosePickerPrompt}
        </Alert>
      ) : null}
      {!previewMode && ctaMode && !stepUpdateInProgress && !topologySelectionPending && !topologySelectionUnavailable ? (
        <div
          className="pointer-events-none absolute inset-x-4 z-20 flex justify-center"
          style={bottomOverlayStyle}
        >
          <Button
            type="button"
            variant="default"
            size="sm"
            className="pointer-events-auto h-9 min-w-0 max-w-[52rem] border border-white bg-white px-4 text-[12px] font-semibold text-black shadow-lg shadow-black/20 hover:bg-white/90 focus-visible:ring-white/40 dark:border-white dark:bg-white dark:text-black dark:hover:bg-white/90 max-sm:w-full"
            disabled={ctaDisabled}
            onClick={() => {
              if (ctaMode === "screenshot") {
                void handleScreenshotCopy?.();
                return;
              }
              void handleCopySelection();
            }}
            title={ctaTitle}
          >
            <span className="min-w-0 truncate">{ctaLabel}</span>
          </Button>
        </div>
      ) : null}
    </div>
  );
}
