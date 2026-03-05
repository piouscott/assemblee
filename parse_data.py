"""Parse les JSON bruts des scrutins et acteurs/organes, construit les DataFrames."""

import json
import os
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def build_organe_map() -> dict[str, dict]:
    """Construit un mapping organeRef -> {libelle, libelleAbrege, codeType, legislature}."""
    organe_dir = RAW_DIR / "acteurs_organes" / "json" / "organe"
    mapping = {}
    for fname in os.listdir(organe_dir):
        if not fname.endswith(".json"):
            continue
        with open(organe_dir / fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        org = data["organe"]
        mapping[org["uid"]] = {
            "libelle": org.get("libelle", ""),
            "libelleAbrege": org.get("libelleAbrege", ""),
            "codeType": org.get("codeType", ""),
            "legislature": org.get("legislature", ""),
        }
    return mapping


def build_acteur_map() -> dict[str, dict]:
    """Construit un mapping acteurRef -> {prenom, nom, uid}."""
    acteur_dir = RAW_DIR / "acteurs_organes" / "json" / "acteur"
    mapping = {}
    for fname in os.listdir(acteur_dir):
        if not fname.endswith(".json"):
            continue
        with open(acteur_dir / fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        act = data["acteur"]
        uid = act["uid"]
        if isinstance(uid, dict):
            uid = uid.get("#text", "")
        ident = act.get("etatCivil", {}).get("ident", {})
        mapping[uid] = {
            "prenom": ident.get("prenom", ""),
            "nom": ident.get("nom", ""),
        }
    return mapping


def _extract_votants(node) -> list[str]:
    """Extrait les acteurRef depuis un noeud de vote (pours/contres/abstentions/nonVotants)."""
    if node is None:
        return []
    votant = node.get("votant", [])
    if isinstance(votant, dict):
        votant = [votant]
    return [v["acteurRef"] for v in votant if "acteurRef" in v]


def parse_scrutins(organe_map: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse tous les scrutins JSON.

    Returns:
        scrutins_df: un row par scrutin avec les infos globales
        votes_df: un row par (scrutin, groupe) avec les décomptes
    """
    scrutin_dir = RAW_DIR / "scrutins" / "json"
    scrutins_rows = []
    votes_rows = []
    votes_detail_rows = []

    for fname in sorted(os.listdir(scrutin_dir)):
        if not fname.endswith(".json"):
            continue
        with open(scrutin_dir / fname, "r", encoding="utf-8") as f:
            data = json.load(f)

        s = data["scrutin"]
        scrutin_uid = s["uid"]
        numero = s.get("numero", "")
        titre = s.get("titre", "")
        date = s.get("dateScrutin", "")
        type_vote = s.get("typeVote", {})
        code_type = type_vote.get("codeTypeVote", "")
        libelle_type = type_vote.get("libelleTypeVote", "")
        sort_code = s.get("sort", {}).get("code", "")
        sort_libelle = s.get("sort", {}).get("libelle", "")
        mode_pub = s.get("modePublicationDesVotes", "")

        synthese = s.get("syntheseVote", {})
        nb_votants = int(synthese.get("nombreVotants", 0))
        nb_exprimes = int(synthese.get("suffragesExprimes", 0))
        decompte_global = synthese.get("decompte", {})

        objet = s.get("objet", {})
        objet_libelle = ""
        if objet:
            objet_libelle = objet.get("libelle", "") or ""

        scrutins_rows.append({
            "scrutin_uid": scrutin_uid,
            "numero": numero,
            "titre": titre,
            "objet": objet_libelle,
            "date": date,
            "code_type_vote": code_type,
            "libelle_type_vote": libelle_type,
            "sort": sort_code,
            "sort_libelle": sort_libelle,
            "mode_publication": mode_pub,
            "nb_votants": nb_votants,
            "nb_exprimes": nb_exprimes,
            "total_pour": int(decompte_global.get("pour", 0)),
            "total_contre": int(decompte_global.get("contre", 0)),
            "total_abstentions": int(decompte_global.get("abstentions", 0)),
        })

        # Ventilation par groupe
        ventilation = s.get("ventilationVotes", {}).get("organe", {})
        groupes = ventilation.get("groupes", {}).get("groupe", [])
        if isinstance(groupes, dict):
            groupes = [groupes]

        for grp in groupes:
            organe_ref = grp.get("organeRef", "")
            nb_membres = int(grp.get("nombreMembresGroupe", 0))
            vote = grp.get("vote", {})
            position_maj = vote.get("positionMajoritaire", "")
            decompte = vote.get("decompteVoix", {})

            nb_pour = int(decompte.get("pour", 0))
            nb_contre = int(decompte.get("contre", 0))
            nb_abstentions = int(decompte.get("abstentions", 0))
            nb_non_votants = int(decompte.get("nonVotants", 0))

            organe_info = organe_map.get(organe_ref, {})
            groupe_nom = organe_info.get("libelle", organe_ref)
            groupe_abrege = organe_info.get("libelleAbrege", organe_ref)

            votes_rows.append({
                "scrutin_uid": scrutin_uid,
                "date": date,
                "organe_ref": organe_ref,
                "groupe_nom": groupe_nom,
                "groupe_abrege": groupe_abrege,
                "nb_membres": nb_membres,
                "position_majoritaire": position_maj,
                "pour": nb_pour,
                "contre": nb_contre,
                "abstentions": nb_abstentions,
                "non_votants": nb_non_votants,
            })

            # Votes nominatifs
            nominatif = vote.get("decompteNominatif", {})
            if nominatif and mode_pub == "DecompteNominatif":
                for position, key in [("pour", "pours"), ("contre", "contres"),
                                       ("abstention", "abstentions"), ("nonVotant", "nonVotants")]:
                    acteurs = _extract_votants(nominatif.get(key))
                    for acteur_ref in acteurs:
                        votes_detail_rows.append({
                            "scrutin_uid": scrutin_uid,
                            "date": date,
                            "organe_ref": organe_ref,
                            "groupe_abrege": groupe_abrege,
                            "acteur_ref": acteur_ref,
                            "position": position,
                        })

    scrutins_df = pd.DataFrame(scrutins_rows)
    scrutins_df["date"] = pd.to_datetime(scrutins_df["date"])
    scrutins_df = scrutins_df.sort_values("date").reset_index(drop=True)

    votes_df = pd.DataFrame(votes_rows)
    votes_df["date"] = pd.to_datetime(votes_df["date"])

    votes_detail_df = pd.DataFrame(votes_detail_rows)
    if not votes_detail_df.empty:
        votes_detail_df["date"] = pd.to_datetime(votes_detail_df["date"])

    return scrutins_df, votes_df, votes_detail_df


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/3] Construction du mapping organes...")
    organe_map = build_organe_map()
    gp_count = sum(1 for v in organe_map.values() if v["codeType"] == "GP")
    print(f"  {len(organe_map)} organes charges ({gp_count} groupes politiques)")

    print("[2/3] Construction du mapping acteurs...")
    acteur_map = build_acteur_map()
    print(f"  {len(acteur_map)} acteurs charges")

    # Sauvegarder le mapping acteurs
    acteurs_df = pd.DataFrame([
        {"acteur_ref": uid, "prenom": info["prenom"], "nom": info["nom"]}
        for uid, info in acteur_map.items()
    ])
    acteurs_df.to_csv(PROCESSED_DIR / "acteurs.csv", index=False, encoding="utf-8")

    print("[3/3] Parsing des scrutins...")
    scrutins_df, votes_df, votes_detail_df = parse_scrutins(organe_map)

    scrutins_df.to_csv(PROCESSED_DIR / "scrutins.csv", index=False, encoding="utf-8")
    votes_df.to_csv(PROCESSED_DIR / "votes_par_groupe.csv", index=False, encoding="utf-8")
    votes_detail_df.to_csv(PROCESSED_DIR / "votes_nominatifs.csv", index=False, encoding="utf-8")

    print(f"\n  Scrutins: {len(scrutins_df)} lignes -> scrutins.csv")
    print(f"  Votes par groupe: {len(votes_df)} lignes -> votes_par_groupe.csv")
    print(f"  Votes nominatifs: {len(votes_detail_df)} lignes -> votes_nominatifs.csv")
    print(f"  Acteurs: {len(acteurs_df)} lignes -> acteurs.csv")
    print(f"\n[ok] Donnees traitees dans {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
