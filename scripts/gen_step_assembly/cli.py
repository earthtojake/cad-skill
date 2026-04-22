from __future__ import annotations

from collections.abc import Sequence

from common.generation import generate_step_assembly_targets, run_tool_cli


def main(argv: Sequence[str] | None = None) -> int:
    return run_tool_cli(
        argv,
        prog="gen_step_assembly",
        description="Generate explicit CAD assembly STEP targets and their viewer artifacts.",
        action=generate_step_assembly_targets,
        step_kind="assembly",
    )
