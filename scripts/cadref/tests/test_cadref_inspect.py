import shutil
import unittest
from pathlib import Path
from unittest import mock

from cadref import inspect as cadref_inspect
from cadref import syntax as cadref_syntax
from common import assembly_spec
from common.step_scene import SelectorBundle, SelectorProfile
from tests.cad_test_roots import IsolatedCadRoots


def _refs_manifest(cad_ref: str) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "profile": "refs",
        "cadPath": cad_ref,
        "stepPath": f"{cad_ref}.step",
        "stepHash": "step-hash-123",
        "bbox": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
        "stats": {
            "occurrenceCount": 2,
            "leafOccurrenceCount": 1,
            "shapeCount": 1,
            "faceCount": 2,
            "edgeCount": 2,
            "vertexCount": 1,
        },
        "tables": {
            "occurrenceColumns": [
                "id",
                "path",
                "name",
                "sourceName",
                "parentId",
                "transform",
                "bbox",
                "shapeStart",
                "shapeCount",
                "faceStart",
                "faceCount",
                "edgeStart",
                "edgeCount",
                "vertexStart",
                "vertexCount",
            ],
            "shapeColumns": [
                "id",
                "occurrenceId",
                "ordinal",
                "kind",
                "bbox",
                "center",
                "area",
                "volume",
                "faceStart",
                "faceCount",
                "edgeStart",
                "edgeCount",
                "vertexStart",
                "vertexCount",
            ],
            "faceColumns": [
                "id",
                "occurrenceId",
                "shapeId",
                "ordinal",
                "surfaceType",
                "area",
                "center",
                "normal",
                "bbox",
                "edgeStart",
                "edgeCount",
                "relevance",
                "flags",
                "params",
                "triangleStart",
                "triangleCount",
            ],
            "edgeColumns": [
                "id",
                "occurrenceId",
                "shapeId",
                "ordinal",
                "curveType",
                "length",
                "center",
                "bbox",
                "faceStart",
                "faceCount",
                "vertexStart",
                "vertexCount",
                "relevance",
                "flags",
                "params",
                "segmentStart",
                "segmentCount",
            ],
            "vertexColumns": [
                "id",
                "occurrenceId",
                "shapeId",
                "ordinal",
                "center",
                "bbox",
                "edgeStart",
                "edgeCount",
                "relevance",
                "flags",
            ],
        },
        "occurrences": [
            [
                "o1",
                "1",
                "Root",
                "Root",
                None,
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
                0,
                1,
                0,
                2,
                0,
                2,
                0,
                1,
            ],
            [
                "o1.2",
                "1.2",
                "Bracket",
                "Bracket",
                "o1",
                [1, 0, 0, 5, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                {"min": [5.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
                0,
                1,
                0,
                2,
                0,
                2,
                0,
                1,
            ],
        ],
        "shapes": [
            [
                "o1.2.s1",
                "o1.2",
                1,
                "solid",
                {"min": [5.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
                [7.5, 5.0, 5.0],
                100.0,
                250.0,
                0,
                2,
                0,
                2,
                0,
                1,
            ]
        ],
        "faces": [
            [
                "o1.2.f1",
                "o1.2",
                "o1.2.s1",
                1,
                "plane",
                20.0,
                [6.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                {"min": [5.0, 0.0, 0.0], "max": [7.0, 2.0, 0.0]},
                0,
                2,
                80,
                0,
                {"origin": [5.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
                0,
                0,
            ],
            [
                "o1.2.f2",
                "o1.2",
                "o1.2.s1",
                2,
                "cylinder",
                12.0,
                [7.0, 2.0, 1.0],
                [1.0, 0.0, 0.0],
                {"min": [6.0, 1.0, 0.0], "max": [8.0, 3.0, 2.0]},
                1,
                0,
                60,
                0,
                {"center": [7.0, 2.0, 1.0], "axis": [1.0, 0.0, 0.0], "radius": 1.0},
                0,
                0,
            ],
        ],
        "edges": [
            [
                "o1.2.e1",
                "o1.2",
                "o1.2.s1",
                1,
                "line",
                4.0,
                [6.0, 1.0, 0.0],
                {"min": [5.0, 0.0, 0.0], "max": [7.0, 2.0, 0.0]},
                0,
                2,
                0,
                1,
                90,
                0,
                {"origin": [5.0, 0.0, 0.0], "direction": [1.0, 0.0, 0.0]},
                0,
                0,
            ],
            [
                "o1.2.e2",
                "o1.2",
                "o1.2.s1",
                2,
                "line",
                3.0,
                [5.5, 0.5, 0.0],
                {"min": [5.0, 0.0, 0.0], "max": [6.0, 1.0, 0.0]},
                2,
                1,
                1,
                1,
                75,
                0,
                {"origin": [5.0, 0.0, 0.0], "direction": [0.0, 1.0, 0.0]},
                0,
                0,
            ],
        ],
        "vertices": [
            [
                "o1.2.v1",
                "o1.2",
                "o1.2.s1",
                1,
                [5.0, 0.0, 0.0],
                {"min": [5.0, 0.0, 0.0], "max": [5.0, 0.0, 0.0]},
                0,
                2,
                95,
                0,
            ]
        ],
        "relations": {
            "faceEdgeRows": [0, 1, 0],
            "edgeFaceRows": [0, 1, 0],
            "edgeVertexRows": [0, 0],
            "vertexEdgeRows": [0, 1],
        },
    }


def _summary_manifest(cad_ref: str) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "profile": "summary",
        "cadPath": cad_ref,
        "stepPath": f"{cad_ref}.step",
        "stepHash": "step-hash-123",
        "bbox": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
        "stats": {
            "occurrenceCount": 1,
            "leafOccurrenceCount": 1,
            "shapeCount": 1,
            "faceCount": 2,
            "edgeCount": 2,
            "vertexCount": 1,
        },
        "tables": {
            "occurrenceColumns": [
                "id",
                "path",
                "name",
                "sourceName",
                "parentId",
                "transform",
                "bbox",
                "shapeStart",
                "shapeCount",
                "faceStart",
                "faceCount",
                "edgeStart",
                "edgeCount",
                "vertexStart",
                "vertexCount",
            ],
            "shapeColumns": [],
            "faceColumns": [],
            "edgeColumns": [],
            "vertexColumns": [],
        },
        "occurrences": [
            [
                "o1",
                "1",
                "Part",
                "Part",
                None,
                [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
                0,
                1,
                0,
                2,
                0,
                2,
                0,
                1,
            ]
        ],
        "shapes": [],
        "faces": [],
        "edges": [],
        "vertices": [],
    }


class CadrefSyntaxTests(unittest.TestCase):
    def test_normalize_selector_list_inherits_occurrence_prefix(self) -> None:
        selectors = cadref_syntax.normalize_selector_list("o1.2.f12,f13,e7,v2,s3")

        self.assertEqual(
            ["o1.2.f12", "o1.2.f13", "o1.2.e7", "o1.2.v2", "o1.2.s3"],
            selectors,
        )

class CadrefInspectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="cadref-inspect-")
        tempdir = self._isolated_roots.temporary_cad_directory(prefix="tmp-cadref-inspect-")
        self._tempdir = tempdir
        self.temp_root = Path(tempdir.name)
        self.relative_dir = self.temp_root.relative_to(assembly_spec.CAD_ROOT).as_posix()
        self.lookup_ref = f"{self.relative_dir}/sample"
        self.cad_ref = self.lookup_ref
        self.step_path = self.temp_root / "sample.step"
        self.step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n")
        self.addCleanup(self._tempdir.cleanup)
        self.addCleanup(lambda: shutil.rmtree(self.temp_root, ignore_errors=True))

    def test_whole_entry_summary_uses_summary_profile(self) -> None:
        def fake_extract(step_path, *, cad_ref=None, profile=None, options=None):
            self.assertEqual(self.step_path.resolve(), step_path.resolve())
            self.assertEqual(SelectorProfile.SUMMARY, profile)
            return SelectorBundle(manifest=_summary_manifest(cad_ref or self.cad_ref))

        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect, "extract_selectors", side_effect=fake_extract
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}]")

        self.assertTrue(result["ok"])
        token = result["tokens"][0]
        self.assertEqual(1, token["summary"]["occurrenceCount"])
        self.assertEqual(2, token["summary"]["faceCount"])
        self.assertEqual([], token["selections"])

    def test_face_lookup_resolves_single_occurrence_alias_and_detail(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#o1.2.f1]", detail=True)

        self.assertTrue(result["ok"])
        selection = result["tokens"][0]["selections"][0]
        self.assertEqual("face", selection["selectorType"])
        self.assertEqual("o1.2.f1", selection["normalizedSelector"])
        self.assertEqual("plane area=20.0", selection["summary"])
        self.assertEqual(["e1", "e2"], selection["detail"]["adjacentEdgeSelectors"])

    def test_vertex_lookup_resolves_corner_detail(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#o1.2.v1]", detail=True)

        self.assertTrue(result["ok"])
        selection = result["tokens"][0]["selections"][0]
        self.assertEqual("vertex", selection["selectorType"])
        self.assertEqual("o1.2.v1", selection["normalizedSelector"])
        self.assertEqual("corner edges=2", selection["summary"])
        self.assertEqual(["e1", "e2"], selection["detail"]["adjacentEdgeSelectors"])
        self.assertEqual(["f1", "f2"], selection["detail"]["adjacentFaceSelectors"])

    def test_single_occurrence_alias_is_compacted_in_copy_text(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_summary_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#f2]", detail=True)

        self.assertFalse(result["ok"])

        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest={
                **_refs_manifest(self.cad_ref),
                "stats": {
                    "occurrenceCount": 1,
                    "leafOccurrenceCount": 1,
                "shapeCount": 1,
                "faceCount": 2,
                "edgeCount": 2,
                "vertexCount": 1,
            },
            "occurrences": [_refs_manifest(self.cad_ref)["occurrences"][1]],
        }),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#v1]", detail=True)

        self.assertTrue(result["ok"])
        selection = result["tokens"][0]["selections"][0]
        self.assertEqual("v1", selection["displaySelector"])
        self.assertEqual(f"@cad[{self.cad_ref}#v1]", selection["copyText"])

    def test_old_part_selector_syntax_is_rejected(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#p:legacy.f1]")

        self.assertFalse(result["ok"])
        self.assertEqual("selector", result["errors"][0]["kind"])

    def test_topology_flag_returns_full_selector_lists(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}]", include_topology=True)

        self.assertTrue(result["ok"])
        topology = result["tokens"][0]["topology"]
        self.assertIn("f1", topology["faces"])
        self.assertIn("e1", topology["edges"])
        self.assertIn("v1", topology["vertices"])

    def test_non_leaf_occurrence_detail_reports_children(self) -> None:
        with mock.patch.object(cadref_inspect, "find_step_path", return_value=self.step_path), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(self.cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{self.cad_ref}#o1]", detail=True)

        self.assertTrue(result["ok"])
        selection = result["tokens"][0]["selections"][0]
        self.assertEqual("occurrence", selection["selectorType"])
        self.assertEqual("o1", selection["normalizedSelector"])
        self.assertEqual(1, selection["detail"]["childCount"])
        self.assertEqual(["o1.2"], selection["detail"]["descendantOccurrenceIds"])

    def test_assembly_topology_lookup_resolves_from_generated_step(self) -> None:
        assembly_cad_ref = f"{self.relative_dir}/sample-assembly"
        assembly_path = self.temp_root / "sample-assembly.py"
        assembly_step_path = self.temp_root / "sample-assembly.step"
        assembly_path.write_text(
            "def gen_step():\n"
            "    return {'instances': [], 'step_output': 'sample-assembly.step'}\n",
            encoding="utf-8",
        )

        with mock.patch.object(
            cadref_inspect,
            "resolve_cad_source_path",
            return_value=("assembly", assembly_path),
        ), mock.patch.object(
            cadref_inspect,
            "find_step_path",
            return_value=assembly_step_path,
        ), mock.patch.object(
            cadref_inspect,
            "extract_selectors",
            return_value=SelectorBundle(manifest=_refs_manifest(assembly_cad_ref)),
        ):
            result = cadref_inspect.inspect_cad_refs(f"@cad[{assembly_cad_ref}#o1.2.f1]", detail=True)

        self.assertTrue(result["ok"])
        selection = result["tokens"][0]["selections"][0]
        self.assertEqual("assembly", result["tokens"][0]["summary"]["kind"])
        self.assertEqual("face", selection["selectorType"])
        self.assertEqual("o1.2.f1", selection["normalizedSelector"])

if __name__ == "__main__":
    unittest.main()
