# Epics restants pour finaliser le projet

## Méthodologie de lecture
- Source prioritaire: statuts backlog PO/TechLead/Bugs.
- Verification de coherence avec le code et la documentation operationnelle existante (API/UI/CI deja presentes).
- Ce document ne change pas le scope produit: il consolide uniquement ce qu'il reste a terminer.
- Demande complementaire prise en compte: inclure explicitement le **moteur de validation des signaux** (regles MTF) dans les epics de finalisation.

## Constat rapide
- Les US PO `US-0001` a `US-0008` sont encore marquees `TODO` cote backlog, meme si une partie importante du socle API/UI existe deja.
- Cote TechLead, l'axe CI/CD historique (TL-09 a TL-15) est largement cloture (`DONE`/`VALIDATED`).
- Le chantier encore actif est surtout le bloc **indicateurs live** (moteur + backfill + contrat API + UI screener + QA de non-regression).
- Un second chantier structurant reste a finaliser: **moteur de validations de signaux** configurable par regles (logique MTF/cascade, gouvernance des validations, traçabilite des decisions).

## Epic 1 - Fiabilisation du pipeline indicateurs live (priorite P0)

### Pourquoi cet epic est restant
- `US-0005` (calcul continu indicateurs) est `TODO`.
- `T-0022` (moteur indicateurs normatif) est `IN_PROGRESS`.
- Bug bloquant associe: `B-0009` (RSI warmup off-by-one) en `TODO`.

### Resultat attendu pour fermer l'epic
- Conformite complete des calculs normatifs (RSI/EMA/SMA/ATR/VWAP/ADX selon spec US).
- Correction des derives numeriques et des fenetres de warmup.
- Batterie de tests de non-regression numerique stable sur snapshots historiques.

### Tickets inclus
- PO: `US-0005`
- Tech: `T-0022`
- QA/Bugs: `B-0009`

## Epic 2 - Backfill robuste et respect strict des limites Binance (priorite P0)

### Pourquoi cet epic est restant
- `US-0006` est `TODO`.
- `T-0023` est `NEEDS_QA` (done technique non encore verrouillee).
- Bug critique associe: `B-0011` (`1M` traite comme 30 jours fixes) en `TODO`.

### Resultat attendu pour fermer l'epic
- Detection fiable des gaps pour toutes granularites (dont `1M` calendaire).
- Rattrapage idempotent, priorise, avec controle fin du budget de requetes.
- Validation QA de robustesse sur erreurs 429/418 + reprise propre.

### Tickets inclus
- PO: `US-0006`
- Tech: `T-0023`
- QA/Bugs: `B-0011`

## Epic 3 - Contrat API indicateurs versionne et cache conditionnel fiable (priorite P0)

### Pourquoi cet epic est restant
- `US-0007` est `TODO`.
- `T-0024` est `NEEDS_QA`.
- Bug associe: `B-0010` (ETag latest non sensible au payload) en `TODO`.

### Resultat attendu pour fermer l'epic
- Garantie de stabilite du contrat OpenAPI (latest/history + pagination curseur).
- ETag strictement derive du payload expose (plus de 304 incorrect).
- Campagne QA contrat/API pour valider backward compatibility et cache semantics.

### Tickets inclus
- PO: `US-0007`
- Tech: `T-0024`
- QA/Bugs: `B-0010`

## Epic 4 - UI screener indicateurs (filtres/tris/presets) a volumetrie elevee (priorite P1)

### Pourquoi cet epic est restant
- `US-0008` est `TODO`.
- `T-0026` (table virtualisee) et `T-0027` (filtres/tris/presets) sont `TODO`.

### Resultat attendu pour fermer l'epic
- Vue screener performante sur >= 200 paires.
- Filtres multicriteres, tris, debounce et presets persistants/rechargeables.
- UX fluide sans surcharge API et avec etats d'erreur explicites.

### Tickets inclus
- PO: `US-0008`
- Tech: `T-0026`, `T-0027`

