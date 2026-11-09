"""Baixa somente Tmax/Tmin cedidos pelo autor; não redistribui os dados."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import gdown
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "Tmax.npz": "1Rrj_4WgxCKOzBOeYLy5uoWaEibYl1mLT",
    "Tmin.npz": "1ASwTqJFgBc2oTQgdkAo3mKwOMsH8BmZl",
}


def main():
    destination = ROOT / "dados" / "brutos"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, file_id in FILES.items():
        path = destination / name
        if not path.exists():
            print(f"Baixando {name}...", flush=True)
            gdown.download(id=file_id, output=str(path), quiet=True,
                           use_cookies=False, timeout=(30, 60), retries=2)
        with np.load(path, allow_pickle=False) as data:
            if not {"data", "lat_lon_alt", "ID"}.issubset(data.files):
                raise ValueError(f"Esquema NPZ inesperado: {name}")
            shape = list(data["data"].shape)
        with path.open("rb") as handle:
            sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
        manifest.append({"filename": name, "source": f"https://drive.google.com/file/d/{file_id}/view",
                         "bytes": path.stat().st_size, "sha256": sha256, "shape": shape})
        print(f"{name}: {shape}, SHA256 {sha256}", flush=True)
    (destination / "manifesto.json").write_text(json.dumps({
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "citation": "https://doi.org/10.1002/joc.7731", "files": manifest,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
