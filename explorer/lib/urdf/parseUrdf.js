import { multiplyTransforms } from "./kinematics.js";

const IDENTITY_TRANSFORM = Object.freeze([
  1, 0, 0, 0,
  0, 1, 0, 0,
  0, 0, 1, 0,
  0, 0, 0, 1
]);
const EXPLORER_METADATA_KIND = "texttocad-urdf-explorer";
const EXPLORER_METADATA_SCHEMA_VERSION = 3;
const MOTION_EXPLORER_METADATA_KIND = "texttocad-robot-motion-explorer";
const MOTION_EXPLORER_METADATA_SCHEMA_VERSION = 1;
const MOTION_SERVER_VERSION = 1;
const MOTION_SERVER_COMMAND_NAMES = new Set(["urdf.solvePose", "urdf.planToPose"]);

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function childElementsByTag(parent, tagName) {
  return Array.from(parent?.childNodes || []).filter((node) => node?.nodeType === 1 && node.tagName === tagName);
}

function parseNumberList(value, count, fallback) {
  if (typeof value !== "string" || !value.trim()) {
    return [...fallback];
  }
  const parsed = value.trim().split(/\s+/).map((entry) => Number(entry));
  if (parsed.length !== count || parsed.some((entry) => !Number.isFinite(entry))) {
    throw new Error(`Expected ${count} numeric values, received ${JSON.stringify(value)}`);
  }
  return parsed;
}

function translationTransform(x, y, z) {
  return [
    1, 0, 0, x,
    0, 1, 0, y,
    0, 0, 1, z,
    0, 0, 0, 1
  ];
}

function scaleTransform(x, y, z) {
  return [
    x, 0, 0, 0,
    0, y, 0, 0,
    0, 0, z, 0,
    0, 0, 0, 1
  ];
}

function rotationTransformFromRpy(roll, pitch, yaw) {
  const sr = Math.sin(roll);
  const cr = Math.cos(roll);
  const sp = Math.sin(pitch);
  const cp = Math.cos(pitch);
  const sy = Math.sin(yaw);
  const cy = Math.cos(yaw);
  return [
    cy * cp, (cy * sp * sr) - (sy * cr), (cy * sp * cr) + (sy * sr), 0,
    sy * cp, (sy * sp * sr) + (cy * cr), (sy * sp * cr) - (cy * sr), 0,
    -sp, cp * sr, cp * cr, 0,
    0, 0, 0, 1
  ];
}

function parseOriginTransform(originElement) {
  if (!originElement) {
    return [...IDENTITY_TRANSFORM];
  }
  const [x, y, z] = parseNumberList(originElement.getAttribute("xyz"), 3, [0, 0, 0]);
  const [roll, pitch, yaw] = parseNumberList(originElement.getAttribute("rpy"), 3, [0, 0, 0]);
  return multiplyTransforms(
    translationTransform(x, y, z),
    rotationTransformFromRpy(roll, pitch, yaw)
  );
}

function parseScaleTransform(meshElement) {
  const [x, y, z] = parseNumberList(meshElement?.getAttribute("scale"), 3, [1, 1, 1]);
  return scaleTransform(x, y, z);
}

function normalizeAbsoluteUrl(url) {
  if (url instanceof URL) {
    return url.toString();
  }
  return new URL(url, globalThis.window?.location?.href || "http://localhost/").toString();
}

function resolveMeshUrl(filename, sourceUrl) {
  const normalizedSourceUrl = normalizeAbsoluteUrl(sourceUrl);
  let resolvedUrl;
  if (filename.startsWith("package://")) {
    resolvedUrl = new URL(filename.slice("package://".length).replace(/^\/+/, ""), new URL("/", normalizedSourceUrl));
  } else {
    resolvedUrl = new URL(filename, normalizedSourceUrl);
  }
  return `${resolvedUrl.pathname}${resolvedUrl.search}`;
}

function labelForMeshFilename(filename) {
  const parts = String(filename || "").split("/");
  return parts[parts.length - 1] || "mesh";
}

function parseRgbaColor(rgbaText, context) {
  const values = parseNumberList(rgbaText, 4, [0, 0, 0, 1]);
  if (values.some((value) => value < 0 || value > 1)) {
    throw new Error(`${context} must use rgba values between 0 and 1`);
  }
  return `#${values.slice(0, 3).map((value) => {
    const component = Math.round(value * 255);
    return component.toString(16).padStart(2, "0");
  }).join("")}`;
}

