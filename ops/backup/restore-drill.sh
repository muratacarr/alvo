#!/usr/bin/env bash
# Restore drill: proves a backup can really be restored. Run it against a SCRATCH stack
# (for example the development stack on your own computer), not against production.
#
#   restore-drill.sh path/to/alvo-YYYYMMDDTHHMMSSZ.dump.age
#
# Required environment:
#   ALVO_BACKUP_AGE_IDENTITY  path to the PRIVATE age key file (kept offline, given only at drill time)
# Optional:
#   ALVO_COMPOSE              how to reach the scratch stack (default: docker compose)
#
# The live database "alvo" is never touched: the dump is restored into a temporary database
# that is dropped afterwards.
set -euo pipefail
umask 077

backup="${1:?usage: restore-drill.sh <backup file>}"
: "${ALVO_BACKUP_AGE_IDENTITY:?set ALVO_BACKUP_AGE_IDENTITY to the private age key file}"
compose="${ALVO_COMPOSE:-docker compose}"
scratch="alvo_restore_drill"

[ -f "$backup" ] || { echo "backup file not found" >&2; exit 2; }
[ -f "$ALVO_BACKUP_AGE_IDENTITY" ] || { echo "age identity file not found" >&2; exit 2; }

# shellcheck disable=SC2086
psql_admin() { $compose exec -T db psql -v ON_ERROR_STOP=1 -U alvo_app -d postgres "$@"; }

cleanup() { psql_admin -c "DROP DATABASE IF EXISTS ${scratch}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

psql_admin -c "DROP DATABASE IF EXISTS ${scratch}" >/dev/null
psql_admin -c "CREATE DATABASE ${scratch}" >/dev/null

# shellcheck disable=SC2086
age -d -i "$ALVO_BACKUP_AGE_IDENTITY" "$backup" | $compose exec -T db pg_restore -U alvo_app -d "$scratch" --no-owner --exit-on-error

# shellcheck disable=SC2086
tables="$($compose exec -T db psql -At -U alvo_app -d "$scratch" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
# shellcheck disable=SC2086
version="$($compose exec -T db psql -At -U alvo_app -d "$scratch" -c "SELECT version_num FROM alembic_version")"

if [ "${tables:-0}" -lt 1 ]; then
  echo "restore produced no tables" >&2
  exit 1
fi
echo "restore drill ok: ${tables} tables, schema version ${version}"
