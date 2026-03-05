"""Classifie les scrutins par theme via mots-cles (pas besoin d'API)."""

import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
THEMES_FILE = PROCESSED_DIR / "themes.csv"

# Mapping mots-cles -> theme
THEME_KEYWORDS = {
    "Emploi / Travail": [
        r"emploi", r"travail", r"chomage", r"ch\u00f4mage", r"salari", r"retraite",
        r"apprenti", r"formation profess", r"assurance.ch\u00f4mage", r"code du travail",
        r"droit.du.travail", r"licenciement", r"plein.emploi", r"interim",
        r"p\u00e9nibilit", r"pension", r"cotisation", r"AGIRC", r"ARRCO",
    ],
    "Sante": [
        r"sant\u00e9", r"sante", r"h\u00f4pital", r"hopital", r"m\u00e9dec", r"medec",
        r"maladie", r"vaccin", r"pharmacie", r"IVG", r"bioethique",
        r"bio\u00e9thique", r"pandemie", r"pand\u00e9mie", r"soignant",
        r"s\u00e9curit\u00e9.sociale", r"PLFSS", r"assurance.maladie",
        r"aide [àa] mourir", r"fin de vie", r"palliatif", r"euthanasi",
    ],
    "Securite / Justice": [
        r"s\u00e9curit\u00e9", r"securite", r"justice", r"p\u00e9nal", r"penal",
        r"police", r"gendarmerie", r"d\u00e9linquance", r"delinquance",
        r"terroris", r"prison", r"d\u00e9tention", r"detention",
        r"magistrat", r"judiciaire", r"criminalit",
        r"garde.\u00e0.vue", r"narcotrafic", r"trafic", r"drogue",
    ],
    "Education / Recherche": [
        r"\u00e9ducation", r"education", r"scolaire", r"\u00e9cole", r"ecole",
        r"universit", r"enseignement", r"recherche.scientif",
        r"professeur", r"lyc\u00e9e", r"lycee", r"coll\u00e8ge", r"college",
        r"\u00e9tudiant", r"baccalaur", r"brevet",
    ],
    "Environnement / Energie": [
        r"environnement", r"\u00e9cologi", r"ecologi", r"climat",
        r"\u00e9nergie", r"energie", r"renouvelable", r"nucl\u00e9aire", r"nucleaire",
        r"carbone", r"pollution", r"biodiversit", r"eau",
        r"d\u00e9veloppement.durable", r"transition.\u00e9nerg",
        r"pesticide", r"d\u00e9chet", r"recyclage",
    ],
    "Budget / Finances": [
        r"budget", r"financ", r"fiscal", r"imp\u00f4t", r"impot", r"taxe",
        r"PLF\b", r"PLFR", r"loi de finances", r"dette",
        r"d\u00e9pense", r"depense", r"recette", r"cr\u00e9dit",
        r"programmation.des.finances", r"TVA", r"contribution",
    ],
    "Immigration": [
        r"immigra", r"asile", r"\u00e9tranger", r"etranger", r"migra",
        r"naturalisation", r"r\u00e9fugi\u00e9", r"refugie", r"fronti\u00e8re",
        r"titre.de.s\u00e9jour", r"visa", r"expulsion",
    ],
    "Europe / International": [
        r"europ\u00e9en", r"europeen", r"trait\u00e9", r"traite",
        r"international", r"coop\u00e9ration", r"cooperation",
        r"diplomati", r"convention.international",
        r"accord.international", r"ratification",
        r"Nations.Unies", r"OTAN", r"Ukraine", r"aide.au.d\u00e9veloppement",
    ],
    "Agriculture / Alimentation": [
        r"agricol", r"agricult", r"alimenta", r"p\u00eache", r"peche",
        r"PAC\b", r"exploitation.agricol", r"fermier", r"paysan",
        r"viticul", r"elevage", r"\u00e9levage", r"\bvin\b",
    ],
    "Logement / Urbanisme": [
        r"logement", r"habitation", r"loyer", r"HLM", r"urbanis",
        r"immobilier", r"construction", r"propri\u00e9taire",
        r"locataire", r"copropri\u00e9t\u00e9", r"APL",
    ],
    "Culture / Medias": [
        r"cultur", r"audiovisuel", r"m\u00e9dia", r"media",
        r"patrimoine", r"mus\u00e9e", r"musee", r"cin\u00e9ma", r"cinema",
        r"livre\b", r"spectacle", r"artiste", r"cr\u00e9ation.artistique",
    ],
    "Numerique / Donnees": [
        r"num\u00e9rique", r"numerique", r"donn\u00e9es", r"donnees",
        r"internet", r"intelligence.artificielle",
        r"cybern\u00e9tique", r"cyber", r"t\u00e9l\u00e9commun", r"telecommun",
    ],
    "Transports / Infrastructures": [
        r"transport", r"ferroviaire", r"SNCF", r"a\u00e9roport", r"aeroport",
        r"autoroute", r"mobilit", r"routier", r"v\u00e9lo",
        r"infrastructure", r"LGV", r"TGV",
    ],
    "Defense / Armee": [
        r"d\u00e9fense", r"defense", r"arm\u00e9e", r"armee", r"militaire",
        r"programmation.militaire", r"ancien.combattant",
        r"loi.de.programmation.militaire", r"LPM",
    ],
    "Institutions / Constitution": [
        r"constitution", r"r\u00e9forme.institutionn", r"referendum",
        r"r\u00e9f\u00e9rendum", r"\u00e9lection", r"election", r"\u00e9lectoral",
        r"scrutin.proportionnel", r"s\u00e9nat", r"49.3", r"49-3",
        r"dissolution", r"motion.de.censure", r"confiance",
        r"article 49", r"r\u00e8glement.de.l.Assembl",
    ],
    "Social / Solidarite": [
        r"solidarit", r"handicap", r"d\u00e9pendance", r"dependance",
        r"exclusion", r"pauvret\u00e9", r"pauvrete", r"RSA",
        r"\u00e9galit\u00e9", r"egalite", r"discrimination",
        r"femme", r"gender", r"genre\b", r"violences.conjug",
        r"protection.de.l.enfance", r"aide.sociale",
    ],
    "Outre-mer": [
        r"outre.mer", r"Nouvelle.Cal\u00e9donie", r"Mayotte", r"Guadeloupe",
        r"Martinique", r"R\u00e9union", r"Guyane", r"Polyn\u00e9sie",
        r"Wallis", r"Saint.Pierre", r"Saint.Barth",
    ],
    "Procedure parlementaire": [
        r"motion.de.renvoi", r"motion.de.rejet", r"question.pr\u00e9alable",
        r"motion.r\u00e9f\u00e9rendaire", r"motion referendaire",
        r"l\u00e8ve.la.s\u00e9ance", r"suspension.de.s\u00e9ance",
        r"ordre.du.jour", r"rappel.au.r\u00e8glement",
        r"commission.sp\u00e9ciale", r"irrecevabilit",
        r"exception.d.irrecevabilit",
    ],
}


