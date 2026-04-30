from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.generation import generate_step_assembly_targets, run_tool_cli


def main(argv: Sequence[str] | None = None) -> int:
    return run_tool_cli(
        argv,
        prog="gen_step_assembly",
        description="Generate explicit CAD assembly STEP targets and their explorer artifacts.",
        action=generate_step_assembly_targets,
        step_kind="assembly",
    )


if __name__ == "__main__":
    raise SystemExit(main())
