@echo off
REM Setup test database with UTF-8 encoding
REM Kullanım: scripts\setup_test_db.bat

setlocal enabledelayedexpansion

set POSTGRES_USER=postgres
set DB_NAME=lojinext_test

echo.
echo 🔧 Test database kurulumu basliyor...
echo DB: %DB_NAME%
echo User: %POSTGRES_USER%
echo.

REM Eski database'i kaldır (psql ile)
echo 📦 Eski database kaldiriliyor...
psql -U %POSTGRES_USER% -d postgres -c "DROP DATABASE IF EXISTS %DB_NAME%;" 2>nul
if errorlevel 0 (
    echo    (Database silindi veya zaten yok)
) else (
    echo    (Database kaldirma isleminde hata - devam ediliyor)
)

REM Yeni database oluştur UTF-8 ile
echo ✨ Yeni UTF-8 database olusturuluyor...
psql -U %POSTGRES_USER% -d postgres -c "CREATE DATABASE %DB_NAME% ENCODING 'UTF8';"

if errorlevel 0 (
    echo.
    echo ✅ Database kurulumu tamamlandi!
    echo.
    echo Sonraki adim: Testleri calistir
    echo.
    echo   set SECRET_KEY=test_key_12345678901234567890
    echo   set DATABASE_URL=postgresql://lojinext_user:lojinext_password@localhost/lojinext_test?ssl=disable
    echo   set REDIS_URL=redis://localhost:6379
    echo   pytest app/tests/integration/test_api_seferler.py -v
) else (
    echo.
    echo ❌ Hata: Database olusturulamadi
    echo Lutfen psql PATH'inda ve postgres servisi baslatilmis mi kontrol et
)

endlocal
