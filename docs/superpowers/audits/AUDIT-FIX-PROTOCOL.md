# AUDIT-FIX-PROTOCOL — Faz 2 Düzeltme Demir Kuralları

> **Faz 2'de (düzeltme) bir bulguya dokunmadan ÖNCE bu dosya okunur.** Bu protokol, Faz 1'de tespit edilen
> hata sınıflarının düzeltme sırasında TEKRAR üretilmesini engellemek içindir. Kapsam: `AUDIT-INDEX.md`'deki 183
> bulgu. Özet: `AUDIT-SUMMARY.md`.

Üç şart (ihlali = fix reddedilir):
1. **Önce doğrula** — hata kanıtlanmadan düzeltme yazılmaz.
2. **Başka yeri bozma** — fix regresyon üretmez; aile-kökü bir kez düzeltilir.
3. **Hayali/sahte kod yok** — var olmayan sembol/kolon/uç çağrılmaz; placeholder/stub/sahte-fallback yazılmaz.

---

## Demir Kural 1 — ÖNCE DOĞRULA (verify-first)

> Gerekçe: Faz 1'in en baskın teması **sessiz başarısızlık**. Doğrulamadan yapılan fix, var olmayan/yanlış-anlaşılan
> bir hatayı "düzeltir" → yeni sessiz hata. AUDIT-179 (`publish_simple` çağrısı — metot yok) tam olarak bu sınıf.

- **`confirmed` bulgu:** düzeltmeden önce hatayı **kırmızı test** ile yeniden üret (failing test). Test yoksa,
  hatayı tetikleyen minimal runtime repro veya kesin kod-trace (dosya:satır + neden) yaz. Kanıt artefaktı olmadan
  fix başlamaz.
- **`needs-verification` bulgu (27 adet):** düzeltmeden ÖNCE doğrula. **Doğrulama bir adımdır, sonuç açık olabilir:**
  - Üretilebiliyorsa → `confirmed`'a çevir, fix'e geç.
  - Üretilemiyorsa → bulguyu **DÜŞÜR/KAPAT** (`AUDIT-INDEX` durum=`wontfix`/`invalid` + gerekçe). **Hayalet hata
    düzeltmek = sahte kod.** Şüpheyle fix yazma.
- Doğrulama reçetesi (DB-dokunan bulgular): [[local_test_db_execution]] — Py3.12/Linux/UTF-8 throwaway testdb.
  Lokal native PG/Py3.14/cp1254 ile koşma (gotcha kök neden).
- **Definition of "doğrulandı":** failing test YEŞİL'e döner VEYA runtime repro fix sonrası kaybolur. "Bence
  düzeldi" yeterli değil.

## Demir Kural 2 — BAŞKA YERİ BOZMA (regresyon güvenliği)

> Gerekçe: bulguların çoğu **aile**. Tek semptomu izole düzeltmek diğer üyeleri kaçırır VEYA paylaşılan kökü
> değiştirip yeni yer bozar (`trip_status`, UoW, hata-zarfı load-bearing).

- **Fix öncesi VE sonrası tam kapı koş** (CLAUDE.md CI hard gates):
  - Backend: `pytest` (unit+integration, %70 coverage), `ruff check app --select E,F,W,I`, `mypy`, `alembic check`.
  - Frontend: `npx vitest --run`, `npm run build`, `npm run lint`.
  - Pre-commit (ruff+ruff-format+detect-secrets) — auto-fix olursa `git add` + tekrar commit (`--no-verify` YASAK).
- **Aile-kökü bir kez düzelt, sonra TÜM aile üyelerini doğrula** — izole semptom yaması yapma:
  - session'sız singleton raw-SQL: **084/085/094/131** (kök: UoW sarmalama deseni)
  - shared AsyncSession `gather`: **044/099/128**
  - event-loop bloke senkron ML/Redis: **063/126/148** (`asyncio.to_thread`)
  - durum TR↔EN: **174/165/058** (kök: tek canonical + ayrı label map)
  - PII-maskeleme: **121/122/127/144**
- **Blast-radius kontrolü:** paylaşılan util/imza değiştirmeden önce TÜM çağıranları `grep`'le (örn.
  `trip_status._fold_status`, `UnitOfWork`, hata-zarfı `{error:{code,message,trace_id}}`). Davranış değişiyorsa
  her çağıranı doğrula.
- **Küçük, geri-alınabilir commit:** bir bulgu-ailesi = bir branch/commit. `main`'e doğrudan yazma (denetim dalı
  `audit/fullcode-2026-06-14` veya yeni `fix/*` dalı).
- **Migration:** şema dokunan fix → `alembic revision --autogenerate` + `alembic check` 1 head. `Base.metadata.create_all`
  prod'da YASAK.

## Demir Kural 3 — HAYALİ/SAHTE KOD YOK (no fabrication)

> Gerekçe: AUDIT-179 (var-olmayan `publish_simple`), AUDIT-051/057 (yanlış kolon/tablo adı) — kod "var sanılan"
> bir şeye dayanıyordu. Fix sırasında AYNI hatayı yapma.

- **Çağırmadan önce DOĞRULA:** her import edilen sembol, DB kolonu, env değişkeni, endpoint path, repo metodu
  `read`/`grep` ile gerçek kod tabanında teyit edilir. "Olmalı" diye yazma. (Repo gotcha'ları: `get_container()`
  var `container` yok; `admin_audit_log` Türkçe kolonlar; repo `get_all` kwarg'ları üniform değil — CLAUDE.md.)
- **Sahte-fallback YASAK:** fix YENİ sessiz fallback eklemez. Hata **yüzeye çıkar** (raise/log/typed exception),
  `except: pass` veya sessiz `None`/0/boş-liste dönüşü ile maskelenmez. (Tema-1'i fix'te tekrar üretme.)
- **Placeholder/stub YASAK:** `TODO: implement`, sahte veri, `return {}` yer-tutucu, "şimdilik" yorumlu boş
  gövde — bulgu "düzeltildi" sayılmaz. Domain exception'lar `app/core/exceptions.py`'den fırlatılır, yutulmaz.
- **Kanıtsız "tamam" YASAK:** her fix'in bir kanıt artefaktı olur (geçen test / log / trace). "Görünüşe göre
  çalışıyor" reddedilir.

---

## Bulgu Kapatma Kriteri (Definition of Done)

Bir bulgu yalnız HEPSİ sağlanınca `fixed`:
1. Hata yeniden üretildi (kırmızı test / runtime repro / kesin trace).
2. Fix yazıldı; kırmızı → **yeşil**.
3. Tam kapı (backend + frontend) fix sonrası **geçiyor**.
4. Yeni bulgu üretilmedi (aynı aile üyeleri + blast-radius doğrulandı).
5. `AUDIT-INDEX.md` satırında durum `fixed` + commit hash; `AUDIT-PROGRESS.md`'de işaretlendi.
6. Yeni sessiz fallback / hayali sembol / stub eklenmedi.

## Sıra

1. **Faz-2 blocker seti önce:** `168, 115, 022` (sırlar) → `131, 061, 179, 180, 142` (sessiz-ölü) → `037, 081, 105`
   (veri-kaybı) → `174/165/058` (durum) → `057, 076`.
2. Aile içinde **kök önce**, sonra üyeler.
3. Her aile ayrı commit; her commit'te tam kapı.

> Demir kural ihlali tespit edilirse fix geri alınır. Statik denetimden farklı olarak Faz 2 **runtime doğrulama**
> gerektirir — kod okumak yetmez, çalıştırıp kanıtla. [[fullcode_audit_campaign]] · [[prod_readiness_audit_series]].
