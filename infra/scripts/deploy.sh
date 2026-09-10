#!/bin/bash
set -e

echo "=== Deploying Tea-Assist Stacks ==="

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "WARNING: .env file not found at $ENV_FILE"
  echo "         Stack deploy may use default values from compose files."
  echo "         Create $ENV_FILE with required vars for production."
else
  # Source env vars (stack deploy reads from environment)
  set -a
  source "$ENV_FILE"
  set +a
fi

# Run Ansible playbook is handled by CI before this step (remote execution).
# For manual local runs, use: ansible-playbook -i '192.0.2.10,' ansible/playbook.yml -u tea --ask-become-pass

deploy_stack() {
  local name=$1
  local compose_file=$2
  echo "--- Deploying $name ---"
  # --detach=false: wait for the rollout so CI fails loudly on failed/rolled-back updates
  docker stack deploy --detach=false --with-registry-auth -c "$compose_file" "$name"
  echo "--- $name deployed ---"
}

# Swarm does NOT re-pull same-tag images — pull app images explicitly so the
# node runs the latest CI build (not a stale cached image).
pull_app_images() {
  echo "--- Pulling latest app images ---"
  for img in \
    ghcr.io/tea-assist/product-graph-ai-engine:main \
    ghcr.io/tea-assist/product-graph-api:main \
    ghcr.io/tea-assist/product-graph-web-ui:main; do
    if docker pull "$img" >/dev/null 2>&1; then
      echo "Pulled $img"
    else
      echo "WARNING: could not pull $img (continuing with cached image)"
    fi
  done
}

pull_app_images

deploy_stack "tea-infra"   "$SCRIPT_DIR/stacks/tea-infra/compose.yml"
sleep 5
deploy_stack "tea-monitor" "$SCRIPT_DIR/stacks/tea-monitor/compose.yml"
sleep 3
deploy_stack "tea-portainer" "$SCRIPT_DIR/stacks/tea-portainer/compose.yml"
sleep 3
deploy_stack "tea-caddy"   "$SCRIPT_DIR/stacks/tea-caddy/compose.yml"
# Force update caddy to reload Caddyfile (bind mount doesn't trigger deploy)
docker service update --force tea-caddy_caddy 2>/dev/null || true
sleep 3
deploy_stack "tea-app"     "$SCRIPT_DIR/stacks/tea-app/compose.yml"
# Force-recreate tasks: stack deploy skips tag-identical images (:main) when the
# swarm manager cannot record the registry digest, leaving stale containers running.
# Retry: concurrent deploy jobs can hit "update out of sequence" on the same service.
force_update_service() {
  local svc=$1
  for attempt in 1 2 3 4 5; do
    if docker service update --force "$svc" >/dev/null 2>&1; then
      echo "Updated $svc"
      return 0
    fi
    echo "Update of $svc failed (attempt $attempt/5) - another deploy may be running; retrying..."
    sleep 10
  done
  echo "ERROR: could not force update $svc" >&2
  return 1
}

for svc in tea-app_ai-engine tea-app_api tea-app_web-ui; do
  echo "--- Force updating $svc ---"
  force_update_service "$svc"
done

echo ""
echo "=== All stacks deployed ==="
echo "Check: docker stack ls"
echo "Logs: docker service logs tea-app_api"
