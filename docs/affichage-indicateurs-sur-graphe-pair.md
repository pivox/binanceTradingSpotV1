# Spécification fonctionnelle — Affichage des indicateurs techniques sur le graphe d’une pair

## Contexte
L’utilisateur consulte déjà un graphe de chandeliers pour une pair (ex: `BTCUSDC`) sur la page `/chart`.
Le besoin est d’afficher, au même endroit, les indicateurs techniques afin d’éviter les allers-retours entre plusieurs écrans et de faciliter la décision de trading.

## Objectif produit
Permettre à l’utilisateur de visualiser les indicateurs techniques directement dans la zone du graphe actif, en conservant le contexte courant:
- même pair,
- même timeframe,
- même fenêtre temporelle affichée.

## Périmètre

### Dans le périmètre (MVP)
1. Ajouter un panneau "Indicateurs" sur `/chart`.
2. Permettre l’activation/désactivation d’indicateurs standards:
   - SMA (par défaut: période 20),
   - EMA (par défaut: période 20),
   - RSI (par défaut: période 14),
   - MACD (paramètres par défaut: 12/26/9).
3. Afficher les indicateurs:
   - sur le graphe principal pour SMA/EMA,
   - dans un sous-graphe aligné temporellement pour RSI/MACD.
4. Synchroniser automatiquement les indicateurs avec le changement de pair et timeframe.
5. Réutiliser les endpoints backend existants (`/indicators/latest`, `/indicators/history`) avec gestion des états loading/empty/error.

### Hors périmètre (cette itération)
- Création d’indicateurs personnalisés utilisateur.
- Backtesting ou signaux automatiques de trading.
- Multi-pairs affichées simultanément dans la même vue.
- Sauvegarde cloud des presets d’indicateurs.

## Parcours utilisateur
1. L’utilisateur ouvre `/chart`.
2. Le graphe charge la pair/timeframe active.
3. L’utilisateur ouvre le panneau "Indicateurs".
4. Il active RSI + EMA.
5. Le graphe se met à jour sans rechargement de page:
   - EMA tracée sur les chandeliers,
   - RSI affiché dans le sous-graphe.
6. L’utilisateur change la timeframe (ex: `1m` -> `15m`):
   - le graphe et les indicateurs se recalculent/rechargent,
   - les indicateurs activés restent sélectionnés.

## Règles fonctionnelles détaillées

### 1) Cohérence pair/timeframe
- Les indicateurs affichés doivent toujours correspondre exactement à la pair/timeframe visible sur le graphe.
- Au changement de pair/timeframe, toute requête indicateur en cours est annulée et remplacée par une nouvelle requête.

### 2) Affichage et lisibilité
- Chaque indicateur dispose d’une couleur dédiée et constante.
- Une légende indique:
  - nom indicateur,
  - paramètres,
  - dernière valeur.
- En cas de données insuffisantes (ex: début de série pour SMA20), la zone manquante n’est pas interpolée artificiellement.

### 3) États UX
- **Loading**: skeleton/spinner local au panneau indicateurs.
- **Empty**: message explicite (ex: "Pas encore de données indicateurs pour cette sélection").
- **Error**: message lisible + action "Réessayer".
- Les erreurs indicateurs ne doivent pas masquer les chandeliers déjà disponibles.

### 4) Performance et rafraîchissement live
- Le rafraîchissement live conserve la sélection d’indicateurs.
- Les indicateurs ne doivent pas provoquer de "full redraw" bloquant lors de chaque tick.
- Objectif UX: mise à jour perçue fluide sur machine standard.

### 5) Accessibilité
- Le panneau indicateurs est utilisable au clavier.
- Les bascules ON/OFF ont un libellé explicite et un état ARIA.
- Les contrastes de couleurs restent lisibles sur thème courant.

## Critères d’acceptation
1. Depuis `/chart`, l’utilisateur peut activer/désactiver SMA, EMA, RSI, MACD sans quitter l’écran.
2. Les indicateurs affichés restent cohérents après changement de pair et/ou timeframe.
3. Si l’API indicateurs est indisponible, le graphe chandeliers reste visible et un message d’erreur indicateurs s’affiche.
4. Les indicateurs overlay (SMA/EMA) apparaissent sur le graphe principal, RSI/MACD dans un sous-graphe synchronisé.
5. En live refresh, les indicateurs se mettent à jour sans reset visuel complet.

## Dépendances
- Endpoints backend:
  - `GET /indicators/latest`
  - `GET /indicators/history`
- Contrat OpenAPI indicateurs: `docs/openapi-indicators.yaml`.
- Comportements existants page chart décrits dans `docs/ui.md`.

## Instrumentation (minimum)
- Événements front:
  - `chart_indicator_toggled` (indicator, status, symbol, timeframe)
  - `chart_indicator_error` (indicator, code, symbol, timeframe)
- KPI de suivi:
  - taux d’activation d’au moins 1 indicateur,
  - taux d’erreur API indicateurs par timeframe,
  - latence médiane d’affichage indicateur après toggle.

## Hypothèses
- Les données indicateurs sont déjà calculées côté backend et accessibles via les endpoints documentés.
- La page `/chart` dispose déjà d’une architecture permettant un sous-graphe temporel synchronisé.
- Les quatre indicateurs définis (SMA, EMA, RSI, MACD) couvrent le besoin court terme PO.

## Questions ouvertes
1. Doit-on autoriser la configuration des paramètres (ex: RSI 14 -> 21) dans le MVP ou la figer aux valeurs par défaut?
2. Doit-on persister les indicateurs sélectionnés entre sessions (localStorage / profil user)?
3. Quelle règle de priorité visuelle en cas de surcharge (plusieurs overlays + écran réduit)?
4. Faut-il aligner exactement les libellés indicateurs sur une nomenclature métier existante?

## Risques
- Surcharge visuelle si trop d’indicateurs actifs simultanément.
- Dégradation de performance sur historiques longs si rendu non optimisé.
- Incohérences perçues si les timestamps chandeliers/indicateurs divergent.
