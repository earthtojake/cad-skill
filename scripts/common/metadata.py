from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path.cwd().resolve()
CAD_ROOT = REPO_ROOT
DEFAULT_STL_TOLERANCE = 0.1
DEFAULT_STL_ANGULAR_TOLERANCE = 0.1
DEFAULT_3MF_TOLERANCE = DEFAULT_STL_TOLERANCE
DEFAULT_3MF_ANGULAR_TOLERANCE = DEFAULT_STL_ANGULAR_TOLERANCE
DEFAULT_GLB_TOLERANCE = 0.1
DEFAULT_GLB_ANGULAR_TOLERANCE = 0.1


@dataclass(frozen=True)
class MeshSettings:
    tolerance: float
    angular_tolerance: float


@dataclass(frozen=True)
class GeneratorMetadata:
    script_path: Path
    kind: str
    display_name: str | None
    generator_names: tuple[str, ...]
    has_gen_step: bool
    has_gen_dxf: bool
    has_gen_urdf: bool
    step_output: str | None
    stl_output: str | None
    three_mf_output: str | None
    dxf_output: str | None
    urdf_output: str | None
    export_stl: bool
    export_3mf: bool
    stl_tolerance: float | None
    stl_angular_tolerance: float | None
    three_mf_tolerance: float | None
    three_mf_angular_tolerance: float | None
    glb_tolerance: float | None
    glb_angular_tolerance: float | None
    skip_topology: bool


@dataclass(frozen=True)
class StepEnvelopeMetadata:
    step_output: str | None
    stl_output: str | None
    three_mf_output: str | None
    export_stl: bool
    export_3mf: bool
    stl_tolerance: float | None
    stl_angular_tolerance: float | None
    three_mf_tolerance: float | None
    three_mf_angular_tolerance: float | None
    glb_tolerance: float | None
    glb_angular_tolerance: float | None
    skip_topology: bool


STEP_ENVELOPE_FIELDS = {
    "shape",
    "instances",
    "children",
    "step_output",
    "stl_output",
    "3mf_output",
    "export_stl",
    "export_3mf",
    "stl_tolerance",
    "stl_angular_tolerance",
    "3mf_tolerance",
    "3mf_angular_tolerance",
    "glb_tolerance",
    "glb_angular_tolerance",
    "skip_topology",
}
DXF_ENVELOPE_FIELDS = {"document", "dxf_output"}
URDF_ENVELOPE_FIELDS = {"xml", "urdf_output", "explorer_metadata"}


DEFAULT_STL_SETTINGS = MeshSettings(
    tolerance=DEFAULT_STL_TOLERANCE,
    angular_tolerance=DEFAULT_STL_ANGULAR_TOLERANCE,
)

DEFAULT_3MF_SETTINGS = MeshSettings(
    tolerance=DEFAULT_3MF_TOLERANCE,
    angular_tolerance=DEFAULT_3MF_ANGULAR_TOLERANCE,
)

DEFAULT_GLB_SETTINGS = MeshSettings(
    tolerance=DEFAULT_GLB_TOLERANCE,
    angular_tolerance=DEFAULT_GLB_ANGULAR_TOLERANCE,
)


