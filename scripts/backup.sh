#!/usr/bin/env bash
# =============================================================================
# LojiNext — PostgreSQL Yedekleme Script'i
# Kullanım: bash scripts/backup.sh
# Cron örneği (her gece 02:00): 0 2 * * * /opt/lojinext/scripts/backup.sh
#
# Gereksinimler:
#   - Proje kökünde .env dosyası olmalı (POSTGRES_* değişkenleri için)
#   - Docker ve docker compose v2 kurulu olmalı
# =============================================================================
set -euo pipefail

# Proje kökünü bul (script nerede olursa olsun)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# .env'den değişkenleri yükle (varsa)
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Yapılandırma
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DB_CONTAINER="${DB_CONTAINER:-$(docker compose ps -q db 2>/dev/null || echo '')}"
POSTGRES_USER="${POSTGRES_USER:-lojinext_user}"
POSTGRES_DB="${POSTGRES_DB:-lojinext_db}"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="$BACKUP_DIR/lojinext_${TIMESTAMP}.sql.gz"

# Renk kodları
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[BACKUP]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC}   $*" >&2; exit 1; }

# Backup dizinini oluştur
mkdir -p "$BACKUP_DIR"

# DB container çalışıyor mu?
if [ -z "$DB_CONTAINER" ]; then
    fail "DB container bulunamadı. 'docker compose up -d db' ile başlatın."
fi

log "=== LojiNext PostgreSQL Backup ==="
log "Veritabanı : $POSTGRES_DB"
log "Hedef      : $BACKUP_FILE"

# pg_dump → gzip
if docker compose exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
    log "Yedek oluşturuldu: $BACKUP_FILE ($BACKUP_SIZE)"
else
    rm -f "$BACKUP_FILE"
    fail "pg_dump başarısız oldu."
fi

# Eski yedekleri temizle
log "Eski yedekler temizleniyor (>${RETENTION_DAYS} gün)..."
DELETED=$(find "$BACKUP_DIR" -name "lojinext_*.sql.gz" -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
log "Silinen yedek sayısı: $DELETED"

# Mevcut yedekleri listele
TOTAL=$(find "$BACKUP_DIR" -name "lojinext_*.sql.gz" | wc -l)
log "Toplam yedek sayısı : $TOTAL"
log "=== Backup tamamlandı ==="
