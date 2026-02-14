---
id: T-0028
title: "QA - Non-regression indicateurs, backfill et contrat API"
status: TODO
owner: techlead
links: ["US-0005", "US-0006", "US-0007", "US-0008", "T-0022", "T-0023", "T-0024", "T-0026", "T-0027"]
---

## Contexte
Les US introduisent un risque eleve de regression silencieuse (calcul numerique, pagination, indisponibilite, performance UI).

## Perimetre
- Construire plan de tests transverses backend/frontend.
- Definir dataset de reference pour indicateurs (golden files).
- Definir matrice de tests contrat API (schema, ETag, curseur, erreurs).
- Definir tests acceptance UI (filtres/tris/stale/accessibilite).

## Criteres d'acceptation
1. Suite de non-regression automatisee executee en CI.
2. Rapports de divergence numerique exploitables.
3. Checklists manuelles de release documentees.

## Definition of Done
- Plan QA valide par techlead + PO.
- Evidence tests rattachees aux tickets de livraison.
