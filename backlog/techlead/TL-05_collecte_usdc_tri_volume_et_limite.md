---
id: TL-05
title: "Collecte USDC - Tri par volume 24h et limite env"
status: DONE
owner: techlead
links: ["TL-05"]
---

# TL-05 Collecte USDC - Tri par volume 24h et limite env

## Objectif
Trier les paires USDC par volume 24h decroissant et limiter le nombre de paires via `USDC_PAIRS_LIMIT`.

## Scope
- Tri decroissant sur un champ de volume 24h (ex: `quoteVolume`).
- Limite configurable via variable d'environnement.
- Validation et valeur par defaut.

## Taches
- Choisir le champ de volume a utiliser et le documenter.
- Implementer le tri strictement decroissant.
- Lire `USDC_PAIRS_LIMIT` avec valeur par defaut.
- Valider la valeur (non numerique ou <= 0 -> erreur explicite).
- Logger les premieres paires retenues.

## Criteres d'acceptation
- L'ordre final est strictement decroissant par volume.
- La limite appliquee respecte `USDC_PAIRS_LIMIT`.
- Valeur invalide -> echec avec message clair.
- Log de demarrage indique les premieres paires retenues.

## Dependances
- TL-04 (liste des paires USDC).
