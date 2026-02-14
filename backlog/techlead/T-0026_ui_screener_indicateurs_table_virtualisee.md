---
id: T-0026
title: "UI - Screener indicateurs avec table virtualisee"
status: TODO
owner: techlead
links: ["US-0008", "US-0007", "T-0021"]
---

## Contexte
US-0008 demande une liste fluide de paires+indicateurs avec volumetrie >= 200 paires, colonnes configurables et rendu explicite des indisponibilites.

## Perimetre
- Implementer ecran screener (table/grille) et configuration colonnes.
- Virtualisation obligatoire au-dela du seuil configure.
- Affichage conforme du statut API (`available/unavailable + reason`).
- Affichage `last updated` + etat `stale`.

## Hors perimetre
- Persistance serveur des presets (si decidee hors v1).

## Tests
- Tests composants rendu statuts indisponibles.
- Tests performance UI (200 paires, temps initial <=2s).
- Tests accessibilite navigation clavier/focus visible.

## Criteres d'acceptation
1. Scroll fluide avec virtualisation active.
2. Aucune valeur trompeuse pour donnee indisponible.
3. Etat stale visible et compréhensible.
