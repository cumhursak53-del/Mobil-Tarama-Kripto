#!/usr/bin/env bash
# VPS Web konsolunda calistirin — canli API'yi duzeltir ve servisi yeniden baslatir
set -euo pipefail

APP="/opt/krpito-app"
DEPLOY="/opt/krpito"

echo "=== Krpito API fix ==="
if [[ ! -d "$APP/.git" ]]; then
  echo "HATA: $APP yok. Once vps_bootstrap.sh calistirin."
  exit 1
fi

git -C "$APP" pull --ff-only
cp /opt/krpito/live.env "$APP/live.env"
cd "$APP"
bash scripts/deploy_vps.sh

echo ""
echo "Test (VPS icinden):"
sleep 2
curl -sf "http://127.0.0.1:10001" | head -c 300 || echo "HATA: localhost:10001 yanit vermiyor"
echo ""
echo "Servis: systemctl status krpito-live --no-pager"
