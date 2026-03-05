"""Construit un index des amendements et enrichit les scrutins avec le contenu."""

import json
import os
import re
from html import unescape
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

AMDT_DIR = RAW_DIR / "amendements" / "json"


def strip_html(html_text: str) -> str:
    """Supprime les tags HTML et decode les entites."""
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_amendment_index() -> dict:
    """Construit un index {numero_simple -> [amendment_data, ...]}.

    Chaque amendement est stocke avec un flag is_seance pour distinguer
    les amendements de seance (hemicycle, prefixeOrganeExamen="AN")
    des amendements de commission (CL, CF, AS, CS...).
    Les scrutins portent sur des votes en seance, donc on priorise les
    amendements de seance lors du matching.
    """
    # index: numero_simple -> liste d'amendements avec ce numero
    index: dict[str, list] = {}
    count = 0

    for dossier in os.listdir(AMDT_DIR):
        if not dossier.startswith("DLR5L17"):
            continue
        dossier_path = AMDT_DIR / dossier
        for texte in os.listdir(dossier_path):
            texte_path = dossier_path / texte
            if not texte_path.is_dir():
                continue
            for fname in os.listdir(texte_path):
                if not fname.endswith(".json"):
                    continue
                fpath = texte_path / fname
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                a = data["amendement"]
                ident = a.get("identification", {})
                numero_long = ident.get("numeroLong", "")
                texte_ref = a.get("texteLegislatifRef", "")
                prefixe_organe = ident.get("prefixeOrganeExamen", "")
                is_seance = (prefixe_organe == "AN")

                # Extraire les champs utiles
                corps = a.get("corps", {})
                contenu = corps.get("contenuAuteur", {})
                dispositif = strip_html(contenu.get("dispositif", ""))
                expose = strip_html(contenu.get("exposeSommaire", ""))

                sig = a.get("signataires", {})
                auteur = sig.get("auteur", {})
                auteur_ref = auteur.get("acteurRef", "")
                groupe_ref = auteur.get("groupePolitiqueRef", "")
                if isinstance(auteur_ref, dict):
                    auteur_ref = ""
                if isinstance(groupe_ref, dict):
                    groupe_ref = ""

                sort_data = a.get("sort", {})
                sort_code = ""
                if isinstance(sort_data, dict):
                    sort_code = sort_data.get("sortEnSeance", sort_data.get("sortEnCommission", ""))

                amdt_data = {
                    "numero_long": numero_long,
                    "texte_ref": texte_ref,
                    "auteur_ref": auteur_ref,
                    "groupe_politique_ref": groupe_ref,
                    "dispositif": dispositif,
                    "expose": expose,
                    "sort": sort_code,
                    "libelle_signataires": strip_html(sig.get("libelle", "")),
                    "is_seance": is_seance,
                }

                # Extraire le numero simple (digits seulement)
                numero_norm = numero_long.strip().replace(" (Rect)", "").replace("(Rect)", "")
                num_simple = re.sub(r"^[A-Z]{1,4}-?[A-Z]{0,4}", "", numero_norm).strip()
                if not num_simple:
                    num_simple = numero_norm

                # Stocker dans la liste pour ce numero
                key = (texte_ref, num_simple)
                if key not in index:
                    index[key] = []
                index[key].append(amdt_data)

                count += 1

    print(f"  {count} amendements indexes ({len(index)} cles)")
    nb_seance = sum(1 for vals in index.values() for v in vals if v["is_seance"])
    print(f"  dont {nb_seance} amendements de seance (hemicycle)")
    return index


