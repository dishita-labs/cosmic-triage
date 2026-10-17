"""Intentionally refresh tests/contracts/schema_snapshot.json after a reviewed contract change (§13.5, §14.1)."""

import json
import sys

from cosmic_triage import contracts as C
from cosmic_triage.settings import PROJECT_ROOT


def main() -> int:
    schema = {cls.__name__: cls.model_json_schema() for cls in C.ALL_CONTRACTS}
    path = PROJECT_ROOT / "tests" / "contracts" / "schema_snapshot.json"
    path.write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")
    print(f"wrote {path} ({len(schema)} contracts, version {C.CONTRACTS_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