def normalize_mesh_numeric(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be greater than 0")
    return normalized


def normalize_stl_numeric(value: object, *, field_name: str) -> float | None:
    return normalize_mesh_numeric(value, field_name=field_name)


def normalize_optional_bool(value: object, *, field_name: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def resolve_stl_settings(
    *,
    cad_ref: str,
    generator_metadata: GeneratorMetadata | None,
    stl_tolerance: float | None = None,
    stl_angular_tolerance: float | None = None,
) -> MeshSettings:
    tolerance = DEFAULT_STL_SETTINGS.tolerance
    angular_tolerance = DEFAULT_STL_SETTINGS.angular_tolerance
    if generator_metadata is not None and generator_metadata.stl_tolerance is not None:
        tolerance = generator_metadata.stl_tolerance
    if generator_metadata is not None and generator_metadata.stl_angular_tolerance is not None:
        angular_tolerance = generator_metadata.stl_angular_tolerance
    if stl_tolerance is not None:
        tolerance = stl_tolerance
    if stl_angular_tolerance is not None:
        angular_tolerance = stl_angular_tolerance
    return MeshSettings(
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )


def resolve_3mf_settings(
    *,
    cad_ref: str,
    generator_metadata: GeneratorMetadata | None,
    three_mf_tolerance: float | None = None,
    three_mf_angular_tolerance: float | None = None,
) -> MeshSettings:
    tolerance = DEFAULT_3MF_SETTINGS.tolerance
    angular_tolerance = DEFAULT_3MF_SETTINGS.angular_tolerance
    if generator_metadata is not None and generator_metadata.three_mf_tolerance is not None:
        tolerance = generator_metadata.three_mf_tolerance
    if generator_metadata is not None and generator_metadata.three_mf_angular_tolerance is not None:
        angular_tolerance = generator_metadata.three_mf_angular_tolerance
    if three_mf_tolerance is not None:
        tolerance = three_mf_tolerance
    if three_mf_angular_tolerance is not None:
        angular_tolerance = three_mf_angular_tolerance
    return MeshSettings(
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )


def resolve_glb_settings(
    *,
    cad_ref: str,
    generator_metadata: GeneratorMetadata | None,
    glb_tolerance: float | None = None,
    glb_angular_tolerance: float | None = None,
) -> MeshSettings:
    tolerance = DEFAULT_GLB_SETTINGS.tolerance
    angular_tolerance = DEFAULT_GLB_SETTINGS.angular_tolerance
    if generator_metadata is not None and generator_metadata.glb_tolerance is not None:
        tolerance = generator_metadata.glb_tolerance
    if generator_metadata is not None and generator_metadata.glb_angular_tolerance is not None:
        angular_tolerance = generator_metadata.glb_angular_tolerance
    if glb_tolerance is not None:
        tolerance = glb_tolerance
    if glb_angular_tolerance is not None:
        angular_tolerance = glb_angular_tolerance
    return MeshSettings(
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )


def parse_generator_metadata(script_path: Path) -> GeneratorMetadata | None:
    try:
        tree = ast.parse(script_path.read_text(), filename=str(script_path))
    except (FileNotFoundError, SyntaxError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Failed to parse {script_path.relative_to(REPO_ROOT)}") from exc

    display_name: str | None = None
    kind: str | None = None
    has_gen_step = False
    has_gen_dxf = False
    has_gen_urdf = False
    generator_names: list[str] = []
    dxf_output: str | None = None
    urdf_output: str | None = None
    step_metadata = StepEnvelopeMetadata(
        step_output=None,
        stl_output=None,
        three_mf_output=None,
        export_stl=False,
        export_3mf=False,
        stl_tolerance=None,
        stl_angular_tolerance=None,
        three_mf_tolerance=None,
        three_mf_angular_tolerance=None,
        glb_tolerance=None,
        glb_angular_tolerance=None,
        skip_topology=False,
    )

    for node in tree.body:
        target: ast.expr | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and value is not None:
            if target.id == "DISPLAY_NAME" and isinstance(value, ast.Constant) and isinstance(value.value, str):
                display_name = value.value.strip()

        if not isinstance(node, ast.FunctionDef) or node.name not in {"gen_step", "gen_dxf", "gen_urdf"}:
            continue
        generator_names.append(node.name)

        if node.args.args or node.args.posonlyargs or node.args.kwonlyargs:
            raise ValueError(
                f"{script_path.relative_to(REPO_ROOT)} {node.name}() must not require arguments"
            )
        if node.args.vararg or node.args.kwarg:
            raise ValueError(
                f"{script_path.relative_to(REPO_ROOT)} {node.name}() must not accept variadic arguments"
            )

        if node.decorator_list:
            raise ValueError(
                f"{script_path.relative_to(REPO_ROOT)} {node.name}() must not use CAD generator decorators; "
                "return a generator envelope dict instead"
            )

        if node.name == "gen_step":
            kind, step_metadata = _parse_step_envelope_metadata(
                script_path=script_path,
                function=node,
            )
            has_gen_step = True
        elif node.name == "gen_dxf":
            dxf_output = _parse_dxf_envelope_metadata(
                script_path=script_path,
                function=node,
            )
            has_gen_dxf = True
        else:
            urdf_output = _parse_urdf_envelope_metadata(
                script_path=script_path,
                function=node,
            )
            has_gen_urdf = True

    if not has_gen_step and not has_gen_dxf and not has_gen_urdf:
        return None
    if not has_gen_step:
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} gen_dxf() and gen_urdf() require a gen_step() envelope entry"
        )

    return GeneratorMetadata(
        script_path=script_path.resolve(),
        kind=kind,
        display_name=display_name,
        generator_names=tuple(generator_names),
        has_gen_step=has_gen_step,
        has_gen_dxf=has_gen_dxf,
        has_gen_urdf=has_gen_urdf,
        step_output=step_metadata.step_output,
        stl_output=step_metadata.stl_output,
        three_mf_output=step_metadata.three_mf_output,
        dxf_output=dxf_output,
        urdf_output=urdf_output,
        export_stl=step_metadata.export_stl,
        export_3mf=step_metadata.export_3mf,
        stl_tolerance=step_metadata.stl_tolerance,
        stl_angular_tolerance=step_metadata.stl_angular_tolerance,
        three_mf_tolerance=step_metadata.three_mf_tolerance,
        three_mf_angular_tolerance=step_metadata.three_mf_angular_tolerance,
        glb_tolerance=step_metadata.glb_tolerance,
        glb_angular_tolerance=step_metadata.glb_angular_tolerance,
        skip_topology=step_metadata.skip_topology,
    )


def _parse_step_envelope_metadata(
    *,
    script_path: Path,
    function: ast.FunctionDef,
) -> tuple[str, StepEnvelopeMetadata]:
    envelope = _parse_literal_return_envelope(script_path=script_path, function=function)
    _reject_unsupported_fields(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        allowed_fields=STEP_ENVELOPE_FIELDS,
    )
    has_shape = "shape" in envelope
    has_instances = "instances" in envelope
    has_children = "children" in envelope
    has_assembly = has_instances or has_children
    if has_instances and has_children:
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} gen_step() envelope must define only one of "
            "'instances' or 'children'"
        )
    if has_shape == has_assembly:
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} gen_step() envelope must define exactly one of "
            "'shape', 'instances', or 'children'"
        )
    kind = "part" if has_shape else "assembly"
    export_stl = _parse_bool_field(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        field_name="export_stl",
    )
    export_3mf = _parse_bool_field(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        field_name="export_3mf",
    )
    skip_topology = _parse_bool_field(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        field_name="skip_topology",
    )
    return kind, StepEnvelopeMetadata(
        step_output=_parse_path_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="step_output",
        ),
        stl_output=_parse_path_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="stl_output",
        ),
        three_mf_output=_parse_path_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="3mf_output",
        ),
        export_stl=export_stl,
        export_3mf=export_3mf,
        stl_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="stl_tolerance",
        ),
        stl_angular_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="stl_angular_tolerance",
        ),
        three_mf_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="3mf_tolerance",
        ),
        three_mf_angular_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="3mf_angular_tolerance",
        ),
        glb_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="glb_tolerance",
        ),
        glb_angular_tolerance=_parse_mesh_numeric_field(
            script_path=script_path,
            function_name=function.name,
            envelope=envelope,
            field_name="glb_angular_tolerance",
        ),
        skip_topology=skip_topology,
    )


