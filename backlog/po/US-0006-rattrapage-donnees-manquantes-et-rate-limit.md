---
id: US-0006
title: "Ingestion - Rattraper les donnees manquantes sans depasser les limites Binance"
status: TODO
owner: po
links: ["EPIC-INDICATEURS-LIVE", "US-0005", "US-0007"]
---

## User Story
En tant qu'operateur de la plateforme
Je veux completer automatiquement les historiques manquants avant calcul des indicateurs
Afin de garantir des indicateurs exploitables sans risque de ban API Binance.

## Contexte
- Le service de rattrapage doit etre pilotable par budget de requetes/weight Binance.
- La strategie doit etre robuste aux erreurs 429/418 et prioriser les actifs critiques.

## Criteres d'acceptation
1. Avant calcul, le systeme detecte precisement les trous de donnees par pair/timeframe/plage temporelle.
2. Le rattrapage recupere uniquement les bougies manquantes (idempotent, sans doublon, tri strict par temps).
3. Le service lit les headers de poids Binance (`X-MBX-USED-WEIGHT-*`) et ajuste dynamiquement le debit.
4. En cas de **429**, backoff exponentiel avec jitter est obligatoire avant tout nouvel appel.
5. En cas de **418** (ban auto), le service passe en stop dur pour la cible, declenche alerte, puis cooldown avant reprise.
6. Retry/backoff bornes et explicites: `max_attempts`, `max_backoff`, `max_retry_window` configurables.
7. Une politique de priorisation est definie (ex: top volume, paires actives UI, timeframe court en priorite) pour eviter starvation.
8. Les events critiques sont traces: trous detectes, retries, 429/418, cooldown, reprise, taux de succes.

## NFR
1. 0 depassement volontaire des limites Binance en nominal.
2. Aucun retry infini; toute sequence de retry est bornée et observable.
3. Le cout API reste optimisable par configuration (batch size, cadence, priorite, fenetres de rattrapage).
4. Le service degrade proprement en mode "slow" quand le budget de weight approche le seuil critique.
