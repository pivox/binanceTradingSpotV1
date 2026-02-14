# Indicators API

Endpoints for US-0007/T-0024:

- `GET /indicators/latest`
- `GET /indicators/history`

Both endpoints are read-only and return JSON.

## Query params

Common params:

- `symbol` (required): `^[A-Z0-9]{2,20}$`
- `timeframe` (required): `^[1-9][0-9]*[mhdwM]$`

History params:

- `limit` (optional, default `100`, bounded by `INDICATOR_HISTORY_MAX_LIMIT`)
- `cursor` (optional, opaque)

## Cache conditionnel

`GET /indicators/latest` supports HTTP conditional cache:

- Response `200` with `ETag`
- Response `304` when request sends matching `If-None-Match`

## Error payload (normalized)

On errors, the API returns:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_cursor",
    "message": "cursor is invalid",
    "categorie": "validation",
    "action_conseillee": "utiliser le curseur retourne par la page precedente"
  }
}
```

## OpenAPI source

Design-first contract source file:

- `docs/openapi-indicators.yaml`
