---
id: T-0033
title: "UI - Screener virtualise avec filtres, tris debounce et presets"
status: TODO
owner: dev
links: ["US-0008", "US-0007", "T-0029", "T-0032", "T-0026", "T-0027"]
---

## Contexte
US-0008 demande un ecran screener complet (table/grille) avec performance sur forte volumetrie, filtres/tris, gestion stale et accessibilite. La page n'existe pas encore dans les assets UI actuels.

## Perimetre
- Ajouter une page/route UI screener (ex: `/screener`) basee sur l'API `T-0032`.
- Afficher une table/grille des paires avec colonnes indicateurs configurables.
- Ajouter filtres + tris client (pilotant l'API) avec debounce configurable.
- Ajouter virtualisation obligatoire au-dela d'un seuil (defaut 100 lignes visibles).
- Afficher `last updated` + etat `stale` explicite.
- Ajouter sauvegarde/rechargement de presets (stockage local v1).
- Assurer accessibilite clavier et focus visible.

## Hors perimetre
- Persistance serveur des presets (v2).
- Refonte globale du design system.

## Plan d'implementation
1. Creer assets `screener.html`, `screener.js`, `screener.css` et route backend statique.
2. Implementer data layer:
   - appels API screener,
   - debounce des interactions,
   - gestion erreurs/retry non bloquant.
3. Implementer table virtualisee et rendu des statuts `available/unavailable`.
4. Implementer filtres/tris + sauvegarde presets (localStorage) + restauration.
5. Ajouter gestion stale (`last updated`, delai configurable), et support clavier/focus/ARIA.

## Tests
- Tests unitaires JS:
  - serialisation/deserialisation presets,
  - logique debounce,
  - rendu statuts indisponibles.
- Tests d'integration UI:
  - filtres + tri + restore preset,
  - navigation clavier (tab/fleches/enter/escape),
  - comportement sur 200+ lignes (virtualisation active).
- Verification manuelle responsive desktop/mobile.

## Criteres d'acceptation
1. Affichage initial <= 2s pour 200 paires sur environnement nominal.
2. Interactions filtre/tri percues <= 200ms cote UI hors latence reseau.
3. Virtualisation active au-dela du seuil configure.
4. Les etats indisponibles/stale sont visibles et non ambigus.
5. Navigation clavier complete et focus visible conforme.

## Definition of Done
- Code merge avec qualite frontend validee + `pytest -q` et `ruff` verts cote backend.
- Documentation usage UI mise a jour (`docs/ui.md`).
