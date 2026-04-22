from __future__ import annotations

from collections.abc import Sequence

from common.generation import generate_step_part_targets, run_tool_cli


def main(argv: Sequence[str] | None = None) -> int:
    return run_tool_cli(
        argv,
        prog="gen_step_part",
        description="Generate explicit CAD part STEP targets and their viewer artifacts.",
        action=generate_step_part_targets,
        step_kind="part",
    )
