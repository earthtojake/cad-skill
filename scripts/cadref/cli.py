from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    package_dir = Path(__file__).resolve().parent
    scripts_dir = package_dir.parent
    sys.path = [
        entry
        for entry in sys.path
        if not entry or Path(entry).resolve() != package_dir
    ]
    sys.path.insert(0, str(scripts_dir))
    from cadref.inspect import (
        CadRefError,
        cad_path_from_target,
        diff_entry_targets,
        inspect_cad_refs,
        inspect_entry_planes,
    )
else:
    from .inspect import (
        CadRefError,
        cad_path_from_target,
        diff_entry_targets,
        inspect_cad_refs,
        inspect_entry_planes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect occurrence-aware @cad[...] refs against STEP source files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Resolve whole-entry or selector refs and return STEP-derived context.",
    )
    inspect_parser.add_argument(
        "input",
        nargs="?",
        help="Token text or multiline prompt text containing @cad[...] refs.",
    )
    inspect_parser.add_argument(
        "--refs",
        nargs="+",
        help="One or more @cad[...] refs to inspect. Can be used instead of positional input.",
    )
    inspect_parser.add_argument(
        "--input-file",
        type=Path,
        help="Read token text from a file instead of CLI input or stdin.",
    )
    inspect_parser.add_argument(
        "--detail",
        action="store_true",
        help="Include detailed geometry facts for selected face/edge refs.",
    )
    inspect_parser.add_argument(
        "--facts",
        action="store_true",
        help="Include compact geometry facts for whole-entry refs and resolved selectors.",
    )
    inspect_parser.add_argument(
        "--topology",
        action="store_true",
        help="Include full face/edge selector lists for whole-entry refs. Expensive on large STEP files.",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output. Recommended for agent workflows.",
    )
    inspect_parser.set_defaults(handler=run_inspect)

    planes_parser = subparsers.add_parser(
        "planes",
        help="Group major coplanar planar faces for a STEP ref by axis and coordinate.",
    )
    planes_parser.add_argument(
        "entry",
        help="CAD STEP path or @cad[...] token for the part to inspect.",
    )
    planes_parser.add_argument(
        "--coordinate-tolerance",
        type=float,
        default=1e-3,
        help="Merge planar face groups whose axis coordinate differs by at most this value. Default: 0.001",
    )
    planes_parser.add_argument(
        "--min-area-ratio",
        type=float,
        default=0.05,
        help="Drop planar groups smaller than this fraction of total planar area. Default: 0.05",
    )
    planes_parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum number of groups to emit. Default: 12",
    )
    planes_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output. Recommended for agent workflows.",
    )
    planes_parser.set_defaults(handler=run_planes)

    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare two CAD STEP refs and summarize selector-level changes.",
    )
    diff_parser.add_argument("left", help="Left CAD STEP path or @cad[...] token.")
    diff_parser.add_argument("right", help="Right CAD STEP path or @cad[...] token.")
    diff_parser.add_argument(
        "--detail",
        action="store_true",
        help="Include major planar face groups for both sides.",
    )
    diff_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output. Recommended for agent workflows.",
    )
    diff_parser.set_defaults(handler=run_diff)

    return parser


def run_inspect(args: argparse.Namespace) -> int:
    try:
        text = _read_input_text(args)
        result = inspect_cad_refs(
            text,
            detail=bool(args.detail),
            include_topology=bool(args.topology),
            facts=bool(args.facts),
        )
    except CadRefError as exc:
        result = {
            "ok": False,
            "tokens": [],
            "errors": [
                {
                    "line": None,
                    "cadPath": None,
                    "selector": None,
                    "kind": "input",
                    "message": str(exc),
                }
            ],
        }

    if args.json or not result.get("ok"):
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        _print_text_summary(result)

    return 0 if bool(result.get("ok")) else 2


def run_planes(args: argparse.Namespace) -> int:
    try:
        result = inspect_entry_planes(
            args.entry,
            coordinate_tolerance=float(args.coordinate_tolerance),
            min_area_ratio=float(args.min_area_ratio),
            limit=int(args.limit),
        )
    except CadRefError as exc:
        result = {
            "ok": False,
            "cadPath": _safe_cad_path(args.entry),
            "errors": [{"message": str(exc)}],
        }

    if args.json or not result.get("ok"):
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        _print_planes_summary(result)
    return 0 if bool(result.get("ok")) else 2


