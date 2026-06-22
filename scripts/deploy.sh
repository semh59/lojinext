#!/usr/bin/env bash
# =============================================================================
# LojiNext — Manuel VPS Deployment Script
# Kullanım: bash scripts/deploy.sh
#
# Gereksinimler:
#   - Sunucuda Docker ve Docker Compose v2 kurulu olmalı
#   - .env dosyası proje kökünde hazır olmalı (bkz. .env.prod.example)
#   - GHCR'a public erişim veya docker login yapılmış olmalı
# =============================================================================
set -euo pipefail

COMPOSE_BASE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
HEALTH_URL="http://localhost:8000/api/v1/health"
HEALTH_RETRIES=30
HEALTH_INTERVAL=5

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail() { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }

# .env kontrolü
if [ ! -f ".env" ]; then
    fail ".env dosyası bulunamadı. .env.prod.example'dan kopyalayın: cp .env.prod.example .env"
fi

# GHCR_OWNER kontrolü
GHCR_OWNER="${GHCR_OWNER:-}"
if [ -z "$GHCR_OWNER" ]; then
    # .env'den okumayı dene
    GHCR_OWNER=$(grep -E '^GHCR_OWNER=' .env | cut -d= -f2 | tr -d '"' || true)
fi
if [ -z "$GHCR_OWNER" ]; then
    fail "GHCR_OWNER tanımlı değil. .env dosyasına veya ortam değişkenine ekleyin."
fi

export GHCR_OWNER

log "=== LojiNext Production Deploy ==="
log "GHCR Owner : $GHCR_OWNER"
log "Image Tag  : ${IMAGE_TAG:-latest}"
log "Host       : $(hostname)"

# 1. GHCR'dan güncel image'ları çek
log "Adım 1/4 — GHCR'dan image'lar çekiliyor..."
$COMPOSE_BASE pull

# 2. Servisleri güncelle (sıfır kesinti için --no-recreate yerine varsayılan)
log "Adım 2/4 — Servisler başlatılıyor / güncelleniyor..."
$COMPOSE_BASE up -d --remove-orphans

# 3. Backend health check bekle
log "Adım 3/4 — Backend sağlık kontrolü bekleniyor (maks ${HEALTH_RETRIES}x${HEALTH_INTERVAL}s)..."
attempt=0
until curl -sf "$HEALTH_URL" > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$HEALTH_RETRIES" ]; then
        warn "Backend sağlık kontrolü zaman aşımına uğradı."
        warn "Logları kontrol edin: docker compose logs backend --tail=50"
        fail "Deploy doğrulanamadı."
    fi
    echo -n "."
    sleep "$HEALTH_INTERVAL"
done
echo ""
log "Backend sağlıklı — $HEALTH_URL"

# 4. Durum özeti
log "Adım 4/4 — Servis durumu:"
$COMPOSE_BASE ps

log "=== Deploy tamamlandı ==="
