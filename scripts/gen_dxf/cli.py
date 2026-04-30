from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.generation import generate_dxf_targets, run_tool_cli


def main(argv: Sequence[str] | None = None) -> int:
    return run_tool_cli(
        argv,
        prog="gen_dxf",
        description="Generate explicit DXF targets from envelope-returning Python sources.",
        action=generate_dxf_targets,
        target_help="Explicit Python source file defining gen_dxf() to generate.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
