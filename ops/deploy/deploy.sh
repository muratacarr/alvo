#!/usr/bin/env bash
# Pull-based deploy, run BY HAND on the Pi (nothing outside can trigger it).
#
#   deploy.sh release-manifest.json              deploy a release
#   deploy.sh --rollback previous.json           go back to an earlier release (no migrations)
#
# The manifest comes from the approved "Release" workflow run (artifact "release-manifest").
# The script accepts only what that manifest names, and only if every check below passes:
#   1. the manifest has exactly the expected shape (commit, two sha256 digests);
#   2. a recent backup exists, there is enough free disk space, and all secrets are present;
#   3. both images carry a signed provenance attestation made by our release workflow;
#   4. database migrations succeed BEFORE the new containers are started;
#   5. the new containers become healthy and answer the smoke checks.
# Nothing here prints a secret.
#
# Settings (all optional):
#   ALVO_PUBLIC_ORIGIN         https address of the site (or put it in /etc/alvo/deploy.env)
#   ALVO_COMPOSE_FILE          default /opt/alvo/compose.prod.yaml
#   ALVO_SECRETS_DIR           default /etc/alvo/secrets
#   ALVO_DEPLOY_STATE_DIR      default /var/lib/alvo-deploy
#   ALVO_BACKUP_STATE_DIR      default /var/lib/alvo-backup
#   ALVO_BACKUP_MAX_AGE_HOURS  default 8 (backups run every 6 hours)
#   ALVO_MIN_FREE_GB           default 5
#   ALVO_DOCKER_ROOT           default /var/lib/docker (where free space is measured)
#   ALVO_VERIFY_ATTESTATIONS   "yes" (default) or "no" (weaker; use only knowingly)
set -euo pipefail
umask 077

rollback=no
if [ "${1:-}" = "--rollback" ]; then
  rollback=yes
  shift
fi
manifest="${1:?usage: deploy.sh [--rollback] <release-manifest.json>}"

if [ -f /etc/alvo/deploy.env ]; then
  # shellcheck disable=SC1091  # only ALVO_PUBLIC_ORIGIN is expected here
  . /etc/alvo/deploy.env
fi
compose_file="${ALVO_COMPOSE_FILE:-/opt/alvo/compose.prod.yaml}"
secrets_dir="${ALVO_SECRETS_DIR:-/etc/alvo/secrets}"
state_dir="${ALVO_DEPLOY_STATE_DIR:-/var/lib/alvo-deploy}"
backup_state="${ALVO_BACKUP_STATE_DIR:-/var/lib/alvo-backup}"
max_age_hours="${ALVO_BACKUP_MAX_AGE_HOURS:-8}"
min_free_gb="${ALVO_MIN_FREE_GB:-5}"
docker_root="${ALVO_DOCKER_ROOT:-/var/lib/docker}"
verify="${ALVO_VERIFY_ATTESTATIONS:-yes}"
repo="muratacarr/alvo"
workflow="${repo}/.github/workflows/release.yml"

fail() { echo "deploy refused: $*" >&2; exit "${2:-1}"; }

# 1. The manifest: strict shape, nothing else is accepted. -------------------------------
[ -f "$manifest" ] || fail "manifest file not found" 2
extract() {
  # prints the value of a one-line JSON string field only when it matches the given pattern
  sed -n "s/^ *\"$1\": \"\\($2\\)\",\\{0,1\\} *\$/\\1/p" "$manifest"
}
digest_re='sha256:[0-9a-f]\{64\}'
commit="$(extract commit '[0-9a-f]\{40\}')"
api_digest="$(extract api_digest "$digest_re")"
web_digest="$(extract web_digest "$digest_re")"
# Exactly one line for each field, a supported schema, and no other fields.
[ "$(grep -c '"commit"' "$manifest" || true)" = 1 ] || fail "manifest must contain one commit" 2
if [ -z "$commit" ] || [ -z "$api_digest" ] || [ -z "$web_digest" ]; then
  fail "manifest is malformed" 2
