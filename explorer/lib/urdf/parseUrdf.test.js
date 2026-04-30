import assert from "node:assert/strict";
import test from "node:test";

import { parseUrdf } from "./parseUrdf.js";

class FakeElement {
  constructor(tagName, attributes = {}, children = []) {
    this.nodeType = 1;
    this.tagName = tagName;
    this.localName = String(tagName || "").split(":").pop();
    this.namespaceURI = null;
    this._attributes = { ...attributes };
    this.childNodes = children;
  }

  getAttribute(name) {
    return Object.hasOwn(this._attributes, name) ? this._attributes[name] : null;
  }
}

class FakeDocument {
  constructor(documentElement) {
    this.documentElement = documentElement;
  }

  querySelector(selector) {
    return selector === "parsererror" ? null : null;
  }
}

function withFakeDomParser(document, callback) {
  const previous = globalThis.DOMParser;
  globalThis.DOMParser = class FakeDomParser {
    parseFromString() {
      return document;
    }
  };
  try {
    return callback();
  } finally {
    globalThis.DOMParser = previous;
  }
}

test("parseUrdf resolves referenced robot material colors from rgba", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("material", { name: "black_aluminum" }, [
      new FakeElement("color", { rgba: "0.168627 0.184314 0.2 1" })
    ]),
    new FakeElement("link", { name: "base_link" }, [
      new FakeElement("visual", {}, [
        new FakeElement("geometry", {}, [
          new FakeElement("mesh", { filename: "meshes/sample_part.stl", scale: "0.001 0.001 0.001" })
        ]),
        new FakeElement("material", { name: "black_aluminum" })
      ])
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", { sourceUrl: "/workspace/sample_robot.urdf" }));

  assert.equal(urdfData.links[0].visuals[0].color, "#2b2f33");
  assert.equal(
    urdfData.links[0].visuals[0].meshUrl,
    "/workspace/meshes/sample_part.stl"
  );
});

test("parseUrdf applies non-zero default joint angles from explorer metadata sidecar", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "arm_link" }),
    new FakeElement("joint", { name: "base_to_arm", type: "continuous" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "arm_link" }),
      new FakeElement("origin", { xyz: "0 0 0", rpy: "0 0 0" }),
      new FakeElement("axis", { xyz: "0 1 0" })
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
    sourceUrl: "/workspace/sample_robot.urdf",
    explorerMetadata: {
      schemaVersion: 3,
      kind: "texttocad-urdf-explorer",
      jointDefaultsByName: {
        base_to_arm: 90
      },
      poses: []
    }
  }));

  assert.equal(urdfData.joints[0].defaultValueDeg, 90);
});

test("parseUrdf accepts prismatic mimic joints", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "driver_link" }),
    new FakeElement("link", { name: "slider_link" }),
    new FakeElement("joint", { name: "driver_joint", type: "revolute" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "driver_link" }),
      new FakeElement("limit", { lower: "0", upper: "1", effort: "1", velocity: "1" })
    ]),
    new FakeElement("joint", { name: "slider_joint", type: "prismatic" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "slider_link" }),
      new FakeElement("axis", { xyz: "1 0 0" }),
      new FakeElement("limit", { lower: "0", upper: "0.05", effort: "1", velocity: "1" }),
      new FakeElement("mimic", { joint: "driver_joint", multiplier: "0.0065", offset: "0" })
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", { sourceUrl: "/workspace/sample_robot.urdf" }));

  assert.equal(urdfData.joints[1].type, "prismatic");
  assert.equal(urdfData.joints[1].maxValueDeg, 0.05);
  assert.deepEqual(urdfData.joints[1].mimic, {
    joint: "driver_joint",
    multiplier: 0.0065,
    offset: 0
  });
});

