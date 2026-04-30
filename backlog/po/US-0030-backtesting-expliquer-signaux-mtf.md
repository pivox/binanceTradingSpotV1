---
id: US-0030
title: "Backtesting - Expliquer les signaux MTF et les rejets"
status: TODO
owner: po
links: ["US-0024", "US-0005", "US-0029"]
---

## User Story
En tant que trader
Je veux comprendre pourquoi un signal MTF a ete pris ou rejete
Afin de calibrer la strategie sans deviner quels filtres ou timeframes posent probleme.

## Contexte
- Le MTF Validator evalue 4h, 1h, 15m et trigger 5m.
- Les filtres bloquants peuvent invalider un setup meme si le score est bon.
- La Roadmap rappelle que les conditions YAML sont la source de verite de la strategie.

## Criteres d'acceptation
1. Pour chaque trade pris, l'UI affiche le score total, les scores par timeframe et le trigger 5m actif.
2. Pour les zones sans trade, l'utilisateur peut inspecter les rejets agreges par raison.
3. L'UI affiche les conditions passees et echouees pour 4h, 1h, 15m et 5m.
4. Les filtres bloquants sont visibles avec leur impact.
5. L'utilisateur peut filtrer les trades par raison de signal: trend ok, structure ok, trigger ok, filtre bloquant, score insuffisant.
6. L'UI affiche la version du profil YAML et le seuil utilise.
7. Si le backtest utilise `validator.py` alors que le flux runtime utilise une autre cascade, l'UI signale explicitement cette difference de moteur.

## NFR
1. L'explication doit etre basee sur le contexte persiste du run, pas recalculee cote UI.
2. Les libelles doivent etre comprehensibles pour un trader sans exposer uniquement des noms de fonctions.
3. Les donnees d'explication doivent pouvoir etre exportees dans le rapport.
