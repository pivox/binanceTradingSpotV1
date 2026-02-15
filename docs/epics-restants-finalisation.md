# Epics restants pour finaliser le projet

## Methodologie de lecture
- Source prioritaire: statuts backlog PO/TechLead/Bugs.
- Verification de coherence avec le code et la documentation operationnelle existante (API/UI/CI deja presentes).
- Ce document ne change pas le scope produit: il consolide uniquement ce qu'il reste a terminer.

## Constat rapide
- Les US PO `US-0001` à `US-0008` sont encore marquées `TODO` côté backlog, même si une partie importante du socle API/UI existe déjà.
- Côté TechLead, l'axe CI/CD historique (TL-09 à TL-15) est largement clôturé (`DONE`/`VALIDATED`).
- Le chantier encore actif est surtout le bloc **indicateurs live** (moteur + backfill + contrat API + UI screener + QA de non-régression).

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

## Epic 5 - QA transverse et readiness release finale (priorite P0)

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


## Epic 6 - Backtesting transverse sur l'ensemble des US de trading (priorite P0)

### Pourquoi cet epic est restant
- Le backlog actuel couvre ingestion, indicateurs, API et UI, mais ne formalise pas encore un epic backtesting end-to-end avec jalons clairs de validation.
- Sans backtesting industrialise, il est difficile de qualifier objectivement la pertinence des strategies, d'arbitrer entre variantes et de securiser les mises en production.
- La demande explicite est d'avoir une "epic backtesting" transverse qui structure les decisions produit/trading sur des resultats mesurables.

### Resultat attendu pour fermer l'epic
- Cadre de backtest reproductible (dataset fige, fenetres temporelles, frais/slippage explicites, seed stable).
- Rejeu complet de la chaine: candles -> indicateurs -> decisions/positions -> metriques.
- Sorties standardisees: PnL, drawdown, hit ratio, expectancy, exposure, turnover, couts.
- Comparateur de strategies (baseline vs candidate) avec rapport diff interpretable pour le PO et le TechLead.
- Garde-fous QA: seuils minimaux de qualite pour eviter une regression silencieuse avant release.
- Industrialisation CI: execution backtest nocturne + gate optionnel pre-release avec archivage des rapports.

### Tickets inclus (a creer/aligner)
- PO: nouvelle US "Backtesting des strategies".
- Tech: ticket TechLead "Backtest runner + catalogues de scenarios + reporting".
- QA: campagne de non-regression backtest integree a `T-0028`.
- Liens fonctionnels: `US-0005`, `US-0006`, `US-0007`, `US-0008`.

## Proposition d'ordre d'execution
1. **Epic 1 + Epic 2 + Epic 3** en flux coordonne (coeur data + contrat API).
2. **Epic 5** en continu pendant l'implementation (QA continue, pas en fin de projet uniquement).
3. **Epic 4** ensuite pour finaliser la valeur trader cote interface de screening.
4. **Epic 6** en continu dès les epics 1-5 pour valider quantitativement les choix (et en gate pre-release).

## Questions ouvertes (à trancher PO/TechLead)
- Quel niveau de tolérance est accepté pour l'écart numérique des indicateurs (epsilon par indicateur) ?
- Quelle politique de versionning API appliquer en cas de changement de formule/métadonnée ?
- Quelle volumétrie cible officielle du screener (200, 500, 1000 paires) pour verrouiller les NFR front ?
- Quels jeux de données historiques de référence sont retenus pour les campagnes de backtesting (période, paires, granularités) ?
- Quels seuils minimaux de performance/risque définissent un "go" release (ex: max drawdown, Sharpe, taux de trades invalides) ?
