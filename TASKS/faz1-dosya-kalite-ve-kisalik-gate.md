# FAZ1 (çatı) — Dosya Kalite Kontratı + Kod Kısalığı Gate'i

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz.

**Amaç:** "En kaliteli, en kısa kod" standardını öznel bırakmadan, ölçülebilir eşiklere bağlamak; kullanıcının kod-kısalığı talimatını ("5 satırlık iş 50 satır olmasın") somut kural haline getirmek.

**Giriş kriteri:** FAZ0 baseline'ları (radon JSON, LOC listesi) mevcut.
**Çıkış kriteri:** `arch/quality_baseline.json` donmuş; yeni/taşınan dosyalarda ihlal = 0; ruff C901 CI'da aktif.

---

## 1. Ölçülü baseline (varsayım değil — FAZ0'da üretilen dosyalardan)

`arch/quality_baseline.json` (FAZ0'daki `faz0-loc-baseline.txt` + `faz0-radon-baseline.json`'dan türetilir):
```json
{
  "loc_over_500": ["<33 dosyanın FAZ0 ölçümünden tam listesi>"],
  "loc_over_1000": ["<7 dosyanın tam listesi>"],
  "cc_over_10": "<156 blok, radon JSON'dan filtrelenmiş liste>",
  "shims": []
}
```
Bu dosya yalnız KÜÇÜLEBİLİR: bir PR, listeden bir dosya çıkarabilir (küçültüldüğü için) ama yeni ekleyemez — CI bunu diff ile kontrol eder.

## 2. ruff C901 (cyclomatic complexity) — baseline'lı gate

`ruff.toml`'a (mevcut dosya, satır sayısı 1.156 — ölçüldü) ekle:
```toml
[lint]
select = ["E", "F", "W", "I", "C901"]

[lint.mccabe]
max-complexity = 10
```
CI adımı: `ruff check app --select C901` çalışır ama `arch/quality_baseline.json`'daki 156 mevcut ihlalli dosya `# noqa: C901` ile FAZ1 başında işaretlenir (mekanik, tek-seferlik toplu ekleme — HANGİ fonksiyonların bu etiketi aldığı `cc_over_10` listesinden birebir gelir, tahmin edilmez). Yeni yazılan/taşınan fonksiyonlarda `noqa` YOK — CC>10 ise CI fail.

## 3. LOC-gate script'i

`scripts/check_new_file_loc.py` (yeni script — mevcut `scripts/` dizinine, 36 dosyalık envantere eklenir):
```python
"""Yeni/değişen dosyaların 400 satırı aşmadığını, aşıyorsa baseline'da olduğunu doğrular."""
import json
import subprocess
import sys

BASELINE = json.load(open("arch/quality_baseline.json", encoding="utf-8"))
MAX_LOC = 400

def changed_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", "origin/main...HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [f for f in out.splitlines() if f.endswith(".py") and f.startswith("app/")]

def main() -> int:
    failed = []
    for f in changed_py_files():
        loc = sum(1 for _ in open(f, encoding="utf-8"))
        if loc > MAX_LOC and f not in BASELINE["loc_over_500"] and f not in BASELINE["loc_over_1000"]:
            failed.append((f, loc))
    if failed:
        for f, loc in failed:
            print(f"FAIL: {f} — {loc} satır > {MAX_LOC} (baseline'da değil)")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## 4. Tek public-callable testi (application/ katmanı)

`app/tests/architecture/test_single_usecase_per_file.py`:
```python
"""application/ altındaki her dosya tam olarak 1 public (alt-çizgisiz) fonksiyon/sınıf export eder."""
import ast
from pathlib import Path

def test_application_files_have_one_public_callable():
    violations = []
    for f in Path("app/modules").glob("*/application/*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        public_defs = [
            n.name for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not n.name.startswith("_")
        ]
        if len(public_defs) > 1:
            violations.append((str(f), public_defs))
    assert not violations, f"Birden fazla public callable: {violations}"
```

## 5. Kod kısalığı kuralı (kullanıcı talimatı — PR-inceleme kontrol listesi)

Her taşıma/split PR'ında şu 4 madde PR açıklamasında yanıtlanır (otomatik gate değil, insan+CI hibrit — çünkü "gereksiz soyutlama" tam otomatik yakalanamaz):
1. **≥2 tüketici testi:** Yeni bir sınıf/interface/adapter eklendiyse, en az 2 gerçek çağıranı var mı? (grep ile kanıtla, PR'a yapıştır)
2. **Shim tek satır mı?** `git diff` ile shim dosyasının satır sayısı = 1 (import satırı) olmalı.
3. **Net-LOC raporu:** `git diff --stat` çıktısı PR'a yapıştırılır; net artış +50'yi geçiyorsa her fazla satır gerekçelendirilir (yeni davranış mı, yoksa gereksiz soyutlama mı).
4. **Split hedefi = ölçülü üye toplamı:** Bir dosya N alt dosyaya bölünüyorsa, alt dosyaların toplam LOC'u orijinal dosyanın LOC'una yakın olmalı (±%10 tolerans — import/docstring farkları hariç); fazlası yeni kod eklendiği anlamına gelir ve gerekçe ister.

## Kabul Kriterleri
- [ ] `arch/quality_baseline.json` FAZ0 verisinden üretildi, commit'lendi
- [ ] ruff C901 aktif, 156 mevcut ihlal `noqa` ile işaretli (yenisi değil)
- [ ] `scripts/check_new_file_loc.py` CI'da çalışıyor
- [ ] `test_single_usecase_per_file.py` yeşil
- [ ] Her taşıma PR'ı kod-kısalığı 4 maddesini açıklamasında yanıtlıyor
