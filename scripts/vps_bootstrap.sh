#!/usr/bin/env bash
# Hostinger VPS tek komut kurulum
# Onkosul: /opt/krpito/live.env dosyasi hazir (Bybit key'leri ile)
set -euo pipefail

LIVE_ENV="/opt/krpito/live.env"
APP_DIR="/opt/krpito-app"
REPO="https://github.com/cumhursak53-del/Mobil-Tarama-Kripto.git"

echo "=== Krpito Live VPS kurulumu ==="

if [[ ! -f "$LIVE_ENV" ]]; then
  echo "HATA: $LIVE_ENV bulunamadi."
  echo "Once: mkdir -p /opt/krpito && nano /opt/krpito/live.env"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-pip python3-venv rsync curl

if [[ -d "$APP_DIR/.git" ]]; then
  echo "Repo guncelleniyor..."
  git -C "$APP_DIR" pull --ff-only
else
  echo "Repo klonlaniyor..."
  rm -rf "$APP_DIR"
  git clone "$REPO" "$APP_DIR"
fi

cp "$LIVE_ENV" "$APP_DIR/live.env"
chmod 600 "$APP_DIR/live.env"
cd "$APP_DIR"
bash scripts/deploy_vps.sh

echo ""
echo "=== Kurulum bitti ==="
echo "Durum: systemctl status krpito-live"
echo "Log:   journalctl -u krpito-live -f"
