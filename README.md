# 01 — Tableau de bord commercial PME (Power BI)

Suivi du chiffre d'affaires, de la marge, des clients et de l'atteinte des objectifs
pour une PME de négoce de matériel électrique fictive — **Voltéa Distribution**,
48 salariés, 3 agences en Savoie / Isère / Haute-Savoie.

Le livrable n'est pas « un joli graphique » : c'est un **modèle de données propre**
sur lequel n'importe quelle question métier se pose en une mesure DAX lisible.

## Ce que contient le dépôt

```
generer_donnees.py      génère le schéma en étoile (Faker + numpy, seed fixé)
apercu_kpi.py           recalcule les mesures en pandas — contrôle des chiffres DAX
dax/mesures.dax         38 mesures prêtes à coller dans Power BI
docs/modele-donnees.md  relations, grain, pages du rapport, pièges à éviter
docs/kpi.json           chiffres de référence produits par apercu_kpi.py
data/*.csv              les 6 tables (générées, non versionnées par défaut)
```

## Démarrer

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python generer_donnees.py          # ~2 s, écrit data/*.csv
python apercu_kpi.py               # affiche les KPI de contrôle
```

Puis dans Power BI Desktop : *Obtenir les données > Texte/CSV*, charger les six
fichiers de `data/`, créer les relations décrites dans `docs/modele-donnees.md`,
et coller les mesures de `dax/mesures.dax`.

## Le jeu de données

2,7 ans d'historique (janvier 2024 → septembre 2026), **51 000 lignes de commande**,
**13,5 M€ de CA HT**, 420 clients, 32 références.

Il n'est pas tiré au hasard uniforme — c'est ce qui le rend utile pour tester un
rapport. Ce qui y est modélisé :

| Phénomène | Traduction dans les données |
|---|---|
| Saisonnalité du négoce | Creux à 52 % en août, pointes en juin et novembre |
| Rythme hebdomadaire | Mardi–jeudi chargés, vendredi à −16 % |
| Croissance | +9 %/an, tirée par le photovoltaïque et la recharge VE |
| Concentration | Loi de Pareto : **113 clients (27 %) font 80 % du CA** |
| Structure de marge | 58 % sur la visserie, 18 % sur les onduleurs — la marge et le CA ne classent pas les produits dans le même ordre |
| Remise | Négociée selon le segment, réduite de 1,5 pt sur le canal web |

C'est précisément cette structure qui fait dire quelque chose au rapport : sans
Pareto, le graphique « top clients » est plat et n'alerte sur rien.

## Chiffres de contrôle

| Mesure | Valeur |
|---|---|
| CA HT | 13 483 511 € |
| Marge brute | 2 771 994 € (20,6 %) |
| Commandes | 19 734 |
| Panier moyen | 683 € |
| Croissance 12 mois glissants | +11,2 % |
| Objectifs mensuels tenus | 63 % |

`apercu_kpi.py` recalcule ces valeurs en pandas. Toute mesure DAX qui s'en écarte
est fausse — c'est le test de non-régression du modèle.

## Points techniques qui méritent un coup d'œil

- **`fait_objectifs` a un grain plus grossier que `fait_ventes`** (mois × commercial contre
  ligne de commande). Le relier directement à `dim_date` est impossible ; la table
  `dim_mois` dérivée en DAX résout l'ambiguïté sans relation bidirectionnelle.
- **La remise moyenne est pondérée par le CA.** Une moyenne arithmétique des taux
  donne un chiffre exact et dépourvu de sens : elle met une remise sur une boîte de
  prises au même poids qu'une remise sur un onduleur vendu 1 146 €.
- **Clients perdus / gagnés** calculés par différence d'ensembles (`EXCEPT`) sur deux
  fenêtres glissantes de 12 mois, pas par un « dernier achat > 12 mois » qui casse
  dès qu'on filtre une agence.
- **Séparation calcul / présentation** : `Couleur atteinte` et `Libellé évolution CA`
  sont des mesures à part, pour que la logique d'affichage ne contamine pas les agrégats.

## Limites assumées

Les données sont synthétiques. Le générateur reproduit la *structure* d'un fichier
de ventes réel (concentration, saisonnalité, dispersion des marges), pas les données
d'un client. Le fichier `.pbix` n'est pas fourni : Power BI Desktop est requis pour
le construire, et le modèle est entièrement décrit dans `docs/modele-donnees.md`.

---

Projet du portfolio de **Laurian Jamin** — data, automatisation et IA appliquée pour les PME.  
Portfolio : <https://colauz.github.io/Portfolio/> · Malt : <https://www.malt.fr/profile/laurianjamin>
