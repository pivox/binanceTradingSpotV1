---
id: T-0017
title: "UI - Page Chart shell + chargement initial chandeliers"
status: NEEDS_QA
owner: techlead
links: ["US-0001", "T-0016"]
---

## Contexte
La vue actuelle ne couvre que le contrôle du daemon. Les US chart requièrent une page dédiée affichant un graphique chandelier à partir des données BDD (via l'API à créer T-0016).

## Perimetre
- Créer une page/route « Chart » (ex: `/chart`) intégrée au frontend existant (aiohttp static).
- Consommer l'API `/chart/candles` pour charger l'historique initial d'une paire/timeframe par défaut (ex: `BTCUSDC` + `1m` si disponibles).
- Rendre un graphique chandelier responsive desktop/mobile, lisible (OHLC + volume optionnel).
- Gérer états : chargement, vide (aucune donnée), erreur lisible sans crash.

## Hors perimetre
- Sélecteurs de timeframe et de paire (couverts par T-0018/T-0019).
- Rafraîchissement live (T-0020).
- Indicateurs ou overlays avancés.

## Solution
- Ajouter un bundle JS dédié (vanilla ou librairie légère type `lightweight-charts` si licence compatible) chargé depuis `static/`.
- Structurer la page avec conteneur chart, header et placeholders pour contrôles futurs.
- Implémenter un client léger pour appeler `/chart/candles` et mapper la réponse vers le chart.
- Gérer le resize via `ResizeObserver` pour garder la lisibilité.
- Limiter le volume initial (ex: 500 bougies) pour respecter le SLA <2s.

## Plan d'implementation
1. Ajouter assets JS/CSS pour la page chart dans `src/tradebot/api/static/`.
2. Créer la route/entrée `chart.html` + lien depuis page d'accueil.
3. Implémenter le chargement initial (fetch + mapping + rendu chart).
4. États UI : loading/empty/error avec messages explicites.
5. Tests manuels + note dans docs si needed.

## Tests
- Tests E2E légers en JS (si infra dispo) ou tests manuels documentés.
- Vérifier temps d'affichage initial <2s sur dataset de test.

## Criteres d'acceptation
- Page Chart accessible depuis l'UI.
- Historique initial affiché en chandelier lisible, basé uniquement sur l'API BDD.
- États vide/erreur gérés sans crash.

## Definition of Done
- Code merge, lint passé (`ruff check .`), format JS/HTML conforme.
- Documentation courte dans `docs/ui.md` (ajout de la page et prérequis API).
