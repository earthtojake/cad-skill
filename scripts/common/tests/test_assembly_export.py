import shutil
import unittest
from pathlib import Path

import build123d

from common.assembly_export import build_assembly_compound, export_assembly_step
from common.assembly_spec import AssemblyInstanceSpec, AssemblyNodeSpec, AssemblySpec
from common.step_scene import SelectorProfile, extract_selectors_from_scene, load_step_scene
from tests.cad_test_roots import IsolatedCadRoots


IDENTITY_TRANSFORM = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
TRANSLATED_TRANSFORM = (1.0, 0.0, 0.0, 4.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


class AssemblyExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="assembly-export-")
        self.cad_root = self._isolated_roots.cad_root

    def tearDown(self) -> None:
        shutil.rmtree(self._isolated_roots.root, ignore_errors=True)

    def _write_part(self) -> Path:
        step_path = self.cad_root / "STEP" / "leaf.step"
        step_path.parent.mkdir(parents=True, exist_ok=True)
        build123d.export_step(build123d.Box(1, 1, 1), step_path)
        return step_path

    def _write_colored_part(self) -> Path:
        step_path = self.cad_root / "STEP" / "leaf.step"
        step_path.parent.mkdir(parents=True, exist_ok=True)
        box = build123d.Box(1, 1, 1)
        box.color = build123d.Color(1, 0, 0, 1)
        build123d.export_step(box, step_path)
        return step_path

    def _assembly_spec(self, *instances: AssemblyInstanceSpec) -> AssemblySpec:
        assembly_path = self.cad_root / "STEP" / "assembly.py"
        assembly_path.parent.mkdir(parents=True, exist_ok=True)
        return AssemblySpec(
            assembly_path=assembly_path,
            instances=instances,
        )

    def _leaf_instance(
        self,
        *,
        instance_id: str = "leaf",
        transform: tuple[float, ...] = IDENTITY_TRANSFORM,
        use_source_colors: bool = True,
    ) -> AssemblyInstanceSpec:
        return AssemblyInstanceSpec(
            instance_id=instance_id,
            source_path=(self.cad_root / "STEP" / "leaf.step").resolve(),
            path="leaf.step",
            name=instance_id,
            transform=transform,
            use_source_colors=use_source_colors,
        )

    def test_imported_part_does_not_read_persistent_source_color(self) -> None:
        self._write_part()
        assembly_spec = self._assembly_spec(self._leaf_instance())

        assembly = build_assembly_compound(assembly_spec, label="assembly")

        self.assertIsNone(assembly.children[0].color)

    def test_instance_can_suppress_embedded_source_color(self) -> None:
        self._write_colored_part()
        assembly_spec = self._assembly_spec(self._leaf_instance(use_source_colors=False))

        assembly = build_assembly_compound(assembly_spec, label="assembly")

        self.assertIsNone(assembly.children[0].color)

    def test_repeated_part_instances_keep_distinct_occurrence_names(self) -> None:
        self._write_part()
        assembly_spec = self._assembly_spec(
            self._leaf_instance(instance_id="leaf_a"),
            self._leaf_instance(instance_id="leaf_b", transform=TRANSLATED_TRANSFORM),
        )
        assembly_path = assembly_spec.assembly_path
        output_path = assembly_path.with_suffix(".step")

        export_assembly_step(assembly_spec, output_path)
        bundle = extract_selectors_from_scene(
            load_step_scene(output_path),
            cad_ref="assemblies/assembly",
            profile=SelectorProfile.SUMMARY,
        )
        columns = bundle.manifest["tables"]["occurrenceColumns"]
        source_names = {
            dict(zip(columns, row))["sourceName"]
            for row in bundle.manifest["occurrences"]
        }

        self.assertIn("leaf_a", source_names)
        self.assertIn("leaf_b", source_names)

    def test_recursive_children_keep_subassembly_labels(self) -> None:
        self._write_part()
        assembly_spec = AssemblySpec(
            assembly_path=self.cad_root / "STEP" / "assembly.py",
            instances=(),
            children=(
                AssemblyNodeSpec(
                    instance_id="module",
                    name="module",
                    transform=IDENTITY_TRANSFORM,
                    children=(
                        AssemblyNodeSpec(
                            instance_id="leaf",
                            name="leaf",
                            source_path=(self.cad_root / "STEP" / "leaf.step").resolve(),
                            path="leaf.step",
                            transform=IDENTITY_TRANSFORM,
                        ),
                    ),
                ),
            ),
        )

        assembly = build_assembly_compound(assembly_spec, label="assembly")

        self.assertEqual("module", assembly.children[0].label)
        self.assertEqual("module__leaf", assembly.children[0].children[0].label)


if __name__ == "__main__":
    unittest.main()
