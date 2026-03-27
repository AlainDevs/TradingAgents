#!/usr/bin/env bash

set -euo pipefail

port="${WEB_CLI_PORT:-7681}"
credentials="${WEB_CLI_CREDENTIALS:-}"

if [[ -n "${WEB_CLI_USER:-}" || -n "${WEB_CLI_PASSWORD:-}" ]]; then
  if [[ -z "${WEB_CLI_USER:-}" || -z "${WEB_CLI_PASSWORD:-}" ]]; then
    echo "Both WEB_CLI_USER and WEB_CLI_PASSWORD must be set to enable auth." >&2
    exit 1
  fi
  credentials="${WEB_CLI_USER}:${WEB_CLI_PASSWORD}"
fi

args=(-p "${port}" -W -w /app)

if [[ -n "${credentials}" ]]; then
  args+=(-c "${credentials}")
fi

exec ttyd "${args[@]}" /usr/local/bin/web_terminal.sh