function materialColorFromElement(materialElement, context) {
  const colorElement = childElementsByTag(materialElement, "color")[0];
  const rgbaText = String(colorElement?.getAttribute("rgba") || "").trim();
  if (!rgbaText) {
    return "";
  }
  return parseRgbaColor(rgbaText, context);
}

function parseNamedMaterialColors(robotElement) {
  const namedMaterials = new Map();
  for (const materialElement of childElementsByTag(robotElement, "material")) {
    const name = String(materialElement.getAttribute("name") || "").trim();
    if (!name) {
      continue;
    }
    const color = materialColorFromElement(materialElement, `URDF material ${name}`);
    if (!color) {
      continue;
    }
    namedMaterials.set(name, color);
  }
  return namedMaterials;
}

function resolveVisualColor(visualElement, namedMaterialColors, { linkName, visualIndex }) {
  const materialElement = childElementsByTag(visualElement, "material")[0];
  if (!materialElement) {
    return "";
  }
  const inlineColor = materialColorFromElement(materialElement, `URDF link ${linkName} visual ${visualIndex} material`);
  if (inlineColor) {
    return inlineColor;
  }
  const materialName = String(materialElement.getAttribute("name") || "").trim();
  return materialName ? String(namedMaterialColors.get(materialName) || "") : "";
}

function parseJointDefaultValueDeg(jointElement, jointName) {
  const rawValue = String(jointElement.getAttribute("default_deg") || "").trim();
  if (!rawValue) {
    return 0;
  }
  const parsedValue = Number(rawValue);
  if (!Number.isFinite(parsedValue)) {
    throw new Error(`URDF joint ${jointName} has invalid default_deg ${JSON.stringify(rawValue)}`);
  }
  return parsedValue;
}

function parseJointMimic(jointElement, jointName) {
  const mimicElement = childElementsByTag(jointElement, "mimic")[0];
  if (!mimicElement) {
    return null;
  }
  const joint = String(mimicElement.getAttribute("joint") || "").trim();
  if (!joint) {
    throw new Error(`URDF mimic joint ${jointName} must reference another joint`);
  }
  const multiplierText = String(mimicElement.getAttribute("multiplier") ?? "1").trim() || "1";
  const offsetText = String(mimicElement.getAttribute("offset") ?? "0").trim() || "0";
  const multiplier = Number(multiplierText);
  const offset = Number(offsetText);
  if (!Number.isFinite(multiplier) || !Number.isFinite(offset)) {
    throw new Error(`URDF mimic joint ${jointName} has invalid multiplier or offset`);
  }
  return {
    joint,
    multiplier,
    offset
  };
}

function parseJoint(jointElement, linkNames) {
  const name = String(jointElement.getAttribute("name") || "").trim();
  if (!name) {
    throw new Error("URDF joint name is required");
  }
  const type = String(jointElement.getAttribute("type") || "").trim().toLowerCase();
  if (!["fixed", "continuous", "revolute", "prismatic"].includes(type)) {
    throw new Error(`Unsupported URDF joint type: ${type || "(missing)"}`);
  }
  const parentElement = childElementsByTag(jointElement, "parent")[0];
  const childElement = childElementsByTag(jointElement, "child")[0];
  const parentLink = String(parentElement?.getAttribute("link") || "").trim();
  const childLink = String(childElement?.getAttribute("link") || "").trim();
  if (!parentLink || !childLink) {
    throw new Error(`URDF joint ${name} must declare parent and child links`);
  }
  if (!linkNames.has(parentLink) || !linkNames.has(childLink)) {
    throw new Error(`URDF joint ${name} references missing links`);
  }
  const axis = type === "fixed"
    ? [1, 0, 0]
    : parseNumberList(childElementsByTag(jointElement, "axis")[0]?.getAttribute("xyz"), 3, [1, 0, 0]);
  let minValueDeg = 0;
  let maxValueDeg = 0;
  if (type === "continuous") {
    minValueDeg = -180;
    maxValueDeg = 180;
  } else if (type === "revolute" || type === "prismatic") {
    const limitElement = childElementsByTag(jointElement, "limit")[0];
    if (!limitElement) {
      throw new Error(`URDF ${type} joint ${name} requires <limit>`);
    }
    const lower = Number(limitElement.getAttribute("lower"));
    const upper = Number(limitElement.getAttribute("upper"));
    if (!Number.isFinite(lower) || !Number.isFinite(upper)) {
      throw new Error(`URDF ${type} joint ${name} has invalid limits`);
    }
    if (type === "revolute") {
      minValueDeg = (lower * 180) / Math.PI;
      maxValueDeg = (upper * 180) / Math.PI;
    } else {
      minValueDeg = lower;
      maxValueDeg = upper;
    }
  }
  return {
    name,
    type,
    parentLink,
    childLink,
    originTransform: parseOriginTransform(childElementsByTag(jointElement, "origin")[0]),
    axis,
    defaultValueDeg: type === "fixed" ? 0 : parseJointDefaultValueDeg(jointElement, name),
    minValueDeg,
    maxValueDeg,
    mimic: parseJointMimic(jointElement, name)
  };
}

