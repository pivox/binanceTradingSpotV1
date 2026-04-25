# Trading Pipeline — Functional TODO

> Dernière mise à jour : 2026-04-25
> Périmètre : fonctionnel uniquement — ce qui empêche un trade complet de fonctionner de bout en bout.
> Les tâches techniques (stubs orphelins, pytest config, dead code) sont suivies séparément.

---

## Contexte : flux d'un trade

```
[bougie 1m fermée]
        │
        ▼
[cascade 4h→1m évaluée]
        │
        ▼
[signal généré → BUY intent créé]
        │
        ▼
[ordre BUY envoyé sur Binance]
        │
        ▼ (fill via ws_user)
[position ACTIVE]
        │
        ├── SL order placé sur Binance
        ├── TP Lot A / Lot B placés sur Binance
        │
        ▼ (tick 5m)
[exit engine évalué]
        │
        ├── high_since_entry mis à jour
        ├── breakeven / trailing → UPDATE_SL envoyé
        └── TP/SL touché → SELL intent créé
        │
        ▼ (fill via ws_user)
[lot marqué rempli → position CLOSED si tout rempli]
```

Les cases ✗ ci-dessous correspondent aux étapes non implémentées.

---

## F-001 — Déclencheur cascade depuis la bougie 1m

**Priorité : BLOQUANT**

### Problème
`ConsumeCandleEventsWorkflow` calcule les snapshots d'indicateurs mais ne déclenche
jamais `CascadeValidateAndEnterWorkflow`. Les deux workflows sont déconnectés :
aucune bougie 1m fermée ne provoque d'évaluation de signal ni d'entrée en position.

### Ce qu'il faut faire
- Dans `ConsumeCandleEventsWorkflow.run()`, après le calcul du snapshot, si
  `evt.timeframe == "1m"` lancer un child workflow (ou une activité directe) qui
  appelle la cascade pour ce symbole.
- Conditionner le lancement : ne déclencher que si aucune position ACTIVE/PENDING
  n'existe déjà sur ce symbole (contrôle de doublons).
- Fichier concerné : `src/tradebot/temporal_app/workflows.py`

### Critère d'acceptation
Une bougie 1m fermée sur BTCUSDC déclenche une évaluation de cascade. Si le signal
est valide, un `OrderIntent` BUY est créé en base dans les 5 secondes.

---

## F-002 — Placement des ordres SL et TP après fill BUY

**Priorité : BLOQUANT**

### Problème
Quand un ordre BUY est rempli (détecté via `ws_user` → `executionReport X=FILLED`),
aucune protection n'est placée sur Binance. Le stop-loss n'existe qu'en base de
données. Si le prix s'effondre, rien ne protège la position.

### Ce qu'il faut faire
1. Dans `ws_user._handle_execution_report`, quand `side=BUY` et `status=FILLED` :
   - Lancer un workflow (ou appel d'activité) `PostFillSetupWorkflow(position_id)`.
2. Ce workflow doit placer 3 ordres sur Binance :
   - **STOP-LIMIT** au niveau `position.stop_loss` — protection downside, lot ALL.
   - **LIMIT GTC** au niveau `signal.tp_lot_a` — take profit Lot A (60 %).
   - **LIMIT GTC** au niveau `signal.tp_lot_b` — take profit Lot B (30 %).
3. Stocker les `binance_order_id` de ces ordres dans les lots correspondants de
   `exit_plan_json` pour pouvoir les annuler si besoin.

### Critère d'acceptation
Après un fill BUY, 3 ordres apparaissent sur Binance (vérifiable via
`GET /api/v3/openOrders`). Leurs IDs sont stockés dans `exit_plan_json`.

---

## F-003 — Mise à jour de `high_since_entry`

**Priorité : HAUTE**

### Problème
Le trailing stop Lot C calcule `trailing_level = high_since_entry - atr * 2`.
`high_since_entry` est initialisé à `entry_price` lors de la création de position
et **n'est jamais mis à jour**. Le trailing ne monte jamais, quelle que soit la
hausse du prix.

### Ce qu'il faut faire
- Dans `update_position_after_actions`, en plus de `last_checked_ms`, mettre à jour
  `high_since_entry` si le prix actuel (close de la bougie 5m) est supérieur.
- L'activité `apply_exit_engine` dispose déjà de la bougie 5m : elle doit retourner
  `new_high` dans son résultat.
- Le workflow `ManageOpenPositionsWorkflow` passe ce `new_high` dans le `patch` de
  `update_position_after_actions`.
- Fichiers : `activities.py` (`apply_exit_engine`, `update_position_after_actions`),
  `workflows.py` (`ManageOpenPositionsWorkflow`).

### Critère d'acceptation
Après 10 bougies 5m avec prix croissant, `positions.high_since_entry` reflète le
plus haut observé. Le niveau de trailing calculé par l'exit engine monte en
conséquence.

---

## F-004 — Envoi des mises à jour SL vers Binance (breakeven / trailing)

**Priorité : HAUTE**

### Problème
L'exit engine retourne des intents de type `UPDATE_SL` (breakeven à 1R/1.5R,
mise à jour du niveau trailing Lot C). `ManageOpenPositionsWorkflow` n'en tient
pas compte — seules les actions `SELL` sont traitées.
Les modifications de stop-loss ne parviennent jamais à Binance.