def classify_title(titre: str) -> str:
    """Classifie un titre de scrutin par mots-cles."""
    if not titre or not isinstance(titre, str):
        return "Autre"

    titre_lower = titre.lower()
    scores = {}

    for theme, keywords in THEME_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if re.search(kw, titre_lower):
                score += 1
        if score > 0:
            scores[theme] = score

    if not scores:
        return "Autre"

    return max(scores, key=scores.get)


# ============================================================
# Classification de l'IMPACT SOCIAL de chaque scrutin
# ============================================================
# On analyse le titre pour determiner si la mesure votee va dans le sens :
#   - "Progressif" : etend des droits, augmente des aides, protege des personnes
#   - "Restrictif" : reduit des droits, durcit des regles, coupe des aides
#   - "Neutre"     : technique, procedural, ou impossible a determiner
#
# IMPORTANT : "amendement de suppression" est un piege.
# Supprimer un article d'une loi progressiste = geste restrictif.
# Supprimer un article d'une loi restrictive = geste progressiste.
# On gere ca en detectant le sens de la loi parente.

# Mots-cles indiquant que la LOI va dans un sens progressiste/social
LOI_PROGRESSISTE_KW = [
    r"visant \u00e0 prot[e\u00e9]ger", r"visant \u00e0 renforcer", r"visant \u00e0 am[e\u00e9]liorer",
    r"visant \u00e0 garantir", r"visant \u00e0 assurer", r"visant \u00e0 favoriser",
    r"visant \u00e0 cr[e\u00e9]er", r"visant \u00e0 \u00e9tendre", r"visant \u00e0 pr[e\u00e9]server",
    r"visant \u00e0 valoriser", r"visant \u00e0 d[e\u00e9]fendre",
    r"visant \u00e0 r[e\u00e9]duire.*frais", r"visant \u00e0 r[e\u00e9]duire.*in[e\u00e9]galit",
    r"visant \u00e0 lutter contre.*pr[e\u00e9]carit", r"visant \u00e0 lutter contre.*discrimin",
    r"visant \u00e0 lutter contre.*pauvret",
    r"portant cr[e\u00e9]ation d.un", r"portant revalorisation",
    r"droit \u00e0 l.aide", r"droit au logement", r"droit \u00e0 la sant",
    r"accompagnement.*palliatif", r"soins palliatif",
    r"protection.*enfan", r"protection.*consommat", r"protection.*donn[e\u00e9]es",
    r"statut de l.\u00e9lu", r"statut.*travailleur",
    r"revalorisation.*salaire", r"revalorisation.*pension", r"revalorisation.*allocation",
    r"augmentation.*SMIC", r"augmentation.*minimum",
    r"\u00e9galit[e\u00e9].*femme", r"\u00e9galit[e\u00e9].*salariale", r"\u00e9galit[e\u00e9].*professionn",
    r"r[e\u00e9]gulation.*meubl", r"encadr.*loyer",
    r"acc\u00e8s.*soin", r"acc\u00e8s.*logement", r"acc\u00e8s.*\u00e9ducation",
    r"transition [e\u00e9]cologique", r"transition [e\u00e9]nerg[e\u00e9]tique",
    r"service public", r"h\u00f4pital public",
    r"interdire.*vapotage", r"interdire.*pesticide",
    r"r[e\u00e9]duire.*frais bancaire",
    r"lutte contre.*\u00e9vasion.fiscal", r"lutte contre.*fraude.fiscal",
    r"pouvoir d.achat",
]

