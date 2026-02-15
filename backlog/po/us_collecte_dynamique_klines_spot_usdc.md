# Epic: Collecte dynamique des klines Spot USDC

## Decomposition en User Stories
- US-0009 Collecte USDC - Recuperer dynamiquement les paires Spot USDC (`US-0009-collecte-usdc-recuperer-paires-dynamiquement.md`)
- US-0010 Collecte USDC - Trier les paires par volume de trade 24h (`US-0010-collecte-usdc-tri-par-volume-24h.md`)
- US-0011 Collecte USDC - Limiter le nombre de paires ecoutees via une variable d'environnement (`US-0011-collecte-usdc-limite-via-variable-env.md`)
- US-0012 Collecte USDC - S'abonner en websocket sur la liste dynamique retenue (`US-0012-collecte-usdc-abonnement-websocket-liste-dynamique.md`)
- US-0013 Collecte USDC - Forcer une liste statique de symboles via SYMBOLS (override) (`US-0013-collecte-usdc-override-manuel-symbols.md`)
- US-0014 Collecte USDC - NFR observabilite, performance et respect des limites Binance (`US-0014-collecte-usdc-nfr-observabilite-performance-limites.md`)

## US-01 - Recuperation dynamique des paires USDC
**En tant que** systeme de collecte market data  
**Je veux** recuperer automatiquement la liste des paires Spot se terminant par `USDC` depuis Binance  
**Afin de** ne plus dependre d'une liste statique de symboles.

### Criteres d'acceptation
1. Le daemon appelle l'API Binance des tickers 24h au demarrage.
2. Seules les paires Spot dont le symbole se termine par `USDC` sont conservees.
3. Si l'API Binance est indisponible, une erreur explicite est loggee et le daemon n'entre pas en ecoute partielle silencieuse.

## US-02 - Tri par volume de trade 24h
**En tant que** trader/ops  
**Je veux** que les paires soient triees par volume de trade 24h decroissant  
**Afin de** prioriser les marches les plus liquides.

### Criteres d'acceptation
1. Le tri est effectue sur le volume 24h (champ defini en conception, ex: `quoteVolume`).
2. L'ordre final des paires est strictement decroissant.
3. Le log de demarrage indique les premieres paires retenues pour audit.

## US-03 - Limitation du nombre de paires via variable d'environnement
**En tant que** operateur  
**Je veux** configurer le nombre de paires a ecouter via une variable d'environnement  
**Afin de** controler la charge du daemon sans changement de code.

### Criteres d'acceptation
1. La variable `USDC_PAIRS_LIMIT` determine le nombre de paires retenues.
2. Si `USDC_PAIRS_LIMIT` est absente, une valeur par defaut est appliquee.
3. Si la valeur est invalide (`<= 0`, non numerique), le daemon echoue avec message clair.

## US-04 - Ecoute websocket sur la liste dynamique
**En tant que** systeme de streaming  
**Je veux** que le daemon s'abonne aux klines 1m de la liste dynamique calculee  
**Afin de** collecter les donnees des paires selectionnees automatiquement.

### Criteres d'acceptation
1. Le daemon construit les streams websocket a partir de la liste dynamique.
2. Le nombre de streams abonnes correspond exactement a la limite retenue.
3. En cas de reconnexion, la meme logique de selection est rejouee avant resubscribe.

## US-05 - Override manuel (optionnel)
**En tant que** operateur  
**Je veux** pouvoir forcer une liste statique de symboles via `SYMBOLS`  
**Afin de** faire du debug/exploitation ciblee.

### Criteres d'acceptation
1. Si `SYMBOLS` est renseignee, elle est prioritaire sur la selection dynamique.
2. Le log indique explicitement que le mode override est actif.
3. Le comportement existant de collecte reste identique pour ces symboles.

## NFR (Non-Fonctionnel)
1. Le demarrage (selection + tri + souscription) doit rester < 5s hors latence reseau exceptionnelle.
2. Les erreurs API Binance doivent etre observables (logs structures).
3. Le mecanisme ne doit pas depasser les limites de souscription websocket Binance (chunking/throttling existant conserve).
