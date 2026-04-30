import { useCallback, useEffect, useRef, useState } from "react";
import {
  isAbortError,
  loadRender3Mf,
  loadRenderDxf,
  loadRenderGlb,
  loadRenderJson,
  loadRenderSelectorBundle,
  loadRenderStl,
  loadRenderUrdf,
  peekRender3Mf,
  peekRenderDxf,
  peekRenderGlb,
  peekRenderJson,
  peekRenderSelectorBundle,
  peekRenderStl,
  peekRenderUrdf
} from "../../../lib/renderAssetClient";
import {
  assemblyCompositionMeshRequests,
  assemblyRootFromTopology,
  buildAssemblyMeshData
} from "../../../lib/assembly/meshData";
import { mapWithConcurrency } from "../../../lib/async/concurrency";
import { ASSET_STATUS, REFERENCE_STATUS } from "../../../lib/workbench/constants";

const ASSEMBLY_MESH_LOAD_CONCURRENCY = 8;

function abortLoad(controllerRef) {
  controllerRef.current?.abort();
  controllerRef.current = null;
}

function urdfMeshUrls(urdfData) {
  return [...new Set(
    (Array.isArray(urdfData?.links) ? urdfData.links : [])
      .flatMap((link) => Array.isArray(link?.visuals) ? link.visuals : [])
      .map((visual) => String(visual?.meshUrl || "").trim())
      .filter(Boolean)
  )];
}

function entryAsset(entry, key) {
  return entry?.assets?.[key] || null;
}

function entryAssetUrl(entry, key) {
  return String(entryAsset(entry, key)?.url || "").trim();
}

function entryAssetHash(entry, key) {
  return String(entryAsset(entry, key)?.hash || "").trim();
}

function entryUrdfAssetHash(entry) {
  return [
    entryAssetHash(entry, "urdf"),
    entryAssetHash(entry, "explorerMetadata"),
    entryAssetHash(entry, "motionExplorerMetadata")
  ].filter(Boolean).join(":");
}

function entryMeshAssetKey(entry) {
  return entry?.kind === "stl" || entry?.kind === "3mf" ? entry.kind : "glb";
}

function entryMeshAssetUrl(entry) {
  return entryAssetUrl(entry, entryMeshAssetKey(entry));
}

function entryMeshAssetHash(entry) {
  return entryAssetHash(entry, entryMeshAssetKey(entry));
}

function resolveAssetUrl(url, baseUrl = "") {
  const rawUrl = String(url || "").trim();
  if (!rawUrl || rawUrl.startsWith("/") || /^[a-z][a-z0-9+.-]*:/i.test(rawUrl)) {
    return rawUrl;
  }
  if (typeof window === "undefined") {
    return rawUrl;
  }
  return new URL(rawUrl, new URL(baseUrl || window.location.href, window.location.href)).toString();
}

function peekRenderMeshForEntry(entry) {
  const meshUrl = entryMeshAssetUrl(entry);
  const assetKey = entryMeshAssetKey(entry);
  if (assetKey === "stl") {
    return peekRenderStl(meshUrl);
  }
  if (assetKey === "3mf") {
    return peekRender3Mf(meshUrl);
  }
  return peekRenderGlb(meshUrl);
}

function loadRenderMeshForEntry(entry, options) {
  const meshUrl = entryMeshAssetUrl(entry);
  const assetKey = entryMeshAssetKey(entry);
  if (assetKey === "stl") {
    return loadRenderStl(meshUrl, options);
  }
  if (assetKey === "3mf") {
    return loadRender3Mf(meshUrl, options);
  }
  return loadRenderGlb(meshUrl, options);
}

function createAssemblyPreviewMeshData(meshData, topologyManifest = null) {
  return {
    ...meshData,
    parts: null,
    assemblyRoot: assemblyRootFromTopology(topologyManifest)
  };
}

