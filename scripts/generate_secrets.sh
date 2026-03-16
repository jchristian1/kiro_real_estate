#!/usr/bin/env bash
# =============================================================================
# generate_secrets.sh
#
# Generates cryptographically secure ENCRYPTION_KEY and SECRET_KEY values and
# writes them to .env. If .env does not exist, it is created from .env.example
# first. Existing values for these two keys are replaced; all other .env
# entries are left untouched.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"

# ---------------------------------------------------------------------------
# Require python3
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is required but was not found in PATH." >&2
  echo "       Install Python 3 and re-run this script." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Generate keys using Python's secrets module.
# ENCRYPTION_KEY: a Fernet key (URL-safe base64, 44 chars) — preferred for
#   use with the cryptography library.  Falls back to token_hex(32) if the
#   cryptography package is not installed.
# SECRET_KEY: 64 hex characters (32 random bytes) for session signing.
# ---------------------------------------------------------------------------
ENCRYPTION_KEY=$(python3 - <<'EOF'
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import secrets
    print(secrets.token_hex(32))
EOF
)

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# ---------------------------------------------------------------------------
# Ensure .env exists (copy from .env.example if needed)
# ---------------------------------------------------------------------------
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE}" ]]; then
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    echo "Created .env from .env.example"
  else
    # Create a minimal .env with just the two keys
    touch "${ENV_FILE}"
    echo "Created empty .env (no .env.example found)"
  fi
fi

# ---------------------------------------------------------------------------
# Update or append ENCRYPTION_KEY in .env
# ---------------------------------------------------------------------------
update_or_append() {
  local key="$1"
  local value="$2"
  local file="$3"

  if grep -qE "^${key}=" "${file}"; then
    # Replace the existing line (works on both macOS and Linux)
    if sed --version &>/dev/null 2>&1; then
      # GNU sed
      sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
    else
      # BSD sed (macOS)
      sed -i '' "s|^${key}=.*|${key}=${value}|" "${file}"
    fi
  else
    echo "${key}=${value}" >> "${file}"
  fi
}

update_or_append "ENCRYPTION_KEY" "${ENCRYPTION_KEY}" "${ENV_FILE}"
update_or_append "SECRET_KEY"     "${SECRET_KEY}"     "${ENV_FILE}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "✓ Secrets written to ${ENV_FILE}"
echo "  ENCRYPTION_KEY = ${ENCRYPTION_KEY}"
echo "  SECRET_KEY     = ${SECRET_KEY}"
echo ""
echo "Keep these values secret — do not commit .env to version control."