# Mots-cles indiquant que la LOI va dans un sens restrictif/securitaire/d'austerite
LOI_RESTRICTIVE_KW = [
    r"visant \u00e0 contr\u00f4ler", r"visant \u00e0 durcir", r"visant \u00e0 restreindre",
    r"visant \u00e0 limiter.*immigration", r"visant \u00e0 limiter.*asile",
    r"visant \u00e0 lutter contre.*immigration", r"ma\u00eetrise.*immigration",
    r"visant \u00e0 r[e\u00e9]primer", r"visant \u00e0 sanctionner",
    r"visant \u00e0 faire ex[e\u00e9]cuter les peines",
    r"contr\u00f4le.*\u00e9tranger", r"obligation de quitter",
    r"durcissement", r"d[e\u00e9]ch[e\u00e9]ance",
    r"r[e\u00e9]duction.*d[e\u00e9]pense", r"r[e\u00e9]duction.*d[e\u00e9]ficit",
    r"ma\u00eetrise.*d[e\u00e9]pense",
    r"s[e\u00e9]curit[e\u00e9] int[e\u00e9]rieure", r"s[e\u00e9]curit[e\u00e9] globale",
    r"narcotrafic", r"lutte contre.*trafic",
    r"expulsion", r"r[e\u00e9]tention.*administrativ",
    r"surveillance", r"vid[e\u00e9]oprotection", r"vid[e\u00e9]osurveillance",
    r"simplification.*vie.\u00e9conomique",
    r"report.*\u00e2ge", r"recul.*\u00e2ge.*retraite", r"allongement.*dur[e\u00e9]e.*cotisation",
]


def classify_impact_title_only(titre: str) -> tuple[str, str]:
    """Classifie par mots-cles du titre seul. Retourne (impact, methode).

    Pour les amendements ordinaires, on retire le nom de la loi parente
    du titre avant le matching, car le nom de la loi ne dit pas dans quel
    sens va l'amendement (ex: un amendement restrictif a une loi progressive).
    Exception : les amendements de suppression et motions de rejet, ou le
    sens de la loi est necessaire pour l'inversion.
    """
    if not titre or not isinstance(titre, str):
        return "Neutre", "aucun"

    titre_lower = titre.lower()
    is_amendment = bool(re.search(r"l.amendement\b|le sous-amendm", titre_lower))
    is_suppression = bool(re.search(r"amendement de suppression", titre_lower))
    is_motion_rejet = bool(re.search(
        r"motion de rejet|motion de renvoi|question pr[eé]alable|exception d.irrecevabilit",
        titre_lower,
    ))

    # Pour les amendements ordinaires (pas suppression), retirer la reference
    # a la loi parente pour eviter de deduire l'impact du nom de la loi
    if is_amendment and not is_suppression:
        titre_for_kw = re.sub(
            r"\b(?:de la |du |de l.)"
            r"(?:proposition de loi|projet de loi|proposition de r[eé]solution)\b.*$",
            "", titre_lower,
        )
    else:
        titre_for_kw = titre_lower

    score_prog = sum(1 for kw in LOI_PROGRESSISTE_KW if re.search(kw, titre_for_kw))
    score_restr = sum(1 for kw in LOI_RESTRICTIVE_KW if re.search(kw, titre_for_kw))

    if score_prog == 0 and score_restr == 0:
        return "Neutre", "titre_aucun_signal"

    if score_prog > score_restr:
        sens_loi = "Progressif"
    elif score_restr > score_prog:
        sens_loi = "Restrictif"
    else:
        return "Neutre", "titre_egal"

    if is_suppression or is_motion_rejet:
        return ("Restrictif" if sens_loi == "Progressif" else "Progressif"), "titre_inverse"

    return sens_loi, "titre"


