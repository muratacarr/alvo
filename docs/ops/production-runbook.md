# Production runbook (Raspberry Pi 5)

Status: **slices 1F-1 and 1F-2.** The production stack definition and the backup tooling exist and are tested. The stack cannot serve real users yet; see "Not done yet" at the end. Nothing in this file contains a secret.

## What exists

| Piece | File |
|---|---|
| Production stack (db, api, web, cloudflared) | `compose.prod.yaml` |
| Encrypted off-device backup | `ops/backup/backup.sh` |
| Restore drill (proves a backup works) | `ops/backup/restore-drill.sh` |
| Release (build, publish, attest) | `.github/workflows/release.yml` |
| Deploy and rollback on the Pi | `ops/deploy/deploy.sh` |

The production file differs from the development one on purpose: images by digest only, no published ports (the only way in is the outbound Cloudflare Tunnel), secrets from root-owned files outside the checkout, no internet route for the API or database, no development sign-in. `apps/api/tests/security/test_compose_prod_policy.py` enforces all of it.

## 1. Prepare the Pi (owner)

Run these and keep the output for the next slice (no secrets in it):

```
uname -m; lsb_release -a; free -h; df -h; lsblk -f
docker --version; docker compose version
```

- **Storage (decision D-6, 2026-10-27): the Pi runs from a 229 GB microSD card; the owner accepted this for now.** Constant database writes wear out SD cards, so treat the card as likely to fail someday and plan for it:
  - Use a high-endurance card (or move to a USB 3 SSD later: stop the stack, move Docker's `data-root`, start it again).
  - Back up **every 6 hours** instead of nightly (RPO 6 hours). The backup is the real safety net, so run a restore drill before launch.
  - Mount the root filesystem with `noatime`, keep `journald` logs bounded, and never run swap on the card.
  - Watch for early warnings: `sudo dmesg | grep -i -E 'mmc|i/o error'` and a filesystem that turns read-only mean "replace the card now".
  - Keep a spare card flashed with Ubuntu and Docker, so recovery is: new card, install, restore the latest backup.
- Install Docker from Docker's official apt repository (not `snap` and not Ubuntu's `docker.io`; the snap build restricts file access and breaks the secret and volume paths used here), and the host tools used by the backup: `age` and `rclone`.
- Enable automatic security updates and a host firewall. Docker bypasses `ufw` for published ports; this stack publishes none, which is the real protection.

## 2. Secrets (owner, on the Pi)

Secrets live in `/etc/alvo/secrets`, readable only by root; the directory, not the file mode, keeps other users out (containers run as other uids and read the bind-mounted files).

```
sudo install -d -m 700 /etc/alvo/secrets
cd /etc/alvo/secrets
sudo sh -c 'umask 022; openssl rand -base64 24 | tr -d "\n=+/" > db_password'
sudo sh -c 'umask 022; openssl rand -base64 48 | tr -d "\n" > alvo_session_secret'
# alvo_database_url must contain the same password as db_password:
#   postgresql+psycopg://alvo_app:<db_password>@db:5432/alvo
# Create it with an editor, not with a command that puts the password into your shell history.
# tunnel_token: the token from the Cloudflare dashboard (step 3).
```

Never paste these values into chat, issues, CI or a commit. Rotate them if they are ever exposed (see `secrets-management.md`).

## 3. Cloudflare Tunnel (owner)

1. Put the domain's **DNS** on Cloudflare (free plan). The owner's domain is registered at Namecheap and stays registered there: add the domain in Cloudflare, check that the imported DNS records are complete (especially any mail records, MX and TXT), then set the two Cloudflare nameservers in Namecheap (Domain List, Manage, Nameservers, Custom DNS). Wait until Cloudflare shows the domain as Active. Use a sub-domain such as `alvo.<your-domain>` for the app.
2. Zero Trust dashboard, Networks, Tunnels: create a tunnel, choose the Docker connector, and copy only the **token** into `/etc/alvo/secrets/tunnel_token`.
3. Add a public hostname (for example `alvo.<your-domain>`) with service type HTTP and URL `http://web:8080`.
4. Set `ALVO_PUBLIC_ORIGIN=https://alvo.<your-domain>`. The API refuses to start in production with an `http://` origin.

