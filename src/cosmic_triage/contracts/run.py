from pydantic import Field

from cosmic_triage.contracts.base import Contract, RunMode


class RunConfig(Contract):
    """Logged into every run (§13.2): seed, config hash, resolved model ids, cost."""

    run_id: str
    mode: RunMode
    seed: int
    config_hash: str
    config_hashes: dict[str, str] = Field(default_factory=dict, description="config name -> content hash")
    model_ids: dict[str, str] = Field(default_factory=dict)
    code_version: str
    script: str


class RunManifest(Contract):
    """Written at the end of every run: the config plus the deterministic output hash and spend."""

    config: RunConfig
    output_hash: str
    outputs: dict[str, str] = Field(default_factory=dict, description="artifact path -> sha256")
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