function parseExplorerJointValue(rawValue, { context, jointName, joint, allowMimic = false }) {
  const valueText = String(rawValue ?? "").trim();
  if (!valueText) {
    throw new Error(`${context} joint ${jointName} is missing value`);
  }
  const parsedValue = Number(valueText);
  if (!Number.isFinite(parsedValue)) {
    throw new Error(`${context} joint ${jointName} has invalid value ${JSON.stringify(valueText)}`);
  }
  const jointType = String(joint?.type || "fixed");
  if (jointType === "fixed") {
    throw new Error(`${context} joint ${jointName} must target a movable joint`);
  }
  if (!allowMimic && joint?.mimic) {
    throw new Error(`${context} joint ${jointName} must target a non-mimic joint`);
  }
  if (jointType !== "continuous") {
    const minValue = Number(joint?.minValueDeg);
    const maxValue = Number(joint?.maxValueDeg);
    if (
      Number.isFinite(minValue) &&
      Number.isFinite(maxValue) &&
      (parsedValue < Math.min(minValue, maxValue) || parsedValue > Math.max(minValue, maxValue))
    ) {
      throw new Error(`${context} joint ${jointName} must stay within joint limits`);
    }
  }
  return parsedValue;
}

function parseExplorerMetadataDefaults(jointDefaultsByName, jointByName) {
  if (jointDefaultsByName == null) {
    return {};
  }
  if (!isPlainObject(jointDefaultsByName)) {
    throw new Error("URDF explorer metadata jointDefaultsByName must be an object");
  }
  const defaults = {};
  for (const [jointName, value] of Object.entries(jointDefaultsByName)) {
    const normalizedJointName = String(jointName || "").trim();
    if (!normalizedJointName) {
      throw new Error("URDF explorer metadata joint default name is required");
    }
    const joint = jointByName.get(normalizedJointName);
    if (!joint) {
      throw new Error(`URDF explorer metadata references missing joint ${normalizedJointName}`);
    }
    defaults[normalizedJointName] = parseExplorerJointValue(value, {
      context: "URDF explorer metadata default",
      jointName: normalizedJointName,
      joint
    });
  }
  return defaults;
}

function parseExplorerMetadataPoses(poses, jointByName) {
  if (poses == null) {
    return [];
  }
  if (!Array.isArray(poses)) {
    throw new Error("URDF explorer metadata poses must be an array");
  }
  const poseNames = new Set();
  return poses.map((pose) => {
    if (!isPlainObject(pose)) {
      throw new Error("URDF explorer metadata pose must be an object");
    }
    const poseName = String(pose.name || "").trim();
    if (!poseName) {
      throw new Error("Explorer pose name is required");
    }
    if (poseNames.has(poseName)) {
      throw new Error(`Duplicate explorer pose name: ${poseName}`);
    }
    poseNames.add(poseName);
    const rawJointValues = pose.jointValuesByName;
    if (!isPlainObject(rawJointValues)) {
      throw new Error(`Explorer pose ${poseName} jointValuesByName must be an object`);
    }
    const jointValuesByName = {};
    for (const [jointName, value] of Object.entries(rawJointValues)) {
      const normalizedJointName = String(jointName || "").trim();
      if (!normalizedJointName) {
        throw new Error(`Explorer pose ${poseName} joint name is required`);
      }
      const joint = jointByName.get(normalizedJointName);
      if (!joint) {
        throw new Error(`Explorer pose ${poseName} references missing joint ${normalizedJointName}`);
      }
      jointValuesByName[normalizedJointName] = parseExplorerJointValue(value, {
        context: `Explorer pose ${poseName}`,
        jointName: normalizedJointName,
        joint
      });
    }
    if (!Object.keys(jointValuesByName).length) {
      throw new Error(`Explorer pose ${poseName} must define at least one joint value`);
    }
    return {
      name: poseName,
      jointValuesByName
    };
  });
}

