"""Code-enforced paid-model spend cap (ARCHITECTURE §10.3 M2, §14.9).

Every live call to a paid model (Claude, Jev) must first obtain ``SpendGuard.authorize`` and then ``record`` its actual
usage. Authorization fails closed: not approved by the owner, unknown price, or the worst-case estimate would exceed
the lifetime cap. The ledger (``runs/spend.jsonl``) is append-only; refused attempts are logged with usd = 0.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cosmic_triage.settings import PROJECT_ROOT, load_config


class SpendError(RuntimeError):
    """Base class: a paid call was refused before any network traffic."""


class SpendNotApproved(SpendError):
    def __init__(self) -> None:
        super().__init__(
            "BLOCKED: SPEND NOT APPROVED — paid model calls require the owner's explicit approval "
            "(set approved: true and approval: {...} in configs/investigator/budget.yaml after approving in the session)"
        )


class SpendCapExceeded(SpendError):
    pass


class SpendPriceUnknown(SpendError):
    pass


@dataclass(frozen=True)
class Authorization:
    provider: str
    model: str
    estimate_usd: float
    spent_before_usd: float


class SpendGuard:
    def __init__(self, config_path: str = "configs/investigator/budget.yaml", ledger_path: Path | None = None) -> None:
        cfg, self.config_hash = load_config(config_path)
        self.cap = float(cfg["total_cap_usd"])
        self.approved = bool(cfg.get("approved")) and bool(cfg.get("approval"))
        self.prices: dict[str, dict[str, float]] = {
            str(k): {"input": float(v["input"]), "output": float(v["output"])} for k, v in cfg["prices_usd_per_mtok"].items()
        }
        self.ledger_path = ledger_path or (PROJECT_ROOT / str(cfg["ledger"]))
        self._lock = threading.Lock()

    def price(self, model: str) -> dict[str, float]:
        if model not in self.prices:
            raise SpendPriceUnknown(f"no price configured for model {model!r} in budget.yaml; refusing the call")
        return self.prices[model]

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p = self.price(model)
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1e6

    def spent(self) -> float:
        if not self.ledger_path.exists():
            return 0.0
        total = 0.0
        for line in self.ledger_path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("kind") == "charge":
                    total += float(rec["usd"])
        return total

    def _append(self, rec: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def authorize(self, provider: str, model: str, est_input_tokens: int, max_output_tokens: int,
                  run_id: str, purpose: str) -> Authorization:
        """Worst-case pre-call check. Raises a SpendError (and logs the refusal) instead of allowing the call."""
        with self._lock:
            base = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "provider": provider, "model": model,
                    "run_id": run_id, "purpose": purpose, "usd": 0.0}
            try:
                if not self.approved:
                    raise SpendNotApproved()
                est = self.cost(model, est_input_tokens, max_output_tokens)
                spent = self.spent()
                if spent + est > self.cap:
                    raise SpendCapExceeded(f"spent ${spent:.4f} + estimate ${est:.4f} would exceed the ${self.cap:.2f} cap")
            except SpendError as exc:
                self._append({**base, "kind": "refused", "reason": type(exc).__name__})
                raise
            return Authorization(provider, model, est, spent)

    def record(self, auth: Authorization, input_tokens: int, output_tokens: int, resolved_model: str,
               run_id: str, purpose: str) -> float:
        usd = self.cost(auth.model, input_tokens, output_tokens)
        with self._lock:
            self._append({"ts": datetime.now(UTC).isoformat(timespec="seconds"), "kind": "charge", "provider": auth.provider,
                          "model": auth.model, "resolved_model": resolved_model, "input_tokens": input_tokens,
                          "output_tokens": output_tokens, "usd": usd, "run_id": run_id, "purpose": purpose})
        return usd
