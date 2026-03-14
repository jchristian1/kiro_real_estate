#!/usr/bin/env bash
# =============================================================================
# validate_clean_clone.sh
#
# Validates that the repository can be cloned and started from scratch with
# a single command. Performs the following steps:
#
#   1. Clone the repo to a temporary directory
#   2. Copy .env.example → .env and inject generated secrets
#   3. Run docker compose up -d
#   4. Poll GET /api/v1/health until status=healthy or 120s timeout
#   5. Report PASS or FAIL and exit with the appropriate code
#
# Usage:
#   scripts/validate_clean_clone.sh [REPO_URL]
#
# If REPO_URL is omitted the script uses the remote URL of the current repo.
#
# Requirements: 13.1, 13.2, 13.4
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEALTH_URL="http://localhost:8000/api/v1/health"
TIMEOUT_SECONDS=120
POLL_INTERVAL=5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { echo "[$(date '+%H:%M:%S')] FAIL: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve repo URL
# ---------------------------------------------------------------------------
if [[ $# -ge 1 ]]; then
  REPO_URL="$1"
else
  if ! REPO_URL=$(git -C "$(dirname "$0")/.." remote get-url origin 2>/dev/null); then
    fail "Could not determine repo URL. Pass it as the first argument: $0 <repo-url>"
  fi
fi

log "Repository: ${REPO_URL}"

# ---------------------------------------------------------------------------
# Create temp directory and register cleanup
# ---------------------------------------------------------------------------
WORK_DIR=$(mktemp -d)
log "Working directory: ${WORK_DIR}"

cleanup() {
  local exit_code=$?
  log "Cleaning up ${WORK_DIR} ..."
  # Bring down containers if they were started
  if [[ -d "${WORK_DIR}/repo" ]]; then
    docker compose -f "${WORK_DIR}/repo/docker-compose.yml" down --volumes --remove-orphans 2>/dev/null || true
  fi
  rm -rf "${WORK_DIR}"
  exit "${exit_code}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: Clone
# ---------------------------------------------------------------------------
log "Step 1: Cloning repository ..."
if ! git clone --depth 1 "${REPO_URL}" "${WORK_DIR}/repo"; then
  fail "git clone failed for ${REPO_URL}"
fi
log "Clone complete."

REPO_DIR="${WORK_DIR}/repo"

# ---------------------------------------------------------------------------
# Step 2: Copy .env.example → .env and inject secrets
# ---------------------------------------------------------------------------
log "Step 2: Preparing .env ..."

if [[ ! -f "${REPO_DIR}/.env.example" ]]; then
  fail ".env.example not found in cloned repository"
fi

cp "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"

# Generate secrets using openssl (no Python dependency at this stage)
ENCRYPTION_KEY=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)

# Replace placeholder values in .env (BSD and GNU sed compatible)
_sed_inplace() {
  if sed --version &>/dev/null 2>&1; then
    sed -i "$@"
  else
    sed -i '' "$@"
  fi
}

_sed_inplace "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" "${REPO_DIR}/.env"
_sed_inplace "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|"             "${REPO_DIR}/.env"

log ".env prepared with generated secrets."

# ---------------------------------------------------------------------------
# Step 3: docker compose up -d
# ---------------------------------------------------------------------------
log "Step 3: Starting services with docker compose up -d ..."
if ! docker compose -f "${REPO_DIR}/docker-compose.yml" up --build -d; then
  fail "docker compose up failed"
fi
log "Services started."

# ---------------------------------------------------------------------------
# Step 4: Poll health endpoint
# ---------------------------------------------------------------------------
log "Step 4: Polling ${HEALTH_URL} (timeout: ${TIMEOUT_SECONDS}s) ..."

elapsed=0
healthy=false

while [[ ${elapsed} -lt ${TIMEOUT_SECONDS} ]]; do
  if response=$(curl -sf --max-time 5 "${HEALTH_URL}" 2>/dev/null); then
    # Check for "healthy" in the response body
    if echo "${response}" | grep -q '"healthy"'; then
      healthy=true
      break
    else
      log "  Health response received but status not healthy yet: ${response}"
    fi
  else
    log "  Health endpoint not reachable yet (${elapsed}s elapsed) ..."
  fi

  sleep "${POLL_INTERVAL}"
  elapsed=$(( elapsed + POLL_INTERVAL ))
done

# ---------------------------------------------------------------------------
# Step 5: Report result
# ---------------------------------------------------------------------------
if [[ "${healthy}" == "true" ]]; then
  log "============================================================"
  log "PASS — system reached healthy state in ${elapsed}s"
  log "============================================================"
  exit 0
else
  log "============================================================"
  log "FAIL — health endpoint did not return healthy within ${TIMEOUT_SECONDS}s"
  log "============================================================"
  log "Container logs:"
  docker compose -f "${REPO_DIR}/docker-compose.yml" logs --tail=50 || true
  exit 1
fi
