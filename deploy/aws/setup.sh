#!/usr/bin/env bash
# Sets up the application on an AWS EC2 Ubuntu 24.04 instance (x86).
# Run as the default "ubuntu" user:   bash deploy/aws/setup.sh
# Safe to run again: it updates the code and restarts the service.
set -euo pipefail

REPO_URL="https://github.com/thorathharish/Intelligent-Document-Investigator.git"
APP_USER="investigator"
APP_DIR="/opt/document-investigator"
DATA_DIR="/var/lib/document-investigator"
WEB_DIR="/var/www/document-investigator"
ENV_FILE="/etc/document-investigator.env"

echo "== system packages"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y software-properties-common git nginx libgl1 libglib2.0-0
if ! command -v python3.11 >/dev/null; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -y
fi
sudo apt-get install -y python3.11 python3.11-venv

echo "== application user and directories"
id -u "$APP_USER" >/dev/null 2>&1 || sudo useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
sudo mkdir -p "$DATA_DIR/models" "$WEB_DIR"
sudo chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
sudo chmod 750 "$DATA_DIR"

echo "== code"
if [ -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
  sudo mkdir -p "$APP_DIR"
  sudo chown "$APP_USER:$APP_USER" "$APP_DIR"
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
fi

echo "== python environment (pinned requirements, unchanged)"
[ -d "$APP_DIR/.venv" ] || sudo -u "$APP_USER" python3.11 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/backend/requirements.txt"

echo "== environment file"
if [ ! -f "$ENV_FILE" ]; then
  sudo cp "$APP_DIR/deploy/aws/document-investigator.env.example" "$ENV_FILE"
  echo "   created $ENV_FILE - add OPENROUTER_API_KEY to it"
fi
sudo chown root:root "$ENV_FILE"
sudo chmod 600 "$ENV_FILE"

echo "== embedding model (downloaded once, kept on disk)"
sudo -u "$APP_USER" env FASTEMBED_CACHE_PATH="$DATA_DIR/models" "$APP_DIR/.venv/bin/python" -c \
  "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5'); print('   embedding model ready')"

echo "== service"
sudo cp "$APP_DIR/deploy/aws/document-investigator.service" /etc/systemd/system/document-investigator.service
sudo systemctl daemon-reload
sudo systemctl enable document-investigator >/dev/null
sudo systemctl restart document-investigator

echo "== nginx"
# installed once: certbot later adds the certificate to this file, so it is not overwritten on a re-run
if [ ! -f /etc/nginx/sites-available/document-investigator ]; then
  sudo cp "$APP_DIR/deploy/aws/nginx.conf" /etc/nginx/sites-available/document-investigator
fi
sudo ln -sf /etc/nginx/sites-available/document-investigator /etc/nginx/sites-enabled/document-investigator
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx >/dev/null
sudo systemctl reload nginx

echo "== health"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/api/health; then echo; break; fi
  sleep 2
done
echo "done. Service: sudo systemctl status document-investigator | Logs: sudo journalctl -u document-investigator -f"
