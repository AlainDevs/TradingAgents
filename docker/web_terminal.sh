#!/usr/bin/env bash

set -uo pipefail

cd /app

clear_screen() {
  printf '\033c'
}

pause_for_input() {
  printf '\nPress Enter to return to the launcher...'
  read -r _
}

run_tradingagents() {
  clear_screen
  cat <<'EOF'
Starting TradingAgents.

- Use Ctrl+C to stop the current run and return to this launcher.
- Your API keys are loaded from the container environment.

EOF

  tradingagents
  status=$?

  printf '\n'
  if [[ ${status} -eq 130 ]]; then
    echo "TradingAgents stopped by user."
  elif [[ ${status} -eq 0 ]]; then
    echo "TradingAgents exited successfully."
  else
    echo "TradingAgents exited with status ${status}."
  fi

  pause_for_input
}

open_shell() {
  clear_screen
  cat <<'EOF'
Interactive shell opened.

- Run `tradingagents` manually whenever you want.
- Type `exit` to return to the launcher.

EOF

  bash
}

while true; do
  clear_screen
  cat <<'EOF'
TradingAgents Web CLI
====================

1) Start TradingAgents CLI
2) Open a shell in the container
3) Exit the web session

Choose an option and press Enter.
EOF

  printf '> '
  read -r choice

  case "${choice}" in
    1)
      run_tradingagents
      ;;
    2)
      open_shell
      ;;
    3)
      exit 0
      ;;
    *)
      echo
      echo "Unknown option: ${choice}"
      pause_for_input
      ;;
  esac
done