function parseMotionServerEndEffectors(endEffectors, links, commandName) {
  if (!Array.isArray(endEffectors) || !endEffectors.length) {
    throw new Error(`robot motion explorer metadata motionServer command ${commandName} endEffectors must be a non-empty array`);
  }
  const linkNames = new Set((Array.isArray(links) ? links : []).map((link) => String(link?.name || "")).filter(Boolean));
  const endEffectorNames = new Set();
  return endEffectors.map((endEffector) => {
    if (!isPlainObject(endEffector)) {
      throw new Error(`robot motion explorer metadata motionServer command ${commandName} end effector must be an object`);
    }
    const name = String(endEffector.name || "").trim();
    if (!name) {
      throw new Error(`robot motion explorer metadata motionServer command ${commandName} end effector name is required`);
    }
    if (endEffectorNames.has(name)) {
      throw new Error(`Duplicate robot motion explorer metadata motionServer end effector name: ${name}`);
    }
    endEffectorNames.add(name);
    const link = String(endEffector.link || "").trim();
    if (!link || !linkNames.has(link)) {
      throw new Error(`robot motion explorer metadata motionServer end effector ${name} references missing link ${link || "(missing)"}`);
    }
    const frame = String(endEffector.frame || "").trim();
    if (!frame || !linkNames.has(frame)) {
      throw new Error(`robot motion explorer metadata motionServer end effector ${name} references missing frame ${frame || "(missing)"}`);
    }
    const rawTolerance = endEffector.positionTolerance;
    const positionTolerance = rawTolerance == null ? 0.002 : Number(rawTolerance);
    if (!Number.isFinite(positionTolerance) || positionTolerance <= 0) {
      throw new Error(`robot motion explorer metadata motionServer end effector ${name} positionTolerance must be positive`);
    }
    return {
      name,
      link,
      frame,
      positionTolerance
    };
  });
}

function rejectUnknownMotionServerCommandKeys(command, commandName, allowedKeys) {
  for (const key of Object.keys(command)) {
    if (!allowedKeys.has(key)) {
      throw new Error(`robot motion explorer metadata motionServer command ${commandName} cannot include ${key}`);
    }
  }
}

function parseMotionServerCommand(commandName, command, links) {
  if (!MOTION_SERVER_COMMAND_NAMES.has(commandName)) {
    throw new Error(`robot motion explorer metadata motionServer command ${commandName} is unsupported`);
  }
  if (!isPlainObject(command)) {
    throw new Error(`robot motion explorer metadata motionServer command ${commandName} must be an object`);
  }
  if (commandName === "urdf.solvePose") {
    rejectUnknownMotionServerCommandKeys(command, commandName, new Set(["endEffectors"]));
    return {
      endEffectors: parseMotionServerEndEffectors(command.endEffectors, links, commandName)
    };
  }
  rejectUnknownMotionServerCommandKeys(command, commandName, new Set());
  return {};
}

function parseMotionServer(motionServer, links) {
  if (motionServer == null) {
    return null;
  }
  if (!isPlainObject(motionServer)) {
    throw new Error("robot motion explorer metadata motionServer must be an object");
  }
  if (Number(motionServer.version) !== MOTION_SERVER_VERSION) {
    throw new Error(`robot motion explorer metadata motionServer.version must be ${MOTION_SERVER_VERSION}`);
  }
  const commands = motionServer.commands;
  if (!isPlainObject(commands) || !Object.keys(commands).length) {
    throw new Error("robot motion explorer metadata motionServer.commands must be a non-empty object");
  }
  const parsedCommands = {};
  for (const [commandName, command] of Object.entries(commands)) {
    parsedCommands[commandName] = parseMotionServerCommand(commandName, command, links);
  }
  if (Object.hasOwn(parsedCommands, "urdf.planToPose") && !Object.hasOwn(parsedCommands, "urdf.solvePose")) {
    throw new Error("robot motion explorer metadata motionServer command urdf.planToPose requires urdf.solvePose");
  }
  return {
    version: MOTION_SERVER_VERSION,
    commands: parsedCommands
  };
}