# Mots-cles progressistes dans l'expose des motifs (ou dispositif) de l'amendement
EXPOSE_PROGRESSIF_KW = [
    # Solidarite / justice sociale
    r"justice sociale", r"solidarit[eé]", r"prot[eé]ger les plus",
    r"int[eé]r[eê]t g[eé]n[eé]ral", r"bien commun", r"dignit[eé]",
    r"injustice", r"in[eé]quit[eé]",
    # Pouvoir d'achat / conditions de vie
    r"pouvoir d.achat", r"revalorisation", r"indexation.*inflation",
    r"augmentation.*minimum", r"augmentation.*salaire",
    r"conditions de travail", r"conditions de vie",
    r"gratuit[eé]", r"acc[eè]s universel",
    # Acces aux droits
    r"droit [aà]", r"droit fondamental", r"droits? des? salari[eé]",
    r"droits? des? travaill", r"acc[eè]s aux soins", r"acc[eè]s au logement",
    r"acc[eè]s [aà] l.[eé]ducation", r"acc[eè]s [aà] l.emploi",
    # Services publics / protection
    r"service public", r"services publics", r"h[oô]pital public",
    r"protection.*consommateur", r"protection.*salari[eé]",
    r"protection.*locataire", r"protection sociale",
    r"renforcer.*protection", r"garantir.*acc[eè]s",
    r"prise en charge", r"couverture.*maladie",
    # Populations vulnerables
    r"pr[eé]carit[eé]", r"in[eé]galit[eé]", r"plus modestes",
    r"plus fragiles", r"plus vuln[eé]rables", r"plus pr[eé]caires",
    r"plus d[eé]munis", r"personnes [aâ]g[eé]es", r"personnes handicap[eé]es",
    r"personnes en situation de handicap", r"minima sociaux",
    r"classes? populaires?", r"sans.abri", r"sans.domicile",
    # Ecologie / transition
    r"urgence sociale", r"urgence climatique", r"transition [eé]cologique",
    r"transition [eé]nerg[eé]tique", r"pr[eé]vention",
    r"sant[eé] publique", r"sant[eé] environnement",
    # Fiscalite progressive
    r"lutte contre.*[eé]vasion fiscal", r"lutte contre.*fraude",
    r"taxe.*superprofits", r"taxe.*transactions financi",
    r"imposition.*fortune", r"justice fiscale",
    r"contribution.*plus riches", r"contribution.*hauts? revenus?",
    # Encadrement / regulation
    r"encadrement.*loyer", r"r[eé]gulation", r"encadrement.*prix",
    r"contr[oô]le.*profit", r"transparence.*r[eé]mun[eé]ration",
    # Verbes d'action progressiste (dans l'expose)
    r"vise [àa] garantir", r"vise [àa] renforcer",
    r"vise [àa] prot[eé]ger", r"vise [àa] am[eé]liorer",
    r"vise [àa] permettre", r"vise [àa] cr[eé]er",
    r"vise [àa] [eé]largir", r"vise [àa] r[eé]tablir",
    r"vise [àa] pr[eé]server", r"vise [àa] d[eé]fendre",
    r"vise [àa] assurer", r"vise [àa] favoriser",
    r"vise [àa] valoriser",
]

EXPOSE_RESTRICTIF_KW = [
    # Austerite / reduction depenses
    r"ma[iî]trise.*d[eé]pense", r"r[eé]duction.*d[eé]ficit",
    r"r[eé]duction.*d[eé]pense", r"r[eé]duire.*d[eé]pense",
    r"r[eé]duire.*co[uû]t", r"r[eé]duire.*endettement",
    r"d[eé]pense publique", r"effort budg[eé]taire", r"effort financ",
    r"discipline budg[eé]taire", r"rationalisation",
    r"[eé]conomies budg[eé]taires", r"d[eé]gager.*[eé]conomie",
    r"plafonnement.*d[eé]pense", r"gel.*prestation",
    # Liberalisation / competitivite
    r"comp[eé]titivit[eé]", r"attractivit[eé]", r"lib[eé]ralisation",
    r"simplification.*administrative", r"simplification.*norme",
    r"all[eé]gement.*charge", r"all[eé]gement.*fiscal",
    r"suppression.*taxe", r"suppression.*imp[oô]t",
    r"d[eé]r[eé]glementation", r"flexibilit[eé].*travail",
    r"flexibilit[eé].*emploi", r"assouplissement",
    # Immigration / securite
    r"contr[oô]le.*immigration", r"expulsion", r"OQTF",
    r"durcir.*peine", r"alourdir.*sanction", r"r[eé]cidive",
    r"surveillance", r"vid[eé]oprotection", r"vid[eé]osurveillance",
    r"renforcement.*s[eé]curit[eé]", r"renforcement.*contr[oô]le",
    r"d[eé]ch[eé]ance", r"restriction",
    # Reduction des aides
    r"plafonnement.*aide", r"conditionnement.*allocation",
    r"d[eé]gressivit[eé]", r"suppression.*emploi",
    r"gel.*allocation",
    # Verbes d'action restrictive (dans l'expose)
    r"vise [àa] restreindre", r"vise [àa] limiter",
    r"vise [àa] contr[oô]ler", r"vise [àa] durcir",
    r"vise [àa] sanctionner", r"vise [àa] r[eé]primer",
]


