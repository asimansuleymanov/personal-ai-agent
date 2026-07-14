#!/bin/bash
set -euo pipefail

REPO_DIR=~/app
REPO_URL=https://github.com/asimansuleymanov/personal-ai-agent.git
BRANCH=phase-1-infra-scaffold
DEFAULT_DOMAIN=46.62.192.135.nip.io
DEFAULT_ACME_EMAIL=asiman.suleymanov@gmail.com

if ! command -v docker &> /dev/null; then
  echo "Docker not found, installing..."
  curl -fsSL https://get.docker.com | sh
fi

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Cloning repo..."
  git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
else
  echo "Repo already present, pulling latest..."
  git -C "$REPO_DIR" fetch origin "$BRANCH"
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" pull origin "$BRANCH"
fi

cd "$REPO_DIR"

if [ ! -f .env ]; then
  echo "No .env found - generating one with freshly random secrets (stays on this server only)..."
  cat > .env <<EOF
DOMAIN=${DOMAIN:-$DEFAULT_DOMAIN}
ACME_EMAIL=${ACME_EMAIL:-$DEFAULT_ACME_EMAIL}
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=$(openssl rand -hex 16)
POSTGRES_USER=agent
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=agent
EOF
  chmod 600 .env
  echo ".env created."
fi

echo "Launching stack..."
docker compose up -d
echo "Waiting for Caddy to request the certificate..."
sleep 8
docker compose logs caddy --tail 50
