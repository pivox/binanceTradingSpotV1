---
id: B-0007
title: "Alerting CI incomplet: erreur principale absente et couverture partielle des jobs critiques"
status: VALIDATED
owner: qa
links: ["B-0007", "T-0015", "TL-15"]
---

# BUG-007 - Alerting CI incomplet sur echecs critiques

## Contexte
Le ticket `T-0015` demande une alerte en cas d'echec de workflow/job critique avec `run ID`, job et erreur principale.

## Description
Deux ecarts sont observes dans `.github/workflows/ci.yml`:
- Le message Slack ne contient pas de resume explicite de l'erreur principale (seulement workflow/job/ref/url).
- L'alerte est implantee uniquement dans le job `test`; un echec du job critique `secrets_check` n'emet pas d'alerte dediee.

## Impact
- Diagnostic plus lent en incident (absence de contexte erreur).
- Risque de manquer des echecs critiques (ex: secrets manquants sur `main`).

## Resultat actuel
- Alerte Slack partielle et non uniforme sur tous les jobs critiques CI.

## Resultat attendu
- Message d'alerte incluant un resume de l'erreur principale.
- Notification emise pour tout echec de job critique CI (dont `secrets_check`).

## Critere de cloture
- Couverture alerting etendue a tous les jobs critiques.
- Message Slack enrichi avec un champ erreur principale (ou reference directe exploitable vers l'erreur).