def classify_impact(titre: str, expose: str, groupe_auteur: str,
                    votes_row: dict | None = None,
                    dispositif: str = "") -> tuple[str, str, str]:
    """Classification hybride de l'impact social.

    Utilise 2 signaux textuels uniquement (pas de signal politique
    pour eviter le biais circulaire) :
    1. Mots-cles du titre
    2. Mots-cles de l'expose des motifs + dispositif (contenu reel)

    Retourne : (impact, confiance, methode)
    """
    # Signal 1 : titre
    impact_titre, methode_titre = classify_impact_title_only(titre)

    # Signal 2 : expose des motifs + dispositif combines
    if not isinstance(expose, str):
        expose = ""
    if not isinstance(dispositif, str):
        dispositif = ""
    texte_complet = (expose + " " + dispositif).lower()
    score_exp_prog = sum(1 for kw in EXPOSE_PROGRESSIF_KW if re.search(kw, texte_complet))
    score_exp_restr = sum(1 for kw in EXPOSE_RESTRICTIF_KW if re.search(kw, texte_complet))

    impact_expose = "Neutre"
    if score_exp_prog > score_exp_restr:
        impact_expose = "Progressif"
    elif score_exp_restr > score_exp_prog:
        impact_expose = "Restrictif"

    # -- Fusion des 2 signaux --
    signals = []
    if impact_titre != "Neutre":
        signals.append(impact_titre)
    if impact_expose != "Neutre":
        signals.append(impact_expose)

    if not signals:
        return "Neutre", "basse", "aucun_signal"

    # Compter les votes
    nb_prog = signals.count("Progressif")
    nb_restr = signals.count("Restrictif")

    if nb_prog > nb_restr:
        impact = "Progressif"
    elif nb_restr > nb_prog:
        impact = "Restrictif"
    else:
        # Egalite : prioriser l'expose (contenu reel) > titre
        if impact_expose != "Neutre":
            impact = impact_expose
        else:
            impact = impact_titre

    # Confiance
    if len(signals) == 2 and (nb_prog == 2 or nb_restr == 2):
        confiance = "haute"  # Les 2 signaux concordent
    elif len(signals) == 2:
        confiance = "moyenne"  # Signaux mixtes (expose priorise)
    else:
        confiance = "basse"  # Un seul signal

    methode = f"titre={impact_titre},expose={impact_expose}"
    return impact, confiance, methode


# ============================================================
# Extraction de la loi parente depuis le titre du scrutin
# ============================================================

def extract_loi_parente(titre: str) -> str:
    """Extrait le nom de la loi parente depuis le titre du scrutin."""
    if not titre or not isinstance(titre, str):
        return ""

    # Patterns pour extraire la reference a la loi
    patterns = [
        # "du projet de loi de finances pour 2025"
        r"(?:du |de la |de l.)(projet de loi (?:de |d.|portant |relatif |organique ).+?)(?:\s*\(|$|\.?\s*$)",
        # "de la proposition de loi visant a..."
        r"(?:du |de la |de l.)(proposition de loi (?:visant [aà]|relative [aà]|portant |d.|organique ).+?)(?:\s*\(|$|\.?\s*$)",
        # "du projet de loi X" (sans qualificatif)
        r"(?:du |de la |de l.)(projet de loi [^(,]+?)(?:\s*\(|$|\.?\s*$)",
        # "de la proposition de loi X" (sans qualificatif)
        r"(?:du |de la |de l.)(proposition de loi [^(,]+?)(?:\s*\(|$|\.?\s*$)",
        # "de la proposition de resolution"
        r"(?:du |de la |de l.)(proposition de r[eé]solution [^(,]+?)(?:\s*\(|$|\.?\s*$)",
    ]

    for pattern in patterns:
        m = re.search(pattern, titre, re.IGNORECASE)
        if m:
            loi = m.group(1).strip()
            # Nettoyer
            loi = re.sub(r"\s*\(.*$", "", loi)  # supprimer parentheses
            loi = re.sub(r",\s*$", "", loi)  # supprimer virgule finale
            loi = re.sub(r"\s*(premi[eè]re|deuxi[eè]me|troisi[eè]me|nouvelle)\s+lecture\s*", "", loi, flags=re.IGNORECASE)
            loi = loi.strip().rstrip(".")
            if len(loi) > 10:  # eviter les faux positifs trop courts
                return loi
    return ""