test("parseUrdf captures explorer pose presets from explorer metadata sidecar", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "arm_link" }),
    new FakeElement("joint", { name: "base_to_arm", type: "continuous" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "arm_link" }),
      new FakeElement("origin", { xyz: "0 0 0", rpy: "0 0 0" }),
      new FakeElement("axis", { xyz: "0 1 0" })
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
    sourceUrl: "/workspace/sample_robot.urdf",
    explorerMetadata: {
      schemaVersion: 3,
      kind: "texttocad-urdf-explorer",
      jointDefaultsByName: {
        base_to_arm: 15
      },
      poses: [
        {
          name: "home",
          jointValuesByName: {
            base_to_arm: 45
          }
        }
      ]
    }
  }));

  assert.equal(urdfData.joints[0].defaultValueDeg, 15);
  assert.deepEqual(urdfData.poses, [
    {
      name: "home",
      jointValuesByName: {
        base_to_arm: 45
      }
    }
  ]);
});

test("parseUrdf captures optional motionServer pose and planning metadata from robot motion explorer sidecar", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "tool_link" }),
    new FakeElement("joint", { name: "base_to_tool", type: "fixed" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "tool_link" })
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
    sourceUrl: "/workspace/sample_robot.urdf",
    explorerMetadata: {
      schemaVersion: 3,
      kind: "texttocad-urdf-explorer",
      poses: []
    },
    motionExplorerMetadata: {
      schemaVersion: 1,
      kind: "texttocad-robot-motion-explorer",
      motionServer: {
        version: 1,
        commands: {
          "urdf.solvePose": {
            endEffectors: [
              {
                name: "tool",
                link: "tool_link",
                frame: "base_link",
                positionTolerance: 0.004
              }
            ]
          },
          "urdf.planToPose": {}
        }
      }
    }
  }));

  assert.deepEqual(urdfData.motion, {
    transport: "motionServer",
    command: "urdf.planToPose",
    canSolvePose: true,
    canPlanToPose: true,
    endEffectors: [
      {
        name: "tool",
        link: "tool_link",
        frame: "base_link",
        positionTolerance: 0.004
      }
    ],
    motionServer: urdfData.motionServer
  });
  assert.ok(urdfData.motionServer.commands["urdf.planToPose"]);
});

test("parseUrdf supports pose-only motionServer metadata", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "tool_link" }),
    new FakeElement("joint", { name: "base_to_tool", type: "fixed" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "tool_link" })
    ])
  ]);

  const urdfData = withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
    sourceUrl: "/workspace/sample_robot.urdf",
    motionExplorerMetadata: {
      schemaVersion: 1,
      kind: "texttocad-robot-motion-explorer",
      motionServer: {
        version: 1,
        commands: {
          "urdf.solvePose": {
            endEffectors: [
              {
                name: "tool",
                link: "tool_link",
                frame: "base_link"
              }
            ]
          }
        }
      }
    }
  }));

  assert.equal(urdfData.motion.command, "urdf.solvePose");
  assert.equal(urdfData.motion.canPlanToPose, false);
});

test("parseUrdf rejects motionServer metadata in URDF explorer sidecar", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" })
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      explorerMetadata: {
        schemaVersion: 3,
        kind: "texttocad-urdf-explorer",
        motionServer: {
          version: 1,
          commands: {
            "urdf.solvePose": {
              endEffectors: []
            }
          }
        }
      }
    })),
    /must not include motionServer/
  );
});

test("parseUrdf rejects motionServer pose metadata that references missing links", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "tool_link" }),
    new FakeElement("joint", { name: "base_to_tool", type: "fixed" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "tool_link" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      motionExplorerMetadata: {
        schemaVersion: 1,
        kind: "texttocad-robot-motion-explorer",
        motionServer: {
          version: 1,
          commands: {
            "urdf.solvePose": {
              endEffectors: [
                {
                  name: "tool",
                  link: "missing_link",
                  frame: "base_link"
                }
              ]
            }
          }
        }
      }
    })),
    /motionServer end effector tool references missing link missing_link/
  );
});

