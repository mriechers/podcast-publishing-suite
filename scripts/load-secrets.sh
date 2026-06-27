#!/usr/bin/env bash
#
# load-secrets.sh — resolve Ghost credentials from 1Password and wire them into the
# two consumers, without ever writing secret values into the repo.
#
# Role-separated keys (see the-lodge registry.yaml + planning notes):
#   GHOST_ADMIN_API_KEY  → "PRX Importer" Ghost integration
#                          consumed by the app via .env.prod and by GitHub Actions
#   GHOST_AGENT_API_KEY  → "Claude Agent Credentials" Ghost integration
#                          consumed by the MCP server via .mcp.json ${GHOST_AGENT_API_KEY}
#
# Both resolve through the-lodge get-secret.sh (1Password → registry/env-map).
#
# Usage:
#   source scripts/load-secrets.sh             # export GHOST_AGENT_API_KEY into the shell (for the MCP)
#   scripts/load-secrets.sh --write-env [prod] # refresh GHOST_ADMIN_API_KEY in .env.<env> (for the app)
#
# The script prints only status to stderr; it never echoes a secret value.

GET_SECRET="${GET_SECRET:-$HOME/Developer/the-lodge/scripts/get-secret.sh}"
_LS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LS_REPO="$(cd "$_LS_DIR/.." && pwd)"

_ls_resolve() {
  local key="$1"
  if [[ ! -x "$GET_SECRET" ]]; then
    echo "load-secrets: get-secret.sh not executable at $GET_SECRET" >&2
    return 1
  fi
  "$GET_SECRET" "$key"
}

# Export the agent key into the current shell so .mcp.json's ${GHOST_AGENT_API_KEY} expands.
ls_export_agent_key() {
  local v
  v="$(_ls_resolve GHOST_AGENT_API_KEY)" || return 1
  [[ -n "$v" ]] || { echo "load-secrets: GHOST_AGENT_API_KEY resolved empty" >&2; return 1; }
  export GHOST_AGENT_API_KEY="$v"
  echo "load-secrets: exported GHOST_AGENT_API_KEY (Claude Agent integration) for the MCP" >&2
}

# Refresh the importer key in the dotenv file the app loads (config.py uses override=True,
# so the file — not the shell env — is the app's source of truth).
ls_write_env() {
  local env_name="${1:-prod}"
  local env_file="$_LS_REPO/.env.$env_name"
  local key_var="GHOST_ADMIN_API_KEY"
  local v tmp
  v="$(_ls_resolve "$key_var")" || return 1
  [[ -n "$v" ]] || { echo "load-secrets: $key_var resolved empty" >&2; return 1; }
  [[ -f "$env_file" ]] || { echo "load-secrets: $env_file not found" >&2; return 1; }
  tmp="$(mktemp)" || return 1
  if grep -q "^${key_var}=" "$env_file"; then
    awk -v k="$key_var" -v val="$v" -F= 'BEGIN{OFS="="} $1==k{print k, val; next} {print}' "$env_file" >"$tmp"
  else
    cp "$env_file" "$tmp"
    printf '%s=%s\n' "$key_var" "$v" >>"$tmp"
  fi
  mv "$tmp" "$env_file"
  echo "load-secrets: refreshed ${key_var} in .env.${env_name} (PRX Importer integration)" >&2
}

# Sourced → export the agent key. Executed → dispatch on args.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  ls_export_agent_key
else
  case "${1:-}" in
    --write-env) ls_write_env "${2:-prod}" ;;
    --export)    ls_export_agent_key ;;   # note: only affects this subshell when executed
    *)
      echo "Usage:" >&2
      echo "  source ${BASH_SOURCE[0]}              # export GHOST_AGENT_API_KEY for the MCP" >&2
      echo "  ${BASH_SOURCE[0]} --write-env [prod]  # refresh GHOST_ADMIN_API_KEY in .env.<env>" >&2
      exit 1
      ;;
  esac
fi
