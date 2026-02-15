---
id: US-0014
title: "Collecte USDC - NFR observabilite, performance et respect des limites Binance"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant qu'operateur de la plateforme
Je veux que la collecte USDC soit observable et respecte les contraintes de performance et de limites Binance
Afin de diagnostiquer rapidement les incidents et d'eviter les comportements a risque (souscriptions excessives, demarrages lents).

## Contexte
- La collecte combine: selection (REST), tri/limite, puis souscription websocket.
- Les erreurs et les timings doivent etre visibles en logs pour permettre un support rapide.

## Criteres d'acceptation
1. Les erreurs API Binance (REST) sont logguees avec endpoint, base_url, code HTTP et duree.
2. Le temps de demarrage (selection + tri + souscription) est mesure et loggue, et reste < 5s hors latence reseau exceptionnelle.
3. Le mecanisme de limitation des souscriptions websocket Binance est conserve (chunking/throttling si necessaire) et ne depasse pas les limites supportees.
4. Un test de non-regression (ou un garde) detecte une augmentation anormale du nombre de streams et echoue explicitement.
5. Les composants additionnels requis a la collecte (ex: orchestrateur de workflows/attentions) sont demarrables via `docker-compose` et documentes.

## NFR
1. Les logs sont structures et filtrables (categorie, symbole, endpoint, duree).
2. Les gardes (limites/temps) sont observables et actionnables (message clair, recommandation).

