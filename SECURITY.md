# Security Policy

## Supported Versions

| Version | Supported          |
| :---    | :---               |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

Security and financial safety are paramount in algorithmic trading.

If you discover a security vulnerability (such as API credential leakage, order execution bypass, or circuit breaker failure), please report it responsibly:

1. **Do not open a public GitHub issue.**
2. Send a detailed report with reproduction steps to `davinmaritza@gmail.com`.
3. We will acknowledge receipt within 24 hours and provide an estimated timeline for remediation.

---

## Financial & Operational Safety Invariants

- Never commit `.env` or any plaintext broker passwords, investor credentials, or Telegram API tokens to git.
- The `.gitignore` is configured to block `.env`, runtime `.json` state caches, and execution database files.
- The built-in **Circuit Breaker** enforces hard limits:
  - Daily Loss Cap: -5.0% (`PAUSED_DAILY`)
  - Peak Drawdown Cap: -15.0% (`SHUTDOWN`)
