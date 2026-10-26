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
#   ALVO_COMPOSE               how to reach the stack (default: docker compose -f /opt/alvo/compose.prod.yaml)
#   ALVO_BACKUP_STATE_DIR      where the "last success" marker is written (default /var/lib/alvo-backup)
set -euo pipefail
umask 077

: "${ALVO_BACKUP_AGE_RECIPIENT:?set ALVO_BACKUP_AGE_RECIPIENT to the age public key}"
: "${ALVO_BACKUP_REMOTE:?set ALVO_BACKUP_REMOTE to the rclone destination}"
compose="${ALVO_COMPOSE:-docker compose -f /opt/alvo/compose.prod.yaml}"
state_dir="${ALVO_BACKUP_STATE_DIR:-/var/lib/alvo-backup}"
min_bytes=1024

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

mkdir -p "$state_dir"
date -u +%s > "$state_dir/last-success"
echo "backup ok: $name (${size} bytes)"
