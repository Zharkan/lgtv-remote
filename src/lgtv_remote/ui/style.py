from __future__ import annotations

import re
from pathlib import Path

from lgtv_remote.ui.styles.palette import PALETTE

_STYLES_DIR = Path(__file__).parent / "styles"
_SHEETS = ["base.qss", "cards.qss", "controls.qss", "dialogs.qss"]
_TOKEN_RE = re.compile(r"@(\w+)")


def load_stylesheet() -> str:
    raw = "\n".join((_STYLES_DIR / name).read_text() for name in _SHEETS)
    return _TOKEN_RE.sub(lambda m: PALETTE.get(m.group(1), m.group(0)), raw)
