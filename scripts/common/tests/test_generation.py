import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from common import generation as cad_generation
from common import render as cad_render
from common import catalog as cad_catalog
from common.catalog import StepImportOptions
from common.step_scene import SelectorBundle
from tests.cad_test_roots import IsolatedCadRoots


IDENTITY_TRANSFORM = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


class CadGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="cad-generation-")
        tempdir = self._isolated_roots.temporary_cad_directory(prefix="tmp-cad-")
        self._tempdir = tempdir
        self.temp_root = Path(tempdir.name)
        self.relative_dir = self.temp_root.relative_to(cad_generation.CAD_ROOT).as_posix()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_root, ignore_errors=True)
        self._tempdir.cleanup()

    def _cad_ref(self, name: str) -> str:
        return f"{self.relative_dir}/{name}"

    def _write_step_at(
        self,
        directory: Path,
        name: str,
        *,
        suffix: str = ".step",
    ) -> Path:
        step_path = directory / f"{name}{suffix}"
        step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n", encoding="utf-8")
        return step_path

    def _step_options(
        self,
        *,
        export_stl: bool = False,
        stl_output: str | None = None,
        stl_tolerance: float | None = None,
        stl_angular_tolerance: float | None = None,
        export_3mf: bool = False,
        three_mf_output: str | None = None,
        three_mf_tolerance: float | None = None,
        three_mf_angular_tolerance: float | None = None,
        glb_tolerance: float | None = None,
        glb_angular_tolerance: float | None = None,
        color: tuple[float, float, float, float] | None = None,
        skip_topology: bool = False,
    ) -> StepImportOptions:
        return StepImportOptions(
            export_stl=export_stl,
            stl_output=stl_output,
            stl_tolerance=stl_tolerance,
            stl_angular_tolerance=stl_angular_tolerance,
            export_3mf=export_3mf,
            three_mf_output=three_mf_output,
            three_mf_tolerance=three_mf_tolerance,
            three_mf_angular_tolerance=three_mf_angular_tolerance,
            glb_tolerance=glb_tolerance,
            glb_angular_tolerance=glb_angular_tolerance,
            color=color,
            skip_topology=skip_topology,
        )

    def _write_step(
        self,
        name: str,
        *,
        suffix: str = ".step",
    ) -> Path:
        return self._write_step_at(self.temp_root, name, suffix=suffix)

    def test_catalog_discovery_ignores_urdf_only_generators(self) -> None:
        self._write_step("sample")
        (self._isolated_roots.cad_root / "sample_urdf.py").write_text(
            "def gen_urdf():\n"
            "    return {'xml': '<robot name=\"sample\" />', 'urdf_output': 'sample.urdf'}\n",
            encoding="utf-8",
        )

        sources = cad_catalog.iter_cad_sources()

        self.assertIn(self._cad_ref("sample"), {source.cad_ref for source in sources})
        self.assertNotIn("sample_urdf", {source.cad_ref for source in sources})

    def _generator_script(
        self,
        name: str,
        *,
        with_dxf: bool = False,
        with_urdf: bool = False,
        dxf_before_step: bool = False,
        step_output: str | None = None,
        export_stl: bool | None = None,
        stl_output: str | None = None,
        export_3mf: bool | None = None,
        three_mf_output: str | None = None,
        dxf_output: str | None = None,
        urdf_output: str | None = None,
        urdf_explorer_metadata: str | None = None,
        stl_tolerance: float | None = None,
        stl_angular_tolerance: float | None = None,
        three_mf_tolerance: float | None = None,
        three_mf_angular_tolerance: float | None = None,
        glb_tolerance: float | None = None,
        glb_angular_tolerance: float | None = None,
        skip_topology: bool | None = None,
    ) -> Path:
        fields: list[str] = ["'shape': _shape()"]
        fields.append(f"'step_output': {(step_output or f'{name}.step')!r}")
        if export_stl and stl_output is None:
            stl_output = f"{name}.stl"
        if export_stl is not None:
            fields.append(f"'export_stl': {export_stl!r}")
        if stl_output is not None:
            fields.append(f"'stl_output': {stl_output!r}")
        if export_3mf and three_mf_output is None:
            three_mf_output = f"{name}.3mf"
        if export_3mf is not None:
            fields.append(f"'export_3mf': {export_3mf!r}")
        if three_mf_output is not None:
            fields.append(f"'3mf_output': {three_mf_output!r}")
        if stl_tolerance is not None:
            fields.append(f"'stl_tolerance': {stl_tolerance!r}")
        if stl_angular_tolerance is not None:
            fields.append(f"'stl_angular_tolerance': {stl_angular_tolerance!r}")
        if three_mf_tolerance is not None:
            fields.append(f"'3mf_tolerance': {three_mf_tolerance!r}")
        if three_mf_angular_tolerance is not None:
            fields.append(f"'3mf_angular_tolerance': {three_mf_angular_tolerance!r}")
        if glb_tolerance is not None:
            fields.append(f"'glb_tolerance': {glb_tolerance!r}")
        if glb_angular_tolerance is not None:
            fields.append(f"'glb_angular_tolerance': {glb_angular_tolerance!r}")
        if skip_topology is not None:
            fields.append(f"'skip_topology': {skip_topology!r}")
        if with_dxf and dxf_output is None:
            dxf_output = f"{name}.dxf"
        if with_urdf and urdf_output is None:
            urdf_output = f"{name}.urdf"

        prologue = [
            "from pathlib import Path",
            f'DISPLAY_NAME = "{name}"',
            "CALLS = Path(__file__).with_suffix('.calls')",
            "def _output_path(suffix, output):",
            "    path = Path(__file__).parent / output if output else Path(__file__).with_suffix(suffix)",
            "    path.parent.mkdir(parents=True, exist_ok=True)",
            "    return path",
            "def _record(name):",
            "    with CALLS.open('a', encoding='utf-8') as handle:",
            "        handle.write(name + '\\n')",
            "class _FakeDxf:",
            "    def saveas(self, output_path):",
            "        Path(output_path).write_text('0\\nEOF\\n', encoding='utf-8')",
            "def _shape():",
            "    import build123d",
            "    return build123d.Box(1, 1, 1)",
            "",
        ]
        step_block = [
            "def gen_step():",
            "    _record('gen_step')",
            "    return {",
            *[f"        {field}," for field in fields],
            "    }",
            "",
        ]
        dxf_block = [
            "def gen_dxf():",
            "    _record('gen_dxf')",
            "    return {",
            "        'document': _FakeDxf(),",
            f"        'dxf_output': {dxf_output!r},",
            "    }",
            "",
        ]
        urdf_block = [
            "def gen_urdf():",
            "    _record('gen_urdf')",
            "    return {",
            "        'xml': '<robot name=\"part\"><link name=\"base\" /></robot>',",
            f"        'urdf_output': {urdf_output!r},",
            "    }",
            "",
        ]
        if urdf_explorer_metadata is not None:
            urdf_block.insert(-2, f"        'explorer_metadata': {urdf_explorer_metadata},")

        blocks = [prologue]
        if with_dxf and dxf_before_step:
            blocks.append(dxf_block)
        blocks.append(step_block)
        if with_dxf and not dxf_before_step:
            blocks.append(dxf_block)
        if with_urdf:
            blocks.append(urdf_block)

        script_path = self.temp_root / f"{name}.py"
        script_path.write_text("\n".join(line for block in blocks for line in block), encoding="utf-8")
        return script_path

    def _write_assembly_generator(
        self,
        name: str,
        *,
        instances: list[dict[str, object]],
        with_dxf: bool = False,
        with_urdf: bool = False,
        step_output: str | None = None,
        export_stl: bool | None = None,
        stl_output: str | None = None,
        export_3mf: bool | None = None,
        three_mf_output: str | None = None,
        dxf_output: str | None = None,
        urdf_output: str | None = None,
        stl_tolerance: float | None = None,
        stl_angular_tolerance: float | None = None,
        three_mf_tolerance: float | None = None,
        three_mf_angular_tolerance: float | None = None,
        glb_tolerance: float | None = None,
        glb_angular_tolerance: float | None = None,
        skip_topology: bool | None = None,
    ) -> Path:
        fields: list[str] = [f"'instances': {instances!r}"]
        fields.append(f"'step_output': {(step_output or f'{name}.step')!r}")
        if export_stl and stl_output is None:
            stl_output = f"{name}.stl"
        if export_stl is not None:
            fields.append(f"'export_stl': {export_stl!r}")
        if stl_output is not None:
            fields.append(f"'stl_output': {stl_output!r}")
        if export_3mf and three_mf_output is None:
            three_mf_output = f"{name}.3mf"
        if export_3mf is not None:
            fields.append(f"'export_3mf': {export_3mf!r}")
        if three_mf_output is not None:
            fields.append(f"'3mf_output': {three_mf_output!r}")
        if stl_tolerance is not None:
            fields.append(f"'stl_tolerance': {stl_tolerance!r}")
        if stl_angular_tolerance is not None:
            fields.append(f"'stl_angular_tolerance': {stl_angular_tolerance!r}")
        if three_mf_tolerance is not None:
            fields.append(f"'3mf_tolerance': {three_mf_tolerance!r}")
        if three_mf_angular_tolerance is not None:
            fields.append(f"'3mf_angular_tolerance': {three_mf_angular_tolerance!r}")
        if glb_tolerance is not None:
            fields.append(f"'glb_tolerance': {glb_tolerance!r}")
        if glb_angular_tolerance is not None:
            fields.append(f"'glb_angular_tolerance': {glb_angular_tolerance!r}")
        if skip_topology is not None:
            fields.append(f"'skip_topology': {skip_topology!r}")
        if with_dxf and dxf_output is None:
            dxf_output = f"{name}.dxf"
        if with_urdf and urdf_output is None:
            urdf_output = f"{name}.urdf"

        lines = [
            "from pathlib import Path",
            "CALLS = Path(__file__).with_suffix('.calls')",
            "def _output_path(suffix, output):",
            "    path = Path(__file__).parent / output if output else Path(__file__).with_suffix(suffix)",
            "    path.parent.mkdir(parents=True, exist_ok=True)",
            "    return path",
            "def _record(name):",
            "    with CALLS.open('a', encoding='utf-8') as handle:",
            "        handle.write(name + '\\n')",
            "class _FakeDxf:",
            "    def saveas(self, output_path):",
            "        Path(output_path).write_text('0\\nEOF\\n', encoding='utf-8')",
            "",
            "def gen_step():",
            "    _record('gen_step')",
            "    return {",
            *[f"        {field}," for field in fields],
            "    }",
            "",
        ]
        if with_dxf:
            lines.extend(
                [
                    "def gen_dxf():",
                    "    _record('gen_dxf')",
                    "    return {",
                    "        'document': _FakeDxf(),",
                    f"        'dxf_output': {dxf_output!r},",
                    "    }",
                    "",
                ]
            )
        if with_urdf:
            lines.extend(
                [
                    "def gen_urdf():",
                    "    _record('gen_urdf')",
                    "    return {",
                    "        'xml': '<robot name=\"sample\"><link name=\"base\" /></robot>',",
                    f"        'urdf_output': {urdf_output!r},",
                    "    }",
                    "",
                ]
            )
        assembly_path = self.temp_root / f"{name}.py"
        assembly_path.write_text("\n".join(lines), encoding="utf-8")
        return assembly_path

    def test_generated_part_discovery_includes_missing_step_output(self) -> None:
        script_path = self._generator_script("flat")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("flat")]

        self.assertEqual(1, len(specs))
        self.assertEqual("part", specs[0].kind)
        self.assertEqual(script_path, specs[0].source_path)
        self.assertFalse(specs[0].step_path.exists())

    def test_generated_part_discovery_ignores_virtualenv_python(self) -> None:
        self._generator_script("flat")
        dependency_dir = self.temp_root / ".venv" / "lib" / "python3.13" / "site-packages"
        dependency_dir.mkdir(parents=True)
        (dependency_dir / "dependency.py").write_bytes(b"\xe9")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("flat")]

        self.assertEqual(1, len(specs))

    def test_generated_part_discovery_ignores_non_generator_decode_failures(self) -> None:
        self._generator_script("flat")
        (self.temp_root / "notes.py").write_bytes(b"\xe9")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("flat")]

        self.assertEqual(1, len(specs))

    def test_generated_step_output_is_not_discovered_as_imported_step(self) -> None:
        self._generator_script("flat")
        (self.temp_root / "flat.step").write_text("ISO-10303-21; END-ISO-10303-21;\n", encoding="utf-8")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("flat")]

        self.assertEqual(1, len(specs))
        self.assertEqual("generated", specs[0].source)

    def test_generated_source_requires_step_output(self) -> None:
        (self.temp_root / "legacy.py").write_text(
            "\n".join(
                [
                    "def gen_step():",
                    "    return {'shape': object()}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "step_output is required"):
            cad_generation.list_entry_specs()

    def test_generated_part_uses_configured_output_paths(self) -> None:
        script_path = self._generator_script(
            "flat",
            with_dxf=True,
            step_output="custom/renamed.step",
            export_stl=True,
            stl_output="../meshes/renamed.stl",
            export_3mf=True,
            three_mf_output="../meshes/renamed.3mf",
            dxf_output="../drawings/renamed.dxf",
        )

        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.source_path == script_path)

        self.assertEqual(f"{self.relative_dir}/custom/renamed", spec.cad_ref)
        self.assertEqual(self.temp_root / "custom" / "renamed.step", spec.step_path)
        self.assertEqual(cad_generation.CAD_ROOT / "meshes" / "renamed.stl", spec.stl_path)
        self.assertEqual(cad_generation.CAD_ROOT / "meshes" / "renamed.3mf", spec.three_mf_path)
        self.assertEqual(cad_generation.CAD_ROOT / "drawings" / "renamed.dxf", spec.dxf_path)

    def test_generated_source_rejects_stl_output_without_export_stl(self) -> None:
        self._generator_script("flat", stl_output="flat.stl")

        with self.assertRaisesRegex(ValueError, "stl_output requires export_stl = True"):
            cad_generation.list_entry_specs()

    def test_generated_source_rejects_3mf_output_without_export_3mf(self) -> None:
        self._generator_script("flat", three_mf_output="flat.3mf")

        with self.assertRaisesRegex(ValueError, "3mf_output requires export_3mf = True"):
            cad_generation.list_entry_specs()

    def test_generated_source_allows_file_relative_parent_outputs(self) -> None:
        self._generator_script("flat", step_output="../../../flat.step")

        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.source_path == self.temp_root / "flat.py")

        self.assertEqual((self.temp_root / "../../../flat.step").resolve(), spec.step_path)

    def test_generated_source_rejects_invalid_output_suffix(self) -> None:
        self._generator_script("flat", step_output="flat.stp")

        with self.assertRaisesRegex(ValueError, "step_output must end in .step"):
            cad_generation.list_entry_specs()

    def test_generated_sidecars_require_configured_output_paths(self) -> None:
        (self.temp_root / "flat.py").write_text(
            "\n".join(
                [
                    "def gen_step():",
                    "    return {'shape': object(), 'step_output': 'flat.step'}",
                    "",
                    "def gen_dxf():",
                    "    return {'document': object()}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "dxf_output is required"):
            cad_generation.list_entry_specs()

    def test_duplicate_generated_output_paths_are_rejected(self) -> None:
        self._generator_script("left", export_stl=True, stl_output="shared.stl")
        self._generator_script("right", export_stl=True, stl_output="shared.stl")

        with self.assertRaisesRegex(ValueError, "Duplicate CAD generated output"):
            cad_generation.list_entry_specs()

    def test_duplicate_generated_3mf_output_paths_are_rejected(self) -> None:
        self._generator_script("left", export_3mf=True, three_mf_output="shared.3mf")
        self._generator_script("right", export_3mf=True, three_mf_output="shared.3mf")

        with self.assertRaisesRegex(ValueError, "Duplicate CAD generated output"):
            cad_generation.list_entry_specs()

    def test_direct_step_is_discovered_as_imported_part(self) -> None:
        self._write_step("loose")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("loose")]

        self.assertEqual(1, len(specs))
        self.assertEqual("part", specs[0].kind)
        self.assertEqual(self.temp_root / "loose.step", specs[0].step_path)

    def test_list_entry_specs_can_use_custom_root(self) -> None:
        scoped_root = self.temp_root / "scoped"
        scoped_root.mkdir()
        self._write_step_at(scoped_root, "only")
        self._write_step("outside")

        specs = cad_generation.list_entry_specs(scoped_root)

        self.assertEqual([f"{self.relative_dir}/scoped/only"], [spec.cad_ref for spec in specs])

    def test_selection_requires_explicit_targets(self) -> None:
        scoped_root = self.temp_root / "scoped"
        scoped_root.mkdir()
        self._write_step_at(scoped_root, "leaf")
        self._write_assembly_generator(
            "dependent-assembly",
            instances=[
                {
                    "path": "scoped/leaf.step",
                    "name": "leaf",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
        )
        all_specs = [
            spec
            for spec in cad_generation.list_entry_specs()
            if spec.cad_ref.startswith(f"{self.relative_dir}/")
        ]

        with self.assertRaisesRegex(ValueError, "At least one CAD target is required"):
            cad_generation.selected_entry_specs(all_specs, [])

    def test_entry_selection_is_exact_and_ordered(self) -> None:
        self._write_step("first")
        self._write_step("second")
        specs = [
            spec
            for spec in cad_generation.list_entry_specs()
            if spec.cad_ref.startswith(f"{self.relative_dir}/")
        ]

        selected = cad_generation.selected_entry_specs(
            specs,
            [self._cad_ref("second"), self._cad_ref("first"), self._cad_ref("second")],
        )

        self.assertEqual(
            [self._cad_ref("second"), self._cad_ref("first"), self._cad_ref("second")],
            [spec.cad_ref for spec in selected],
        )

    def test_step_part_generation_regenerates_selected_entries_in_supplied_order(self) -> None:
        first_path = self._write_step("first")
        second_path = self._write_step("second")
        calls: list[str] = []

        def fake_generate(spec, *, entries_by_step_path):
            self.assertIn(spec.step_path.resolve(), entries_by_step_path)
            calls.append(spec.cad_ref)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets([str(second_path), str(first_path)])

        self.assertEqual([self._cad_ref("second"), self._cad_ref("first")], calls)

    def test_entry_selection_does_not_execute_unrelated_assembly_generators(self) -> None:
        selected_path = self._write_step("selected")
        assembly_path = self.temp_root / "unrelated.py"
        assembly_path.write_text(
            "\n".join(
                [
                    "def gen_step():",
                    "    raise RuntimeError('unrelated assembly should not run')",
                    "    return {'instances': [], 'step_output': 'unrelated.step'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        calls: list[str] = []

        def fake_generate(spec, *, entries_by_step_path):
            self.assertNotIn(assembly_path.with_suffix(".step").resolve(), entries_by_step_path)
            calls.append(spec.cad_ref)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets([str(selected_path)])

        self.assertEqual([self._cad_ref("selected")], calls)

    def test_step_part_generation_rejects_assembly_target(self) -> None:
        self._write_step("imported-part")
        assembly_path = self._write_assembly_generator(
            "robot",
            instances=[
                {
                    "path": "imported-part.step",
                    "name": "leaf",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "expected a part target"):
            cad_generation.generate_step_part_targets([str(assembly_path)])

    def test_step_assembly_generation_rejects_generated_part_target(self) -> None:
        script_path = self._generator_script("part")

        with self.assertRaisesRegex(ValueError, "expected an assembly target"):
            cad_generation.generate_step_assembly_targets([str(script_path)])

    def test_dxf_generation_rejects_source_without_dxf(self) -> None:
        script_path = self._generator_script("part")

        with self.assertRaisesRegex(ValueError, "does not define gen_dxf\\(\\) envelope"):
            cad_generation.generate_dxf_targets([str(script_path)])

    def test_urdf_generation_rejects_source_without_urdf(self) -> None:
        script_path = self._generator_script("part")

        with self.assertRaisesRegex(ValueError, "does not define gen_urdf\\(\\) envelope"):
            cad_generation.generate_urdf_targets([str(script_path)])

    def test_step_generator_does_not_run_sidecars(self) -> None:
        script_path = self._generator_script("flat", with_dxf=True, with_urdf=True, dxf_before_step=True)
        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("flat"))

        cad_generation.run_script_generator(spec, "gen_step")

        self.assertEqual("gen_step\n", script_path.with_suffix(".calls").read_text(encoding="utf-8"))
        self.assertFalse(script_path.with_suffix(".dxf").exists())
        self.assertTrue(script_path.with_suffix(".step").exists())
        self.assertFalse(script_path.with_suffix(".urdf").exists())

    def test_gen_urdf_does_not_run_step_or_dxf_sidecars(self) -> None:
        self._write_step("imported-part")
        assembly_path = self._write_assembly_generator(
            "robot",
            instances=[
                {
                    "path": "imported-part.step",
                    "name": "leaf",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
            with_dxf=True,
            with_urdf=True,
        )
        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("robot"))

        cad_generation.run_script_generator(spec, "gen_urdf")

        self.assertEqual("gen_urdf\n", assembly_path.with_suffix(".calls").read_text(encoding="utf-8"))
        self.assertFalse(assembly_path.with_suffix(".dxf").exists())
        self.assertFalse(assembly_path.with_suffix(".step").exists())
        self.assertTrue(assembly_path.with_suffix(".urdf").exists())

    def test_gen_urdf_writes_explorer_metadata_sidecar(self) -> None:
        script_path = self._generator_script(
            "robot",
            with_urdf=True,
            urdf_explorer_metadata=(
                "{'schemaVersion': 1, 'kind': 'texttocad-urdf-explorer', "
                "'jointDefaultsByName': {'joint_1': 90}, 'poses': []}"
            ),
        )
        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("robot"))

        cad_generation.run_script_generator(spec, "gen_urdf")

        self.assertEqual(
            {
                "schemaVersion": 1,
                "kind": "texttocad-urdf-explorer",
                "jointDefaultsByName": {"joint_1": 90},
                "poses": [],
            },
            json.loads((script_path.parent / ".robot.urdf" / "explorer.json").read_text(encoding="utf-8")),
        )

    def test_sidecars_are_not_separate_generation_specs(self) -> None:
        self._generator_script("flat", with_dxf=True)
        self._write_step("imported-part")
        self._write_assembly_generator(
            "robot",
            instances=[
                {
                    "path": "imported-part.step",
                    "name": "leaf",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
            with_urdf=True,
        )

        cad_refs = {
            spec.cad_ref
            for spec in cad_generation.list_entry_specs()
            if spec.cad_ref.startswith(f"{self.relative_dir}/")
        }

        self.assertIn(self._cad_ref("flat"), cad_refs)
        self.assertIn(self._cad_ref("robot"), cad_refs)
        self.assertNotIn(self._cad_ref("flat") + ".dxf", cad_refs)
        self.assertNotIn(self._cad_ref("robot") + ".urdf", cad_refs)

    def test_step_toml_target_is_not_supported(self) -> None:
        (self.temp_root / "broken.step.toml").write_text('kind = "part"\n', encoding="utf-8")

        with self.assertRaisesRegex(FileNotFoundError, "Python generator or STEP/STP file path"):
            cad_generation.generate_step_part_targets([str(self.temp_root / "broken.step.toml")])

    def test_direct_step_generation_reads_configured_stl_output(self) -> None:
        step_path = self._write_step("source")
        calls: list[Path | None] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec.stl_path)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(
                    export_stl=True,
                    stl_output="../meshes/source.stl",
                ),
            )

        self.assertEqual([cad_generation.CAD_ROOT / "meshes" / "source.stl"], calls)

    def test_direct_step_generation_reads_configured_3mf_output(self) -> None:
        step_path = self._write_step("source")
        calls: list[Path | None] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec.three_mf_path)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(
                    export_3mf=True,
                    three_mf_output="../meshes/source.3mf",
                ),
            )

        self.assertEqual([cad_generation.CAD_ROOT / "meshes" / "source.3mf"], calls)

    def test_direct_step_rejects_stl_output_without_export_stl(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "stl_output requires export_stl = true"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(stl_output="source.stl"),
            )

    def test_direct_step_rejects_3mf_output_without_export_3mf(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "3mf_output requires export_3mf = true"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(three_mf_output="source.3mf"),
            )

    def test_direct_step_requires_stl_output_when_export_stl_is_enabled(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "stl_output is required when export_stl = true"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(export_stl=True),
            )

    def test_direct_step_requires_3mf_output_when_export_3mf_is_enabled(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "3mf_output is required when export_3mf = true"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(export_3mf=True),
            )

    def test_direct_step_rejects_invalid_stl_output_suffix(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "stl_output must end in .stl"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(export_stl=True, stl_output="source.txt"),
            )

    def test_direct_step_rejects_invalid_3mf_output_suffix(self) -> None:
        step_path = self._write_step("source")

        with self.assertRaisesRegex(ValueError, "3mf_output must end in .3mf"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(export_3mf=True, three_mf_output="source.txt"),
            )

    def test_direct_step_allows_file_relative_parent_stl_output(self) -> None:
        step_path = self._write_step("source")
        calls: list[Path | None] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec.stl_path)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(
                    export_stl=True,
                    stl_output="../../../../source.stl",
                ),
            )

        self.assertEqual([(self.temp_root / "../../../../source.stl").resolve()], calls)

    def test_direct_step_reuses_mesh_numeric_validation(self) -> None:
        step_path = self._write_step("broken")

        with self.assertRaisesRegex(ValueError, "3mf_tolerance must be greater than 0"):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(three_mf_tolerance=-0.1),
            )

    def test_step_metadata_flags_are_rejected_for_python_targets(self) -> None:
        script_path = self._generator_script("generated")

        with self.assertRaisesRegex(ValueError, "metadata flags can only be used"):
            cad_generation.generate_step_part_targets(
                [str(script_path)],
                step_options=self._step_options(glb_tolerance=0.2),
            )

    def test_step_metadata_flags_are_rejected_for_mixed_targets(self) -> None:
        step_path = self._write_step("imported")
        script_path = self._generator_script("generated")

        with self.assertRaisesRegex(ValueError, "metadata flags can only be used"):
            cad_generation.generate_step_part_targets(
                [str(step_path), str(script_path)],
                step_options=self._step_options(glb_tolerance=0.2),
            )

    def test_generator_discovery_rejects_non_envelope_gen_step(self) -> None:
        script_path = self.temp_root / "broken.py"
        script_path.write_text(
            "\n".join(
                [
                    'DISPLAY_NAME = "broken"',
                    "def gen_step():",
                    "    return None",
                ]
            )
            + "\n"
        )

        with self.assertRaisesRegex(ValueError, "must return a generator envelope dict"):
            cad_generation.list_entry_specs()

    def test_generator_discovery_ignores_sidecar_only_scripts(self) -> None:
        script_path = self.temp_root / "flat.py"
        script_path.write_text(
            "\n".join(
                [
                    "def gen_dxf():",
                    "    return {'document': object(), 'dxf_output': 'flat.dxf'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        specs = cad_generation.list_entry_specs()

        self.assertFalse(any(spec.source_path == script_path for spec in specs))

    def test_generated_part_reads_mesh_settings_from_envelope_metadata(self) -> None:
        self._generator_script(
            "meshy",
            export_stl=True,
            export_3mf=True,
            stl_tolerance=0.6,
            stl_angular_tolerance=0.35,
            three_mf_tolerance=0.7,
            three_mf_angular_tolerance=0.4,
            glb_tolerance=0.2,
            glb_angular_tolerance=0.25,
        )

        specs = {
            spec.cad_ref: spec
            for spec in cad_generation.list_entry_specs()
            if spec.cad_ref.startswith(f"{self.relative_dir}/")
        }

        self.assertTrue(specs[self._cad_ref("meshy")].export_stl)
        self.assertTrue(specs[self._cad_ref("meshy")].export_3mf)
        self.assertEqual(0.6, specs[self._cad_ref("meshy")].stl_tolerance)
        self.assertEqual(0.35, specs[self._cad_ref("meshy")].stl_angular_tolerance)
        self.assertEqual(0.7, specs[self._cad_ref("meshy")].three_mf_tolerance)
        self.assertEqual(0.4, specs[self._cad_ref("meshy")].three_mf_angular_tolerance)
        self.assertEqual(0.2, specs[self._cad_ref("meshy")].glb_tolerance)
        self.assertEqual(0.25, specs[self._cad_ref("meshy")].glb_angular_tolerance)

    def test_generated_part_reads_skip_topology_from_envelope_metadata(self) -> None:
        self._generator_script("summary-only", skip_topology=True)

        spec = next(spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("summary-only"))

        self.assertTrue(spec.skip_topology)

    def test_generated_assembly_rejects_skip_topology_envelope_metadata(self) -> None:
        self._write_assembly_generator("assembly", instances=[], skip_topology=True)

        with self.assertRaisesRegex(ValueError, "skip_topology is not supported for assembly entries"):
            cad_generation.list_entry_specs()

    def test_generated_assembly_paths_include_step_glb_topology_and_sidecars(self) -> None:
        self._write_step("imported-part")
        self._write_assembly_generator(
            "assembly",
            instances=[
                {
                    "path": "imported-part.step",
                    "name": "leaf",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
            with_dxf=True,
            with_urdf=True,
            export_stl=True,
            export_3mf=True,
            stl_tolerance=0.8,
            stl_angular_tolerance=0.45,
            three_mf_tolerance=0.85,
            three_mf_angular_tolerance=0.5,
            glb_tolerance=0.3,
            glb_angular_tolerance=0.2,
        )

        spec = next(
            spec
            for spec in cad_generation.list_entry_specs()
            if spec.cad_ref == self._cad_ref("assembly")
        )

        self.assertEqual("assembly", spec.kind)
        self.assertEqual(self.temp_root / "assembly.step", spec.step_path)
        self.assertEqual(self.temp_root / "assembly.dxf", spec.dxf_path)
        self.assertEqual(self.temp_root / "assembly.urdf", spec.urdf_path)
        self.assertTrue(spec.export_stl)
        self.assertTrue(spec.export_3mf)
        self.assertEqual(0.8, spec.stl_tolerance)
        self.assertEqual(0.45, spec.stl_angular_tolerance)
        self.assertEqual(0.85, spec.three_mf_tolerance)
        self.assertEqual(0.5, spec.three_mf_angular_tolerance)
        self.assertEqual(0.3, spec.glb_tolerance)
        self.assertEqual(0.2, spec.glb_angular_tolerance)

    def test_imported_step_defaults_to_part(self) -> None:
        self._write_step("imported")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("imported")]

        self.assertEqual(1, len(specs))
        self.assertEqual("part", specs[0].kind)

    def test_imported_stp_defaults_to_part(self) -> None:
        self._write_step("imported-stp", suffix=".stp")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("imported-stp")]

        self.assertEqual(1, len(specs))
        self.assertEqual("part", specs[0].kind)

    def test_imported_step_uses_default_mesh_settings(self) -> None:
        self._write_step("imported-mesh")

        specs = [spec for spec in cad_generation.list_entry_specs() if spec.cad_ref == self._cad_ref("imported-mesh")]

        self.assertEqual(1, len(specs))
        self.assertFalse(specs[0].export_stl)
        self.assertFalse(specs[0].export_3mf)
        self.assertEqual(cad_generation.DEFAULT_STL_TOLERANCE, specs[0].stl_tolerance)
        self.assertEqual(cad_generation.DEFAULT_STL_ANGULAR_TOLERANCE, specs[0].stl_angular_tolerance)
        self.assertEqual(cad_generation.DEFAULT_3MF_TOLERANCE, specs[0].three_mf_tolerance)
        self.assertEqual(cad_generation.DEFAULT_3MF_ANGULAR_TOLERANCE, specs[0].three_mf_angular_tolerance)
        self.assertEqual(cad_generation.DEFAULT_GLB_TOLERANCE, specs[0].glb_tolerance)
        self.assertEqual(cad_generation.DEFAULT_GLB_ANGULAR_TOLERANCE, specs[0].glb_angular_tolerance)

    def test_imported_step_reads_mesh_settings_from_cli_options(self) -> None:
        step_path = self._write_step("imported-heavy")
        calls: list[cad_generation.EntrySpec] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(
                    export_stl=True,
                    stl_output="imported-heavy.stl",
                    stl_tolerance=1.25,
                    stl_angular_tolerance=0.7,
                    export_3mf=True,
                    three_mf_output="imported-heavy.3mf",
                    three_mf_tolerance=1.5,
                    three_mf_angular_tolerance=0.8,
                    glb_tolerance=0.9,
                    glb_angular_tolerance=0.45,
                ),
            )

        self.assertEqual(1, len(calls))
        self.assertTrue(calls[0].export_stl)
        self.assertTrue(calls[0].export_3mf)
        self.assertEqual(1.25, calls[0].stl_tolerance)
        self.assertEqual(0.7, calls[0].stl_angular_tolerance)
        self.assertEqual(1.5, calls[0].three_mf_tolerance)
        self.assertEqual(0.8, calls[0].three_mf_angular_tolerance)
        self.assertEqual(0.9, calls[0].glb_tolerance)
        self.assertEqual(0.45, calls[0].glb_angular_tolerance)

    def test_imported_step_reads_skip_topology_from_cli_options(self) -> None:
        step_path = self._write_step("opaque-import")
        calls: list[cad_generation.EntrySpec] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(skip_topology=True),
            )

        self.assertTrue(calls[0].skip_topology)

    def test_imported_step_reads_color_from_cli_options(self) -> None:
        step_path = self._write_step("colored-import")
        calls: list[cad_generation.EntrySpec] = []

        def fake_generate(spec, *, entries_by_step_path):
            calls.append(spec)

        with mock.patch.object(cad_generation, "_generate_step_outputs", side_effect=fake_generate):
            cad_generation.generate_step_part_targets(
                [str(step_path)],
                step_options=self._step_options(color=(0.1, 0.2, 0.3, 1.0)),
            )

        self.assertEqual((0.1, 0.2, 0.3, 1.0), calls[0].color)

    def test_script_step_material_colors_accepts_tuple_rgba(self) -> None:
        script_path = self.temp_root / "colored_assembly.py"
        script_path.write_text(
            "\n".join(
                [
                    "URDF_MATERIALS = {'black_aluminum': (0.168627, 0.184314, 0.2, 1.0)}",
                    "URDF_STEP_MATERIALS = {'imports/sample_component.step': 'black_aluminum'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        spec = cad_generation.EntrySpec(
            source_ref=self._cad_ref("colored_assembly.py"),
            cad_ref=self._cad_ref("colored_assembly"),
            kind="assembly",
            source_path=script_path,
            display_name="colored_assembly",
            source="generated",
            script_path=script_path,
        )

        self.assertEqual(
            {"imports/sample_component.step": (0.168627, 0.184314, 0.2, 1.0)},
            cad_generation._script_step_material_colors(spec),
        )

    def test_imported_assembly_rejects_skip_topology(self) -> None:
        step_path = self._write_step("imported-assembly")

        with self.assertRaisesRegex(ValueError, "skip_topology is not supported for assembly entries"):
            cad_generation.generate_step_assembly_targets(
                [str(step_path)],
                step_options=self._step_options(skip_topology=True),
            )

    def test_generate_part_outputs_writes_selector_artifacts_beside_glb(self) -> None:
        step_path = self._write_step("selector-output")
        _, selected_specs = cad_generation._selected_specs_for_targets(
            [str(step_path)],
            step_options=self._step_options(glb_tolerance=0.3, glb_angular_tolerance=0.2),
        )
        spec = selected_specs[0]
        selector_manifest_path = cad_render.part_selector_manifest_path(step_path)
        self.addCleanup(selector_manifest_path.unlink, missing_ok=True)
        scene = object()

        def fake_export_glb(step_path_arg, *, linear_deflection, angular_deflection, color=None):
            self.assertEqual(spec.glb_tolerance, linear_deflection)
            self.assertEqual(spec.glb_angular_tolerance, angular_deflection)
            glb_path = cad_render.part_glb_path(step_path_arg)
            glb_path.parent.mkdir(parents=True, exist_ok=True)
            glb_path.write_bytes(b"glb")
            return glb_path

        def fake_extract(scene_arg, *, cad_ref, profile, options):
            self.assertIs(scene, scene_arg)
            self.assertEqual(spec.cad_ref, cad_ref)
            self.assertEqual(cad_generation.SelectorProfile.ARTIFACT, profile)
            self.assertLessEqual(options.linear_deflection, spec.glb_tolerance)
            self.assertLessEqual(options.angular_deflection, spec.glb_angular_tolerance)
            return SelectorBundle(manifest={"schemaVersion": 2, "cadPath": spec.cad_ref}, buffers={})

        with mock.patch.object(cad_generation, "load_step_scene", return_value=scene) as load_scene, mock.patch.object(
            cad_generation, "export_part_stl_from_scene"
        ) as export_stl, mock.patch.object(
            cad_generation,
            "export_part_glb_from_step",
            side_effect=fake_export_glb,
        ), mock.patch.object(
            cad_generation,
            "mesh_step_scene",
        ), mock.patch.object(
            cad_generation,
            "extract_selectors_from_scene",
            side_effect=fake_extract,
        ):
            cad_generation._generate_part_outputs(spec, entries_by_step_path={spec.step_path.resolve(): spec})

        load_scene.assert_called_once_with(step_path)
        export_stl.assert_not_called()
        self.assertTrue(cad_render.part_glb_path(step_path).exists())
        self.assertTrue(selector_manifest_path.exists())

    def test_generate_part_outputs_skips_topology_when_requested(self) -> None:
        step_path = self._write_step("summary-only")
        _, selected_specs = cad_generation._selected_specs_for_targets(
            [str(step_path)],
            step_options=self._step_options(
                export_stl=True,
                stl_output="summary-only.stl",
                skip_topology=True,
            ),
        )
        spec = selected_specs[0]
        selector_manifest_path = cad_render.part_selector_manifest_path(step_path)
        selector_binary_path = cad_render.part_selector_binary_path(step_path)
        selector_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        selector_manifest_path.write_text("stale", encoding="utf-8")
        selector_binary_path.write_bytes(b"stale")
        scene = object()

        def fake_export(step_path_arg, scene_arg, *, target_path=None):
            self.assertIs(scene, scene_arg)
            stl_path = target_path
            self.assertIsNotNone(stl_path)
            stl_path.parent.mkdir(parents=True, exist_ok=True)
            stl_path.write_text("solid ok\nendsolid ok\n")
            return stl_path

        def fake_export_glb(step_path_arg, *, linear_deflection, angular_deflection, color=None):
            glb_path = cad_render.part_glb_path(step_path_arg)
            glb_path.parent.mkdir(parents=True, exist_ok=True)
            glb_path.write_bytes(b"glb")
            return glb_path

        with mock.patch.object(cad_generation, "load_step_scene", return_value=scene), mock.patch.object(
            cad_generation,
            "export_part_stl_from_scene",
            side_effect=fake_export,
        ), mock.patch.object(
            cad_generation,
            "export_part_glb_from_step",
            side_effect=fake_export_glb,
        ), mock.patch.object(
            cad_generation,
            "mesh_step_scene",
        ), mock.patch.object(cad_generation, "extract_selectors_from_scene") as extract_selectors:
            cad_generation._generate_part_outputs(spec, entries_by_step_path={spec.step_path.resolve(): spec})

        extract_selectors.assert_not_called()
        self.assertIsNotNone(spec.stl_path)
        self.assertTrue(spec.stl_path.exists())
        self.assertTrue(cad_render.part_glb_path(step_path).exists())
        self.assertTrue(selector_manifest_path.exists())
        self.assertTrue(selector_binary_path.exists())

    def test_generate_part_outputs_writes_3mf_sidecar(self) -> None:
        step_path = self._write_step("printable")
        _, selected_specs = cad_generation._selected_specs_for_targets(
            [str(step_path)],
            step_options=self._step_options(
                export_3mf=True,
                three_mf_output="printable.3mf",
                three_mf_tolerance=0.4,
                three_mf_angular_tolerance=0.3,
                skip_topology=True,
            ),
        )
        spec = selected_specs[0]
        scene = object()

        def fake_export_3mf(step_path_arg, scene_arg, *, target_path=None, color=None):
            self.assertEqual(step_path, step_path_arg)
            self.assertIs(scene, scene_arg)
            self.assertEqual(spec.three_mf_path, target_path)
            self.assertIsNone(color)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(b"3mf")
            return target_path

        def fake_export_glb(step_path_arg, *, linear_deflection, angular_deflection, color=None):
            glb_path = cad_render.part_glb_path(step_path_arg)
            glb_path.parent.mkdir(parents=True, exist_ok=True)
            glb_path.write_bytes(b"glb")
            return glb_path

        with mock.patch.object(cad_generation, "load_step_scene", return_value=scene), mock.patch.object(
            cad_generation,
            "export_part_3mf_from_scene",
            side_effect=fake_export_3mf,
        ) as export_3mf, mock.patch.object(
            cad_generation,
            "export_part_glb_from_step",
            side_effect=fake_export_glb,
        ), mock.patch.object(
            cad_generation,
            "mesh_step_scene",
        ) as mesh_scene, mock.patch.object(cad_generation, "extract_selectors_from_scene"):
            cad_generation._generate_part_outputs(spec, entries_by_step_path={spec.step_path.resolve(): spec})

        export_3mf.assert_called_once()
        self.assertTrue(any(
            call.kwargs.get("linear_deflection") == 0.4 and call.kwargs.get("angular_deflection") == 0.3
            for call in mesh_scene.mock_calls
        ))
        self.assertIsNotNone(spec.three_mf_path)
        self.assertTrue(spec.three_mf_path.exists())

    def test_native_component_export_falls_back_to_empty_mesh(self) -> None:
        step_path = self._write_step("imported-assembly")
        _, selected_specs = cad_generation._selected_specs_for_targets(
            [str(step_path)],
            direct_step_kind="assembly",
        )
        spec = selected_specs[0]
        node = object()

        with mock.patch.object(cad_generation, "scene_leaf_occurrences", return_value=[node]), mock.patch.object(
            cad_generation,
            "occurrence_selector_id",
            return_value="o1.1",
        ), mock.patch.object(
            cad_generation,
            "scene_occurrence_prototype_shape",
            return_value=object(),
        ), mock.patch.object(
            cad_generation,
            "export_shape_glb",
            side_effect=RuntimeError("cannot mesh"),
        ), mock.patch.object(
            cad_generation,
            "write_empty_glb",
            side_effect=lambda path: path.parent.mkdir(parents=True, exist_ok=True) or path.write_bytes(b"glb") or path,
        ):
            paths = cad_generation._native_component_mesh_paths(spec, object())

        self.assertEqual(["o1.1"], list(paths))
        self.assertEqual(self.temp_root / ".imported-assembly.step" / "components" / "o1.1.glb", paths["o1.1"])
        self.assertEqual(b"glb", paths["o1.1"].read_bytes())


if __name__ == "__main__":
    unittest.main()
