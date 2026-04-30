import unittest
from unittest import mock

from gen_dxf import cli


class GenDxfCliTests(unittest.TestCase):
    def test_requires_explicit_target(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main([])
        self.assertEqual(2, cm.exception.code)

    def test_rejects_root_option(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            cli.main(["--root", "workspace/samples"])
        self.assertEqual(2, cm.exception.code)

    def test_passes_targets_in_order(self) -> None:
        with mock.patch.object(cli, "generate_dxf_targets", return_value=0) as generate:
            self.assertEqual(0, cli.main(["drawings/second.dxf", "drawings/first.dxf", "--summary"]))

        generate.assert_called_once_with(["drawings/second.dxf", "drawings/first.dxf"], summary=True)


if __name__ == "__main__":
    unittest.main()
