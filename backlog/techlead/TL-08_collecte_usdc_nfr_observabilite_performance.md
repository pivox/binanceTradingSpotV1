# TL-08 Collecte USDC - NFR Observabilite, performance et limites Binance

## Objectif
Garantir observabilite, temps de demarrage et respect des limites de souscription websocket.

## Scope
- Logs structures sur erreurs API Binance.
- Demarrage (selection + tri + souscription) < 5s hors latence reseau exceptionnelle.
- Conservation du mecanisme de chunking/throttling pour limites websocket.
- Attentions Temporal implementees sous forme conteneurisee.
- Temporal configure via `docker-compose.yml` (racine).

## Taches
- Ajouter logs structures pour erreurs API et timings de demarrage.
- Mesurer le temps de demarrage et logguer les durées.
- Verifier que le chunking/throttling existant est conserve.
- Tests de non-regression sur le volume d'abonnements.
- Ajouter/mettre a jour la definition conteneurisee pour les attentions Temporal.
- Declarer Temporal dans `docker-compose.yml`.

## Criteres d'acceptation
- Les erreurs API Binance sont observables (logs structures).
- Temps de demarrage respecte la contrainte hors latence reseau exceptionnelle.
- Les limites de souscription websocket ne sont pas depassees.
- Les attentions Temporal s'executent via un conteneur.
- Temporal est configure dans `docker-compose.yml`.

## Dependances
- TL-04, TL-05, TL-06.

## Questions ouvertes
- Que recouvre exactement "attentions Temporal" (service Temporal.io, workflows d'alerting, autre) ?