## Epic 5 - Moteur de validations de signaux MTF configurable (priorite P0)

### Pourquoi cet epic est restant
- Le besoin existe fonctionnellement (validation de signaux avant execution), mais n'apparait pas encore comme epic PO explicite dans les US.
- Le code contient deja des briques (`signal_engine`, `exit_engine`, `services/mtf/cascade`) sans specification produit unifiee de type "catalogue de regles".
- Demande complementaire exprimee: converger vers un moteur de validations declaratif (inspire d'une approche `validations.regular.yaml`) pour uniformiser les checks.

### Resultat attendu pour fermer l'epic
- Contrat declaratif de regles de validation (format YAML/JSON versionne) couvrant les controles principaux:
  - confirmations multi-timeframes,
  - seuils indicateurs,
  - exclusions marche (volatilite/liquidite),
  - regles de conflit/precedence.
- Moteur d'evaluation deterministe (ordre de regles stable, resultat reproductible).
- Explicabilite: pour chaque signal, journal de decision (`passed/failed`, regle, valeur observee, seuil).
- Tests de non-regression sur scenarios de validation (golden files + cas limites).

### Tickets inclus (a creer/aligner)
- PO: nouvelle US "Validation des signaux par regles configurables".
- Tech: nouveau ticket TechLead "Moteur de validation declaratif + registry de regles".
- QA: plan de tests contractuels sur jeu de configurations (regular/aggressive/conservative).

## Epic 6 - QA transverse et readiness release finale (priorite P0)

### Pourquoi cet epic est restant
- `T-0028` (non-regression indicateurs/backfill/API/UI) est `TODO`.
- Plusieurs tickets `NEEDS_QA` sur le flux chart/indicateurs indiquent une fermeture fonctionnelle non complete.
- Bug transverse encore `TODO`: `B-0008` (demarrage daemon/chart indisponible selon scenarios QA).

### Resultat attendu pour fermer l'epic
- Plan QA bout-en-bout automatise + scenarii manuels critiques.
- Passage de tous tickets `NEEDS_QA` vers `VALIDATED`/`DONE`.
- Go-live checklist (observabilite, alerting, rollback, runbook incident) signee.

### Tickets inclus
- Tech/QA: `T-0028`, `T-0016`, `T-0017`, `T-0018`, `T-0019`, `T-0020`, `T-0021`, `T-0023`, `T-0024`, `T-0025`
- Bugs: `B-0008`


## Epic 7 - Backtesting transverse sur l'ensemble des US de trading (priorite P0)

### Vision PO
Fournir une capacite de backtesting fiable, lisible et decisionnelle pour valider les strategies avant mise en production.
L'epic doit permettre au PO, au TechLead et à la QA de répondre à une question simple : **"est-ce que cette version améliore réellement le couple performance/risque ?"**

### Probleme produit a resoudre
- Les US actuelles couvrent bien la collecte, le calcul d'indicateurs, l'API et l'UI, mais pas encore la boucle d'evaluation historique complete.
- Sans backtesting cadre, les decisions d'evolution des regles de signaux restent peu objectivables.
- Les regressions de qualite peuvent passer en production faute de seuils quantitatifs explicites.

### Scope fonctionnel (MVP puis extension)
#### MVP (obligatoire)
- Lancer un backtest reproductible sur une periode, un univers de paires et un profil de regles donne.
- Rejouer de bout en bout: `candles -> indicateurs -> validations MTF -> signaux -> execution simulee -> KPIs`.
- Produire un rapport standard machine + humain (JSON + Markdown) exploitable en revue de release.

#### Extension (phase 2)
- Comparaison automatique baseline vs candidate.
- Multi-profils (regular/aggressive/conservative) et classement automatique.
- Scenarios de stress (forte volatilite, regime de range, regime de tendance).

### User Stories cibles de l'epic
1. En tant que **PO**, je veux comparer objectivement deux versions de strategie afin de decider un go/no-go release.
2. En tant que **TechLead**, je veux un runner deterministe pour reproduire les resultats localement et en CI.
3. En tant que **QA**, je veux des seuils de non-regression pour bloquer une release qui degrade les metriques critiques.
4. En tant qu'**Ops**, je veux des rapports historises pour comprendre l'impact d'un changement de regles.

### Criteres d'acceptation (Definition of Done)
1. Un meme jeu d'entrees (dataset + config + seed) produit exactement les memes sorties de backtest.
2. Le moteur couvre au minimum les US `US-0005`, `US-0006`, `US-0007` et la logique de validations signaux (Epic 5).
3. Le rapport de sortie contient au minimum: `PnL`, `max_drawdown`, `hit_ratio`, `expectancy`, `exposure`, `turnover`, `fees`, `slippage`.
4. Un mode "compare" fournit un diff baseline/candidate avec verdict explicite (`improved`, `neutral`, `degraded`).
5. Les seuils de qualite definis par PO/TechLead sont executables en CI et bloquent en cas de regression.
6. Chaque run est tracable (horodatage, version code, version regles, hash dataset, parametres).

### NFR
- Reproductibilite: 100% deterministe a inputs identiques.
- Performance: execution d'un run standard (univers cible PO) en temps acceptable pour usage CI.
- Auditabilite: chaque decision de trade simule est explicable via les regles appliquees.
- Maintainabilite: ajout d'un nouveau profil/regle sans recoder le moteur.

### Hors scope (pour eviter la derive)
- Optimisation automatique de parametres type "auto-ML" en phase initiale.
- Trading live reel depuis le moteur de backtest.
- Visualisations avancees interactives (dashboard complet) avant validation du socle.

### Decoupage propose en sous-lots
- **Lot BT-1**: contrat d'entree/sortie + runner deterministe + rapport minimal.
- **Lot BT-2**: simulation execution (fees/slippage) + metriques standardisees.
- **Lot BT-3**: mode comparaison baseline/candidate + verdict.
- **Lot BT-4**: gates CI de non-regression + publication des artefacts.
- **Lot BT-5**: scenarios de stress et couverture QA etendue.

### Tickets inclus (a creer/aligner)
- PO: nouvelle US "Backtesting des strategies et des regles de validation".
- Tech: ticket TechLead "Moteur/backtest runner + catalogues de scenarios + reporting".
- QA: campagne de non-regression backtest integree a `T-0028`.
- Liens fonctionnels: `US-0005`, `US-0006`, `US-0007`, `US-0008` + Epic 5 (validations signaux).

## Proposition d'ordre d'execution
1. **Epic 1 + Epic 2 + Epic 3** en flux coordonne (coeur data + contrat API).
2. **Epic 5** en parallele: cadrer tot le moteur de validation de signaux pour eviter un recablage tardif de l'execution.
3. **Epic 6** en continu pendant l'implementation (QA continue, pas en fin de projet uniquement).
4. **Epic 4** ensuite pour finaliser la valeur trader cote interface de screening.
5. **Epic 7** en continu des epics 1-5 pour valider quantitativement les choix (et en gate pre-release).

## Questions ouvertes (a trancher PO/TechLead)
- Quel niveau de tolérance est accepté pour l'écart numérique des indicateurs (epsilon par indicateur) ?
- Quelle politique de versionning API appliquer en cas de changement de formule/metadonnee ?
- Quelle volumetrie cible officielle du screener (200, 500, 1000 paires) pour verrouiller les NFR front ?
- Quel format cible pour les regles de validation des signaux (YAML versionne, schema JSON, ou mix) ?
- Souhaite-t-on plusieurs profils de validation (regular/aggressive/conservative) selectionnables au runtime ?
- Quels jeux de donnees historiques de reference sont retenus pour les campagnes de backtesting (periode, paires, granularites) ?
- Quels seuils minimaux de performance/risque definissent un "go" release (ex: max drawdown, Sharpe, taux de trades invalides) ?
