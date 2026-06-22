"""
Security Sanitizer - Logs & Data Cleanup
Hassas verileri loglardan temizler ve geçici dosyaları siler.
"""

import re
from pathlib import Path

# Proje Kök Dizini
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "app" / "logs"
DATA_DIR = ROOT_DIR / "data"

# PII Patterns for Sanitization
PII_PATTERNS = [
    # Şifre sızıntıları: password.value, password="...", sifre=...
    (
        r'(?i)(password|passwd|sifre|secret|token|api_key|secret_key|auth)\s*([.:=,)]|$|["\'])',
        r"\1: ***SANITIZED***",
    ),
    # Email, Telefon, TCKN
    (r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Z|a-z]{2,}\b", "<EMAIL_SANITIZED>"),
    (r"\b(?:\+90|0)?5\d{9}\b", "<PHONE_SANITIZED>"),
    (r"\b\d{11}\b", "<TCKN_SANITIZED>"),
]


def sanitize_logs():
    """Tüm log dosyalarını tarar ve hassas verileri temizler"""
    print(f"[*] Sanitizing logs in {LOG_DIR}...")

    if not LOG_DIR.exists():
        print("[!] Log directory not found.")
        return

    for log_file in LOG_DIR.glob("*.log"):
        print(f"  - Processing {log_file.name}...")
        try:
            content = log_file.read_text(encoding="utf-8")
            original_len = len(content)

            for pattern, subst in PII_PATTERNS:
                content = re.sub(pattern, subst, content)

            if len(content) != original_len or "***SANITIZED***" in content:
                log_file.write_text(content, encoding="utf-8")
                print(f"    [+] Sanitized {log_file.name}")
            else:
                print(f"    [.] No sensitive data found in {log_file.name}")

        except Exception as e:
            print(f"    [!] Error processing {log_file.name}: {e}")


def cleanup_data():
    """Test veri dosyalarını ve gereksiz kalıntıları siler"""
    print("[*] Cleaning up data files...")

    # Test DB (GÜVENLİK: Production'da kesinlikle silinmeli)
    test_db = DATA_DIR / "test.db"
    if test_db.exists():
        test_db.unlink()
        print(f"  [+] Deleted {test_db.name}")

    # Diğer gereksiz dosyalar
    junk_files = [
        ROOT_DIR / "test_output.txt",
        ROOT_DIR / "test_err.txt",
        ROOT_DIR / "pytestdebug.log",
    ]

    for f in junk_files:
        if f.exists():
            f.unlink()
            print(f"  [+] Deleted {f.name}")


if __name__ == "__main__":
    print("=== LojiNext Security Sanitizer STARTED ===")
    sanitize_logs()
    cleanup_data()
    print("=== LojiNext Security Sanitizer FINISHED ===")
