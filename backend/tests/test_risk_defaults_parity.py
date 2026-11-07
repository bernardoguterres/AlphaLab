"""The UI's risk defaults (frontend DEFAULT_RISK_SETTINGS, used by the
Backtest, Compare and Settings pages) must equal the backend's RiskSettings
model defaults, so a request built from the form and one that relies on the
model's defaults describe the same run."""

import re
from pathlib import Path

from alphalab.api.validators import RiskSettings

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "index.ts"


def _frontend_defaults() -> dict:
    source = TYPES_TS.read_text()
    block = re.search(
        r"export const DEFAULT_RISK_SETTINGS: RiskSettings = \{(.*?)\};", source, re.S
    )
    assert block, "DEFAULT_RISK_SETTINGS not found in frontend/src/types/index.ts"
    values = {}
    for key, raw in re.findall(r"(\w+):\s*([^,\n]+),", block.group(1)):
        values[key] = {"true": True, "false": False}.get(raw, None)
        if values[key] is None:
            values[key] = float(raw)
    return values


def test_frontend_risk_defaults_match_backend_model():
    backend = RiskSettings().model_dump()
    frontend = _frontend_defaults()
    assert frontend.keys() == backend.keys()
    for key, value in backend.items():
        assert frontend[key] == value, key
