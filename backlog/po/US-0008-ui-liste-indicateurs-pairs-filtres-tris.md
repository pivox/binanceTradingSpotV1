---
id: US-0008
title: "UI - Lister indicateurs et pairs avec filtres et tris"
status: TODO
owner: po
links: ["EPIC-INDICATEURS-LIVE", "US-0003", "US-0007"]
---

## User Story
En tant que trader
Je veux une UI qui liste les indicateurs disponibles et les pairs associes avec filtres et tris
Afin d'identifier rapidement les opportunites selon mes criteres de marche sans degradation de performance.

## Contexte
- L'ecran doit consommer le contrat API versionne des indicateurs.
- La liste doit rester fluide sur volumetrie elevee (>= 200 pairs).

## Criteres d'acceptation
1. L'UI affiche une table/grille des pairs avec colonnes d'indicateurs configurables.
2. L'utilisateur peut filtrer par pair, timeframe, indicateur actif et plage de valeur (ex: RSI < 30).
3. L'utilisateur peut trier ascendant/descendant sur chaque colonne numerique.
4. Les valeurs indisponibles suivent le statut API (`unavailable + reason`) avec rendu explicite (pas de valeur trompeuse).
5. Les donnees peuvent etre rafraichies en mode poll ou push; la strategie choisie est documentee et configurable.
6. L'UI indique la fraicheur (`last updated`) et un etat `stale` si depassement du delai attendu.
7. Les actions de filtre/tri sont debouncees pour limiter les appels API inutiles.
8. L'utilisateur peut enregistrer un preset de filtres/tri et le recharger.

## NFR performance/scalabilite
1. Affichage initial <= 2 secondes pour 200 pairs avec colonnes indicateurs principales.
2. Interactions filtre/tri percue <= 200 ms cote UI (hors latence reseau).
3. Virtualisation obligatoire de la table/grille au-dela d'un seuil configurable (par defaut 100 lignes visibles).
4. Les rafraichissements n'occasionnent pas de re-render complet inutile (memoization/selective updates).

## NFR accessibilite
1. Navigation clavier complete (tab, fleches dans la grille, activation Enter/Espace).
2. Focus visible conforme WCAG 2.2 (critere Focus Visible) sur tous les controles interactifs.
3. Annonces des changements d'etat critiques (stale, erreurs de chargement) via regions ARIA appropriees.
