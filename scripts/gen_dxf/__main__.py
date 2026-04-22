from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    tool_dir = Path(__file__).resolve().parent
    sys.path = [path for path in sys.path if Path(path or ".").resolve() != tool_dir]
    sys.path.insert(0, str(tool_dir.parent))
    from gen_dxf.cli import main
else:
    from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