export function useCadAssets({
  entryHasMesh,
  entryHasReferences,
  entryHasDxf,
  buildNormalizedReferenceState,
}) {
  const [meshState, setMeshState] = useState(null);
  const [meshLoadInProgress, setMeshLoadInProgress] = useState(false);
  const [meshLoadTargetFile, setMeshLoadTargetFile] = useState("");
  const [meshLoadStage, setMeshLoadStage] = useState("");
  const [status, setStatus] = useState(ASSET_STATUS.READY);
  const [error, setError] = useState("");
  const [dxfState, setDxfState] = useState(null);
  const [dxfStatus, setDxfStatus] = useState(ASSET_STATUS.PENDING);
  const [dxfError, setDxfError] = useState("");
  const [dxfLoadStage, setDxfLoadStage] = useState("");
  const [urdfState, setUrdfState] = useState(null);
  const [urdfStatus, setUrdfStatus] = useState(ASSET_STATUS.PENDING);
  const [urdfError, setUrdfError] = useState("");
  const [urdfLoadStage, setUrdfLoadStage] = useState("");
  const [referenceState, setReferenceState] = useState(null);
  const [referenceStatus, setReferenceStatus] = useState(REFERENCE_STATUS.IDLE);
  const [referenceError, setReferenceError] = useState("");
  const [referenceLoadStage, setReferenceLoadStage] = useState("");

  const requestIdRef = useRef(0);
  const dxfRequestIdRef = useRef(0);
  const urdfRequestIdRef = useRef(0);
  const referenceRequestIdRef = useRef(0);
  const meshAbortControllerRef = useRef(null);
  const dxfAbortControllerRef = useRef(null);
  const urdfAbortControllerRef = useRef(null);
  const referenceAbortControllerRef = useRef(null);

  const getAssemblyMeshHash = useCallback((entry) => {
    return [entryAssetHash(entry, "topology"), entryAssetHash(entry, "glb")].filter(Boolean).join(":");
  }, []);

  const buildAssemblyMeshState = useCallback((entry, topologyManifest, meshesBySourcePath) => {
    return {
      file: entry.file,
      kind: entry.kind,
      meshHash: getAssemblyMeshHash(entry),
      meshData: buildAssemblyMeshData(topologyManifest, meshesBySourcePath),
      assemblyStructureReady: true,
      assemblyInteractionReady: true,
      assemblyBackgroundError: ""
    };
  }, [getAssemblyMeshHash]);

  const buildAssemblyPreviewMeshState = useCallback((entry, meshData, topologyManifest = null) => {
    const previewMeshData = createAssemblyPreviewMeshData(meshData, topologyManifest);
    return {
      file: entry.file,
      kind: entry.kind,
      meshHash: getAssemblyMeshHash(entry),
      meshData: previewMeshData,
      assemblyStructureReady: !!previewMeshData.assemblyRoot,
      assemblyInteractionReady: false,
      assemblyBackgroundError: ""
    };
  }, [getAssemblyMeshHash]);

  const getCachedMeshState = useCallback((entry) => {
    if (!entryHasMesh(entry)) {
      return null;
    }
    if (entry?.kind === "assembly") {
      const previewMeshData = peekRenderGlb(entryAssetUrl(entry, "glb"));
      if (!previewMeshData) {
        return null;
      }
      const topologyUrl = entryAssetUrl(entry, "topology");
      const topologyManifest = peekRenderJson(topologyUrl);
      if (!topologyManifest) {
        return buildAssemblyPreviewMeshState(entry, previewMeshData);
      }
      const meshesBySourcePath = new Map();
      for (const request of assemblyCompositionMeshRequests(topologyManifest)) {
        const meshUrl = resolveAssetUrl(request.meshUrl, topologyUrl);
        const sourceMesh = peekRenderGlb(meshUrl);
        if (!meshUrl || !sourceMesh) {
          return buildAssemblyPreviewMeshState(entry, previewMeshData, topologyManifest);
        }
        meshesBySourcePath.set(request.key, sourceMesh);
      }
      return buildAssemblyMeshState(entry, topologyManifest, meshesBySourcePath);
    }
    const meshData = peekRenderMeshForEntry(entry);
    if (!meshData) {
      return null;
    }
    return {
      file: entry.file,
      kind: entry.kind,
      meshHash: entryMeshAssetHash(entry),
      meshData
    };
  }, [buildAssemblyMeshState, buildAssemblyPreviewMeshState, entryHasMesh]);

  const getCachedReferenceState = useCallback((entry) => {
    if (!entryHasReferences(entry)) {
      return null;
    }
    const bundle = peekRenderSelectorBundle(
      entryAssetUrl(entry, "topology"),
      entryAssetUrl(entry, "topologyBinary")
    );
    return bundle ? buildNormalizedReferenceState(entry, bundle) : null;
  }, [buildNormalizedReferenceState, entryHasReferences]);

  const getCachedDxfState = useCallback((entry) => {
    if (!entryHasDxf(entry)) {
      return null;
    }
    const dxfData = peekRenderDxf(entryAssetUrl(entry, "dxf"));
    if (!dxfData) {
      return null;
    }
    return {
      file: entry.file,
      kind: entry.kind,
      dxfHash: entryAssetHash(entry, "dxf"),
      dxfData
    };
  }, [entryHasDxf]);

  const getCachedUrdfState = useCallback((entry) => {
    if (entry?.kind !== "urdf" || !entryAssetUrl(entry, "urdf")) {
      return null;
    }
    const urdfData = peekRenderUrdf(entryAssetUrl(entry, "urdf"), {
      explorerMetadataUrl: entryAssetUrl(entry, "explorerMetadata"),
      motionExplorerMetadataUrl: entryAssetUrl(entry, "motionExplorerMetadata")
    });
    if (!urdfData) {
      return null;
    }
    const meshUrls = urdfMeshUrls(urdfData);
    const meshes = meshUrls.map((meshUrl) => peekRenderStl(meshUrl)).filter(Boolean);
    if (meshes.length !== meshUrls.length) {
      return null;
    }
    const meshesByUrl = new Map(meshUrls.map((meshUrl, index) => [meshUrl, meshes[index]]));
    return {
      file: entry.file,
      kind: entry.kind,
      urdfHash: entryUrdfAssetHash(entry),
      urdfData,
      meshesByUrl
    };
  }, []);

  const cancelMeshLoad = useCallback(() => {
    requestIdRef.current += 1;
    abortLoad(meshAbortControllerRef);
    setMeshLoadInProgress(false);
    setMeshLoadTargetFile("");
    setMeshLoadStage("");
  }, []);

  const cancelDxfLoad = useCallback(() => {
    dxfRequestIdRef.current += 1;
    abortLoad(dxfAbortControllerRef);
    setDxfLoadStage("");
  }, []);

  const cancelUrdfLoad = useCallback(() => {
    urdfRequestIdRef.current += 1;
    abortLoad(urdfAbortControllerRef);
    setUrdfLoadStage("");
  }, []);

  const cancelReferenceLoad = useCallback(() => {
    referenceRequestIdRef.current += 1;
    abortLoad(referenceAbortControllerRef);
    setReferenceLoadStage("");
  }, []);

  const loadMeshForEntry = useCallback(async (entry) => {
    cancelMeshLoad();
    const requestId = requestIdRef.current;

    if (!entryHasMesh(entry)) {
      setMeshState(null);
      setStatus(ASSET_STATUS.PENDING);
      setError("");
      return;
    }

    const cachedMeshState = getCachedMeshState(entry);
    if (cachedMeshState) {
      setMeshState(cachedMeshState);
      setStatus(ASSET_STATUS.READY);
      setError("");
      if (entry?.kind !== "assembly" || cachedMeshState.assemblyInteractionReady || cachedMeshState.assemblyBackgroundError) {
        return;
      }
    }

    const controller = new AbortController();
    meshAbortControllerRef.current = controller;
    setMeshLoadInProgress(true);
    setMeshLoadTargetFile(String(entry?.file || "").trim());
    setMeshLoadStage(entry?.kind === "assembly" ? "loading assembly mesh" : "loading mesh");
    const keepRenderedAssemblyVisible = entry?.kind === "assembly" && !!cachedMeshState;
    let assemblyPreviewVisible = keepRenderedAssemblyVisible;
    if (!keepRenderedAssemblyVisible) {
      setStatus(ASSET_STATUS.LOADING);
      setError("");
    }

    try {
      if (entry?.kind === "assembly") {
        const meshUrl = entryAssetUrl(entry, "glb");
        if (!meshUrl) {
          throw new Error(`STEP assembly is missing GLB asset: ${entry.file || "(unknown)"}`);
        }
        const previewMeshData = cachedMeshState?.meshData || await loadRenderGlb(meshUrl, { signal: controller.signal });
        if (requestId !== requestIdRef.current) {
          return;
        }
        if (!cachedMeshState) {
          setMeshState(buildAssemblyPreviewMeshState(entry, previewMeshData));
          setStatus(ASSET_STATUS.READY);
          setError("");
          assemblyPreviewVisible = true;
        }
        const topologyUrl = entryAssetUrl(entry, "topology");
        setMeshLoadStage("loading topology");
        const topologyManifest = await loadRenderJson(topologyUrl, { signal: controller.signal });
        if (requestId !== requestIdRef.current) {
          return;
        }
        if (!cachedMeshState?.assemblyStructureReady) {
          setMeshState(buildAssemblyPreviewMeshState(entry, previewMeshData, topologyManifest));
        }
        const meshRequests = assemblyCompositionMeshRequests(topologyManifest);
        setMeshLoadStage(meshRequests.length ? "loading meshes" : "building assembly");
        const loadedMeshes = await mapWithConcurrency(meshRequests, ASSEMBLY_MESH_LOAD_CONCURRENCY, async (request) => {
          const meshUrl = resolveAssetUrl(request.meshUrl, topologyUrl);
          if (!meshUrl) {
            throw new Error(`Assembly source part is missing GLB asset: ${request.sourcePath || request.key}`);
          }
          return [
            request.key,
            await loadRenderGlb(meshUrl, { signal: controller.signal })
          ];
        });
        const meshesBySourcePath = new Map(loadedMeshes);
        if (requestId !== requestIdRef.current) {
          return;
        }
        setMeshState(buildAssemblyMeshState(entry, topologyManifest, meshesBySourcePath));
        setStatus(ASSET_STATUS.READY);
        setError("");
        return;
      }
      const meshUrl = entryMeshAssetUrl(entry);
      if (!meshUrl) {
        const assetLabel = entryMeshAssetKey(entry).toUpperCase();
        throw new Error(`${assetLabel} entry is missing ${assetLabel} asset: ${entry.file || "(unknown)"}`);
      }
      const meshData = await loadRenderMeshForEntry(entry, { signal: controller.signal });
      const meshHash = entryMeshAssetHash(entry);
      if (requestId !== requestIdRef.current) {
        return;
      }
      setMeshLoadStage("building");
      setMeshState({
        file: entry.file,
        kind: entry.kind,
        meshHash,
        meshData
      });
      setStatus(ASSET_STATUS.READY);
    } catch (err) {
      if (requestId !== requestIdRef.current || isAbortError(err) || controller.signal.aborted) {
        return;
      }
      if (entry?.kind === "assembly" && assemblyPreviewVisible) {
        setMeshState((current) => {
          if (!current || current.file !== entry.file || current.meshHash !== getAssemblyMeshHash(entry)) {
            return current;
          }
          return {
            ...current,
            assemblyBackgroundError: err instanceof Error ? err.message : String(err)
          };
        });
        return;
      }
      setStatus(ASSET_STATUS.ERROR);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (requestId === requestIdRef.current) {
        setMeshLoadInProgress(false);
        setMeshLoadTargetFile("");
        setMeshLoadStage("");
      }
      if (meshAbortControllerRef.current === controller) {
        meshAbortControllerRef.current = null;
      }
    }
  }, [buildAssemblyMeshState, buildAssemblyPreviewMeshState, cancelMeshLoad, entryHasMesh, getAssemblyMeshHash, getCachedMeshState]);

  const loadReferencesForEntry = useCallback(async (entry) => {
    cancelReferenceLoad();
    const requestId = referenceRequestIdRef.current;

    if (!entryHasReferences(entry)) {
      setReferenceState(null);
      setReferenceStatus(REFERENCE_STATUS.DISABLED);
      setReferenceError("");
      return;
    }

    const cachedReferenceState = getCachedReferenceState(entry);
    if (cachedReferenceState) {
      setReferenceState(cachedReferenceState);
      setReferenceStatus(cachedReferenceState.disabledReason ? REFERENCE_STATUS.DISABLED : REFERENCE_STATUS.READY);
      setReferenceError(cachedReferenceState.disabledReason || "");
      return;
    }

    const controller = new AbortController();
    referenceAbortControllerRef.current = controller;
    setReferenceStatus(REFERENCE_STATUS.LOADING);
    setReferenceError("");
    setReferenceLoadStage("loading topology");

    try {
      const bundle = await loadRenderSelectorBundle(
        entryAssetUrl(entry, "topology"),
        entryAssetUrl(entry, "topologyBinary"),
        { signal: controller.signal }
      );
      if (requestId !== referenceRequestIdRef.current) {
        return;
      }
      const nextReferenceState = buildNormalizedReferenceState(entry, bundle);
      setReferenceState(nextReferenceState);
      setReferenceStatus(nextReferenceState.disabledReason ? REFERENCE_STATUS.DISABLED : REFERENCE_STATUS.READY);
      setReferenceError(nextReferenceState.disabledReason || "");
    } catch (err) {
      if (requestId !== referenceRequestIdRef.current || isAbortError(err) || controller.signal.aborted) {
        return;
      }
      setReferenceStatus(REFERENCE_STATUS.ERROR);
      setReferenceError(err instanceof Error ? err.message : String(err));
    } finally {
      if (referenceAbortControllerRef.current === controller) {
        referenceAbortControllerRef.current = null;
      }
      if (requestId === referenceRequestIdRef.current) {
        setReferenceLoadStage("");
      }
    }
  }, [buildNormalizedReferenceState, cancelReferenceLoad, entryHasReferences, getCachedReferenceState]);

  const loadDxfForEntry = useCallback(async (entry) => {
    cancelDxfLoad();
    const requestId = dxfRequestIdRef.current;

    if (!entryHasDxf(entry)) {
      setDxfState(null);
      setDxfStatus(ASSET_STATUS.PENDING);
      setDxfError("");
      return;
    }

    const cachedDxfState = getCachedDxfState(entry);
    if (cachedDxfState) {
      setDxfState(cachedDxfState);
      setDxfStatus(ASSET_STATUS.READY);
      setDxfError("");
      return;
    }

    const controller = new AbortController();
    dxfAbortControllerRef.current = controller;
    setDxfStatus(ASSET_STATUS.LOADING);
    setDxfError("");
    setDxfLoadStage("loading DXF");

    try {
      const dxfData = await loadRenderDxf(entryAssetUrl(entry, "dxf"), { signal: controller.signal });
      if (requestId !== dxfRequestIdRef.current) {
        return;
      }
      setDxfLoadStage("building preview");
      setDxfState({
        file: entry.file,
        kind: entry.kind,
        dxfHash: entryAssetHash(entry, "dxf"),
        dxfData
      });
      setDxfStatus(ASSET_STATUS.READY);
    } catch (err) {
      if (requestId !== dxfRequestIdRef.current || isAbortError(err) || controller.signal.aborted) {
        return;
      }
      setDxfStatus(ASSET_STATUS.ERROR);
      setDxfError(err instanceof Error ? err.message : String(err));
    } finally {
      if (dxfAbortControllerRef.current === controller) {
        dxfAbortControllerRef.current = null;
      }
      if (requestId === dxfRequestIdRef.current) {
        setDxfLoadStage("");
      }
    }
  }, [cancelDxfLoad, entryHasDxf, getCachedDxfState]);

  const loadUrdfForEntry = useCallback(async (entry) => {
    cancelUrdfLoad();
    const requestId = urdfRequestIdRef.current;

    if (entry?.kind !== "urdf" || !entryAssetUrl(entry, "urdf")) {
      setUrdfState(null);
      setUrdfStatus(ASSET_STATUS.PENDING);
      setUrdfError("");
      return;
    }

    const cachedUrdfState = getCachedUrdfState(entry);
    if (cachedUrdfState) {
      setUrdfState(cachedUrdfState);
      setUrdfStatus(ASSET_STATUS.READY);
      setUrdfError("");
      return;
    }

    const controller = new AbortController();
    urdfAbortControllerRef.current = controller;
    setUrdfStatus(ASSET_STATUS.LOADING);
    setUrdfError("");
    setUrdfLoadStage("loading URDF");

    try {
      const urdfData = await loadRenderUrdf(entryAssetUrl(entry, "urdf"), {
        signal: controller.signal,
        explorerMetadataUrl: entryAssetUrl(entry, "explorerMetadata"),
        motionExplorerMetadataUrl: entryAssetUrl(entry, "motionExplorerMetadata")
      });
      const meshUrls = urdfMeshUrls(urdfData);
      setUrdfLoadStage(meshUrls.length ? "loading meshes" : "building robot");
      const meshes = await Promise.all(
        meshUrls.map((meshUrl) => loadRenderStl(meshUrl, { signal: controller.signal }))
      );
      if (requestId !== urdfRequestIdRef.current) {
        return;
      }
      setUrdfLoadStage("building robot");
      const meshesByUrl = new Map(meshUrls.map((meshUrl, index) => [meshUrl, meshes[index]]));
      setUrdfState({
        file: entry.file,
        kind: entry.kind,
        urdfHash: entryUrdfAssetHash(entry),
        urdfData,
        meshesByUrl
      });
      setUrdfStatus(ASSET_STATUS.READY);
    } catch (err) {
      if (requestId !== urdfRequestIdRef.current || isAbortError(err) || controller.signal.aborted) {
        return;
      }
      setUrdfStatus(ASSET_STATUS.ERROR);
      setUrdfError(err instanceof Error ? err.message : String(err));
    } finally {
      if (urdfAbortControllerRef.current === controller) {
        urdfAbortControllerRef.current = null;
      }
      if (requestId === urdfRequestIdRef.current) {
        setUrdfLoadStage("");
      }
    }
  }, [cancelUrdfLoad, getCachedUrdfState]);

  useEffect(() => () => {
    abortLoad(meshAbortControllerRef);
    abortLoad(dxfAbortControllerRef);
    abortLoad(urdfAbortControllerRef);
    abortLoad(referenceAbortControllerRef);
  }, []);

  return {
    meshState,
    setMeshState,
    meshLoadInProgress,
    meshLoadTargetFile,
    meshLoadStage,
    status,
    setStatus,
    error,
    setError,
    dxfState,
    setDxfState,
    dxfStatus,
    setDxfStatus,
    dxfError,
    setDxfError,
    dxfLoadStage,
    urdfState,
    setUrdfState,
    urdfStatus,
    setUrdfStatus,
    urdfError,
    setUrdfError,
    urdfLoadStage,
    referenceState,
    setReferenceState,
    referenceStatus,
    setReferenceStatus,
    referenceError,
    setReferenceError,
    referenceLoadStage,
    getCachedMeshState,
    getCachedReferenceState,
    getCachedDxfState,
    getCachedUrdfState,
    cancelMeshLoad,
    cancelDxfLoad,
    cancelUrdfLoad,
    cancelReferenceLoad,
    loadMeshForEntry,
    loadDxfForEntry,
    loadUrdfForEntry,
    loadReferencesForEntry
  };
}
