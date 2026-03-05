"""Télécharge et extrait les données open data de l'Assemblée Nationale (17e législature)."""

import os
import zipfile
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"

DATASETS = {
    "scrutins": "https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip",
    "acteurs_organes": "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/tous_acteurs_mandats_organes_xi_legislature/AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip",
    "amendements": "https://data.assemblee-nationale.fr/static/openData/repository/17/loi/amendements_div_legis/Amendements.json.zip",
}


def download_and_extract(name: str, url: str):
    dest_dir = RAW_DIR / name
    zip_path = RAW_DIR / f"{name}.zip"

    if dest_dir.exists() and any(dest_dir.iterdir()):
        print(f"[skip] {name} déjà présent dans {dest_dir}")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"[download] {name} depuis {url}...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[download] {name} terminé ({zip_path.stat().st_size / 1024 / 1024:.1f} Mo)")

    print(f"[extract] Extraction de {name}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    print(f"[extract] {name} extrait dans {dest_dir}")

    zip_path.unlink()


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in DATASETS.items():
        download_and_extract(name, url)
    print("\n[ok] Toutes les donnees ont ete telechargees.")


if __name__ == "__main__":
    main()
