#!/bin/bash
# SevaCRM deployment script
# Usage: ./deploy.sh

set -e

SERVER="109.172.114.197"
SSH_KEY="$HOME/.ssh/id_ed25519_seva"
REMOTE="root@${SERVER}"
APP_DIR="/opt/sevacrm"
SSH="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no"
SCP="scp -i ${SSH_KEY} -o StrictHostKeyChecking=no"

echo "=== SevaCRM Deploy ==="

# 1. Prepare remote directory
echo "[1/5] Creating directories on server..."
$SSH $REMOTE "mkdir -p ${APP_DIR}/uploads"

# 2. Sync application code (exclude venv, node_modules, .git, local db, nginx)
echo "[2/5] Syncing code to server..."
rsync -avz --progress \
  -e "ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no" \
  --exclude='.venv/' \
  --exclude='node_modules/' \
  --exclude='.git/' \
  --exclude='sevacrm.db' \
  --exclude='uploads/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='nginx/' \
  . ${REMOTE}:${APP_DIR}/

# 3. Upload .env
echo "[3/5] Uploading .env..."
$SCP .env ${REMOTE}:${APP_DIR}/.env

# 4. Build and start Docker
echo "[4/5] Building and starting Docker..."
$SSH $REMOTE "cd ${APP_DIR} && docker compose -f docker-compose.prod.yml down 2>/dev/null || true && docker compose -f docker-compose.prod.yml build --no-cache && docker compose -f docker-compose.prod.yml up -d"

# 5. Update user credentials
echo "[5/5] Updating user credentials..."
$SSH $REMOTE "cd ${APP_DIR} && docker compose -f docker-compose.prod.yml exec -T app python update_user.py --old-username admin --new-username 'seva@hren.com' --password 'pidoras1712' 2>/dev/null || docker compose -f docker-compose.prod.yml exec -T app python update_user.py --new-username 'seva@hren.com' --password 'pidoras1712'"

echo ""
echo "=== Deploy complete! ==="
echo "App: https://sevacrm.ru"
echo "Login: seva@hren.com"
