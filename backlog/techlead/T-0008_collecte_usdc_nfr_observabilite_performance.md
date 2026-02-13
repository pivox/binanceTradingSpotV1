---
id: T-0008
title: "Collecte USDC - NFR observabilite, performance et limites Binance"
status: VALIDATED
owner: dev
links: ["TL-08"]
---

## Contexte
Le TL-08 demande d'assurer l'observabilite, un temps de demarrage < 5s (hors latence reseau exceptionnelle), le respect des limites de souscription websocket et l'execution d'"attentions Temporal" via conteneur.

## Hypotheses
- Les logs structures utilisent le meme format que le reste du projet (si defini) ou un format JSON simple cle/valeur.
- Les limites websocket sont gerees par le mecanisme de chunking/throttling deja en place.
- "Attentions Temporal" fait reference a un service Temporal.io a lancer via `docker-compose.yml`.

## Questions ouvertes
- Confirmer la definition de "attentions Temporal" (service Temporal.io, workflows d'alerting, autre).

## Perimetre
- Instrumentation des logs d'erreurs API Binance et des timings de demarrage.
- Mesure et journalisation de la duree de demarrage (selection + tri + souscription).
- Verification que le chunking/throttling existant est conserve.
- Definition conteneurisee pour Temporal et declaration dans `docker-compose.yml`.

## Hors perimetre
- Optimisations de performance au-dela du time budget initial.
- Changement d'API Binance ou refonte du flux websocket.

## Plan d'implementation
- Localiser le flux de demarrage (recuperation paires, tri, souscription).
- Ajouter des timers et logs structures (start/end + duree).
- Ajouter logs structures sur erreurs API Binance (code, message, endpoint, contexte).
- Verifier les limites de chunking/throttling existantes et ajouter un test de non-regression.
- Ajouter un service Temporal dans `docker-compose.yml` et la definition conteneurisee associee.

## Tests
- Tests unitaires ou d'integration sur le calcul de duree de demarrage.
- Test de non-regression sur le volume d'abonnements (chunking/throttling).

## Criteres d'acceptation
- Logs structures sur erreurs API Binance et timings de demarrage.
- Duree de demarrage < 5s hors latence reseau exceptionnelle, avec log de mesure.
- Respect des limites de souscription websocket.
- Temporal demarre via conteneur et est declare dans `docker-compose.yml`.

## Definition of Done
- Code merge avec tests passes.
- `docker-compose.yml` mis a jour pour Temporal.
- Logs et timers visibles et exploitables en prod.
