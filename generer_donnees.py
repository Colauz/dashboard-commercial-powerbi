"""
Génère un jeu de données commercial réaliste pour une PME de négoce
de matériel électrique (« Voltéa Distribution », 48 salariés, 3 agences).

Sortie : un schéma en étoile prêt à charger dans Power BI.

    data/dim_date.csv        calendrier continu, marqué par exercice fiscal
    data/dim_client.csv      clients B2B (installateurs, industriels, collectivités)
    data/dim_produit.csv     catalogue hiérarchisé famille > sous-famille > produit
    data/dim_commercial.csv  force de vente rattachée à une agence
    data/fait_ventes.csv     lignes de commande (grain : 1 ligne = 1 produit commandé)
    data/fait_objectifs.csv  objectifs de CA mensuels par commercial

Usage :
    python generer_donnees.py [--depuis 2024-01-01] [--jusqua 2026-09-21] [--seed 73]
"""

from __future__ import annotations

import argparse
import math
import random
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

DOSSIER_DATA = Path(__file__).parent / "data"

AGENCES = ["Chambéry", "Grenoble", "Annecy"]

# Catalogue : famille -> sous-famille -> (libellé produit, prix d'achat, taux de marge cible)
CATALOGUE = {
    "Appareillage": {
        "Disjoncteurs": [
            ("Disjoncteur modulaire 16A courbe C", 8.40, 0.38),
            ("Disjoncteur modulaire 20A courbe C", 9.10, 0.38),
            ("Disjoncteur différentiel 30mA 40A", 52.00, 0.32),
            ("Disjoncteur tétrapolaire 63A", 118.00, 0.29),
        ],
        "Coffrets": [
            ("Coffret 3 rangées 39 modules", 64.00, 0.34),
            ("Coffret étanche IP65 12 modules", 41.50, 0.36),
            ("Platine de raccordement compteur", 27.80, 0.40),
        ],
        "Prises et interrupteurs": [
            ("Prise 2P+T encastrée blanc", 3.20, 0.52),
            ("Interrupteur va-et-vient blanc", 2.90, 0.54),
            ("Prise renforcée 32A IP44", 18.60, 0.44),
        ],
    },
    "Câbles et conduits": {
        "Câbles cuivre": [
            ("Câble U-1000 R2V 3G2.5 (couronne 100m)", 128.00, 0.22),
            ("Câble U-1000 R2V 5G6 (couronne 50m)", 286.00, 0.19),
            ("Câble H07V-U 2.5 rouge (couronne 100m)", 39.00, 0.25),
        ],
        "Conduits et goulottes": [
            ("Gaine ICTA Ø20 (couronne 100m)", 22.40, 0.41),
            ("Goulotte PVC 60x40 (barre 2m)", 11.80, 0.45),
            ("Chemin de câbles fil 100mm (3m)", 34.60, 0.37),
        ],
    },
    "Éclairage": {
        "Luminaires tertiaires": [
            ("Dalle LED 600x600 36W 4000K", 42.00, 0.35),
            ("Réglette LED étanche 1500mm 50W", 38.50, 0.36),
            ("Projecteur LED 150W IP66", 76.00, 0.33),
        ],
        "Sources et commandes": [
            ("Ampoule LED E27 9W 2700K", 2.10, 0.58),
            ("Détecteur de présence plafond 360°", 44.00, 0.42),
        ],
    },
    "Énergies renouvelables": {
        "Photovoltaïque": [
            ("Panneau PV monocristallin 425Wc", 128.00, 0.21),
            ("Onduleur hybride 5kW monophasé", 940.00, 0.18),
            ("Coffret AC/DC protection PV", 186.00, 0.27),
        ],
        "Recharge véhicule": [
            ("Borne de recharge 7.4kW T2S", 486.00, 0.24),
            ("Borne de recharge 22kW pilotable", 1180.00, 0.22),
            ("Câble de recharge T2 5m 32A", 142.00, 0.31),
        ],
    },
    "Outillage et EPI": {
        "Outillage": [
            ("Pince à dénuder automatique", 24.50, 0.48),
            ("Perforateur SDS+ 800W", 168.00, 0.29),
            ("Multimètre TRMS CAT III 600V", 96.00, 0.35),
        ],
        "Protection": [
            ("Casque isolant classe 0", 38.00, 0.44),
            ("Gants isolants classe 00 (paire)", 52.00, 0.41),
        ],
    },
}

