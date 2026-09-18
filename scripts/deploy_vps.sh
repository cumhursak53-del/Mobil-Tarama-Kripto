#!/usr/bin/env bash
# Hetzner/VPS kurulum — 7/24 canli motor
# Usage: bash scripts/deploy_vps.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f live.env ]]; then
  cp live.env.example live.env
  echo "live.env olusturuldu — BYBIT_API_KEY ve BYBIT_API_SECRET ekleyin."
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip
pip install -r requirements-live.txt

if ! id krpito &>/dev/null; then
  sudo useradd -r -m -s /bin/bash krpito || true
fi

sudo mkdir -p /opt/krpito
sudo rsync -a --exclude .venv --exclude __pycache__ --exclude .git "$ROOT/" /opt/krpito/
sudo cp "$ROOT/live.env" /opt/krpito/live.env
sudo chown -R krpito:krpito /opt/krpito

cd /opt/krpito
sudo -u krpito python3 -m venv .venv
sudo -u krpito .venv/bin/pip install -r requirements-live.txt

sudo cp deploy/krpito-live.service /etc/systemd/system/krpito-live.service
sudo systemctl daemon-reload
sudo systemctl enable krpito-live
sudo systemctl restart krpito-live

echo ""
echo "Kurulum tamam. Durum:"
sudo systemctl status krpito-live --no-pager || true
echo ""
echo "Log: journalctl -u krpito-live -f"
echo "API: http://$(curl -s ifconfig.me 2>/dev/null || echo VPS_IP):10001"
