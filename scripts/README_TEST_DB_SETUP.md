# Test Database UTF-8 Setup

## Problem
PostgreSQL test database (`lojinext_test`) is configured with SQL_ASCII encoding, which cannot store Unicode characters. This causes 3 integration tests to fail when updating sefer records with JSON metadata containing Turkish text.

## Solution
Recreate the test database with UTF-8 encoding.

## Windows (Recommended for your setup)

### 1. Run the setup script:
```batch
scripts\setup_test_db.bat
```

### What it does:
- Drops existing `lojinext_test` database (if exists)
- Creates new database with UTF-8 encoding
- Outputs next steps

### 2. After script completes, verify with:
```bash
psql -U postgres -d lojinext_test -c "\l"  # pragma: allowlist secret
```

You should see:
```
Name         | Owner    | Encoding | ...
lojinext_test | postgres | UTF8     | ...
```

## Linux / macOS

### 1. Run the setup script:
```bash
bash scripts/setup_test_db.sh
```

### 2. Or manually:
```bash
sudo -u postgres dropdb lojinext_test 2>/dev/null || true
sudo -u postgres createdb -E UTF8 lojinext_test
```

## After Setup: Run Integration Tests

```bash
export SECRET_KEY="test_key_12345678901234567890"  # pragma: allowlist secret
export DATABASE_URL="postgresql://lojinext_user:lojinext_password@localhost/lojinext_test?ssl=disable"  # pragma: allowlist secret
export REDIS_URL="redis://localhost:6379"

pytest app/tests/integration/test_api_seferler.py -v
```

Expected result: **8/8 tests passing** ✅

## Troubleshooting

### "psql: command not found"
PostgreSQL client tools not in PATH. Install PostgreSQL or add to PATH:
```bash
# Windows (example path, adjust for your setup)
set PATH=%PATH%;C:\Program Files\PostgreSQL\15\bin
```

### "FATAL: role 'postgres' does not exist"
PostgreSQL superuser role doesn't exist. Create it:
```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"  # pragma: allowlist secret
```

### "connection refused"
PostgreSQL service not running:
```bash
# Windows
net start postgresql-x64-15

# Linux
sudo systemctl start postgresql

# macOS
brew services start postgresql
```

## Verification

After setup, all these should pass:

```bash
# Unit tests (should already pass)
pytest app/tests/unit -q --tb=no
# Expected: 1397 passed ✅

# Integration tests (should now pass after DB setup)
pytest app/tests/integration/test_api_seferler.py -v
# Expected: 8 passed ✅
```

## Notes
- This script only affects the **test** database, not production
- Test database is dropped and recreated fresh
- All migrations and schema creation are handled by conftest.py on test start
- No application code changes needed
