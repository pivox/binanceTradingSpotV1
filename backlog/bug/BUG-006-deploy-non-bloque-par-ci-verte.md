---
id: B-0006
title: "Le deploiement manuel n'est pas conditionne a une CI verte"
status: VALIDATED
owner: qa
links: ["B-0006", "T-0013", "TL-13"]
---

# BUG-006 - Le deploiement manuel n'est pas conditionne a une CI verte

## Contexte
Le ticket `T-0013` exige que le deploiement `staging` soit possible apres CI verte.

## Description
Le workflow de deploiement `.github/workflows/deploy.yml` est declenche manuellement (`workflow_dispatch`) sans verification explicite du statut du dernier workflow CI pour le commit/reference cible.

## Impact
- Possibilite de deployer un commit dont la CI est en echec ou non executee.
- Risque de regression en `staging`/`production`.

## Etapes pour reproduire
1. Avoir un commit avec CI en echec.
2. Declencher `Deploy` manuellement vers `staging`.
3. Observer que le workflow peut demarrer sans garde CI.

## Resultat actuel
- Aucun gate technique dans `deploy.yml` ne bloque le deploiement si la CI n'est pas verte.

## Resultat attendu
- Le deploiement doit etre bloque tant que la CI associee au commit/ref n'est pas reussie.

## Critere de cloture
- Ajout d'un gate automatique liant le deploiement a un statut CI `success` (par exemple verification API GitHub, `workflow_run`, ou mecanisme equivalent).
- Echec explicite du job de deploiement si la CI n'est pas verte.
