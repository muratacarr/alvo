# Known and Accepted Scanner Findings

Findings that a scanner reports but that are accepted by design are recorded here instead of being silenced without explanation. Each entry needs a rationale, compensating controls and a review trigger.

## KF-001: CodeQL `py/clear-text-storage-sensitive-data` in `apps/api/scripts/make_dev_secrets.py`

- **Status:** Accepted (dismissed in GitHub code scanning as "Won't fix"), 2026-10-26.
- **What the scanner sees:** a randomly generated database password is written to a file.
- **Why it is by design:** the script generates local development secrets. Docker secrets are plaintext files mounted at `/run/secrets`; there is no encrypted alternative in Compose.
- **Compensating controls:**
  - Output directory `secrets/` is gitignored and created with mode `0700`.
  - Values are random per developer and valid only for the local throwaway database.
  - The script never overwrites existing files and never prints values.
  - Production secrets are provisioned outside the repository (slice 1F); this script is not used there.
- **Suggested fix rejected:** switching the URL to `?passfile=<path>` would not work. libpq expects a `.pgpass`-format file (`host:port:db:user:password`), the host path does not exist inside the container, and `Settings` requires a password in the URL (covered by tests).
- **Review trigger:** revisit if the script is ever reused outside local development, or if Compose gains native encrypted secrets.