function motionFromMotionServer(motionServer) {
  const solvePose = motionServer?.commands?.["urdf.solvePose"];
  if (!solvePose) {
    return null;
  }
  return {
    transport: "motionServer",
    command: Object.hasOwn(motionServer.commands, "urdf.planToPose") ? "urdf.planToPose" : "urdf.solvePose",
    canSolvePose: true,
    canPlanToPose: Object.hasOwn(motionServer.commands, "urdf.planToPose"),
    endEffectors: solvePose.endEffectors,
    motionServer
  };
}

function parseExplorerMetadata(explorerMetadata, joints, links) {
  if (explorerMetadata == null) {
    return null;
  }
  if (!isPlainObject(explorerMetadata)) {
    throw new Error("URDF explorer metadata must be an object");
  }
  if (Number(explorerMetadata.schemaVersion) !== EXPLORER_METADATA_SCHEMA_VERSION) {
    throw new Error(`URDF explorer metadata schemaVersion must be ${EXPLORER_METADATA_SCHEMA_VERSION}`);
  }
  if (String(explorerMetadata.kind || "") !== EXPLORER_METADATA_KIND) {
    throw new Error(`URDF explorer metadata kind must be ${EXPLORER_METADATA_KIND}`);
  }
  if (explorerMetadata.motionServer != null) {
    throw new Error("URDF explorer metadata must not include motionServer; use robot-motion/explorer.json");
  }
  const jointByName = new Map(joints.map((joint) => [String(joint?.name || ""), joint]).filter(([name]) => name));
  return {
    jointDefaultsByName: parseExplorerMetadataDefaults(explorerMetadata.jointDefaultsByName, jointByName),
    poses: parseExplorerMetadataPoses(explorerMetadata.poses, jointByName),
  };
}

function parseMotionExplorerMetadata(motionExplorerMetadata, links) {
  if (motionExplorerMetadata == null) {
    return null;
  }
  if (!isPlainObject(motionExplorerMetadata)) {
    throw new Error("robot motion explorer metadata must be an object");
  }
  if (Number(motionExplorerMetadata.schemaVersion) !== MOTION_EXPLORER_METADATA_SCHEMA_VERSION) {
    throw new Error(`robot motion explorer metadata schemaVersion must be ${MOTION_EXPLORER_METADATA_SCHEMA_VERSION}`);
  }
  if (String(motionExplorerMetadata.kind || "") !== MOTION_EXPLORER_METADATA_KIND) {
    throw new Error(`robot motion explorer metadata kind must be ${MOTION_EXPLORER_METADATA_KIND}`);
  }
  const motionServer = parseMotionServer(motionExplorerMetadata.motionServer, links);
  if (!motionServer) {
    throw new Error("robot motion explorer metadata does not define motionServer");
  }
  return {
    motionServer,
    motion: motionFromMotionServer(motionServer)
  };
}

function applyExplorerMetadata(joints, explorerMetadata, motionExplorerMetadata, links) {
  const parsedMetadata = parseExplorerMetadata(explorerMetadata, joints, links);
  const parsedMotionMetadata = parseMotionExplorerMetadata(motionExplorerMetadata, links);
  if (!parsedMetadata) {
    return {
      joints,
      poses: [],
      motion: parsedMotionMetadata?.motion || null,
      motionServer: parsedMotionMetadata?.motionServer || null
    };
  }
  return {
    joints: joints.map((joint) => {
      if (!Object.hasOwn(parsedMetadata.jointDefaultsByName, joint.name)) {
        return joint;
      }
      return {
        ...joint,
        defaultValueDeg: parsedMetadata.jointDefaultsByName[joint.name]
      };
    }),
    poses: parsedMetadata.poses,
    motion: parsedMotionMetadata?.motion || null,
    motionServer: parsedMotionMetadata?.motionServer || null
  };
}

function validateMimicJoints(joints) {
  const jointNames = new Set(joints.map((joint) => joint.name));
  for (const joint of joints) {
    if (!joint.mimic) {
      continue;
    }
    if (!jointNames.has(joint.mimic.joint)) {
      throw new Error(`URDF mimic joint ${joint.name} references missing joint ${joint.mimic.joint}`);
    }
  }
}

