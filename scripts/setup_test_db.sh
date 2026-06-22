#!/bin/bash
# Setup test database with UTF-8 encoding
# Kullanım: ./scripts/setup_test_db.sh

set -e

POSTGRES_USER="${POSTGRES_USER:-postgres}"
DB_NAME="lojinext_test"

echo "🔧 Test database kurulumu başlıyor..."
echo "DB: $DB_NAME"
echo "User: $POSTGRES_USER"
echo ""

# Eski database'i kaldır
echo "📦 Eski database kaldırılıyor..."
sudo -u "$POSTGRES_USER" dropdb "$DB_NAME" 2>/dev/null || echo "   (Database zaten yok, skip ediliyor)"

# Yeni database oluştur UTF-8 ile
echo "✨ Yeni UTF-8 database oluşturuluyor..."
sudo -u "$POSTGRES_USER" createdb -E UTF8 "$DB_NAME"

echo ""
echo "✅ Database kurulumu tamamlandı!"
echo ""
echo "Sonraki adım: Testleri çalıştır"
echo "  export SECRET_KEY='test_key_12345678901234567890'  # pragma: allowlist secret"
echo "  export DATABASE_URL='postgresql://lojinext_user:lojinext_password@localhost/lojinext_test?ssl=disable'  # pragma: allowlist secret"
echo "  export REDIS_URL='redis://localhost:6379'"
echo "  pytest app/tests/integration/test_api_seferler.py -v"
