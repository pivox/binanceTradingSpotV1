---
id: T-0019
title: "UI - Sélecteur de paire depuis la liste des pairs disponibles"
status: NEEDS_QA
owner: techlead
links: ["US-0003", "US-0001", "US-0002", "T-0016", "T-0017", "T-0018"]
---

## Contexte
L'utilisateur doit pouvoir ouvrir la liste des paires disponibles (issues des données BDD) et recharger le graphique sur la paire choisie.

## Perimetre
- Afficher la paire courante en haut de la vue chart; clic ou touche ouvre une liste/overlay des paires disponibles.
- Charger la liste via l'API `/chart/symbols` (tri alpha), fallback message si vide.
- Sur sélection : fermer la liste, marquer la paire active, recharger le graphique avec la timeframe courante.
- Navigation clavier (haut/bas/enter/escape) pour accessibilité.

## Hors perimetre
- Recherche/filtre texte (option à considérer plus tard).
- Groupement par quote (USDC/USDT) si non fourni par l'API.

## Solution
- Composant liste/overlay léger (CSS + JS) réutilisable.
- Stocker la paire active dans un state partagé; déclencher un fetch `/chart/candles` avec la timeframe actuelle.
- Gestion des cas : liste vide, erreur API, spinner lors du chargement initial.
- Afficher un badge/état explicite quand aucune donnée pour la paire/timeframe.

## Plan d'implementation
1. Créer l'overlay/liste et l'ancrer à l'entête de la page chart.
2. Intégrer l'appel `/chart/symbols` avec cache léger (en mémoire) et refresh manuel optionnel.
3. Implémenter la sélection (click + clavier) et le reload du chart.
4. Styles responsives (mobile/desktop) et focus management (trap focus dans l'overlay).
5. Documenter le flux dans `docs/ui.md`.

## Tests
- Tests JS unitaires simples : mapping de la réponse, gestion liste vide.
- Vérification manuelle : ouverture <300ms, reload chart <2s.

## Criteres d'acceptation
- Paire courante visible; clic ouvre une liste des paires BDD.
- Sélection ferme la liste, met en évidence la paire choisie et recharge le chart.
- Liste vide affiche un message explicite sans crash.
- Navigation clavier fonctionnelle.

## Definition of Done
- Code merge avec lint/format OK.
- Documentation courte (usage API, comportements clavier).