Traffic terminates at Cloudflare; this is the accepted trade-off for not opening any port at home (decision D-3).

## 4. Releasing and deploying

Two separate steps, on purpose: **GitHub builds and publishes** (after you approve), and **you deploy by hand on the Pi**. GitHub never holds a key to the Pi and nothing can push a change onto it.

### One-time GitHub setup (owner)
1. Settings, Environments, New environment `production`: tick **Required reviewers** and add yourself. A release run then waits for your approval before it publishes anything. Under "Deployment branches" allow only `main`.
2. After the first release, open each package (`alvo-api`, `alvo-web`) under your profile's Packages, Package settings, and set visibility to **Public**. The images contain no secrets (the repository is public too), and this lets the Pi pull them without storing any token.

### One-time Pi setup (owner)
- Put the repository on the Pi: `sudo git clone https://github.com/muratacarr/alvo.git /opt/alvo`.
- Install the GitHub CLI (`gh`) from GitHub's official apt instructions. The deploy script uses it to verify image attestations; no login is needed because the repository is public.
- Create `/etc/alvo/deploy.env` (mode 644, root) containing one line: `ALVO_PUBLIC_ORIGIN=https://alvo.<your-domain>`.

### Each release
1. Merge to `main` as usual (CI green).
2. Actions, **Release**, Run workflow (branch `main`). Approve the run when GitHub asks. It builds the two ARM64 images natively, publishes them tagged with the commit, signs provenance attestations, and produces the artifact `release-manifest` (commit and the two image digests; also shown in the run summary).
3. Download `release-manifest.json` and copy it to the Pi (for example `scp`).
4. On the Pi:
   ```
   sudo git -C /opt/alvo fetch && sudo git -C /opt/alvo checkout <commit from the manifest>
   sudo /opt/alvo/ops/deploy/deploy.sh /path/to/release-manifest.json
   ```
   The script refuses unless: the manifest has exactly the expected shape, both images carry an attestation made by this repository's release workflow, the checked-out commit equals the release commit, all secrets exist, the last backup is under 8 hours old, and there is enough disk space. It then pulls by digest, runs the database migrations **before** starting anything new (a failed migration leaves the old version running), starts the stack, waits for health, runs two smoke checks, and records the release in `/var/lib/alvo-deploy`.

### Rollback
Images roll back by redeploying the previous release; the database is not rolled back (migrations are forward-only, written as expand-then-contract, and a restore from backup is the last resort).

```
sudo git -C /opt/alvo checkout <previous commit>
sudo /opt/alvo/ops/deploy/deploy.sh --rollback /var/lib/alvo-deploy/previous.json
```

### First start on a new Pi
Do the secrets and tunnel steps above first. The very first deploy has no database to back up yet, so use the one-time `--first` option (the script refuses it once any release has been deployed):

```
sudo /opt/alvo/ops/deploy/deploy.sh --first /path/to/release-manifest.json
```

Then take the first backup right away (section 5) and run the restore drill. From the second deploy on, the script requires a backup younger than 8 hours. `docker compose -f compose.prod.yaml ps` should show every service healthy; `cloudflared` shows `unhealthy` while the tunnel is not connected.

## 5. Backups

**Design (decision D-4, 2026-10-27): the backup copy goes to Backblaze B2 (bucket `alvo-storage`, private, server-side encryption on).**

