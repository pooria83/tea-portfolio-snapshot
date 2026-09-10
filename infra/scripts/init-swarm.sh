#!/bin/bash
set -e

echo "=== One-time Swarm Init ==="
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Init swarm if not already
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q active; then
  docker swarm init --advertise-addr "$(hostname -I | awk '{print $1}')"
  echo "Swarm initialized"
else
  echo "Swarm already active"
fi

# Create overlay network
if ! docker network ls --filter name=tea-infra-net --format '{{.Name}}' | grep -q tea-infra-net; then
  docker network create --driver overlay --attachable tea-infra-net
  echo "Network tea-infra-net created"
else
  echo "Network tea-infra-net already exists"
fi

# Create secrets from .env file
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file not found at $SCRIPT_DIR/.env"
  echo "Create it from .env.example first"
  exit 1
fi

source "$SCRIPT_DIR/.env"

create_secret() {
  local name=$1
  local value="${!2}"
  if [ -z "$value" ]; then
    echo "WARNING: Secret $name is empty, skipping"
    return
  fi
  if ! docker secret ls --filter name="$name" --format '{{.Name}}' 2>/dev/null | grep -q "^$name$"; then
    echo "$value" | docker secret create "$name" -
    echo "Secret $name created"
  else
    echo "Secret $name already exists"
  fi
}

create_secret "postgres_password_v2"    "POSTGRES_PASSWORD"
create_secret "minio_root_password_v3"  "MINIO_ROOT_PASSWORD"

docker login ghcr.io -u TEA-assist --password-stdin <<< "$GHCR_TOKEN" 2>/dev/null || true

echo ""
echo "=== Init complete ==="
echo "Run: bash scripts/deploy.sh"
