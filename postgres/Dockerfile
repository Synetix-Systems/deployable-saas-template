FROM postgres:18

# ---------------------------------------------------------------------------
# WAL-G — compressed, S3-compatible WAL archiving and base backups.
#
# Replaces the raw `cp` archive_command: writes compressed WAL segments and
# full base backups to any S3-compatible store (AWS S3, Backblaze B2, MinIO)
# so backups survive host failure. Config is read from env vars injected at
# runtime by the Helm chart (see charts/app/templates/db.yaml).
#
# Binary is architecture-aware: amd64 → amd64, arm64 → aarch64.
# ---------------------------------------------------------------------------

ARG WALG_VERSION=v3.0.8

RUN set -eux; \
    ARCH="$(dpkg --print-architecture)"; \
    case "$ARCH" in \
      amd64)   WALG_ARCH=amd64   ;; \
      arm64)   WALG_ARCH=aarch64 ;; \
      *)       echo "Unsupported arch: $ARCH" >&2; exit 1 ;; \
    esac; \
    WALG_URL="https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-22.04-${WALG_ARCH}"; \
    apt-get update -qq && apt-get install -y --no-install-recommends ca-certificates curl && \
    curl -fsSL "$WALG_URL" -o /usr/local/bin/wal-g && \
    chmod +x /usr/local/bin/wal-g && \
    apt-get purge -y --auto-remove curl && \
    rm -rf /var/lib/apt/lists/*
