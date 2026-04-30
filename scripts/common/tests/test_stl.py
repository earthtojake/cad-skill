import shutil
import unittest
from pathlib import Path

from common import render as cad_render
from tests.cad_test_roots import IsolatedCadRoots


class CadgenRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="cad-render-")
        tempdir = self._isolated_roots.temporary_cad_directory(prefix="tmp-cad-render-")
        self._tempdir = tempdir
        self.temp_root = Path(tempdir.name)
        self.relative_dir = self.temp_root.relative_to(cad_render.CAD_ROOT).as_posix()
        self.cleanup_paths: set[Path] = set()

    def tearDown(self) -> None:
        for path in self.cleanup_paths:
            path.unlink(missing_ok=True)
        shutil.rmtree(self.temp_root, ignore_errors=True)
        self._tempdir.cleanup()

    def _write_step(self, name: str, *, extension: str = ".step") -> Path:
        step_path = self.temp_root / f"{name}{extension}"
        step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n")
        self.cleanup_paths.update(
            (
                cad_render.part_glb_path(step_path),
                cad_render.part_selector_manifest_path(step_path),
                cad_render.part_selector_binary_path(step_path),
            )
        )
        return step_path

    def test_direct_step_has_no_persistent_stl_path(self) -> None:
        step_path = self._write_step("part")

        with self.assertRaisesRegex(ValueError, "no configured STL output"):
            cad_render.part_stl_path(step_path)

    def test_explorer_paths_use_step_artifact_directory(self) -> None:
        step_path = self._write_step("part")

        glb_path = cad_render.part_glb_path(step_path)
        selector_manifest_path = cad_render.part_selector_manifest_path(step_path)
        selector_binary_path = cad_render.part_selector_binary_path(step_path)

        self.assertEqual(self.temp_root / ".part.step" / "model.glb", glb_path)
        self.assertEqual(self.temp_root / ".part.step" / "topology.json", selector_manifest_path)
        self.assertEqual(self.temp_root / ".part.step" / "topology.bin", selector_binary_path)

    def test_render_paths_preserve_stp_extension_in_artifact_directory(self) -> None:
        step_path = self._write_step("part-stp", extension=".stp")

        glb_path = cad_render.part_glb_path(step_path)
        selector_manifest_path = cad_render.part_selector_manifest_path(step_path)
        selector_binary_path = cad_render.part_selector_binary_path(step_path)

        self.assertEqual(self.temp_root / ".part-stp.stp" / "model.glb", glb_path)
        self.assertEqual(self.temp_root / ".part-stp.stp" / "topology.json", selector_manifest_path)
        self.assertEqual(self.temp_root / ".part-stp.stp" / "topology.bin", selector_binary_path)


if __name__ == "__main__":
    unittest.main()
