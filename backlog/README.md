# Backlog produit et technique

- `backlog/po/`: user stories (US), exigences fonctionnelles et critères d'acceptation.
- `backlog/techlead/`: tickets techniques, découpage d'implémentation, dette technique.
- `backlog/bug/`: bugs rédigés par QA.

Ce dossier remplace l'usage de `docs/` pour le suivi opérationnel PO/Tech Lead.

## Règles de workflow

- Les fichiers restent dans leur dossier par rôle. Ils ne sont jamais déplacés selon leur status.
- Le status est porté par le front-matter YAML (`id`, `title`, `status`, `owner`, `links`).
- Action QA standard: `valider les bugs rédigés` signifie mettre le bug en `status: VALIDATED` avec `owner: qa`, puis compléter les `links` vers les tickets concernés.