# ============================================================
# Classification par DOCTRINE ECONOMIQUE
# ============================================================

DOCTRINE_LIBERAL_KW = [
    r"simplification.*(administrative|r[eé]glementation|norme|d[eé]marche|bureaucra)",
    r"all[eéè]gement.*charges?", r"comp[eé]titivit[eé]",
    r"privatisation", r"lib[eé]ralisation", r"flexibilit[eé].*travail",
    r"ouverture.*capital", r"libert[eé].*entreprendre", r"attractivit[eé]",
    r"r[eé]duction.*cotisation", r"baisse.*imp[oô]t",
    r"d[eé]r[eé]glementation",
    r"initiative priv[eé]e", r"alloc.*d[eé]gressive", r"plafonnement.*indemnit",
    r"suppression.*taxe", r"suppression.*imp[oô]t", r"zone franche",
    r"d[eé]fiscalisation",
    r"libre.[eé]change", r"march[eé].*lib[eé]r",
    r"ouverture.*concurrence", r"libre.*concurrence", r"mise en concurrence",
    # Keywords retires car bidirectionnels (apparaissent autant pour creer
    # que pour supprimer un mecanisme) : exoneration, credit d'impot
]

DOCTRINE_INTERVENTIONNISTE_KW = [
    r"nationalisation", r"r[eé]gulation", r"encadrement.*prix",
    r"contr[oô]le.*[eéÉ]tat", r"intervention.*[eéÉ]tat",
    r"service public", r"monopole public", r"secteur strat[eé]gique",
    r"planification", r"bien commun", r"int[eé]r[eê]t g[eé]n[eé]ral",
    r"op[eé]rateur public", r"r[eé]gie", r"cadre r[eé]glementaire renforc",
    r"mission de service public", r"patrimoine public",
    r"interdiction.*sp[eé]culation", r"encadrement.*march[eé]",
    r"taxe.*superprofits", r"taxe.*transactions financi",
    # Contre-signaux : supprimer/limiter un mecanisme liberal = interventionniste
    r"supprim.*exon[eé]ration", r"supprim.*cr[eé]dit d.imp[oô]t",
    r"supprim.*niche", r"abroge.*exon[eé]ration",
    r"plafonne.*exon[eé]ration", r"plafonne.*niche",
    r"augment.*imp[oô]t", r"hausse.*imp[oô]t", r"hausse.*taxe",
    r"cr[eé]ation.*taxe", r"instaur.*taxe", r"contribution.*exceptionnelle",
    r"progressivit[eé].*imp[oô]t", r"justice fiscal",
    r"niche.*fiscal.*supprim", r"niche.*fiscal.*plafon",
]

DOCTRINE_SOCIAL_KW = [
    r"revalorisation.*SMIC", r"pouvoir d.achat", r"salaire minimum",
    r"protection.*locataire", r"encadrement.*loyer",
    r"allocation.*ch[oô]mage", r"minimum vieillesse", r"prestations? sociales?",
    r"aide.*logement", r"couverture.*maladie", r"justice sociale",
    r"lutte contre.*pauvret", r"lutte contre.*in[eé]galit",
    r"protection sociale", r"solidarit[eé]", r"gratuit[eé]",
    r"indexation.*inflation", r"revalorisation.*pension",
    r"revalorisation.*allocation", r"minima sociaux",
    r"acc[eè]s universel", r"droit [aà] l", r"RSA",
    r"compl[eé]mentaire sant[eé]", r"s[eé]curit[eé] sociale",
]

DOCTRINE_AUSTERITE_KW = [
    r"ma[iî]trise.*d[eé]pense", r"r[eé]duction.*d[eé]ficit",
    r"[eé]quilibre budg[eé]taire", r"rigueur budg[eé]taire",
    r"discipline budg[eé]taire", r"r[eé]duction.*dette",
    r"[eé]conomies? budg[eé]taires?", r"assainissement.*finances",
    r"restriction budg[eé]taire", r"effort collectif",
    r"contr[oô]le.*d[eé]penses", r"responsabilit[eé] budg[eé]taire",
    r"r[eè]gle d.or", r"d[eé]ficit z[eé]ro",
    r"trajectoire.*finances publiques", r"consolidation.*budg[eé]taire",
]


