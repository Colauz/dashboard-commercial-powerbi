# Modèle de données — schéma en étoile

Un seul grain de fait, quatre dimensions conformes, aucune relation bidirectionnelle.
C'est le modèle qui rend les mesures DAX lisibles : tout filtre part d'une dimension
et descend vers le fait.

```
                       ┌──────────────┐
                       │   dim_date   │  ← table marquée comme table de dates
                       └──────┬───────┘
                              │ 1..*
       ┌──────────────┐       │        ┌──────────────────┐
       │  dim_client  ├───────┼────────┤  dim_commercial  │
       └──────────────┘  1..* │  1..*  └────────┬─────────┘
                       ┌──────┴───────┐         │ 1..*
                       │ fait_ventes  │         │
                       └──────┬───────┘   ┌─────┴──────────┐
                              │ 1..*      │ fait_objectifs │
                       ┌──────┴───────┐   └────────────────┘
                       │ dim_produit  │
                       └──────────────┘
```

## Grain

| Table | Grain | Lignes |
|---|---|---|
| `fait_ventes` | une ligne de commande (1 produit sur 1 commande) | ~51 000 |
| `fait_objectifs` | un objectif de CA mensuel par commercial | ~300 |

`fait_objectifs` est un fait de granularité plus grossière (mois × commercial).
Il se relie à `dim_date` par `annee_mois` et non par `cle_date` — d'où la table
intermédiaire décrite plus bas.

## Relations à créer dans Power BI

| De | Vers | Cardinalité | Sens du filtre |
|---|---|---|---|
| `fait_ventes[cle_date]` | `dim_date[cle_date]` | * → 1 | Simple |
| `fait_ventes[cle_client]` | `dim_client[cle_client]` | * → 1 | Simple |
| `fait_ventes[cle_produit]` | `dim_produit[cle_produit]` | * → 1 | Simple |
| `fait_ventes[cle_commercial]` | `dim_commercial[cle_commercial]` | * → 1 | Simple |
| `fait_objectifs[cle_commercial]` | `dim_commercial[cle_commercial]` | * → 1 | Simple |
| `fait_objectifs[annee_mois]` | `dim_mois[annee_mois]` | * → 1 | Simple |

### Pourquoi une table `dim_mois`

Relier directement `fait_objectifs` à `dim_date` est impossible : un objectif
mensuel n'a pas de date. La solution propre est une dimension mois dérivée,
créée en DAX :

```dax
dim_mois =
SUMMARIZE (
    dim_date,
    dim_date[annee_mois],
    dim_date[annee],
    dim_date[mois_numero],
    dim_date[mois_nom]
)
```

`dim_mois` se relie ensuite à `dim_date[annee_mois]` (1 → *), ce qui propage
correctement un filtre de période vers les objectifs sans créer de relation
ambiguë.

## Étapes de mise en place

1. **Charger** les six CSV depuis `data/` (Power Query : *Obtenir les données > Texte/CSV*).
2. **Typer** les colonnes : `date` en Date, `cle_date` en Nombre entier,
   les montants en Nombre décimal fixe, `est_ouvre` en Booléen.
3. **Marquer** `dim_date` comme table de dates (*Outils de table > Marquer comme table de dates*,
   colonne `date`). Sans cela, `DATEADD`, `TOTALYTD` et `DATESINPERIOD` renvoient des résultats faux.
4. **Masquer** toutes les colonnes de clés (`cle_*`) dans la vue Rapport : elles servent au
   moteur, pas à l'utilisateur.
5. **Créer** une table vide `_Mesures` (*Entrer des données*, table à une colonne vide,
   colonne masquée) et y déplacer toutes les mesures de `dax/mesures.dax`.
6. **Trier** `dim_date[mois_nom]` par `dim_date[mois_numero]`, sinon l'axe s'affiche
   par ordre alphabétique (avril, août, décembre…).

## Pages du rapport

| Page | Question à laquelle elle répond | Visuels |
|---|---|---|
| **Pilotage** | Où en est-on par rapport à l'an dernier et à l'objectif ? | 4 cartes KPI, courbe CA / CA N-1, jauge d'atteinte, sélecteur d'exercice |
| **Clients** | Sur qui repose le chiffre ? | Pareto CA cumulé, tableau top 20 avec marge, matrice segment × agence, clients perdus |
| **Produits** | Qu'est-ce qui fait la marge ? | Treemap famille / sous-famille, nuage CA × taux de marge, top/flop 10 références |
| **Équipe** | Qui tient ses objectifs ? | Barres commercial × atteinte, small multiples mensuels, remise moyenne accordée |
| **Mobile** | Les 3 chiffres à voir depuis le terrain | Mise en page mobile dédiée : CA du mois, atteinte, top 5 clients |

## Bonnes pratiques appliquées

- **Aucun `CALCULATE` implicite dans les visuels** : chaque agrégat passe par une mesure nommée,
  ce qui rend le rapport lisible et refactorable.
- **`DIVIDE` systématique** plutôt que `/` : pas de `#DIV/0!` quand un objectif est absent.
- **Remise moyenne pondérée par le CA**, pas moyenne arithmétique des taux — une moyenne
  simple donne un chiffre juste mais sans signification métier.
- **Mesures de mise en forme séparées** (`Couleur atteinte`, `Libellé évolution CA`) pour que
  la logique de présentation ne pollue pas les mesures de calcul.
