# NVM — Natura Vending Machine

Portable cooperative financial, NFC payment, loan and vending platform.

## Minimum system requirements

NVM targets lightweight Linux systems and is designed to run with:

- 2 CPU cores minimum
- 315 MB RAM minimum
- Python 3.10 or newer
- SQLite3
- POSIX shell for the installer

The application does not require a specific Linux distribution, hostname, IP address, username, home directory, init system, or hardware platform.

## Source and build

GitHub is the source of truth. GitHub Actions builds and tests the project.

The installer is distribution/init-system agnostic. Systemd, OpenRC, or another service manager may be configured separately; the application itself does not depend on one.

Production databases, credentials, secrets, instance configuration and test data must not be committed.
