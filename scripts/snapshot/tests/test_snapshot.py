import shutil
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

import numpy as np
import trimesh

from snapshot import cli as snapshot_cli
from common.render import part_glb_path
from tests.cad_test_roots import IsolatedCadRoots


IDENTITY_TRANSFORM = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def _read_png_rgb(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("invalid PNG signature")
    cursor = 8
    width = 0
    height = 0
    idat = bytearray()
    while cursor < len(data):
        length = int.from_bytes(data[cursor : cursor + 4], "big")
        chunk_type = data[cursor + 4 : cursor + 8]
        chunk_data = data[cursor + 8 : cursor + 8 + length]
        cursor += 12 + length
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    rows = []
    stride = (width * 3) + 1
    for row_index in range(height):
        row = raw[row_index * stride : (row_index + 1) * stride]
        if row[0] != 0:
            raise AssertionError("unsupported PNG filter in test helper")
        rows.append(np.frombuffer(row[1:], dtype=np.uint8).reshape(width, 3))
    return np.stack(rows, axis=0)


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._isolated_roots = IsolatedCadRoots(self, prefix="snapshot-")
        tempdir = self._isolated_roots.temporary_cad_directory(prefix="tmp-snapshot-")
        self._tempdir = tempdir
        self.temp_root = Path(tempdir.name)
        self.relative_dir = self.temp_root.relative_to(snapshot_cli.CAD_ROOT).as_posix()
        self.render_paths: list[Path] = []

    def tearDown(self) -> None:
        for render_path in self.render_paths:
            render_path.unlink(missing_ok=True)
        shutil.rmtree(self.temp_root, ignore_errors=True)
        self._tempdir.cleanup()

    def _local_step_ref(self, name: str) -> str:
        return f"{name}.step"

    def _write_part(self, name: str) -> Path:
        step_path = self.temp_root / f"{name}.step"
        step_path.write_text("ISO-10303-21; END-ISO-10303-21;\n")
        glb_path = part_glb_path(step_path)
        self.render_paths.append(glb_path)
        return self._write_triangle_glb(glb_path)

    def _write_assembly_generator(self, name: str, *, instances: list[dict[str, object]]) -> Path:
        assembly_path = self.temp_root / f"{name}.py"
        assembly_path.write_text(
            "\n".join(
                [
                    "def gen_step():",
                    f"    return {{'instances': {instances!r}, 'step_output': {f'{name}.step'!r}}}",
                    "",
                ]
            )
        )
        return assembly_path

    def _write_triangle_stl(self, path: Path) -> Path:
        path.write_text(
            "\n".join(
                [
                    "solid triangle",
                    "  facet normal 0 0 1",
                    "    outer loop",
                    "      vertex 0 0 0",
                    "      vertex 20 0 0",
                    "      vertex 0 15 0",
                    "    endloop",
                    "  endfacet",
                    "  facet normal 0 0 1",
                    "    outer loop",
                    "      vertex 20 0 0",
                    "      vertex 20 15 0",
                    "      vertex 0 15 0",
                    "    endloop",
                    "  endfacet",
                    "endsolid triangle",
                    "",
                ]
            )
        )
        return path

    def _write_triangle_glb(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        mesh = trimesh.Trimesh(
            vertices=np.asarray(
                [
                    [0.0, 0.0, 0.0],
                    [0.02, 0.0, 0.0],
                    [0.0, 0.015, 0.0],
                    [0.02, 0.015, 0.0],
                ],
                dtype=float,
            ),
            faces=np.asarray([[0, 1, 2], [1, 3, 2]], dtype=np.int64),
            process=False,
        )
        mesh.export(path)
        return path

    def test_snapshot_renders_single_glb(self) -> None:
        glb_path = self._write_part("part")
        png_path = self.temp_root / "part.png"

        snapshot_cli.main(
            [
                str(glb_path),
                "--out",
                str(png_path),
                "--width",
                "240",
                "--height",
                "160",
                "--no-axes",
            ]
        )

        pixels = _read_png_rgb(png_path)
        self.assertLessEqual(pixels.shape[0], 160)
        self.assertLessEqual(pixels.shape[1], 240)
        self.assertTrue(pixels.shape[0] < 160 or pixels.shape[1] < 240)
        self.assertGreater(len(np.unique(pixels.reshape(-1, 3), axis=0)), 1)
        background = pixels[0, 0]
        non_background = np.any(pixels != background, axis=2)
        self.assertGreater(float(non_background.mean()), 0.18)

    def test_snapshot_renders_single_stl(self) -> None:
        stl_path = self._write_triangle_stl(self.temp_root / "mesh.stl")
        png_path = self.temp_root / "mesh.png"

        snapshot_cli.main(
            [
                str(stl_path),
                "--out",
                str(png_path),
                "--width",
                "240",
                "--height",
                "160",
                "--no-axes",
            ]
        )

        pixels = _read_png_rgb(png_path)
        self.assertLessEqual(pixels.shape[0], 160)
        self.assertLessEqual(pixels.shape[1], 240)
        self.assertGreater(len(np.unique(pixels.reshape(-1, 3), axis=0)), 1)

    def test_snapshot_renders_multiple_views_to_out_dir(self) -> None:
        glb_path = self._write_part("part")
        output_dir = self.temp_root / "views"

        snapshot_cli.main(
            [
                str(glb_path),
                "--views",
                "isometric,top,right",
                "--out-dir",
                str(output_dir),
                "--width",
                "240",
                "--height",
                "160",
                "--no-axes",
            ]
        )

        for view_name in ("isometric", "top", "right"):
            png_path = output_dir / f"part-{view_name}.png"
            pixels = _read_png_rgb(png_path)
            self.assertGreater(len(np.unique(pixels.reshape(-1, 3), axis=0)), 1)

    def test_snapshot_no_edges_skips_feature_edge_analysis(self) -> None:
        glb_path = self._write_part("part")
        png_path = self.temp_root / "part-no-edges.png"

        with mock.patch.object(snapshot_cli, "_feature_edges", side_effect=AssertionError("unexpected edge pass")):
            snapshot_cli.main(
                [
                    str(glb_path),
                    "--out",
                    str(png_path),
                    "--width",
                    "240",
                    "--height",
                    "160",
                    "--no-axes",
                    "--no-edges",
                ]
            )

        pixels = _read_png_rgb(png_path)
        self.assertGreater(len(np.unique(pixels.reshape(-1, 3), axis=0)), 1)

    def test_snapshot_renders_python_assembly_generator(self) -> None:
        part_path = self._write_part("part")
        assembly_path = self._write_assembly_generator(
            "assembly",
            instances=[
                {
                    "path": self._local_step_ref("part"),
                    "name": "left",
                    "transform": [1, 0, 0, -12, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                },
                {
                    "path": self._local_step_ref("part"),
                    "name": "right",
                    "transform": [1, 0, 0, 12, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                },
            ],
        )
        png_path = self.temp_root / "assembly.png"

        snapshot_cli.main(
            [
                str(assembly_path),
                "--out",
                str(png_path),
                "--width",
                "260",
                "--height",
                "180",
                "--no-axes",
            ]
        )

        self.assertTrue(part_path.exists())
        pixels = _read_png_rgb(png_path)
        self.assertLessEqual(pixels.shape[0], 180)
        self.assertLessEqual(pixels.shape[1], 260)
        self.assertGreater(len(np.unique(pixels.reshape(-1, 3), axis=0)), 1)

    def test_snapshot_rejects_invalid_python_assembly_schema(self) -> None:
        part_path = self._write_part("shared")
        root_assembly = self._write_assembly_generator(
            "broken",
            instances=[
                {
                    "path": self._local_step_ref("shared"),
                    "name": "bad name",
                    "transform": IDENTITY_TRANSFORM,
                }
            ],
        )

        self.assertTrue(part_path.exists())
        with self.assertRaisesRegex(ValueError, "letters, numbers"):
            snapshot_cli.load_mesh_instances(root_assembly)

    def test_snapshot_accepts_explicit_inputs_outside_cwd(self) -> None:
        tempdir = tempfile.TemporaryDirectory(prefix="tmp-snapshot-outside-")
        self.addCleanup(tempdir.cleanup)
        outside_glb = Path(tempdir.name) / "outside.glb"
        self._write_triangle_glb(outside_glb)

        instances = snapshot_cli.load_mesh_instances(outside_glb)

        self.assertEqual(1, len(instances))


if __name__ == "__main__":
    unittest.main()
