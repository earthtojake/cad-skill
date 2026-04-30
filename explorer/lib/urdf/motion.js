import { clampJointValueDeg, linkOriginInFrame } from "./kinematics.js";

const MOTION_LIMIT_EPSILON = 1e-6;

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function toFiniteNumber(value, fallback = 0) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : fallback;
}

export function normalizeMotionTargetPosition(value, fallback = [0, 0, 0]) {
  const source = Array.isArray(value) ? value : fallback;
  return [0, 1, 2].map((index) => toFiniteNumber(source[index], fallback[index] ?? 0));
}

export function positionDistance(left, right) {
  const a = normalizeMotionTargetPosition(left);
  const b = normalizeMotionTargetPosition(right);
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

export function validateUrdfMotionJointValues(urdfData, jointValuesByName) {
  if (!isPlainObject(jointValuesByName)) {
    throw new Error("Motion server response jointValuesByName must be an object");
  }
  const joints = Array.isArray(urdfData?.joints) ? urdfData.joints : [];
  const jointByName = new Map(joints.map((joint) => [String(joint?.name || ""), joint]).filter(([name]) => name));
  const validated = {};
  for (const [name, rawValue] of Object.entries(jointValuesByName)) {
    const jointName = String(name || "").trim();
    if (!jointName) {
      throw new Error("Motion server response includes an empty joint name");
    }
    const joint = jointByName.get(jointName);
    if (!joint) {
      throw new Error(`Motion server response references unknown joint ${jointName}`);
    }
    const jointType = String(joint?.type || "fixed");
    if (jointType === "fixed") {
      throw new Error(`Motion server response cannot set fixed joint ${jointName}`);
    }
    if (joint?.mimic) {
      throw new Error(`Motion server response cannot set mimic joint ${jointName}`);
    }
    const numericValue = Number(rawValue);
    if (!Number.isFinite(numericValue)) {
      throw new Error(`Motion server response joint ${jointName} must be a finite number`);
    }
    const clampedValue = clampJointValueDeg(joint, numericValue);
    if (jointType !== "continuous" && Math.abs(clampedValue - numericValue) > MOTION_LIMIT_EPSILON) {
      throw new Error(`Motion server response joint ${jointName} must stay within joint limits`);
    }
    validated[jointName] = numericValue;
  }
  return validated;
}

export function validateUrdfMotionTrajectory(urdfData, trajectory) {
  if (!isPlainObject(trajectory)) {
    throw new Error("Motion server response trajectory must be an object");
  }
  const rawJointNames = Array.isArray(trajectory.jointNames) ? trajectory.jointNames : [];
  const jointNames = rawJointNames.map((name) => String(name || "").trim()).filter(Boolean);
  if (!jointNames.length) {
    throw new Error("Motion server response trajectory.jointNames must be a non-empty array");
  }
  const rawPoints = Array.isArray(trajectory.points) ? trajectory.points : [];
  if (!rawPoints.length) {
    throw new Error("Motion server response trajectory.points must be a non-empty array");
  }
  let previousTime = -Number.EPSILON;
  const points = rawPoints.map((point, pointIndex) => {
    if (!isPlainObject(point)) {
      throw new Error(`Motion server response trajectory point ${pointIndex + 1} must be an object`);
    }
    const timeFromStartSec = Number(point.timeFromStartSec);
    if (!Number.isFinite(timeFromStartSec) || timeFromStartSec < 0 || timeFromStartSec < previousTime) {
      throw new Error("Motion server response trajectory times must be finite, non-negative, and sorted");
    }
    previousTime = timeFromStartSec;
    const positionsDeg = Array.isArray(point.positionsDeg) ? point.positionsDeg.map((value) => Number(value)) : [];
    if (positionsDeg.length !== jointNames.length || positionsDeg.some((value) => !Number.isFinite(value))) {
      throw new Error("Motion server response trajectory positionsDeg must match trajectory.jointNames");
    }
    const positionsByNameDeg = Object.fromEntries(jointNames.map((jointName, index) => [jointName, positionsDeg[index]]));
    validateUrdfMotionJointValues(urdfData, positionsByNameDeg);
    return {
      timeFromStartSec,
      positionsDeg,
      positionsByNameDeg
    };
  });
  return {
    jointNames,
    points
  };
}

export function measureUrdfMotionResult(urdfData, jointValuesByName, endEffector, targetPosition) {
  const actualPosition = linkOriginInFrame(
    urdfData,
    jointValuesByName,
    endEffector?.link,
    endEffector?.frame
  );
  if (!actualPosition) {
    return {
      actualPosition: null,
      positionError: Number.POSITIVE_INFINITY
    };
  }
  return {
    actualPosition,
    positionError: positionDistance(actualPosition, targetPosition)
  };
}
