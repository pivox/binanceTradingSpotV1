---
id: T-0020
title: "UI - Rafraîchissement live du graphique chandeliers"
status: NEEDS_QA
owner: techlead
links: ["US-0004", "US-0001", "US-0002", "US-0003", "T-0016", "T-0017", "T-0018", "T-0019"]
---

## Contexte
Le daemon alimente en continu la table `candles`. L'UI doit se mettre à jour en live pour la paire/timeframe active sans perte de sélection et avec un état stable en cas d'erreur temporaire.

## Perimetre
- Mettre en place un rafraîchissement périodique (polling) côté UI sur `/chart/candles` avec paramètre `from_open_time_ms` pour ne récupérer que les nouvelles bougies.
- Intégrer les nouvelles bougies au graphique sans clignotement ni reset du viewport.
- Afficher le dernier horodatage de mise à jour.
- Comportement en cas d'absence de nouveautés : conserver l'affichage.
- Gestion des erreurs temporaires : afficher message non bloquant et reprendre au cycle suivant.
- Suspendre/ralentir les rafraîchissements quand l'onglet est inactif (Page Visibility API).

## Hors perimetre
- Websocket push (option future).
- Calculs d'indicateurs temps réel.

## Solution
- State partagé contenant la dernière `open_time_ms` rendue; au polling, appeler `/chart/candles?from_open_time_ms=...&limit=...` et append/replace si doublons.
- Intervalle de polling configurable (ex: 1s pour `1m`; adaptable si besoin).
- Debounce des redraws pour éviter les micro-saccades; mise à jour du label `Dernier update`.
- Journaliser les erreurs côté console/log UI; ne pas bloquer l'UI.

## Plan d'implementation
1. Ajouter un module `liveUpdater` dans le JS chart qui gère l'intervalle et la visibilité page.
2. Utiliser `from_open_time_ms` pour limiter la charge; fallback full reload en cas d'écart détecté.
3. Intégrer la mise à jour du graphique (append) et du label d'horodatage.
4. Gérer les erreurs temporaires (afficher message, conserver données existantes).
5. Tests manuels sur dataset de test; vérifier latence cible (<2s entre BDD et UI).

## Tests
- Tests unitaires JS sur le calcul du prochain `from_open_time_ms` et la fusion de bougies.
- Tests manuels : erreurs simulées, onglet inactif, absence de nouvelles données.

## Criteres d'acceptation
- Live update actif, conserve paire/timeframe, sans clignotement.
- Horodatage de dernière mise à jour visible.
- Erreurs temporaires n'effacent pas les données; reprise automatique.
- Rafraîchissements suspendus ou réduits lorsque la page est inactive.

## Definition of Done
- Code merge avec lint/format OK.
- Documentation courte (paramètres de polling, comportements erreur/inactivité).

## Journal Dev (2026-02-15) - Retours PR #16
- `src/tradebot/api/static/chart.js`
  - Suppression des styles inline indicateurs dans le JS; rendu aligne sur `chart.css` (separation presentation/logique).
  - Suppression du retry `setTimeout` redondant au boot de la page (la boucle bootstrap periodique reste la source unique de retry).
  - Protection de la boucle bootstrap indicateurs contre l'annulation en boucle des requetes lentes:
    - ajout d'un garde `indicatorRequestInFlight`,
    - les retries bootstrap n'annulent plus la requete active.
  - Correction du fallback de selection initiale: un `pair` fourni par query string n'est retenu que si des bougies existent, sinon fallback sur le flux de decouverte.

## Journal Dev (2026-02-15) - Retours PR #17
- `src/tradebot/api/static/chart.js`
  - Remplacement des valeurs temporelles "magiques" de l'axe (`6h`, `3j`) par des constantes nommees (`SIX_HOURS_MS`, `THREE_DAYS_MS`) pour clarifier la logique de formatage.
