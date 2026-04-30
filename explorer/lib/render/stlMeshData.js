function buildBoundsFromGeometry(geometry) {
  geometry.computeBoundingBox();
  const min = geometry.boundingBox?.min;
  const max = geometry.boundingBox?.max;
  if (!min || !max) {
    return {
      min: [0, 0, 0],
      max: [0, 0, 0],
    };
  }
  return {
    min: [min.x, min.y, min.z],
    max: [max.x, max.y, max.z],
  };
}

function buildMeshDataFromStlGeometry(geometry) {
  const positions = geometry.getAttribute("position");
  const normals = geometry.getAttribute("normal");
  if (!positions || positions.itemSize !== 3) {
    throw new Error("STL geometry is missing vertex positions");
  }
  const vertexCount = positions.count;
  const indices = new Uint32Array(vertexCount);
  for (let index = 0; index < vertexCount; index += 1) {
    indices[index] = index;
  }
  return {
    vertices: new Float32Array(positions.array),
    indices,
    normals: normals?.itemSize === 3 ? new Float32Array(normals.array) : new Float32Array(positions.array.length),
    colors: new Float32Array(0),
    edge_indices: new Uint32Array(0),
    bounds: buildBoundsFromGeometry(geometry),
    parts: [],
  };
}

export async function buildMeshDataFromStlBuffer(buffer) {
  const { STLLoader } = await import("three/examples/jsm/loaders/STLLoader.js");
  const loader = new STLLoader();
  return buildMeshDataFromStlGeometry(loader.parse(buffer));
}
