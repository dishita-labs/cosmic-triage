"""Kill-test #8: does `btsbot` install and run on ALeRCE stamps? (inference on 10 alerts)

btsbot pulls torch/timm, so it runs in an isolated venv (path in --venv), never in the project env.
Step 1 (project env): fetch FITS cutout triplets for 10 BTS objects through the shared cache.
Step 2 (isolated venv): load the public BTSbot weights from HuggingFace and score the triplets.
Writes runs/m0/kt8_btsbot.json, read by scripts/m0_killtests.py.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from astropy.io import fits

from cosmic_triage.ingest import AlerceClient, Cache
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.settings import PROJECT_ROOT, load_config

INFER = r'''
import json, sys, time, numpy as np, torch, btsbot
d = np.load(sys.argv[1])
x = torch.from_numpy(np.ascontiguousarray(np.transpose(d["triplets"].astype(np.float32), (0, 3, 1, 2))))
t0 = time.time()
model = btsbot.load_HF_model("convnext", False, "galaxyzoo")
if model is None:  # some btsbot versions load in place without returning
    import btsbot.from_HF as H, os
    cfg = json.load(open(os.path.join(H.get_local_model_dir("convnext", False, "galaxyzoo"), "train_config.json")))
    model = getattr(btsbot.architectures, cfg["model_name"])(cfg)
    model.load_state_dict(torch.load(os.path.join(H.get_local_model_dir("convnext", False, "galaxyzoo"), "pytorch_model.bin"), map_location="cpu"))
model = model.to("cpu").eval()
load_s = time.time() - t0
t0 = time.time()
with torch.no_grad():
    scores = torch.sigmoid(model(input_data=x)).squeeze(-1).numpy().tolist()
print(json.dumps({"scores": scores, "load_s": load_s, "infer_s": time.time() - t0,
                  "btsbot_version": btsbot.__version__, "torch": torch.__version__,
                  "model": "nabeelr/BTSbot-convnext-pico-galaxyzoo (image-only)"}))
'''


def triplet(alerce: AlerceClient, oid: str, candid: str) -> np.ndarray:
    chans = []
    for kind in ("science", "template", "difference"):
        raw = alerce.stamp(oid, candid, kind, fmt="fits")
        with fits.open(io.BytesIO(gzip.decompress(raw))) as hdu:
            data = np.nan_to_num(np.asarray(hdu[0].data, dtype=np.float64))
        if data.shape != (63, 63):
            data = np.pad(data, [(0, 63 - data.shape[0]), (0, 63 - data.shape[1])], constant_values=1e-9)
        chans.append(data / (np.linalg.norm(data) or 1.0))
    return np.stack(chans, axis=-1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", required=True, help="isolated venv with `btsbot` installed")
    args = ap.parse_args()
    cache = Cache()
    alerce = AlerceClient(cache)
    rcfg, _ = load_config("configs/replay/replay.yaml")
    bts = BTSCatalog(cache)
    df = bts.load(str(rcfg["bts_snapshot_date"]))
    y25 = df[df["ZTFID"].str.startswith("ZTF25")]
    picks = list(y25[y25["type"] == "SN Ia"]["ZTFID"][:5]) + list(y25[y25["type"].isin(["AGN", "CV"])]["ZTFID"][:5])
    trips, meta = [], []
    for oid in picks:
        dets = [d for d in alerce.lightcurve(oid)["detections"] if d.get("has_stamp")]
        if not dets:
            continue
        first = min(dets, key=lambda d: d["mjd"])
        trips.append(triplet(alerce, oid, str(first["candid"])))
        meta.append({"oid": oid, "candid": str(first["candid"]), "bts_type": str(df[df["ZTFID"] == oid]["type"].iloc[0])})
    out = PROJECT_ROOT / "runs" / "m0" / "kt8_btsbot.json"
    with tempfile.TemporaryDirectory() as td:
        npz = Path(td) / "triplets.npz"
        np.savez(npz, triplets=np.stack(trips))
        py = Path(args.venv) / "bin" / "python"
        proc = subprocess.run([str(py), "-c", INFER, str(npz)], cwd=Path(args.venv).parent, capture_output=True,
                              text=True, timeout=3600)
    if proc.returncode != 0:
        res = {"verdict": "FAIL", "evidence": [f"btsbot inference failed: {proc.stderr[-1500:]}"]}
    else:
        r = json.loads(proc.stdout.strip().splitlines()[-1])
        rows = [f"{m['oid']} ({m['bts_type']}): {s:.3f}" for m, s in zip(meta, r["scores"], strict=True)]
        res = {
            "verdict": "PASS" if len(r["scores"]) == 10 else "PARTIAL",
            "evidence": [
                f"btsbot {r['btsbot_version']} (torch {r['torch']}) installed in an isolated venv; model {r['model']}",
                f"{len(r['scores'])} first-alert ALeRCE FITS triplets scored on CPU; load {r['load_s']:.1f}s, "
                f"inference {r['infer_s']:.2f}s",
                "scores (sigmoid; higher = BTS-worthy SN-like): " + "; ".join(rows),
                "Image-only model used (the multimodal variant also needs 25 alert-packet features; M7 work).",
            ],
        }
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