fi
grep -q '^ *"schema": 1,\{0,1\} *$' "$manifest" || fail "unsupported manifest schema" 2
[ "$(grep -c '":' "$manifest" || true)" = 4 ] || fail "manifest has unexpected fields" 2

: "${ALVO_PUBLIC_ORIGIN:?set ALVO_PUBLIC_ORIGIN (or /etc/alvo/deploy.env)}"
export ALVO_PUBLIC_ORIGIN
export ALVO_API_DIGEST="$api_digest"
export ALVO_WEB_DIGEST="$web_digest"
compose="docker compose -f $compose_file"

# The stack definition on the Pi must be the one that belongs to this release.
repo_dir="$(dirname "$compose_file")"
if [ -d "$repo_dir/.git" ]; then
  head="$(git -C "$repo_dir" rev-parse HEAD)"
  [ "$head" = "$commit" ] || fail "checked-out commit differs from the release commit; run: git -C $repo_dir fetch && git -C $repo_dir checkout $commit"
fi

# 2. Safe to proceed? (local checks first) --------------------------------------------------------------------
[ -f "$compose_file" ] || fail "compose file not found" 2
for secret in db_password alvo_database_url alvo_session_secret tunnel_token; do
  [ -s "$secrets_dir/$secret" ] || fail "secret file missing or empty: $secret"
done

if [ "$rollback" = "no" ]; then
  [ -f "$backup_state/last-success" ] || fail "no backup has ever succeeded; run backup.sh first"
  last="$(cat "$backup_state/last-success")"
  case "$last" in ''|*[!0-9]*) fail "backup marker is corrupt" ;; *) ;; esac
  age_hours=$(( ( $(date -u +%s) - last ) / 3600 ))
  [ "$age_hours" -le "$max_age_hours" ] || fail "last backup is ${age_hours}h old (limit ${max_age_hours}h); run backup.sh"
fi

probe="$docker_root"
[ -d "$probe" ] || probe=/
free_kb="$(df -Pk "$probe" | awk 'NR==2 {print $4}')"
[ "$(( free_kb / 1024 / 1024 ))" -ge "$min_free_gb" ] || fail "less than ${min_free_gb} GB of free disk space"

# 3b. Both images must come from our release workflow. -----------------------------------
if [ "$verify" = "yes" ]; then
  for image in "alvo-api@${api_digest}" "alvo-web@${web_digest}"; do
    gh attestation verify "oci://ghcr.io/muratacarr/${image}" --repo "$repo" \
      --signer-workflow "$workflow" >/dev/null || fail "no valid attestation for ${image%%@*}"
  done
else
  echo "WARNING: image attestations were NOT verified (ALVO_VERIFY_ATTESTATIONS=no)" >&2
fi

# 4. Prepare and migrate BEFORE switching anything. -------------------------------------
$compose config -q
$compose pull api web
if [ "$rollback" = "no" ]; then
  # Forward-only. A failed migration stops here, with the old version still running.
  $compose run --rm api alembic upgrade head
fi

# 5. Switch and prove it works. ----------------------------------------------------------
$compose up -d --wait --wait-timeout 180
smoke_ok=yes
$compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || smoke_ok=no
$compose exec -T web wget -q -O /dev/null http://127.0.0.1:8080/healthz || smoke_ok=no
if [ "$smoke_ok" != "yes" ]; then
  echo "smoke test FAILED. The previous release is saved; to go back run:" >&2
  echo "  ops/deploy/deploy.sh --rollback $state_dir/current.json" >&2
  exit 1
fi

# 6. Record it. --------------------------------------------------------------------------
mkdir -p "$state_dir/history"
if [ -f "$state_dir/current.json" ] && ! cmp -s "$state_dir/current.json" "$manifest"; then
  cp "$state_dir/current.json" "$state_dir/previous.json"
fi
cp "$manifest" "$state_dir/current.json"
cp "$manifest" "$state_dir/history/$(date -u +%Y%m%dT%H%M%SZ)-${commit%"${commit#????????????}"}.json"
echo "deployed ${commit} (rollback: ${rollback})"
