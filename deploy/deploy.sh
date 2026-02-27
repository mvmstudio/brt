#!/bin/bash
set -euo pipefail

APP_DIR="/opt/brt.mvm.st"
REPO_URL="git@github.com:mvmstudio/brt.git"

echo "=== BRT Deploy ==="

# Clone or pull
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning repository..."
    git clone "$REPO_URL" "$APP_DIR"
else
    echo "Pulling latest changes..."
    cd "$APP_DIR"
    git pull origin main
fi

cd "$APP_DIR"

# Backend
echo "=== Backend setup ==="
cd "$APP_DIR/backend"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# Ensure data directory exists
mkdir -p data

# Set permissions
chown -R www-data:www-data "$APP_DIR/backend"

# Frontend
echo "=== Frontend setup ==="
cd "$APP_DIR/frontend"

npm ci --prefer-offline --no-audit 2>/dev/null || npm install
npm run build

chown -R www-data:www-data "$APP_DIR/frontend"

# Systemd services
echo "=== Installing services ==="
cp "$APP_DIR/deploy/brt-backend.service" /etc/systemd/system/
cp "$APP_DIR/deploy/brt-frontend.service" /etc/systemd/system/
systemctl daemon-reload

# Restart services
echo "=== Restarting services ==="
systemctl restart brt-backend
systemctl restart brt-frontend
systemctl enable brt-backend
systemctl enable brt-frontend

sleep 3

# Check status
echo "=== Status ==="
systemctl is-active brt-backend && echo "Backend: OK" || echo "Backend: FAILED"
systemctl is-active brt-frontend && echo "Frontend: OK" || echo "Frontend: FAILED"

echo "=== Deploy complete ==="