### Ce qu'il faut faire
1. Dans `ManageOpenPositionsWorkflow.run()`, traiter les actions `UPDATE_SL` :
   - Annuler l'ordre STOP actuel sur Binance (`cancel_order`).
   - Placer un nouvel ordre STOP au nouveau niveau (`place_order`).
   - Mettre à jour `position.stop_loss` et `exit_plan_json` (lot trailing level).
2. Créer une activité `update_stop_loss(position_id, new_sl, symbol)` ou réutiliser
   `create_sell_intent` avec `order_type=STOP_MARKET`.

### Critère d'acceptation
Quand le prix atteint 1R, l'ordre STOP initial est annulé et remplacé par un nouvel
ordre au niveau breakeven. Vérifiable via les logs Binance et le champ
`stop_loss` en base.

---

## F-005 — Fermeture de la position quand tous les lots sont remplis

**Priorité : MOYENNE**

### Problème
Quand les lots A, B et C sont tous remplis (`exit_plan.all_filled == True`), la
position reste indéfiniment au statut `ACTIVE`. Elle continue d'être chargée par
`fetch_due_positions` et évaluée par l'exit engine à chaque tick.

### Ce qu'il faut faire
- Dans `ws_user._handle_execution_report`, après avoir marqué un lot comme rempli,
  relire `exit_plan_json` et vérifier si `all_filled`.
- Si oui : `UPDATE positions SET status='CLOSED', closed_at_ms=$now WHERE id=$pos_id`.
- Annuler les éventuels ordres Binance encore ouverts sur cette position
  (l'ordre SL doit être annulé si Lot C a été le dernier rempli).

### Critère d'acceptation
Après le fill du dernier lot, `positions.status = 'CLOSED'` et aucun ordre ouvert
ne subsiste sur Binance pour cette position.

---

## F-006 — Suivi du statut de position tout au long du cycle de vie

**Priorité : MOYENNE**

### Problème
Les transitions de statut sont incomplètes :

| Événement | Statut attendu | Statut actuel |
|-----------|----------------|---------------|
| `create_buy_intent` | `PENDING_ENTRY` | ✅ |
| `place_order` envoyé | `OPEN_ENTRY_SENT` | ✗ reste `PENDING_ENTRY` |
| BUY fill (ws_user) | `ACTIVE` | ✅ |
| `create_sell_intent` envoyé | `CLOSING` | ✗ reste `ACTIVE` |
| Tous lots remplis | `CLOSED` | ✗ (F-005) |

### Ce qu'il faut faire
- `place_order` : après envoi réussi d'un BUY, `UPDATE positions SET status='OPEN_ENTRY_SENT'`.
- `create_sell_intent` : lors de la création d'un premier SELL, `UPDATE positions SET status='CLOSING'`.
- Fichier : `activities.py`.

### Critère d'acceptation
À tout moment, `positions.status` reflète exactement l'étape du trade en cours.
Un tableau de bord peut afficher l'état en temps réel sans ambiguïté.

---

## Récapitulatif et ordre d'exécution suggéré

```
F-001  Déclencheur cascade           BLOQUANT   ~1j
F-002  Ordres SL + TP post-fill BUY  BLOQUANT   ~1j
F-003  high_since_entry              HAUTE      ~2h
F-004  UPDATE_SL vers Binance        HAUTE      ~4h
F-005  Position CLOSED               MOYENNE    ~2h
F-006  Transitions de statut         MOYENNE    ~2h
```

**F-001 et F-002 en premier** — sans eux, aucune position ne peut être ouverte ni
protégée. Les autres peuvent être développées en parallèle une fois le flux
de base opérationnel.

---

## Hors périmètre (non bloquant)

Les éléments suivants sont utiles mais non nécessaires pour un premier trade live :

- **PnL en temps réel** — calcul du profit/perte par position et journalier.
- **Circuit-breaker** — arrêt automatique si la perte journalière dépasse un seuil.
- **Alerting** — notifications Slack/email sur fill, stop touché, timeout.
- **Backtesting offline** — rejouer l'historique pour valider la stratégie.
- **Gestion des fills partiels BUY** — ajuster `entry_price` et `quantity_total`
  progressivement si l'ordre LIMIT ne se remplit que partiellement.
