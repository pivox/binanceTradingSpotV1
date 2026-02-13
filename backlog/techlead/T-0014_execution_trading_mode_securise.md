---
id: T-0014
title: "Execution trading en mode securise"
status: VALIDATED
owner: dev
links: ["TL-14"]
---

## Contexte
Garantir un mode simulation par defaut et un passage en mode reel uniquement avec validation explicite.

## Perimetre
- Guard runtime pour execution live.
- Journalisation horodatee des signaux et ordres.
- Tests de comportement (dry_run par defaut, live bloque sans approval, live ok avec approval).

## Plan
1. Ajouter un guard `EXECUTION_MODE` + `LIVE_TRADING_APPROVED`.
2. Router l'execution dans `place_order`/`cancel_order`.
3. Ajouter logs horodates.
4. Ajouter tests unitaires.

## Definition of Done
- Mode dry_run par defaut.
- Live uniquement avec approval explicite.
- Logs horodates pour signaux et ordres.
