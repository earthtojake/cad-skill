import { useEffect, useLayoutEffect, useRef } from "react";

import { filenameLabelForEntry } from "../../../lib/workbench/sidebar.js";

function normalizeRestoredOpenTabs(openTabs, createTabRecord, initialSelectedTabSnapshot) {
  const restoredTabs = Array.isArray(openTabs) ? openTabs : [];
  const defaultTabToolMode = String(initialSelectedTabSnapshot?.tabToolMode || "").trim();
  const defaultDrawingTool = String(initialSelectedTabSnapshot?.drawingTool || "").trim();

  if (!defaultTabToolMode || !defaultDrawingTool) {
    return restoredTabs;
  }

  return restoredTabs.map((tab) => {
    const tabToolMode = String(tab?.tabToolMode || "").trim();
    const drawingTool = String(tab?.drawingTool || "").trim();
    const drawingStrokes = Array.isArray(tab?.drawingStrokes) ? tab.drawingStrokes : [];
    const drawingUndoStack = Array.isArray(tab?.drawingUndoStack) ? tab.drawingUndoStack : [];
    const drawingRedoStack = Array.isArray(tab?.drawingRedoStack) ? tab.drawingRedoStack : [];

    if (
      tabToolMode !== "draw" ||
      drawingTool !== defaultDrawingTool ||
      drawingStrokes.length ||
      drawingUndoStack.length ||
      drawingRedoStack.length
    ) {
      return tab;
    }

    return createTabRecord(tab.key, {
      ...tab,
      tabToolMode: defaultTabToolMode
    });
  });
}

export function restoredSidebarWidthForViewport(
  restoredSession,
  {
    defaultSidebarWidth = 260,
    sidebarMinWidth = 0
  } = {}
) {
  const restoredWidth = Number(restoredSession?.sidebarWidth);
  const nextWidth = Number.isFinite(restoredWidth) ? restoredWidth : defaultSidebarWidth;

  if (restoredSession?.sidebarOpen && nextWidth <= sidebarMinWidth) {
    return defaultSidebarWidth;
  }

  return nextWidth;
}

