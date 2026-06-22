#!/bin/bash
# LojiNext PostgreSQL Backup Script
# Günlük pg_dump — crontab ile çalıştırılacak
# Kullanım: crontab -e → 0 2 * * * /path/to/backup_postgres.sh

set -euo pipefail

# Konfigürasyon
BACKUP_DIR="${BACKUP_DIR:-/backup/lojinext}"
DB_NAME="${POSTGRES_DB:-lojinext_db}"
DB_USER="${POSTGRES_USER:-lojinext_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/lojinext_${TIMESTAMP}.sql.gz"

# Backup dizinini oluştur
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] LojiNext Backup başlatılıyor..."
echo "  DB: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "  Hedef: ${BACKUP_FILE}"

# pg_dump ile sıkıştırılmış backup
if pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-privileges \
    --format=custom \
    --compress=9 \
    -f "${BACKUP_FILE%.gz}.dump" 2>&1; then

    echo "[$(date)] ✅ Backup başarılı: $(du -h "${BACKUP_FILE%.gz}.dump" | cut -f1)"
else
    echo "[$(date)] ❌ Backup BAŞARISIZ!" >&2
    exit 1
fi

# Eski backupları temizle
DELETED=$(find "${BACKUP_DIR}" -name "lojinext_*.dump" -mtime +"${RETENTION_DAYS}" -delete -print | wc -l)
if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date)] 🗑️ ${DELETED} eski backup silindi (>${RETENTION_DAYS} gün)"
fi

# Backup boyut raporu
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "lojinext_*.dump" | wc -l)
echo "[$(date)] 📊 Toplam: ${BACKUP_COUNT} backup, ${TOTAL_SIZE} disk"
echo "[$(date)] Backup tamamlandı."
