import unittest
from unittest import mock

from gen_step_part import cli


class GenStepPartCliTests(unittest.TestCase):
    def test_requires_explicit_target(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main([])
        self.assertEqual(2, cm.exception.code)

    def test_rejects_root_option(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main(["--root", "workspace/samples"])
        self.assertEqual(2, cm.exception.code)

    def test_passes_targets_in_order(self) -> None:
        with mock.patch.object(cli, "generate_step_part_targets", return_value=0) as generate:
            self.assertEqual(0, cli.main(["parts/second.step", "parts/first.step", "--summary"]))

        generate.assert_called_once()
        self.assertEqual(["parts/second.step", "parts/first.step"], generate.call_args.args[0])
        self.assertTrue(generate.call_args.kwargs["summary"])
        self.assertFalse(generate.call_args.kwargs["step_options"].has_metadata)

    def test_passes_import_metadata_flags(self) -> None:
        with mock.patch.object(cli, "generate_step_part_targets", return_value=0) as generate:
            self.assertEqual(
                0,
                cli.main(
                    [
                        "imports/sample_part.step",
                        "--export-stl",
                        "--stl-output",
                        "../meshes/sample_part.stl",
                        "--stl-tolerance",
                        "0.6",
                        "--stl-angular-tolerance",
                        "0.35",
                        "--export-3mf",
                        "--3mf-output",
                        "../meshes/sample_part.3mf",
                        "--3mf-tolerance",
                        "0.7",
                        "--3mf-angular-tolerance",
                        "0.4",
                        "--glb-tolerance",
                        "0.2",
                        "--glb-angular-tolerance",
                        "0.25",
                        "--color",
                        "0.1,0.2,0.3,1.0",
                        "--skip-topology",
                    ]
                ),
            )

        generate.assert_called_once()
        self.assertEqual(["imports/sample_part.step"], generate.call_args.args[0])
        self.assertFalse(generate.call_args.kwargs["summary"])
        options = generate.call_args.kwargs["step_options"]
        self.assertTrue(options.export_stl)
        self.assertEqual("../meshes/sample_part.stl", options.stl_output)
        self.assertEqual(0.6, options.stl_tolerance)
        self.assertEqual(0.35, options.stl_angular_tolerance)
        self.assertTrue(options.export_3mf)
        self.assertEqual("../meshes/sample_part.3mf", options.three_mf_output)
        self.assertEqual(0.7, options.three_mf_tolerance)
        self.assertEqual(0.4, options.three_mf_angular_tolerance)
        self.assertEqual(0.2, options.glb_tolerance)
        self.assertEqual(0.25, options.glb_angular_tolerance)
        self.assertEqual((0.1, 0.2, 0.3, 1.0), options.color)
        self.assertTrue(options.skip_topology)

    def test_rejects_invalid_numeric_flag(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main(["imports/sample_part.step", "--glb-tolerance", "nan"])
        self.assertEqual(2, cm.exception.code)


if __name__ == "__main__":
    unittest.main()