def _parse_dxf_envelope_metadata(
    *,
    script_path: Path,
    function: ast.FunctionDef,
) -> str | None:
    envelope = _parse_literal_return_envelope(script_path=script_path, function=function)
    _reject_unsupported_fields(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        allowed_fields=DXF_ENVELOPE_FIELDS,
    )
    if "document" not in envelope:
        raise ValueError(f"{script_path.relative_to(REPO_ROOT)} gen_dxf() envelope must define 'document'")
    return _parse_path_field(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        field_name="dxf_output",
    )


def _parse_urdf_envelope_metadata(
    *,
    script_path: Path,
    function: ast.FunctionDef,
) -> str | None:
    envelope = _parse_literal_return_envelope(script_path=script_path, function=function)
    _reject_unsupported_fields(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        allowed_fields=URDF_ENVELOPE_FIELDS,
    )
    if "xml" not in envelope:
        raise ValueError(f"{script_path.relative_to(REPO_ROOT)} gen_urdf() envelope must define 'xml'")
    return _parse_path_field(
        script_path=script_path,
        function_name=function.name,
        envelope=envelope,
        field_name="urdf_output",
    )


def _parse_literal_return_envelope(
    *,
    script_path: Path,
    function: ast.FunctionDef,
) -> dict[str, ast.expr]:
    returns = [statement for statement in function.body if isinstance(statement, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Dict):
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} {function.name}() must return a generator envelope dict"
        )
    envelope: dict[str, ast.expr] = {}
    for key_node, value_node in zip(returns[0].value.keys, returns[0].value.values, strict=True):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            raise ValueError(
                f"{script_path.relative_to(REPO_ROOT)} {function.name}() envelope keys must be string literals"
            )
        key = key_node.value
        if key in envelope:
            raise ValueError(
                f"{script_path.relative_to(REPO_ROOT)} {function.name}() envelope duplicate field: {key}"
            )
        envelope[key] = value_node
    return envelope


