---
id: T-0018
title: "UI - Sélecteur de timeframe avec rechargement graphique"
status: NEEDS_QA
owner: techlead
links: ["US-0002", "US-0001", "T-0016", "T-0017"]
---

## Contexte
L'utilisateur doit pouvoir basculer rapidement entre `1m`, `5m`, `15m`, `1h`, `4h` sur la vue chart. Les données proviennent de la BDD via l'API chart.

## Perimetre
- Ajouter un composant sélecteur de timeframe visible sur la page Chart.
- Options minimales : `1m`, `5m`, `15m`, `1h`, `4h` (sources dynamiques possibles via `/chart/timeframes`).
- Au changement, rechargement du graphique avec la timeframe sélectionnée (API `/chart/candles`).
- Mettre en évidence la timeframe active; conserver la sélection lors des rafraîchissements live (T-0020).
- Gestion des cas sans données pour la paire/timeframe : état vide explicite.

## Hors perimetre
- Persistence cross-session (localStorage) optionnelle mais non obligatoire.
- Shortcuts clavier.

## Solution
- Composant bouton/segmented control en JS, accessible clavier.
- Source des options : liste fixe fallback, mais si l'API `/chart/timeframes?symbol=` renvoie une liste, l'utiliser pour rester cohérent avec la BDD.
- Sur sélection : annuler les requêtes en cours si possible, afficher spinner local, puis re-render chart.
- Conserver la timeframe active dans un state central (module JS partagé avec T-0020).

## Plan d'implementation
1. Créer le composant UI (CSS + JS) et l'insérer dans `chart.html`.
2. Brancher l'appel `/chart/timeframes` avec fallback statique.
3. Implémenter la logique de reload du chart sur changement de timeframe.
4. Gérer état vide/erreur (message + pas de crash).
5. Tests manuels (latence <2s) et mise à jour doc `docs/ui.md`.

## Tests
- Tests JS unitaires simples (mapping options, format de réponse).
- Vérification manuelle du temps de bascule (<2s) sur dataset de test.

## Criteres d'acceptation
- Sélecteur visible, timeframe active différenciée.
- Changement de timeframe recharge le graphique sans perdre la paire sélectionnée.
- État vide/erreur affiché si aucune donnée pour la timeframe.

## Definition of Done
- Code merge avec lint/format OK.
- Documentation courte des options et du flux de reload.
