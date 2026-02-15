#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: rollback_smoke.sh <owner/repo> <sha_tag>" >&2
  exit 2
fi

repo="$1"
sha_tag="$2"
image="ghcr.io/${repo}:${sha_tag}"

echo "rollback_smoke_image=${image}"
docker manifest inspect "${image}" >/dev/null
echo "rollback_smoke_result=ok"
