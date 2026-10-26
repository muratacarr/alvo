#!/usr/bin/env bash
# Nightly encrypted database backup, sent off the device.
#
#   pg_dump  ->  age (public key only)  ->  object storage via rclone
#
# The server holds only the PUBLIC age key, so a stolen server cannot decrypt old backups.
# The private key stays with the owner (offline). Nothing secret is printed.
#
# Required environment:
#   ALVO_BACKUP_AGE_RECIPIENT  age public key ("age1...")
#   ALVO_BACKUP_REMOTE         rclone destination, e.g. "alvo-backups:my-bucket/db"
# Optional:
#   ALVO_COMPOSE               how to reach the stack (default: docker compose -p alvo, i.e. the running
#                              project; the production Compose file itself needs release variables)
#   ALVO_BACKUP_STATE_DIR      where the "last success" marker is written (default /var/lib/alvo-backup)
#   ALVO_BACKUP_KEEP_DAYS      delete backups older than this many days from the destination, but
#                              only after the new one was uploaded. Use it when the destination is
#                              a local folder; leave it unset for object storage (use its lifecycle rules).
#
# ALVO_BACKUP_REMOTE may be a plain folder (for example /var/backups/alvo). A computer at home then
# PULLS the files from the Pi (see docs/ops/production-runbook.md), so the Pi holds no credentials
# for that computer.
set -euo pipefail
umask 077

: "${ALVO_BACKUP_AGE_RECIPIENT:?set ALVO_BACKUP_AGE_RECIPIENT to the age public key}"
: "${ALVO_BACKUP_REMOTE:?set ALVO_BACKUP_REMOTE to the rclone destination}"
compose="${ALVO_COMPOSE:-docker compose -p alvo}"
state_dir="${ALVO_BACKUP_STATE_DIR:-/var/lib/alvo-backup}"
min_bytes=1024
keep_days="${ALVO_BACKUP_KEEP_DAYS:-}"

case "$keep_days" in
  "") ;;
  *[!0-9]* | 0) echo "ALVO_BACKUP_KEEP_DAYS must be a positive whole number" >&2; exit 2 ;;
  *) ;;
esac

case "$ALVO_BACKUP_AGE_RECIPIENT" in
  age1*) ;;
  *) echo "ALVO_BACKUP_AGE_RECIPIENT must be an age public key (age1...)" >&2; exit 2 ;;
esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

name="alvo-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
file="$work/$name"

# shellcheck disable=SC2086  # $compose is intentionally split into words
$compose exec -T db pg_dump -U alvo_app -d alvo --format=custom | age -r "$ALVO_BACKUP_AGE_RECIPIENT" -o "$file"

size="$(wc -c < "$file")"
if [ "$size" -lt "$min_bytes" ]; then
  echo "backup is suspiciously small (${size} bytes); not uploading" >&2
  exit 1
fi

rclone copyto "$file" "${ALVO_BACKUP_REMOTE%/}/$name"

if [ -n "$keep_days" ]; then
  rclone delete --min-age "${keep_days}d" --include "alvo-*.dump.age" "${ALVO_BACKUP_REMOTE%/}"
fi

mkdir -p "$state_dir"
date -u +%s > "$state_dir/last-success"
echo "backup ok: $name (${size} bytes)"