test("parseUrdf rejects provider details in explorer motion metadata", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "tool_link" }),
    new FakeElement("joint", { name: "base_to_tool", type: "fixed" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "tool_link" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      motionExplorerMetadata: {
        schemaVersion: 1,
        kind: "texttocad-robot-motion-explorer",
        motionServer: {
          version: 1,
          commands: {
            "urdf.solvePose": {
              provider: "unknown_planner",
              endEffectors: [
                {
                  name: "tool",
                  link: "tool_link",
                  frame: "base_link"
                }
              ]
            }
          }
        }
      }
    })),
    /command urdf\.solvePose cannot include provider/
  );
});

test("parseUrdf rejects planning metadata without a pose command", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "tool_link" }),
    new FakeElement("joint", { name: "base_to_tool", type: "fixed" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "tool_link" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      motionExplorerMetadata: {
        schemaVersion: 1,
        kind: "texttocad-robot-motion-explorer",
        motionServer: {
          version: 1,
          commands: {
            "urdf.planToPose": {}
          }
        }
      }
    })),
    /urdf\.planToPose requires urdf\.solvePose/
  );
});

test("parseUrdf rejects sidecar explorer poses that reference missing joints", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "arm_link" }),
    new FakeElement("joint", { name: "base_to_arm", type: "continuous" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "arm_link" }),
      new FakeElement("axis", { xyz: "0 1 0" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      explorerMetadata: {
        schemaVersion: 3,
        kind: "texttocad-urdf-explorer",
        poses: [
          {
            name: "home",
            jointValuesByName: {
              missing_joint: 45
            }
          }
        ]
      }
    })),
    /Explorer pose home references missing joint missing_joint/
  );
});

test("parseUrdf rejects duplicate sidecar explorer pose names", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "arm_link" }),
    new FakeElement("joint", { name: "base_to_arm", type: "continuous" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "arm_link" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      explorerMetadata: {
        schemaVersion: 3,
        kind: "texttocad-urdf-explorer",
        poses: [
          { name: "home", jointValuesByName: { base_to_arm: 0 } },
          { name: "home", jointValuesByName: { base_to_arm: 45 } }
        ]
      }
    })),
    /Duplicate explorer pose name: home/
  );
});

test("parseUrdf rejects sidecar explorer poses that target mimic joints", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "driver_link" }),
    new FakeElement("link", { name: "slider_link" }),
    new FakeElement("joint", { name: "driver_joint", type: "revolute" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "driver_link" }),
      new FakeElement("limit", { lower: "0", upper: "1", effort: "1", velocity: "1" })
    ]),
    new FakeElement("joint", { name: "slider_joint", type: "prismatic" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "slider_link" }),
      new FakeElement("axis", { xyz: "1 0 0" }),
      new FakeElement("limit", { lower: "0", upper: "0.05", effort: "1", velocity: "1" }),
      new FakeElement("mimic", { joint: "driver_joint", multiplier: "0.0065", offset: "0" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      explorerMetadata: {
        schemaVersion: 3,
        kind: "texttocad-urdf-explorer",
        poses: [
          { name: "pinch", jointValuesByName: { slider_joint: 0.02 } }
        ]
      }
    })),
    /Explorer pose pinch joint slider_joint must target a non-mimic joint/
  );
});

test("parseUrdf rejects sidecar explorer values outside joint limits", () => {
  const robot = new FakeElement("robot", { name: "sample_robot" }, [
    new FakeElement("link", { name: "base_link" }),
    new FakeElement("link", { name: "arm_link" }),
    new FakeElement("joint", { name: "base_to_arm", type: "revolute" }, [
      new FakeElement("parent", { link: "base_link" }),
      new FakeElement("child", { link: "arm_link" }),
      new FakeElement("limit", { lower: "0", upper: "1", effort: "1", velocity: "1" })
    ])
  ]);

  assert.throws(
    () => withFakeDomParser(new FakeDocument(robot), () => parseUrdf("<robot />", {
      sourceUrl: "/workspace/sample_robot.urdf",
      explorerMetadata: {
        schemaVersion: 3,
        kind: "texttocad-urdf-explorer",
        poses: [
          { name: "too_far", jointValuesByName: { base_to_arm: 90 } }
        ]
      }
    })),
    /Explorer pose too_far joint base_to_arm must stay within joint limits/
  );
});