def _strip_loi_from_titre(titre_lower: str) -> str:
    """Retire le nom de la loi parente du titre d'un amendement.

    Evite de deduire la doctrine/classe du simple nom de la loi
    (ex: 'simplification de la vie economique' → Liberal pour tous les amendements).
    """
    is_amendment = bool(re.search(r"l.amendement\b|le sous-amendm", titre_lower))
    is_suppression = bool(re.search(r"amendement de suppression", titre_lower))
    if is_amendment and not is_suppression:
        return re.sub(
            r"\b(?:de la |du |de l.)"
            r"(?:proposition de loi|projet de loi|proposition de r[eé]solution)\b.*$",
            "", titre_lower,
        )
    return titre_lower


_LIBERAL_NEGATION_RE = re.compile(
    r"(?:supprim|abrog|plafonne|met(?:tre)? fin|r[eé]dui|limit|encadr)"
    r".{0,30}"
    r"(?:exon[eé]ration|cr[eé]dit d.imp[oô]t|niche|all[eè]gement|avantage fiscal)",
)


def classify_doctrine_eco(titre: str, expose: str) -> str:
    """Classifie la doctrine economique d'un scrutin."""
    if not isinstance(titre, str):
        titre = ""
    if not isinstance(expose, str):
        expose = ""

    titre_lower = _strip_loi_from_titre(titre.lower())
    expose_lower = expose.lower()

    # Detecter si l'expose parle de SUPPRIMER des mecanismes liberaux
    # (ex: "supprimer l'exoneration de cotisations") : ces keywords ne
    # doivent pas compter comme Liberal, mais comme Interventionniste.
    nb_negations = len(_LIBERAL_NEGATION_RE.findall(expose_lower))

    scores = {}
    for doctrine, keywords in [
        ("Liberal", DOCTRINE_LIBERAL_KW),
        ("Interventionniste", DOCTRINE_INTERVENTIONNISTE_KW),
        ("Social", DOCTRINE_SOCIAL_KW),
        ("Austerite", DOCTRINE_AUSTERITE_KW),
    ]:
        score = 0
        for kw in keywords:
            if re.search(kw, titre_lower):
                score += 2  # le titre compte double
            if re.search(kw, expose_lower):
                score += 1
        if score > 0:
            scores[doctrine] = score

    # Si des negations sont detectees, transferer du score Liberal vers
    # Interventionniste (chaque negation annule 2 pts de Liberal)
    if nb_negations > 0 and "Liberal" in scores:
        penalty = nb_negations * 2
        scores["Liberal"] = max(scores.get("Liberal", 0) - penalty, 0)
        scores["Interventionniste"] = scores.get("Interventionniste", 0) + penalty
        if scores["Liberal"] == 0:
            del scores["Liberal"]

    if not scores:
        return "Non economique"

    max_score = max(scores.values())
    top = [d for d, s in scores.items() if s == max_score]

    if len(top) == 1:
        return top[0]
    if len(top) >= 2:
        return "Mixte"
    return "Non economique"


# ============================================================
# Classification par CLASSE SOCIALE VISEE
# ============================================================

CLASSE_POPULAIRES_KW = [
    r"pr[eé]cari", r"ch[oô]meur", r"demandeur.*emploi",
    r"travailleur.*pauvre", r"bas salaire", r"ouvrier",
    r"exclusion sociale", r"int[eé]rim", r"revenus? modestes?",
    r"handicap", r"minima sociaux", r"RSA",
    r"aide.*mourir", r"soins palliatif", r"d[eé]pendance",
    r"personnes? [aâ]g[eé]es?", r"personnes? handicap",
    r"sans.abri", r"SDF", r"mal.log[eé]",
    r"travail temporaire", r"CDD", r"saisonnier",
]

CLASSE_MOYENNES_KW = [
    r"PME", r"artisan", r"commer[cç]ant",
    r"profession lib[eé]rale", r"auto.entrepreneur",
    r"microentreprise", r"petit.*patron", r"[eé]conomie locale",
    r"classe.*moyenne", r"propri[eé]taire.*occupant",
    r"acc[eé]dant.*propri[eé]t[eé]", r"[eé]pargne.*populaire",
    r"petit.*exploitant", r"TPE", r"commerce.*proximit[eé]",
    r"[eé]conomie.*proximit[eé]",
]

CLASSE_AISEES_KW = [
    r"grande.*entreprise", r"multinationale", r"investisseur",
    r"actionnaire", r"revenus? du capital", r"fortune",
    r"haut.*revenu", r"secteur financier", r"secteur bancaire",
    r"capital.investiss", r"superprofits?", r"dividende",
    r"soci[eé]t[eé].*cot[eé]e", r"patrimoine.*mobilier",
    r"optimisation.*fiscale", r"holding",
    r"r[eé]mun[eé]ration.*dirigeant", r"stock.option",
]