function validateTree(links, joints) {
  const linkNames = new Set(links.map((link) => link.name));
  const children = new Set();
  const jointsByParent = new Map();
  const jointNames = new Set();
  for (const joint of joints) {
    if (jointNames.has(joint.name)) {
      throw new Error(`Duplicate URDF joint name: ${joint.name}`);
    }
    jointNames.add(joint.name);
    if (children.has(joint.childLink)) {
      throw new Error(`URDF link ${joint.childLink} has multiple parents`);
    }
    children.add(joint.childLink);
    const current = jointsByParent.get(joint.parentLink) || [];
    current.push(joint.childLink);
    jointsByParent.set(joint.parentLink, current);
  }
  const rootCandidates = [...linkNames].filter((linkName) => !children.has(linkName));
  if (rootCandidates.length !== 1) {
    throw new Error(`URDF must form a single rooted tree; found roots ${JSON.stringify(rootCandidates)}`);
  }
  const rootLink = rootCandidates[0];
  const visited = new Set();
  const visiting = new Set();
  const visit = (linkName) => {
    if (visited.has(linkName)) {
      return;
    }
    if (visiting.has(linkName)) {
      throw new Error("URDF joint graph contains a cycle");
    }
    visiting.add(linkName);
    for (const childLink of jointsByParent.get(linkName) || []) {
      visit(childLink);
    }
    visiting.delete(linkName);
    visited.add(linkName);
  };
  visit(rootLink);
  if (visited.size !== links.length) {
    const missing = links.map((link) => link.name).filter((linkName) => !visited.has(linkName));
    throw new Error(`URDF leaves links disconnected from the root: ${JSON.stringify(missing)}`);
  }
  return rootLink;
}

export function parseUrdf(xmlText, { sourceUrl, explorerMetadata = null, motionExplorerMetadata = null } = {}) {
  if (typeof DOMParser === "undefined") {
    throw new Error("DOMParser is unavailable in this environment");
  }
  const document = new DOMParser().parseFromString(String(xmlText || ""), "application/xml");
  const parseError = document.querySelector("parsererror");
  if (parseError) {
    throw new Error("Failed to parse URDF XML");
  }
  const robot = document.documentElement;
  if (!robot || robot.tagName !== "robot") {
    throw new Error("URDF root element must be <robot>");
  }
  const robotName = String(robot.getAttribute("name") || "").trim();
  if (!robotName) {
    throw new Error("URDF robot name is required");
  }
  const namedMaterialColors = parseNamedMaterialColors(robot);

  const links = childElementsByTag(robot, "link").map((linkElement) => {
    const name = String(linkElement.getAttribute("name") || "").trim();
    if (!name) {
      throw new Error("URDF link name is required");
    }
    const visuals = childElementsByTag(linkElement, "visual").map((visualElement, index) => {
      const geometryElement = childElementsByTag(visualElement, "geometry")[0];
      const meshElement = geometryElement ? childElementsByTag(geometryElement, "mesh")[0] : null;
      if (!meshElement) {
        throw new Error(`URDF link ${name} uses unsupported visual geometry`);
      }
      const filename = String(meshElement.getAttribute("filename") || "").trim();
      if (!filename) {
        throw new Error(`URDF link ${name} visual ${index + 1} is missing a mesh filename`);
      }
      return {
        id: `${name}:v${index + 1}`,
        label: labelForMeshFilename(filename),
        meshUrl: resolveMeshUrl(filename, sourceUrl || "/"),
        color: resolveVisualColor(visualElement, namedMaterialColors, {
          linkName: name,
          visualIndex: index + 1
        }),
        localTransform: multiplyTransforms(
          parseOriginTransform(childElementsByTag(visualElement, "origin")[0]),
          parseScaleTransform(meshElement)
        )
      };
    });
    return {
      name,
      visuals
    };
  });

  const linkNames = new Set();
  for (const link of links) {
    if (linkNames.has(link.name)) {
      throw new Error(`Duplicate URDF link name: ${link.name}`);
    }
    linkNames.add(link.name);
  }

  const parsedJoints = childElementsByTag(robot, "joint").map((jointElement) => parseJoint(jointElement, linkNames));
  const { joints, poses, motion, motionServer } = applyExplorerMetadata(parsedJoints, explorerMetadata, motionExplorerMetadata, links);
  validateMimicJoints(joints);
  const rootLink = validateTree(links, joints);

  return {
    robotName,
    rootLink,
    rootWorldTransform: [...IDENTITY_TRANSFORM],
    links,
    joints,
    poses,
    motion,
    motionServer
  };
}