- `backup.sh` runs `pg_dump`, encrypts it with the **public** age key and uploads the file with rclone. The Pi never holds the private key, so someone who steals the Pi, the bucket or the files cannot read the backups.
- The Pi's B2 application key is **Write Only** and limited to bucket `alvo-storage` and the file prefix `db/`. It cannot list, read or delete files, so a compromised Pi cannot destroy or read the stored backups. Because it cannot read, **restoring means downloading the file in the B2 web console** (or with a separate read key that you create only when needed).
- Retention is a B2 lifecycle rule, not a script: file path `db/`, days till hide 35, days till delete 1. `ALVO_BACKUP_KEEP_DAYS` stays unset for B2 (it is for local folders).
- Home-computer pull (a read-only SSH user that copies the Pi's local folder) was designed first and is kept below as an **optional second destination**; it is not set up.

One-time setup:

1. **Key pair for encryption (on your own computer, not on the Pi).** Windows: `winget install FiloSottile.age`, then `age-keygen -o alvo-backup.key`. Keep this file offline (password manager and a second offline copy). Losing it means losing every backup. Copy only the printed public key (`age1...`) to the Pi.
2. **Backblaze B2 (primary destination).** Create a private bucket with encryption on and the lifecycle rule above. Create an application key: name `alvo-pi-yedek`, bucket `alvo-storage`, type **Write Only**, file name prefix `db/`, no "list all bucket names". (The web form offers only Read and Write, Read Only and Write Only; Read and Write includes delete, so do not use it for the Pi.) Then on the Pi, entering the key ID and key only in the terminal, never in chat or a file you commit:
   ```
   sudo rclone config                      # new remote "alvo-b2", type b2
   sudo install -m 600 -o root -g root /root/.config/rclone/rclone.conf /etc/alvo/rclone.conf
   ```
   The service runs with `ProtectHome=yes` and cannot see `/root`, so the rclone settings must live in `/etc/alvo/rclone.conf` (root only) and be named in `backup.env` with `RCLONE_CONFIG`. Keep the key ID and key in your password manager; rotate them if they were ever exposed.
   Settings in `/etc/alvo/backup.env` (no secrets in this file):
   ```
   ALVO_BACKUP_AGE_RECIPIENT=age1...
   ALVO_BACKUP_REMOTE=alvo-b2:alvo-storage/db
   RCLONE_CONFIG=/etc/alvo/rclone.conf
   RCLONE_LOW_LEVEL_RETRIES=2
   RCLONE_CONTIMEOUT=10s
   RCLONE_TIMEOUT=60s
   RCLONE_VERBOSE=1
   ```
   From the home network, `f003.backblazeb2.com` (the download host) timed out in the TLS handshake while the API host answered quickly. rclone looks the target name up there before uploading, which made `copyto` fail. `backup.sh` therefore uses `--no-check-dest` (names carry a UTC timestamp and are always new), and the short timeouts above keep a bad network from hanging the service for minutes. A backup took about 13 seconds afterwards.

   *Optional second destination (not set up): a read-only user for a home computer to pull from the Pi's local folder (`ALVO_BACKUP_REMOTE=/var/backups/alvo` and `ALVO_BACKUP_KEEP_DAYS=14` would then be used instead). The rest of this step, step 3 and step 5 are only for that:*
   ```
   sudo groupadd --system alvo-backup
   sudo useradd --system --create-home --shell /usr/sbin/nologin --gid alvo-backup alvo-backup-reader
   sudo chown root:alvo-backup /var/backups/alvo
   sudo chmod 2750 /var/backups/alvo        # setgid: new files keep the group
   ```
   New backups are written with mode 640 (owner root, group `alvo-backup`). Files created before this change (mode 600) need `sudo chgrp alvo-backup /var/backups/alvo/*.age && sudo chmod 640 /var/backups/alvo/*.age` once.
3. **Read-only SSH key for the home computer.** Generate a key pair on the home computer (`ssh-keygen -t ed25519 -f alvo-backup-pull`), and put the public half in `/home/alvo-backup-reader/.ssh/authorized_keys` on the Pi with the options `restrict` in front of it (no shell, no forwarding). The reader user can only read the folder above, because of the file permissions.
4. **Schedule on the Pi (systemd timer, every 6 hours at 02, 08, 14 and 20 o'clock).** The settings file `/etc/alvo/backup.env` (step 2) holds only the PUBLIC key, the destination and rclone options, no secrets. Create it with `sudo` and an editor, mode 644:
   ```
   sudo cp /opt/alvo/ops/systemd/alvo-backup.service /opt/alvo/ops/systemd/alvo-backup.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl start alvo-backup.service        # take the first backup now
   sudo systemctl status alvo-backup.service       # should say "backup ok: alvo-....dump.age"
   sudo systemctl enable --now alvo-backup.timer
   systemctl list-timers alvo-backup.timer
   ```
   Replace `age1...` with your real public key (it is not a secret). The units live in `ops/systemd/`.
5. **Schedule on the home computer** (Windows Task Scheduler, every 6 hours, only while it is on): `rclone copy` from the Pi's folder to a local folder, using an rclone SFTP remote with the key from step 3. Restrict the key file to your user. If the computer is off for a while, nothing is lost: the Pi keeps 14 days of backups and the next run catches up.

The script refuses a suspiciously small dump, uploads nothing on failure, prunes old files only after the new one is stored, and records `/var/lib/alvo-backup/last-success` (the deploy step in the next slice will refuse to deploy without a fresh backup).

**Restore drill (do it before launch, then every quarter).** Never practise on production. Use a scratch stack, for example the development stack on your computer:

```
# download one backup in the B2 web console (Browse Files, db/), start the dev database
# (docker compose up -d db), then in Git Bash:
ALVO_BACKUP_AGE_IDENTITY=/path/to/alvo-backup.key \
  ops/backup/restore-drill.sh alvo-20260101T020000Z.dump.age
```

It restores into a temporary database, prints the table count and schema version, then drops it. A backup that has never been restored is not a backup.

Targets: RPO 6 hours on the microSD card (24 hours once the database is on an SSD), RTO 4 hours. Schedule the backup every 6 hours.

### What was verified, and how

On 2026-10-26 the real chain (real `pg_dump`, real `age`, real `pg_restore`) was run against the development database: the encrypted file started with the age header and contained no plaintext, the drill restored 10 tables at schema version 0005, a wrong key failed cleanly, and the live database was untouched. That first run used a stand-in for `rclone`.

On 2026-10-27 the real chain ran on the Pi: `backup.sh` from the systemd service uploaded an encrypted dump (23 399 bytes) to B2 with the Write Only key; the file was downloaded in the B2 web console and restored on the owner's computer with the private key (`restore drill ok: 10 tables, schema version 0005`, scratch database dropped, live database untouched). The data was nearly empty (nobody can sign in yet), so repeat the drill once real data exists. Not tested: B2 lifecycle deletion (it acts after 35 days), the home-computer pull (not set up), and the private key's offline copies (the owner must confirm the password manager and USB copies open).

## Not done yet (do not tell anyone the system is production-ready)

- **Real sign-in method.** In production nobody can sign in yet. Google sign-in with invitations is built (slice 1G-1, ADR 0010) but not switched on: it needs the Google OAuth client, an egress network for the API and the web button (slice 1G-2).
- **Proven on 2026-10-27:** a real release run, `gh attestation verify` for both images, the first deploy with `deploy.sh --first`, external checks (HTTPS with strict CSP, `/docs` and `/openapi.json` return 404, unauthenticated API call returns 401, HTTP redirects to HTTPS), and a real off-device backup plus restore (section 5). **Not yet proven:** a normal (non-first) deploy with its backup-freshness gate, `--rollback`, a reboot test that brings the stack back healthy without help, an external port scan, and low-disk and tunnel-down behaviour. HSTS is not enabled yet. The Pi's `gh` login token expires after 90 days: renew it before then, or deploys will refuse (attestation check).
- **Rate limiting is built (slice 1F-3, ADR 0009) but untested on the Pi.** Check it after the next deploy: send more than 40 quick requests to `/api/v1/auth/me` from one machine and expect `429`. Cloudflare-side rate limiting and bot protection are optional extras set in the Cloudflare dashboard.
- **Provider calls and spend control** (BudgetGuard): Phase 3.
