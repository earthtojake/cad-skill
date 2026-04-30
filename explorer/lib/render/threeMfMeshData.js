function buildBoundsFromVertices(vertices) {
  if (!vertices?.length) {
    return {
      min: [0, 0, 0],
      max: [0, 0, 0],
    };
  }
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index + 2 < vertices.length; index += 3) {
    const x = Number(vertices[index]);
    const y = Number(vertices[index + 1]);
    const z = Number(vertices[index + 2]);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
      continue;
    }
    min[0] = Math.min(min[0], x);
    min[1] = Math.min(min[1], y);
    min[2] = Math.min(min[2], z);
    max[0] = Math.max(max[0], x);
    max[1] = Math.max(max[1], y);
    max[2] = Math.max(max[2], z);
  }
  if (!min.every(Number.isFinite) || !max.every(Number.isFinite)) {
    return {
      min: [0, 0, 0],
      max: [0, 0, 0],
    };
  }
  return { min, max };
}

function colorFromMaterial(material) {
  if (!material?.color) {
    return null;
  }
  return {
    rgb: [material.color.r, material.color.g, material.color.b],
    hex: `#${material.color.getHexString()}`,
  };
}

function materialForGroup(material, group) {
  if (Array.isArray(material)) {
    const materialIndex = Number.isInteger(group?.materialIndex) ? group.materialIndex : 0;
    return material[materialIndex] || material[0] || null;
  }
  return material || null;
}

function appendMeshPrimitive(THREE, accumulator, mesh, group, material) {
  const geometry = mesh?.geometry;
  const positions = geometry?.getAttribute?.("position");
  if (!positions || positions.itemSize !== 3 || positions.count <= 0) {
    return;
  }
  if (!geometry.getAttribute("normal")) {
    geometry.computeVertexNormals?.();
  }
  mesh.updateWorldMatrix?.(true, false);
  const matrixWorld = mesh.matrixWorld || null;
  const normalMatrix = matrixWorld ? new THREE.Matrix3().getNormalMatrix(matrixWorld) : null;
  const normals = geometry.getAttribute("normal");
  const indexAttribute = geometry.getIndex?.();
  const sourceStart = Math.max(0, Math.floor(Number(group?.start || 0)));
  const availableCount = indexAttribute?.count || positions.count;
  const rawCount = Math.floor(Number(group?.count || (availableCount - sourceStart)));
  const sourceCount = Math.max(0, Math.min(rawCount, availableCount - sourceStart));
  const triangleVertexCount = sourceCount - (sourceCount % 3);
  if (triangleVertexCount <= 0) {
    return;
  }
  const color = colorFromMaterial(material);
  const positionVector = new THREE.Vector3();
  const normalVector = new THREE.Vector3();
  const vertexOffset = Math.floor(accumulator.vertices.length / 3);
  const triangleOffset = Math.floor(accumulator.indices.length / 3);
  const partVertices = [];

  for (let localIndex = 0; localIndex < triangleVertexCount; localIndex += 1) {
    const sourceSlot = sourceStart + localIndex;
    const sourceIndex = indexAttribute ? indexAttribute.getX(sourceSlot) : sourceSlot;
    if (sourceIndex < 0 || sourceIndex >= positions.count) {
      continue;
    }
    const outputIndex = Math.floor(partVertices.length / 3);
    positionVector.set(
      positions.getX(sourceIndex),
      positions.getY(sourceIndex),
      positions.getZ(sourceIndex)
    );
    if (matrixWorld) {
      positionVector.applyMatrix4(matrixWorld);
    }
    accumulator.vertices.push(positionVector.x, positionVector.y, positionVector.z);
    partVertices.push(positionVector.x, positionVector.y, positionVector.z);
    if (normals?.itemSize === 3 && sourceIndex < normals.count) {
      normalVector.set(normals.getX(sourceIndex), normals.getY(sourceIndex), normals.getZ(sourceIndex));
      if (normalMatrix) {
        normalVector.applyMatrix3(normalMatrix).normalize();
      }
      accumulator.normals.push(normalVector.x, normalVector.y, normalVector.z);
    } else {
      accumulator.normals.push(0, 0, 0);
    }
    if (color) {
      accumulator.colors.push(color.rgb[0], color.rgb[1], color.rgb[2]);
    }
    accumulator.indices.push(vertexOffset + outputIndex);
  }

  const vertexCount = Math.floor(partVertices.length / 3);
  const triangleCount = Math.floor(vertexCount / 3);
  if (vertexCount <= 0 || triangleCount <= 0) {
    return;
  }
  const label = String(mesh?.name || mesh?.parent?.name || `3mf:${accumulator.parts.length}`).trim();
  const id = `3mf:${accumulator.parts.length}`;
  accumulator.parts.push({
    id,
    occurrenceId: id,
    name: label || id,
    label: label || id,
    nodeType: "part",
    color: color?.hex || "",
    bounds: buildBoundsFromVertices(partVertices),
    vertexOffset,
    vertexCount,
    triangleOffset,
    triangleCount,
    edgeIndexOffset: 0,
    edgeIndexCount: 0,
  });
  if (color?.hex) {
    accumulator.colorSet.add(color.hex.toLowerCase());
  }
}

export function buildMeshDataFromThreeMfGroup(THREE, group) {
  const accumulator = {
    vertices: [],
    indices: [],
    normals: [],
    colors: [],
    parts: [],
    colorSet: new Set(),
  };
  group?.updateWorldMatrix?.(true, true);
  group?.traverse?.((object) => {
    if (object?.isMesh && object.geometry) {
      const groups = Array.isArray(object.geometry.groups) && object.geometry.groups.length
        ? object.geometry.groups
        : [null];
      for (const geometryGroup of groups) {
        appendMeshPrimitive(THREE, accumulator, object, geometryGroup, materialForGroup(object.material, geometryGroup));
      }
    }
  });
  const vertices = new Float32Array(accumulator.vertices);
  const colors = accumulator.colors.length === accumulator.vertices.length
    ? new Float32Array(accumulator.colors)
    : new Float32Array(0);
  return {
    vertices,
    indices: new Uint32Array(accumulator.indices),
    normals: new Float32Array(accumulator.normals),
    colors,
    edge_indices: new Uint32Array(0),
    bounds: buildBoundsFromVertices(vertices),
    parts: accumulator.parts,
    has_source_colors: colors.length === vertices.length && colors.length > 0,
    sourceColor: accumulator.colorSet.size === 1 ? [...accumulator.colorSet][0] : "",
  };
}

export async function buildMeshDataFrom3MfBuffer(buffer) {
  const [THREE, { ThreeMFLoader }] = await Promise.all([
    import("three"),
    import("three/examples/jsm/loaders/3MFLoader.js"),
  ]);
  const loader = new ThreeMFLoader();
  return buildMeshDataFromThreeMfGroup(THREE, loader.parse(buffer));
}