def _reject_unsupported_fields(
    *,
    script_path: Path,
    function_name: str,
    envelope: dict[str, ast.expr],
    allowed_fields: set[str],
) -> None:
    extra_fields = sorted(key for key in envelope if key not in allowed_fields)
    if extra_fields:
        joined = ", ".join(extra_fields)
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope has unsupported field(s): {joined}"
        )


def _literal_field(
    *,
    script_path: Path,
    function_name: str,
    envelope: dict[str, ast.expr],
    field_name: str,
) -> object | None:
    if field_name not in envelope:
        return None
    try:
        return ast.literal_eval(envelope[field_name])
    except (ValueError, SyntaxError) as exc:
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope {field_name} must be a literal"
        ) from exc


def _parse_path_field(
    *,
    script_path: Path,
    function_name: str,
    envelope: dict[str, ast.expr],
    field_name: str,
) -> str | None:
    value = _literal_field(
        script_path=script_path,
        function_name=function_name,
        envelope=envelope,
        field_name=field_name,
    )
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope {field_name} "
            "must be a non-empty string"
        )
    if "\\" in value:
        raise ValueError(
            f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope {field_name} "
            "must use POSIX '/' separators"
        )
    return value.strip()


def _parse_mesh_numeric_field(
    *,
    script_path: Path,
    function_name: str,
    envelope: dict[str, ast.expr],
    field_name: str,
) -> float | None:
    try:
        return normalize_mesh_numeric(
            _literal_field(
                script_path=script_path,
                function_name=function_name,
                envelope=envelope,
                field_name=field_name,
            ),
            field_name=field_name,
        )
    except ValueError as exc:
        raise ValueError(f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope {exc}") from exc


def _parse_bool_field(
    *,
    script_path: Path,
    function_name: str,
    envelope: dict[str, ast.expr],
    field_name: str,
) -> bool:
    try:
        return normalize_optional_bool(
            _literal_field(
                script_path=script_path,
                function_name=function_name,
                envelope=envelope,
                field_name=field_name,
            ),
            field_name=field_name,
        )
    except ValueError as exc:
        raise ValueError(f"{script_path.relative_to(REPO_ROOT)} {function_name}() envelope {exc}") from exc
