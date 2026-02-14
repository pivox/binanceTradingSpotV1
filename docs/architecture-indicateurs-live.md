# Architecture cible - Indicateurs live, rattrapage, API catalogue et UI screener

## Objectif
Concevoir une architecture coherente pour realiser US-0005 a US-0008 sans divergence de calcul, avec robustesse face aux trous de donnees et limites Binance, puis exposition stable pour l'UI.

## Principes d'architecture
1. **Source de verite unique des bougies**: stockage local des candles closes (`is_final=true`) avant tout calcul.
2. **Moteur deterministic**: meme historique en entree => memes indicateurs en sortie (tolerance numerique <= 1e-8).
3. **Pipeline event-driven**: ingestion, rattrapage, calcul, exposition API decouples par files/evenements internes.
4. **Contrat API versionne**: OpenAPI design-first, indisponibilite explicite (`status/reason`).
5. **UI orientee performance**: virtualisation, debounce, tri/filtre cote client + serveur selon volumetrie.

## Vue logique (composants)

### 1) Ingestion temps reel
- **Market Data Ingestor**
  - recoit klines Binance,
  - persiste uniquement les bougies closes,
  - detecte out-of-order/corrections tardives,
  - publie `candle.closed`.

### 2) Gap Detection + Backfill (US-0006)
- **Gap Detector**
  - scanne par `(symbol, timeframe)` et detecte plages manquantes.
- **Backfill Orchestrator**
  - ordonnance les rattrapages selon priorites,
  - controle budget weight Binance via headers `X-MBX-USED-WEIGHT-*`,
  - applique politique 429/418 (backoff/cooldown),
  - publie `candle.backfilled`.

### 3) Moteur d'indicateurs (US-0005)
- **Indicator Engine**
  - consomme `candle.closed` et `candle.backfilled`,
  - maintient un etat incremental par `(symbol,timeframe)`,
  - recalcule depuis la premiere bougie impactee si correction,
  - calcule RSI/EMA/SMA/MACD/Bollinger/ATR/VWAP/ADX/StochRSI/Pivots selon specs PO,
  - produit `indicator.snapshot.computed`.

### 4) Stockage lecture/API (US-0007)
- **Snapshot Store**
  - table dernier snapshot + table historique snapshots,
  - index `symbol,timeframe,close_time desc`.
- **Indicator API**
  - route dernier snapshot (ETag/304),
  - route historique paginee par curseur opaque,
  - expose format `status/reason` par champ,
  - publie metriques p50/p95 + cache hit.

### 5) UI Screener (US-0008)
- **Indicators Screener UI**
  - table virtuelle (>=100 lignes),
  - filtres/tris debounce,
  - colonnes configurables,
  - gestion `stale` et `last updated`,
  - presets sauvegardables.

## Flux de donnees principal
1. Binance -> Ingestor -> `candles`
2. Gap Detector detecte trous -> Backfill Orchestrator appelle Binance REST
3. Backfill complete trous -> `candles`
4. Indicator Engine lit candles closes -> calcule snapshot
5. Snapshot Store persiste
6. API lit Snapshot Store -> UI consomme API

## Donnees et schema (proposition)

### Tables
- `candles(symbol, timeframe, open_time, close_time, open, high, low, close, volume, is_final, source, updated_at)`
- `indicator_snapshots(symbol, timeframe, close_time, computed_at, schema_version, payload_json, etag, rsi, macd_hist, atr, adx, stoch_rsi_k, stoch_rsi_d, vwap, bb_upper, bb_middle, bb_lower, ... indicateurs filtrables/triables)`
- `indicator_state(symbol, timeframe, state_json, last_close_time, updated_at)` (etat incremental/warmup)
- `backfill_jobs(id, symbol, timeframe, range_start, range_end, priority, status, attempts, next_retry_at, last_error, created_at, updated_at)`
- `api_rate_budget(scope, used_weight, window, observed_at)`

### Contrat payload (US-0007)
- Respect strict des namespaces: `macd`, `bollinger`, `stoch_rsi`, `pivots`.
- Valeur indisponible en `{status:"unavailable",reason:"warmup|missing_history|not_supported"}`.
- `payload_json` reste la source canonique flexible; les colonnes numeriques denormalisees sont maintenues pour les filtres/tris performants US-0008.
- Index recommandes: (timeframe, close_time desc), (timeframe, rsi, close_time, symbol), (timeframe, macd_hist, close_time, symbol), et autres indexes btree composites couvrant le tri + tie-break.

## Strategies techniques clefs

### Determinisme calculs
- Interdire options implicites de librairies.
- Versionner les formules et parametres (`schema_version` + `calc_profile_version`).
- Jeu de reference fixe en tests de non-regression multi-environnements.

### Recalcul apres correction/out-of-order
- Trouver `t0` premiere bougie impactee.
- Rejouer candles `[t0..now]` pour ce `(symbol,timeframe)`.
- Upsert snapshots impacts en gardant tri strict `close_time`.

### Rate-limit Binance
- Bucket logique par fenetre minute + marge de securite.
- Degradation "slow mode" proche seuil critique.
- 429 -> backoff exponentiel + jitter (borne par config).
- 418 -> stop dur cible + alerte + cooldown obligatoire.

### API/Cache
- ETag derive de `(symbol,timeframe,close_time,computed_at,schema_version)`.
- Reponse 304 si `If-None-Match` egal.
- Historique par curseur opaque dependant du tri demande, encode `(sort_value, close_time, symbol, timeframe)`.
- Le serveur impose toujours un tie-break stable (`close_time`,`symbol`,`timeframe`) pour garantir une pagination deterministe, meme avec tri sur indicateur (`rsi`, `macd_hist`, etc.).

### Performance UI
- Virtualisation pour listes volumineuses.
- Memoization/selective updates pour eviter re-render complet.
- Debounce filtre/tri (ex. 150-300ms configurable).

## Observabilite
- **Ingestion**: candles recus/s, retard, out-of-order count.
- **Backfill**: trous detectes, taux succes, retries, 429, 418, temps cooldown.
- **Moteur indicateurs**: temps calcul par snapshot, recalc depth, erreurs numeriques.
- **API**: latence p50/p95, 304 hit ratio, erreurs par categorie.
- **UI**: temps rendu initial, latence interaction filtre/tri, stale duration.

## Securite et fiabilite
- Idempotence sur insertion candles/backfill.
- Retries bornes et sans boucle infinie.
- DLQ ou file d'erreurs pour jobs backfill en echec definitif.
- Feature flags pour activer incrementiellement timeframe/symbol universe.

## Risques et mitigations
1. **Divergence de calcul inter-env** -> kit de reference + tolerance fixe + CI.
2. **Ban Binance** -> controle dynamique weight + guardrails 429/418.
3. **Explosion cout calcul** -> incremental O(1) + recalc cible par segment.
4. **UI lente >200 pairs** -> virtualisation + pagination/cache + selective rendering.

## Open questions (a valider PO/Tech)
1. Univers initial des symbols/timeframes prioritaires en v1.
2. Strategie de refresh UI par defaut (poll vs push) et intervalle cible.
3. Retention historique snapshots (90j, 180j, autre).
4. Seuil exact de passage en "slow mode" rate-limit.
5. Politique de persistance presets UI (local storage vs serveur utilisateur).
