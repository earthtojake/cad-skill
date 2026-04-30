import unittest
from unittest import mock

from gen_step_assembly import cli


class GenStepAssemblyCliTests(unittest.TestCase):
    def test_requires_explicit_target(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main([])
        self.assertEqual(2, cm.exception.code)

    def test_rejects_root_option(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main(["--root", "workspace/samples"])
        self.assertEqual(2, cm.exception.code)

    def test_passes_targets_in_order(self) -> None:
        with mock.patch.object(cli, "generate_step_assembly_targets", return_value=0) as generate:
            self.assertEqual(0, cli.main(["assemblies/second.step", "assemblies/first.step", "--summary"]))

        generate.assert_called_once()
        self.assertEqual(["assemblies/second.step", "assemblies/first.step"], generate.call_args.args[0])
        self.assertTrue(generate.call_args.kwargs["summary"])
        self.assertFalse(generate.call_args.kwargs["step_options"].has_metadata)

    def test_passes_import_metadata_flags(self) -> None:
        with mock.patch.object(cli, "generate_step_assembly_targets", return_value=0) as generate:
            self.assertEqual(
                0,
                cli.main(
                    [
                        "imports/sample_assembly.step",
                        "--export-3mf",
                        "--3mf-output",
                        "../meshes/sample_assembly.3mf",
                        "--3mf-tolerance",
                        "1.2",
                        "--3mf-angular-tolerance",
                        "0.6",
                        "--glb-tolerance",
                        "1.0",
                        "--glb-angular-tolerance",
                        "0.55",
                        "--color",
                        "#11223344",
                    ]
                ),
            )

        generate.assert_called_once()
        self.assertEqual(["imports/sample_assembly.step"], generate.call_args.args[0])
        self.assertFalse(generate.call_args.kwargs["summary"])
        options = generate.call_args.kwargs["step_options"]
        self.assertTrue(options.export_3mf)
        self.assertEqual("../meshes/sample_assembly.3mf", options.three_mf_output)
        self.assertEqual(1.2, options.three_mf_tolerance)
        self.assertEqual(0.6, options.three_mf_angular_tolerance)
        self.assertEqual(1.0, options.glb_tolerance)
        self.assertEqual(0.55, options.glb_angular_tolerance)
        self.assertEqual((0x11 / 255.0, 0x22 / 255.0, 0x33 / 255.0, 0x44 / 255.0), options.color)

    def test_rejects_skip_topology_for_assembly(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main(["imports/sample_assembly.step", "--skip-topology"])
        self.assertEqual(2, cm.exception.code)


if __name__ == "__main__":
    unittest.main()
