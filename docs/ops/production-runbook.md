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
Do the secrets and tunnel steps above first, then run the first release exactly as described. `docker compose -f compose.prod.yaml ps` should show every service healthy; `cloudflared` shows `unhealthy` while the tunnel is not connected.

## 5. Backups

**Design (decision D-4, 2026-10-27): the backup copy goes to a computer at home, and that computer pulls it.**

- `backup.sh` runs `pg_dump`, encrypts it with the **public** age key and stores the file in `/var/backups/alvo` on the Pi (kept for 14 days). The Pi never holds the private key, so someone who steals the Pi or the files cannot read the backups.
- Your home computer then **pulls** the files from the Pi with a read-only SSH key. The Pi has no key, password or address for the home computer, so a compromised Pi cannot reach it. The computer uses `copy`, never `sync`, so deleting files on the Pi cannot delete the copies.
- Trade-off you accepted: both machines are in the same home. Fire, theft or a power surge can take both. If that matters later, add cloud storage as a second destination (`ALVO_BACKUP_REMOTE` accepts any rclone remote); nothing else changes.

One-time setup:

1. **Key pair for encryption (on your own computer).** `age-keygen -o alvo-backup.key`. Keep this file offline (password manager and a second offline copy). Losing it means losing every backup. Copy only the printed public key (`age1...`) to the Pi.
2. **Backup folder on the Pi (as root).**
   ```
   sudo install -d -m 750 -o root -g root /var/backups/alvo
   sudo useradd --system --create-home --shell /usr/sbin/nologin alvo-backup-reader
   sudo setfacl -m u:alvo-backup-reader:rx /var/backups/alvo   # read-only access to the folder
   ```
   (Install `acl` if `setfacl` is missing. New files must also be readable: `sudo setfacl -d -m u:alvo-backup-reader:r /var/backups/alvo`.)
3. **Read-only SSH key for the home computer.** Generate a key pair on the home computer (`ssh-keygen -t ed25519 -f alvo-backup-pull`), and put the public half in `/home/alvo-backup-reader/.ssh/authorized_keys` on the Pi with the options `restrict` in front of it (no shell, no forwarding). The reader user can only read the folder above, because of the file permissions.
4. **Schedule on the Pi (systemd timer or cron, as root), every 6 hours:**
   ```
   ALVO_BACKUP_AGE_RECIPIENT=age1... \
   ALVO_BACKUP_REMOTE=/var/backups/alvo \
   ALVO_BACKUP_KEEP_DAYS=14 \
   /opt/alvo/ops/backup/backup.sh
   ```
5. **Schedule on the home computer** (Windows Task Scheduler, every 6 hours, only while it is on): `rclone copy` from the Pi's folder to a local folder, using an rclone SFTP remote with the key from step 3. Restrict the key file to your user. If the computer is off for a while, nothing is lost: the Pi keeps 14 days of backups and the next run catches up.

The script refuses a suspiciously small dump, uploads nothing on failure, prunes old files only after the new one is stored, and records `/var/lib/alvo-backup/last-success` (the deploy step in the next slice will refuse to deploy without a fresh backup).

**Restore drill (do it before launch, then every quarter).** Never practise on production. Use a scratch stack, for example the development stack on your computer:

```
# copy one backup file from your pulled folder, then:
ALVO_BACKUP_AGE_IDENTITY=/path/to/alvo-backup.key \
  ops/backup/restore-drill.sh alvo-20260101T020000Z.dump.age
```

It restores into a temporary database, prints the table count and schema version, then drops it. A backup that has never been restored is not a backup.

Targets: RPO 6 hours on the microSD card (24 hours once the database is on an SSD), RTO 4 hours. Schedule the backup every 6 hours.

### What was verified, and how

On 2026-10-26 the real chain (real `pg_dump`, real `age`, real `pg_restore`) was run against the development database: the encrypted file started with the age header and contained no plaintext, the drill restored 10 tables at schema version 0005, a wrong key failed cleanly, and the live database was untouched. The copy to the backup folder was done by a stand-in for `rclone`, so **real rclone (local folder, pruning with `--min-age`/`--include`, and the SFTP pull from the home computer) has not been tested**. Do that during the first setup.

## Not done yet (do not tell anyone the system is production-ready)

- **Real sign-in method.** In production nobody can sign in (the development login is forbidden there). Decision D-1 is still open.
- **The release workflow and the deploy script have never run for real.** Their logic is tested with stand-ins, and the workflow is linted, but the first real release, the attestation check (`gh attestation verify`), pulling from GHCR and the first start on the Pi are unverified until you do them (slice 1F-2 ships the tools, not the proof).
- **General and sign-in rate limiting** at the edge and in the API: slice 1F-3.
- **Host facts** (D-6) and the first real start on the Pi, including an external port scan, reboot test, low-disk and tunnel-down behaviour.
- **Provider calls and spend control** (BudgetGuard): Phase 3.