export function useCadWorkspaceSession({
  manifestEntries,
  fileKey,
  readCadWorkspaceSessionState,
  restoredCadWorkspaceSessionRef,
  cadWorkspaceSessionBootstrappedRef,
  cadWorkspaceSessionPersistenceReadyRef,
  setQuery,
  setExpandedDirectoryIds,
  setSidebarOpen,
  setFileSheetOpen,
  setLookMenuOpen,
  setSidebarWidth,
  setTabToolsWidth,
  setUrdfEntryAnimationEnabled,
  setOpenTabs,
  applyTabRecord,
  selectedEntryKeyFromUrl,
  createTabRecord,
  initialSelectedTabSnapshot = null,
  upsertTabRecord,
  buildPersistedCadWorkspaceSession,
  scheduleCadWorkspaceSessionPersistence = () => {},
  flushCadWorkspaceSessionPersistence = () => {},
  selectedEntry,
  defaultDocumentTitle,
  selectedKey,
  entryMap,
  buildActiveTabSnapshot,
  catalogEntries,
  manifestRevision = 0,
  defaultSidebarWidth = 260,
  sidebarMinWidth = 0,
  readCadParam = () => null,
  readCadRefQueryParams = () => [],
  setPendingCadRefQueryParams = () => {},
  activateEntryTab,
  resetActiveWorkspace,
  writeCadParam
}) {
  const initialManifestRevisionRef = useRef(manifestRevision);
  const initialUnresolvedUrlSelectionRef = useRef(false);

  useLayoutEffect(() => {
    if (cadWorkspaceSessionBootstrappedRef.current) {
      return;
    }
    cadWorkspaceSessionBootstrappedRef.current = true;

    const validEntryKeys = manifestEntries.length
      ? new Set(manifestEntries.map((entry) => fileKey(entry)))
      : undefined;
    const initialCadRefQueryParams = readCadRefQueryParams();
    if (initialCadRefQueryParams.length) {
      setPendingCadRefQueryParams(initialCadRefQueryParams);
    }
    const urlSelectedKey = selectedEntryKeyFromUrl(manifestEntries);
    initialUnresolvedUrlSelectionRef.current = Boolean(readCadParam() || initialCadRefQueryParams.length) && !urlSelectedKey;
    const restoredSession = readCadWorkspaceSessionState(validEntryKeys);
    if (restoredSession) {
      restoredCadWorkspaceSessionRef.current = true;
      const restoredSidebarWidth = restoredSidebarWidthForViewport(restoredSession, {
        defaultSidebarWidth,
        sidebarMinWidth
      });
      const restoredOpenTabs = normalizeRestoredOpenTabs(
        restoredSession.openTabs,
        createTabRecord,
        initialSelectedTabSnapshot
      );
      setQuery(restoredSession.query);
      setExpandedDirectoryIds(new Set(restoredSession.expandedDirectoryIds));
      setSidebarOpen(restoredSession.sidebarOpen);
      setFileSheetOpen(restoredSession.fileSheetOpen);
      setLookMenuOpen(restoredSession.lookSheetOpen);
      setSidebarWidth(restoredSidebarWidth);
      setTabToolsWidth(restoredSession.tabToolsWidth);
      setUrdfEntryAnimationEnabled(restoredSession.urdfEntryAnimationEnabled);

      const urlActiveTab = urlSelectedKey
        ? (
          initialCadRefQueryParams.length
            ? null
            : restoredOpenTabs.find((tab) => tab.key === urlSelectedKey) || null
        )
        : null;
      const activeTab = urlSelectedKey
        ? (urlActiveTab || createTabRecord(urlSelectedKey, initialSelectedTabSnapshot || {}))
        : initialUnresolvedUrlSelectionRef.current
          ? null
          : restoredOpenTabs.find((tab) => tab.key === restoredSession.selectedKey) || null;

      setOpenTabs(urlSelectedKey
        ? upsertTabRecord(restoredOpenTabs, urlSelectedKey, activeTab)
        : restoredOpenTabs);
      if (activeTab) {
        applyTabRecord(activeTab);
      }
      cadWorkspaceSessionPersistenceReadyRef.current = true;
      return;
    }

    if (urlSelectedKey) {
      const nextTab = createTabRecord(urlSelectedKey, initialSelectedTabSnapshot || {});
      setOpenTabs((current) => upsertTabRecord(current, urlSelectedKey, nextTab));
      applyTabRecord(nextTab);
    }
    cadWorkspaceSessionPersistenceReadyRef.current = true;
  }, [
    applyTabRecord,
    createTabRecord,
    fileKey,
    manifestEntries,
    defaultSidebarWidth,
    readCadRefQueryParams,
    readCadParam,
    readCadWorkspaceSessionState,
    restoredCadWorkspaceSessionRef,
    selectedEntryKeyFromUrl,
    setExpandedDirectoryIds,
    setFileSheetOpen,
    setLookMenuOpen,
    setOpenTabs,
    setPendingCadRefQueryParams,
    setQuery,
    setSidebarOpen,
    setSidebarWidth,
    setTabToolsWidth,
    setUrdfEntryAnimationEnabled,
    upsertTabRecord,
    initialSelectedTabSnapshot,
    cadWorkspaceSessionBootstrappedRef,
    cadWorkspaceSessionPersistenceReadyRef,
    sidebarMinWidth
  ]);

  useEffect(() => {
    if (!cadWorkspaceSessionPersistenceReadyRef.current) {
      return;
    }
    scheduleCadWorkspaceSessionPersistence();
  }, [buildPersistedCadWorkspaceSession, scheduleCadWorkspaceSessionPersistence, cadWorkspaceSessionPersistenceReadyRef]);

  useEffect(() => {
    const persistSession = () => {
      if (!cadWorkspaceSessionPersistenceReadyRef.current) {
        return;
      }
      flushCadWorkspaceSessionPersistence();
    };

    window.addEventListener("pagehide", persistSession);
    window.addEventListener("beforeunload", persistSession);

    return () => {
      window.removeEventListener("pagehide", persistSession);
      window.removeEventListener("beforeunload", persistSession);
      persistSession();
    };
  }, [flushCadWorkspaceSessionPersistence, cadWorkspaceSessionPersistenceReadyRef]);

  useEffect(() => {
    const filename = filenameLabelForEntry(selectedEntry);
    document.title = filename ? `${defaultDocumentTitle} | ${filename}` : defaultDocumentTitle;
  }, [defaultDocumentTitle, selectedEntry]);

  useEffect(() => {
    if (selectedKey && entryMap.has(selectedKey)) {
      setOpenTabs((current) => upsertTabRecord(current, selectedKey, buildActiveTabSnapshot()));
      return;
    }

    const nextSelectedKey = selectedEntryKeyFromUrl(catalogEntries);
    if (!nextSelectedKey) {
      if (selectedKey) {
        if (manifestRevision === initialManifestRevisionRef.current && !entryMap.size) {
          return;
        }
        resetActiveWorkspace();
      }
      return;
    }

    if (nextSelectedKey !== selectedKey) {
      activateEntryTab(nextSelectedKey);
    }
  }, [
    activateEntryTab,
    buildActiveTabSnapshot,
    catalogEntries,
    entryMap,
    manifestRevision,
    resetActiveWorkspace,
    selectedEntryKeyFromUrl,
    selectedKey,
    setOpenTabs,
    upsertTabRecord
  ]);

  useEffect(() => {
    const syncSelectionFromHistory = () => {
      const nextCadRefQueryParams = readCadRefQueryParams();
      setPendingCadRefQueryParams(nextCadRefQueryParams);

      const nextSelectedKey = selectedEntryKeyFromUrl(catalogEntries);
      if (nextSelectedKey) {
        activateEntryTab(nextSelectedKey);
        return;
      }
      resetActiveWorkspace();
    };

    window.addEventListener("popstate", syncSelectionFromHistory);
    return () => {
      window.removeEventListener("popstate", syncSelectionFromHistory);
    };
  }, [
    activateEntryTab,
    catalogEntries,
    readCadRefQueryParams,
    resetActiveWorkspace,
    selectedEntryKeyFromUrl,
    setPendingCadRefQueryParams
  ]);

  useEffect(() => {
    if (selectedEntry) {
      writeCadParam(fileKey(selectedEntry));
      return;
    }
    if (!selectedKey) {
      const unresolvedUrlSelection = Boolean(readCadParam() || readCadRefQueryParams().length);
      if (unresolvedUrlSelection) {
        const urlSelectedKey = selectedEntryKeyFromUrl(catalogEntries);
        if (
          urlSelectedKey ||
          readCadParam() ||
          (
            initialUnresolvedUrlSelectionRef.current &&
            (manifestRevision === initialManifestRevisionRef.current || !entryMap.size)
          )
        ) {
          return;
        }
      }
      writeCadParam("");
    }
  }, [
    catalogEntries,
    fileKey,
    manifestRevision,
    readCadParam,
    readCadRefQueryParams,
    selectedEntry,
    selectedEntryKeyFromUrl,
    selectedKey,
    writeCadParam
  ]);

  useEffect(() => {
    if (!selectedKey) {
      return;
    }
    setOpenTabs((current) => upsertTabRecord(current, selectedKey, buildActiveTabSnapshot()));
  }, [buildActiveTabSnapshot, selectedKey, setOpenTabs, upsertTabRecord]);
}
