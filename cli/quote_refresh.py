from __future__ import annotations

import json
import os
import sys

# Ensure project root is on path when invoked from the web app.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cli.services.quote_service import refresh_mtm_quotes


def main() -> int:
    result = refresh_mtm_quotes()
    printable = {
        "ok": result.get("ok", False),
        "message": result.get("message"),
        "provider_messages": result.get("provider_messages", []),
        "requested_equities": result.get("requested_equities", 0),
        "requested_options": result.get("requested_options", 0),
        "invalid_contracts": result.get("invalid_contracts", 0),
        "statuses": result.get("statuses", {}),
        "save_result": result.get("save_result", {}),
    }
    print(json.dumps(printable))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