def run_diff(args: argparse.Namespace) -> int:
    try:
        result = diff_entry_targets(args.left, args.right, detail=bool(args.detail))
    except CadRefError as exc:
        result = {
            "ok": False,
            "left": {"cadPath": _safe_cad_path(args.left)},
            "right": {"cadPath": _safe_cad_path(args.right)},
            "errors": [{"message": str(exc)}],
        }

    if args.json or not result.get("ok"):
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        _print_diff_summary(result)
    return 0 if bool(result.get("ok")) else 2


def _read_input_text(args: argparse.Namespace) -> str:
    input_sources = sum(
        1
        for source in (args.input_file, args.input, args.refs)
        if source is not None
    )
    if input_sources > 1:
        raise CadRefError("Pass only one of positional input, --input-file, or --refs.")

    if args.refs:
        text = "\n".join(str(ref) for ref in args.refs)
    elif args.input_file:
        try:
            text = args.input_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise CadRefError(f"Failed to read input file: {args.input_file}") from exc
    elif args.input is not None:
        text = str(args.input)
    else:
        text = sys.stdin.read()

    if not str(text).strip():
        raise CadRefError("No input text provided.")
    return text


def _print_text_summary(result: dict[str, object]) -> None:
    token_results = result.get("tokens")
    if not isinstance(token_results, list):
        print("No tokens inspected.")
        return

    for token in token_results:
        if not isinstance(token, dict):
            continue
        line = token.get("line")
        token_text = token.get("token")
        cad_path = token.get("cadPath")
        step_path = token.get("stepPath")
        print(f"line={line} cadPath={cad_path} step={step_path}")
        print(f"  token: {token_text}")
        summary = token.get("summary")
        if isinstance(summary, dict):
            print(
                "  summary: "
                f"kind={summary.get('kind')} occurrences={summary.get('occurrenceCount')} "
                f"leafOccurrences={summary.get('leafOccurrenceCount')} faces={summary.get('faceCount')} "
                f"edges={summary.get('edgeCount')} vertices={summary.get('vertexCount')} bounds={summary.get('bounds')}"
            )

        selections = token.get("selections")
        if isinstance(selections, list):
            for selection in selections:
                if not isinstance(selection, dict):
                    continue
                selector = selection.get("normalizedSelector")
                selector_type = selection.get("selectorType")
                status = selection.get("status")
                print(f"  - {selector} [{selector_type}] {status}")

        warnings = token.get("warnings")
        if isinstance(warnings, list):
            for warning in warnings:
                print(f"  warning: {warning}")
        entry_facts = token.get("entryFacts")
        if isinstance(entry_facts, dict):
            print(f"  entryFacts: {entry_facts}")
        if isinstance(selections, list):
            for selection in selections:
                if not isinstance(selection, dict):
                    continue
                geometry_facts = selection.get("geometryFacts")
                if isinstance(geometry_facts, dict):
                    print(f"    geometryFacts: {geometry_facts}")


def _print_planes_summary(result: dict[str, object]) -> None:
    print(f"cadPath={result.get('cadPath')} step={result.get('stepPath')}")
    planes = result.get("planes")
    if not isinstance(planes, list) or not planes:
        print("  no major planar groups")
        return
    for plane in planes:
        if not isinstance(plane, dict):
            continue
        print(
            "  "
            f"axis={plane.get('axis')} coordinate={plane.get('coordinate')} "
            f"faces={plane.get('faceCount')} area={plane.get('totalArea')} selectors={plane.get('selectors')}"
        )


def _print_diff_summary(result: dict[str, object]) -> None:
    left = result.get("left") if isinstance(result.get("left"), dict) else {}
    right = result.get("right") if isinstance(result.get("right"), dict) else {}
    diff = result.get("diff") if isinstance(result.get("diff"), dict) else {}
    print(f"left={left.get('cadPath')} right={right.get('cadPath')}")
    print(
        "  "
        f"topologyChanged={diff.get('topologyChanged')} "
        f"geometryChanged={diff.get('geometryChanged')} "
        f"bboxChanged={diff.get('bboxChanged')} "
        f"countDelta={diff.get('countDelta')}"
    )
    if diff.get("sizeDelta") is not None:
        print(f"  sizeDelta={diff.get('sizeDelta')}")
    if diff.get("centerDelta") is not None:
        print(f"  centerDelta={diff.get('centerDelta')}")


def _safe_cad_path(target: str) -> str:
    try:
        return cad_path_from_target(target)
    except CadRefError:
        return str(target)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
