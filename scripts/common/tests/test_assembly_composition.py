import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace

from common.assembly_composition import build_linked_assembly_composition, build_native_assembly_composition
from common.assembly_spec import AssemblyInstanceSpec, AssemblySpec
from common.render import part_selector_manifest_path
from tests.cad_test_roots import IsolatedCadRoots


IDENTITY_TRANSFORM = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


class NativeAssemblyCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="assembly-composition-")
        tempdir = self._isolated_roots.temporary_cad_directory(prefix="tmp-assembly-composition-")
        self._tempdir = tempdir
        self.temp_root = Path(tempdir.name)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_root, ignore_errors=True)
        self._tempdir.cleanup()

    def _write_step(self, name: str) -> Path:
        step_path = self.temp_root / f"{name}.step"
        step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n", encoding="utf-8")
        return step_path

    def _write_catalog_step(self, cad_ref: str) -> Path:
        step_path = self._isolated_roots.cad_root / f"{cad_ref}.step"
        step_path.parent.mkdir(parents=True, exist_ok=True)
        step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n", encoding="utf-8")
        return step_path

    def _write_topology(self, rows: list[list[object]]) -> Path:
        topology_path = self.temp_root / ".assembly.step" / "topology.json"
        topology_path.parent.mkdir(parents=True, exist_ok=True)
        topology_path.write_text(
            json.dumps(
                {
                    "tables": {
                        "occurrenceColumns": [
                            "id",
                            "parentId",
                            "path",
                            "name",
                            "sourceName",
                            "transform",
                            "bbox",
                            "shapeCount",
                            "faceCount",
                            "edgeCount",
                            "vertexCount",
                        ]
                    },
                    "occurrences": rows,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return topology_path

    def _write_component_mesh(self, occurrence_id: str) -> Path:
        mesh_path = self.temp_root / ".assembly.step" / "components" / f"{occurrence_id}.glb"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(b"glb component")
        return mesh_path

    def _write_source_topology(self, step_path: Path) -> None:
        topology_path = part_selector_manifest_path(step_path)
        topology_path.parent.mkdir(parents=True, exist_ok=True)
        topology_path.write_text(
            json.dumps(
                {
                    "stats": {
                        "shapeCount": 1,
                        "faceCount": 6,
                        "edgeCount": 12,
                        "vertexCount": 8,
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_native_assembly_composition_embeds_component_mesh_assets(self) -> None:
        self._write_step("assembly")
        topology_path = self._write_topology(
            [
                ["o1", "", "1", "root", "root", IDENTITY_TRANSFORM, None, 0, 0, 0, 0],
                [
                    "o1.1",
                    "o1",
                    "1.1",
                    "sample_component",
                    "SAMPLE_COMPONENT",
                    IDENTITY_TRANSFORM,
                    {"min": [0, 0, 0], "max": [1, 1, 1]},
                    1,
                    6,
                    12,
                    8,
                ],
            ]
        )
        mesh_path = self._write_component_mesh("o1.1")

        payload = build_native_assembly_composition(
            cad_ref="imports/assembly",
            topology_path=topology_path,
            topology_manifest=json.loads(topology_path.read_text(encoding="utf-8")),
            component_mesh_paths={"o1.1": mesh_path},
        )

        self.assertEqual("native", payload["mode"])
        root = payload["root"]
        self.assertEqual("assembly", root["displayName"])
        self.assertEqual(1, len(root["children"]))
        part = root["children"][0]
        self.assertEqual("part", part["nodeType"])
        self.assertEqual(
            {
                "shapes": 1,
                "faces": 6,
                "edges": 12,
                "vertices": 8,
            },
            part["topologyCounts"],
        )
        self.assertEqual("sample_component", part["displayName"])
        self.assertTrue(part["assets"]["glb"]["url"].startswith("components/"))
        self.assertIn("components/o1.1.glb?v=", part["assets"]["glb"]["url"])

    def test_native_assembly_composition_falls_back_to_single_component(self) -> None:
        self._write_step("assembly")
        topology_path = self._write_topology(
            [
                [
                    "o1",
                    "",
                    "1",
                    "vendor-assembly",
                    "vendor-assembly",
                    IDENTITY_TRANSFORM,
                    {"min": [0, 0, 0], "max": [2, 2, 2]},
                    1,
                    12,
                    24,
                    16,
                ],
            ]
        )
        mesh_path = self._write_component_mesh("o1")

        payload = build_native_assembly_composition(
            cad_ref="imports/assembly",
            topology_path=topology_path,
            topology_manifest=json.loads(topology_path.read_text(encoding="utf-8")),
            component_mesh_paths={"o1": mesh_path},
        )

        root = payload["root"]
        self.assertEqual(1, len(root["children"]))
        part = root["children"][0]
        self.assertEqual("o1", part["occurrenceId"])
        self.assertEqual("vendor-assembly", part["displayName"])

    def test_linked_assembly_matches_build123d_component_source_names(self) -> None:
        leaf_step_path = self._write_catalog_step("parts/leaf")
        self._write_source_topology(leaf_step_path)
        topology_path = self._write_topology(
            [
                ["o1", "", "1", "assembly", "assembly", IDENTITY_TRANSFORM, None, 1, 6, 12, 8],
                [
                    "o1.1",
                    "o1",
                    "1.1",
                    "=>[0:1:1:2]",
                    "leaf",
                    IDENTITY_TRANSFORM,
                    {"min": [0, 0, 0], "max": [1, 1, 1]},
                    1,
                    6,
                    12,
                    8,
                ],
                [
                    "o1.1.1",
                    "o1.1",
                    "1.1.1",
                    "=>[0:1:1:3]",
                    "=>[0:1:1:3]",
                    IDENTITY_TRANSFORM,
                    {"min": [0, 0, 0], "max": [1, 1, 1]},
                    1,
                    6,
                    12,
                    8,
                ],
            ]
        )
        assembly_spec = AssemblySpec(
            assembly_path=self.temp_root / "assembly.py",
            instances=(
                AssemblyInstanceSpec(
                    instance_id="leaf",
                    source_path=leaf_step_path.resolve(),
                    path="leaf.step",
                    name="leaf",
                    transform=tuple(float(value) for value in IDENTITY_TRANSFORM),
                ),
            ),
        )

        payload = build_linked_assembly_composition(
            cad_ref="assemblies/assembly",
            topology_path=topology_path,
            topology_manifest=json.loads(topology_path.read_text(encoding="utf-8")),
            assembly_spec=assembly_spec,
            entries_by_step_path={
                leaf_step_path.resolve(): SimpleNamespace(
                    kind="part",
                    step_path=leaf_step_path,
                )
            },
            read_assembly_spec=lambda path: (_ for _ in ()).throw(AssertionError(path)),
        )

        child = payload["root"]["children"][0]
        self.assertEqual("linked", payload["mode"])
        self.assertEqual("o1.1", child["occurrenceId"])
        self.assertEqual("leaf", child["displayName"])
        self.assertEqual(
            {
                "shapes": 1,
                "faces": 6,
                "edges": 12,
                "vertices": 8,
            },
            child["topologyCounts"],
        )


if __name__ == "__main__":
    unittest.main()
