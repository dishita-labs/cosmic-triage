"""Export pydantic contract JSON schemas for the console (§13.2: types generated from pydantic).

Then: cd console && npm run types   (json-schema-to-typescript -> src/types/contracts.ts)
"""

import json
import sys

from pydantic.json_schema import models_json_schema

from cosmic_triage import contracts as C
from cosmic_triage.settings import PROJECT_ROOT


def main() -> int:
    _, schema = models_json_schema([(m, "serialization") for m in C.ALL_CONTRACTS], title="CosmicTriageContracts")
    out = PROJECT_ROOT / "console" / "src" / "types" / "contracts.schema.json"
    out.write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