SEGMENTS = {
    # segment -> (part du portefeuille, panier moyen relatif, sensibilité remise)
    "Installateur indépendant": (0.46, 0.55, 0.03),
    "PME du bâtiment": (0.28, 1.00, 0.06),
    "Industrie": (0.14, 2.30, 0.09),
    "Collectivité": (0.08, 1.80, 0.11),
    "Grand compte": (0.04, 5.20, 0.14),
}

# Saisonnalité du négoce électrique : creux en août, pointes en juin et novembre.
SAISONNALITE = {
    1: 0.86, 2: 0.94, 3: 1.06, 4: 1.04, 5: 1.02, 6: 1.18,
    7: 0.97, 8: 0.52, 9: 1.11, 10: 1.09, 11: 1.16, 12: 0.93,
}

JOURS_FERIES_APPROX = {(1, 1), (5, 1), (5, 8), (7, 14), (8, 15), (11, 1), (11, 11), (12, 25)}


def sans_accents(texte: str) -> str:
    """Normalise pour construire des identifiants et des adresses e-mail."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def construire_dim_date(depuis: date, jusqua: date) -> pd.DataFrame:
    jours = pd.date_range(depuis, jusqua, freq="D")
    df = pd.DataFrame({"date": jours})
    df["cle_date"] = df["date"].dt.strftime("%Y%m%d").astype(int)
    df["annee"] = df["date"].dt.year
    df["trimestre"] = "T" + df["date"].dt.quarter.astype(str)
    df["mois_numero"] = df["date"].dt.month
    df["mois_nom"] = df["date"].dt.month.map({
        1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
        7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
    })
    df["annee_mois"] = df["date"].dt.strftime("%Y-%m")
    df["semaine_iso"] = df["date"].dt.isocalendar().week.astype(int)
    df["jour_semaine"] = df["date"].dt.dayofweek + 1
    df["jour_nom"] = df["date"].dt.dayofweek.map({
        0: "lundi", 1: "mardi", 2: "mercredi", 3: "jeudi",
        4: "vendredi", 5: "samedi", 6: "dimanche",
    })
    est_ferie = df["date"].apply(lambda d: (d.month, d.day) in JOURS_FERIES_APPROX)
    df["est_ouvre"] = (df["jour_semaine"] <= 5) & (~est_ferie)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def construire_dim_produit(faker: Faker) -> pd.DataFrame:
    lignes = []
    for famille, sous_familles in CATALOGUE.items():
        for sous_famille, produits in sous_familles.items():
            for libelle, cout, marge_cible in produits:
                prix_public = round(cout / (1 - marge_cible), 2)
                lignes.append({
                    "cle_produit": f"P{len(lignes) + 1:04d}",
                    "reference": f"{sans_accents(famille)[:3].upper()}-{len(lignes) + 1:04d}",
                    "libelle_produit": libelle,
                    "famille": famille,
                    "sous_famille": sous_famille,
                    "cout_achat_ht": cout,
                    "prix_catalogue_ht": prix_public,
                    "taux_tva": 0.20,
                })
    return pd.DataFrame(lignes)


def construire_dim_client(faker: Faker, nb_clients: int, depuis: date) -> pd.DataFrame:
    segments = list(SEGMENTS)
    poids = [SEGMENTS[s][0] for s in segments]
    lignes = []
    for i in range(nb_clients):
        segment = random.choices(segments, weights=poids, k=1)[0]
        agence = random.choices(AGENCES, weights=[0.45, 0.33, 0.22], k=1)[0]
        anciennete_jours = int(abs(np.random.normal(900, 700)))
        lignes.append({
            "cle_client": f"C{i + 1:05d}",
            "raison_sociale": faker.company(),
            "segment": segment,
            "agence_rattachement": agence,
            "code_postal": faker.postcode(),
            "ville": faker.city(),
            "date_entree_portefeuille": (depuis - timedelta(days=anciennete_jours)).isoformat(),
            "encours_autorise_ht": int(round(SEGMENTS[segment][1] * 4000 * random.uniform(0.6, 1.8), -2)),
        })
    return pd.DataFrame(lignes)


def construire_dim_commercial(faker: Faker) -> pd.DataFrame:
    lignes = []
    effectif = {"Chambéry": 4, "Grenoble": 3, "Annecy": 2}
    for agence, nb in effectif.items():
        for _ in range(nb):
            prenom, nom = faker.first_name(), faker.last_name()
            lignes.append({
                "cle_commercial": f"V{len(lignes) + 1:03d}",
                "nom_commercial": f"{prenom} {nom}",
                "email": f"{sans_accents(prenom).lower()}.{sans_accents(nom).lower()}@voltea-distribution.fr",
                "agence": agence,
                "role": "Chargé d'affaires" if len(lignes) % 4 else "Responsable d'agence",
            })
    return pd.DataFrame(lignes)


def tendance_annuelle(jour: date, depuis: date) -> float:
    """Croissance ~+9 %/an, accélérée sur les familles liées à la transition énergétique."""
    annees = (jour - depuis).days / 365.25
    return (1.09 ** annees)


def construire_faits(
    dim_date: pd.DataFrame,
    dim_client: pd.DataFrame,
    dim_produit: pd.DataFrame,
    dim_commercial: pd.DataFrame,
    depuis: date,
) -> pd.DataFrame:
    jours_ouvres = dim_date[dim_date["est_ouvre"]].copy()
    produits = dim_produit.to_dict("records")
    clients = dim_client.to_dict("records")

    # Un commercial par agence pour router les commandes.
    par_agence: dict[str, list[dict]] = {a: [] for a in AGENCES}
    for v in dim_commercial.to_dict("records"):
        par_agence[v["agence"]].append(v)

    # Loi de Pareto : quelques clients pèsent l'essentiel du CA.
    intensite_client = {c["cle_client"]: np.random.pareto(1.4) + 0.25 for c in clients}

    lignes = []
    numero_commande = 1
    for _, jour in jours_ouvres.iterrows():
        d = date.fromisoformat(jour["date"])
        facteur = SAISONNALITE[d.month] * tendance_annuelle(d, depuis)
        # Creux de fin de semaine, pointe du mardi au jeudi.
        facteur *= {1: 1.02, 2: 1.08, 3: 1.06, 4: 1.00, 5: 0.84}[jour["jour_semaine"]]
        nb_commandes = max(1, int(np.random.poisson(26 * facteur)))

        for _ in range(nb_commandes):
            client = random.choices(clients, weights=[intensite_client[c["cle_client"]] for c in clients], k=1)[0]
            segment = client["segment"]
            _, panier_relatif, sensibilite = SEGMENTS[segment]
            vendeurs = par_agence[client["agence_rattachement"]]
            vendeur = random.choice(vendeurs)

            nb_lignes = max(1, int(np.random.gamma(2.0, 1.4 * math.sqrt(panier_relatif))))
            canal = random.choices(["Comptoir", "Web", "Télévente"], weights=[0.52, 0.30, 0.18], k=1)[0]
            reference_commande = f"CMD{d.year}{numero_commande:06d}"
            numero_commande += 1

            for _ in range(min(nb_lignes, 12)):
                produit = random.choice(produits)
                # Les grosses références partent à l'unité, la visserie par paquets.
                base_quantite = max(1, int(round(60 / max(produit["prix_catalogue_ht"], 2))))
                quantite = max(1, int(np.random.poisson(base_quantite * panier_relatif ** 0.4)))

                remise = min(0.35, max(0.0, np.random.normal(sensibilite, 0.035)))
                if canal == "Web":
                    remise = max(0.0, remise - 0.015)  # moins de négociation en ligne
                prix_unitaire = round(produit["prix_catalogue_ht"] * (1 - remise), 2)

                ca_ht = round(prix_unitaire * quantite, 2)
                cout_total = round(produit["cout_achat_ht"] * quantite, 2)
                lignes.append({
                    "cle_ligne": len(lignes) + 1,
                    "numero_commande": reference_commande,
                    "cle_date": jour["cle_date"],
                    "cle_client": client["cle_client"],
                    "cle_produit": produit["cle_produit"],
                    "cle_commercial": vendeur["cle_commercial"],
                    "canal": canal,
                    "quantite": quantite,
                    "prix_unitaire_ht": prix_unitaire,
                    "taux_remise": round(remise, 4),
                    "ca_ht": ca_ht,
                    "cout_achat_total_ht": cout_total,
                })
    return pd.DataFrame(lignes)


def construire_objectifs(faits: pd.DataFrame, dim_date: pd.DataFrame, dim_commercial: pd.DataFrame) -> pd.DataFrame:
    """Objectifs = réalisé N-1 revalorisé, bruité — comme une vraie lettre d'objectifs."""
    jointure = faits.merge(dim_date[["cle_date", "annee", "mois_numero", "annee_mois"]], on="cle_date")
    reel = jointure.groupby(["cle_commercial", "annee", "mois_numero"], as_index=False)["ca_ht"].sum()

    lignes = []
    for _, row in reel.iterrows():
        cible = row["ca_ht"] * random.uniform(0.86, 1.08)
        lignes.append({
            "cle_commercial": row["cle_commercial"],
            "annee": int(row["annee"]),
            "mois_numero": int(row["mois_numero"]),
            "annee_mois": f"{int(row['annee'])}-{int(row['mois_numero']):02d}",
            "objectif_ca_ht": round(cible, -2),
        })
    return pd.DataFrame(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depuis", default="2024-01-01", type=date.fromisoformat)
    parser.add_argument("--jusqua", default="2026-09-21", type=date.fromisoformat)
    parser.add_argument("--clients", default=420, type=int)
    parser.add_argument("--seed", default=73, type=int)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    faker = Faker("fr_FR")
    Faker.seed(args.seed)

    DOSSIER_DATA.mkdir(exist_ok=True)

    dim_date = construire_dim_date(args.depuis, args.jusqua)
    dim_produit = construire_dim_produit(faker)
    dim_client = construire_dim_client(faker, args.clients, args.depuis)
    dim_commercial = construire_dim_commercial(faker)
    faits = construire_faits(dim_date, dim_client, dim_produit, dim_commercial, args.depuis)
    objectifs = construire_objectifs(faits, dim_date, dim_commercial)

    tables = {
        "dim_date": dim_date,
        "dim_client": dim_client,
        "dim_produit": dim_produit,
        "dim_commercial": dim_commercial,
        "fait_ventes": faits,
        "fait_objectifs": objectifs,
    }
    for nom, df in tables.items():
        chemin = DOSSIER_DATA / f"{nom}.csv"
        df.to_csv(chemin, index=False, encoding="utf-8")
        print(f"{chemin.name:24s} {len(df):>8,} lignes".replace(",", " "))

    ca = faits["ca_ht"].sum()
    marge = ca - faits["cout_achat_total_ht"].sum()
    print(f"\nCA total   : {ca:>14,.0f} € HT".replace(",", " "))
    print(f"Marge brute: {marge:>14,.0f} € HT  ({marge / ca:.1%})".replace(",", " "))
    print(f"Commandes  : {faits['numero_commande'].nunique():>14,}".replace(",", " "))


if __name__ == "__main__":
    main()
