# Security Review Checklist (run on EVERY change)

Record the result in the slice report. Critical/High block acceptance; Medium needs a fix or an owner-approved, expiring exception.

1. **Trust boundaries:** what new inputs, outputs or data flows does this change add?
2. **AuthN/AuthZ:** sessions, CSRF, CORS; ownership checks on every object; two-user negative tests (BOLA/BFLA).
3. **Input and output:** validation bounds, injection, XSS, file handling, deserialization, resource limits.
4. **Secrets and privacy:** no secrets, tokens, PII or recordings in code, fixtures, migrations, logs, errors, images.
5. **Supply chain:** new or changed dependencies, lockfile diff, action or base-image pins, known vulnerabilities.
6. **Configuration and infrastructure:** defaults fail closed; no published ports, privileged containers or broad permissions.
7. **Tests:** malicious and negative cases exist and were seen failing first; OWASP ASVS / API Top 10 mapping noted.
8. **Spend:** does anything reach a paid provider outside `BudgetGuard`?

Report format: scope reviewed, controls applied, findings (severity, exploitability), evidence, fixes, residual risk.