def extract_amdt_numero(titre: str) -> str | None:
    """Extrait le numero d'amendement du titre d'un scrutin."""
    if not titre:
        return None
    m = re.search(r"amendement.*?n[°o\s]+(\d+)", titre, re.IGNORECASE)
    if m:
        return m.group(1)
    # Sous-amendement
    m = re.search(r"sous-amendement.*?n[°o\s]+(\d+)", titre, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extract_auteur_from_titre(titre: str) -> str | None:
    """Extrait le nom de l'auteur depuis le titre du scrutin.

    Ex: 'l'amendement n° 37 de M. Fayssat' -> 'Fayssat'
    Ex: 'l'amendement n° 12 de Mme Abomangoli' -> 'Abomangoli'
    Ex: 'l'amendement n° 5 du Gouvernement' -> 'Gouvernement'
    """
    if not titre:
        return None
    # "de M. Nom", "de Mme Nom", "du Gouvernement", "de la commission"
    m = re.search(
        r"(?:de\s+(?:M\.|Mme|Mlle)\s+([A-ZÀ-Ü][a-zà-ü]+(?:\s[A-ZÀ-Ü][a-zà-ü]+)?)"
        r"|du\s+(Gouvernement))",
        titre,
    )
    if m:
        return m.group(1) or m.group(2)
    return None


def pick_best_amendment(candidates: list[dict], auteur_name: str | None,
                        acteur_map: dict) -> dict | None:
    """Choisit le meilleur amendement parmi les candidats.

    Priorite :
    1. Amendements de seance (is_seance=True)
    2. Parmi ceux-ci, celui dont l'auteur correspond au nom dans le titre
    """
    if not candidates:
        return None

    # Separer seance vs commission
    seance = [c for c in candidates if c.get("is_seance")]
    commission = [c for c in candidates if not c.get("is_seance")]

    # Prioriser les amendements de seance
    pool = seance if seance else commission

    # Si on a le nom de l'auteur dans le titre, essayer de matcher
    if auteur_name and acteur_map:
        auteur_lower = auteur_name.lower()
        for amdt in pool:
            acteur_ref = amdt.get("auteur_ref", "")
            nom_acteur = acteur_map.get(acteur_ref, "")
            if nom_acteur and auteur_lower in nom_acteur.lower():
                return amdt
            # Aussi chercher dans le libelle signataires
            signataires = amdt.get("libelle_signataires", "").lower()
            if auteur_lower in signataires:
                return amdt

    # Sinon, retourner le premier de la pool prioritaire
    return pool[0]


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] Construction de l'index des amendements...")
    amdt_index = build_amendment_index()

    print("[2/4] Chargement des scrutins et acteurs...")
    scrutins = pd.read_csv(PROCESSED_DIR / "scrutins.csv", encoding="utf-8")

    # Charger le mapping organe -> groupe pour resoudre les groupePolitiqueRef
    organe_map = {}
    organe_dir = RAW_DIR / "acteurs_organes" / "json" / "organe"
    for fname in os.listdir(organe_dir):
        if not fname.endswith(".json"):
            continue
        with open(organe_dir / fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        org = data["organe"]
        if org.get("codeType") == "GP":
            organe_map[org["uid"]] = org.get("libelleAbrege", org.get("libelle", ""))

    # Charger le mapping acteur -> nom pour valider l'auteur
    acteur_map = {}
    acteur_dir = RAW_DIR / "acteurs_organes" / "json" / "acteur"
    for fname in os.listdir(acteur_dir):
        if not fname.endswith(".json"):
            continue
        with open(acteur_dir / fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        act = data["acteur"]
        uid = act["uid"]["#text"] if isinstance(act["uid"], dict) else act["uid"]
        etat = act.get("etatCivil", {}).get("ident", {})
        nom = etat.get("nom", "")
        prenom = etat.get("prenom", "")
        acteur_map[uid] = f"{nom} {prenom}".strip()

    print(f"  {len(acteur_map)} acteurs charges")

    print("[3/4] Enrichissement des scrutins avec les amendements...")

    # Pour chaque scrutin, essayer de trouver l'amendement correspondant
    enriched = []
    matched = 0
    matched_by_auteur = 0
    for _, row in scrutins.iterrows():
        titre = row.get("titre", "") or ""
        numero = extract_amdt_numero(titre)
        auteur_name = extract_auteur_from_titre(titre)

        amdt_data = None
        if numero:
            # Collecter tous les candidats avec ce numero
            candidates = []
            for key, vals in amdt_index.items():
                if key[1] == numero:
                    candidates.extend(vals)

            if candidates:
                amdt_data = pick_best_amendment(candidates, auteur_name, acteur_map)
                if auteur_name and amdt_data:
                    # Verifier si on a matche par auteur
                    nom_acteur = acteur_map.get(amdt_data.get("auteur_ref", ""), "")
                    if auteur_name.lower() in nom_acteur.lower():
                        matched_by_auteur += 1

        if amdt_data:
            matched += 1
            groupe_abrege = organe_map.get(amdt_data["groupe_politique_ref"], "")
            enriched.append({
                "scrutin_uid": row["scrutin_uid"],
                "amdt_numero": amdt_data["numero_long"],
                "amdt_auteur_ref": amdt_data["auteur_ref"],
                "amdt_groupe_ref": amdt_data["groupe_politique_ref"],
                "amdt_groupe_abrege": groupe_abrege,
                "amdt_expose": amdt_data["expose"],
                "amdt_dispositif": amdt_data["dispositif"],
                "amdt_signataires": amdt_data["libelle_signataires"],
            })
        else:
            enriched.append({
                "scrutin_uid": row["scrutin_uid"],
                "amdt_numero": "",
                "amdt_auteur_ref": "",
                "amdt_groupe_ref": "",
                "amdt_groupe_abrege": "",
                "amdt_expose": "",
                "amdt_dispositif": "",
                "amdt_signataires": "",
            })

    enriched_df = pd.DataFrame(enriched)
    enriched_df.to_csv(PROCESSED_DIR / "scrutins_amendements.csv", index=False, encoding="utf-8")

    print(f"\n  Scrutins enrichis: {matched} / {len(scrutins)} matches")
    print(f"  dont {matched_by_auteur} valides par correspondance auteur")
    print(f"  -> {PROCESSED_DIR / 'scrutins_amendements.csv'}")

    # Verification sur le cas Fayssat
    print("\n[4/4] Verification cas Fayssat (amendement postal)...")
    for _, row in scrutins.iterrows():
        titre = row.get("titre", "") or ""
        if "Fayssat" in titre and "postal" in titre:
            uid = row["scrutin_uid"]
            match = enriched_df[enriched_df["scrutin_uid"] == uid].iloc[0]
            print(f"  Titre: {titre[:120]}...")
            print(f"  Numero matche: {match['amdt_numero']}")
            print(f"  Groupe: {match['amdt_groupe_abrege']}")
            print(f"  Signataires: {match['amdt_signataires']}")
            break

    # Stats par groupe auteur
    with_groupe = enriched_df[enriched_df["amdt_groupe_abrege"] != ""]
    print(f"\n  Amendements avec groupe identifie: {len(with_groupe)}")
    print("  Repartition par groupe auteur:")
    for grp, cnt in with_groupe["amdt_groupe_abrege"].value_counts().head(15).items():
        print(f"    {grp}: {cnt}")


if __name__ == "__main__":
    main()