CLASSE_UNIVERSEL_KW = [
    r"tous les citoyens", r"ensemble de la population",
    r"universalit[eé]", r"[eé]galit[eé] des droits",
    r"droits? fondament", r"solidarit[eé] nationale",
    r"pour tous", r"pour chacun", r"ensemble.*fran[cç]ais",
    r"int[eé]r[eê]t g[eé]n[eé]ral", r"bien commun",
]


def classify_classe_sociale(titre: str, expose: str) -> str:
    """Classifie la classe sociale visee par un scrutin."""
    if not isinstance(titre, str):
        titre = ""
    if not isinstance(expose, str):
        expose = ""

    titre_lower = _strip_loi_from_titre(titre.lower())
    expose_lower = expose.lower()

    scores = {}
    for classe, keywords in [
        ("Populaires", CLASSE_POPULAIRES_KW),
        ("Moyennes", CLASSE_MOYENNES_KW),
        ("Aisees/Entreprises", CLASSE_AISEES_KW),
        ("Universel", CLASSE_UNIVERSEL_KW),
    ]:
        score = 0
        for kw in keywords:
            if re.search(kw, titre_lower):
                score += 2
            if re.search(kw, expose_lower):
                score += 1
        if score > 0:
            scores[classe] = score

    if not scores:
        return "Non determine"

    return max(scores, key=scores.get)


def main():
    scrutins_df = pd.read_csv(PROCESSED_DIR / "scrutins.csv", encoding="utf-8")
    print(f"[info] {len(scrutins_df)} scrutins a classifier")

    # Charger les donnees d'amendements si disponibles
    amdt_path = PROCESSED_DIR / "scrutins_amendements.csv"
    if amdt_path.exists():
        amdt_df = pd.read_csv(amdt_path, encoding="utf-8")
        amdt_map = dict(zip(amdt_df["scrutin_uid"], amdt_df.to_dict("records")))
        print(f"  {len(amdt_map)} amendements charges pour enrichissement")
    else:
        amdt_map = {}
        print("  [warn] Pas de donnees amendements. Lance enrich_amendements.py d'abord.")

    results = []
    for _, row in scrutins_df.iterrows():
        uid = row["scrutin_uid"]
        titre = row.get("titre", "") or row.get("objet", "") or ""
        theme = classify_title(titre)

        amdt = amdt_map.get(uid, {})
        expose = str(amdt.get("amdt_expose", "") or "")
        dispositif = str(amdt.get("amdt_dispositif", "") or "")
        groupe_auteur = str(amdt.get("amdt_groupe_abrege", "") or "")

        impact, confiance, methode = classify_impact(titre, expose, groupe_auteur,
                                                     dispositif=dispositif)
        loi_parente = extract_loi_parente(titre)
        expose_complet = (expose + " " + dispositif).strip()
        doctrine_eco = classify_doctrine_eco(titre, expose_complet)
        classe_sociale = classify_classe_sociale(titre, expose_complet)

        results.append({
            "scrutin_uid": uid,
            "theme": theme,
            "impact": impact,
            "confiance": confiance,
            "methode_impact": methode,
            "loi_parente": loi_parente,
            "doctrine_eco": doctrine_eco,
            "classe_sociale": classe_sociale,
        })

    themes_df = pd.DataFrame(results)
    themes_df.to_csv(THEMES_FILE, index=False, encoding="utf-8")

    # Stats
    print("\nRepartition par theme:")
    for theme, count in themes_df["theme"].value_counts().head(10).items():
        print(f"  {theme}: {count}")

    print("\nRepartition par impact:")
    for impact, count in themes_df["impact"].value_counts().items():
        print(f"  {impact}: {count}")

    print("\nRepartition par doctrine economique:")
    for doctrine, count in themes_df["doctrine_eco"].value_counts().items():
        print(f"  {doctrine}: {count}")

    print("\nRepartition par classe sociale visee:")
    for classe, count in themes_df["classe_sociale"].value_counts().items():
        print(f"  {classe}: {count}")

    # Lois parentes
    lois = themes_df[themes_df["loi_parente"] != ""]
    print(f"\nScrutins rattaches a une loi: {len(lois)} / {len(themes_df)}")
    print(f"Lois distinctes: {lois['loi_parente'].nunique()}")
    print("\nTop 10 lois (par nb de scrutins):")
    for loi, count in lois["loi_parente"].value_counts().head(10).items():
        print(f"  [{count:4d}] {loi[:100]}")

    print(f"\n[ok] {len(themes_df)} scrutins classifies -> {THEMES_FILE}")


if __name__ == "__main__":
    main()
