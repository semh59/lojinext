# UI Eksik-Özellik Çalışması — CTO Kalite Denetimi

Tarih: 2026-06-17 · Dal: main

Kullanıcı bulgusuyla eklenen yönetim ekranları + sonrasında CTO gözüyle kalite denetimi.

## Eklenen özellikler
| # | Özellik | Backend | Frontend | Commit |
|---|---------|---------|----------|--------|
| 5 | AI chat (orphaned'dı) | mevcut (/ai/chat,/ai/status) | EliteLayout mount | 6dd91547 |
| 2 | Rol yönetimi (CRUD) | admin_roles GET/POST + **yeni PUT/DELETE** | RollerPage liste/oluştur/düzenle/sil | 6dd91547, 6a9b1103 |
| 3/4 | Bakım + Arıza girişi | admin_maintenance POST | BakimPage giriş formu (tip: PERIYODIK/ARIZA/ACIL) | 6dd91547 |
| 6 | Sefer atama (attribution) | admin_attribution POST /override | AtamaPage | 6dd91547 |
| 7 | Tahmin doğruluk paneli | admin_fuel_accuracy GET | DogrulukPage | 6dd91547 |

## CTO denetim bulguları
1. **BUG (düzeltildi)** — `adminAttributionApi` `/admin/attribution` POST ediyordu ama
   backend endpoint `/admin/attribution/override` → her atama 404 olurdu. → path düzeltildi (6a9b1103).
2. **Güvenlik — rol CRUD**: PUT/DELETE'e privilege-escalation guard (çağıran kendinde
   olmayan yetkiyi veremez), sistem rolleri (super_admin/admin) korumalı, atanmış
   kullanıcısı olan rol 409 ile silinemez (FK koruması), tüm yazımlar audit'li. ✅
2b. **Path doğrulaması**: maintenance `/admin/maintenance/`, fuel-accuracy `/admin/fuel-accuracy`,
   roles `/admin/roles/{id}`, ai `/ai/chat`+`/ai/status` — tümü router'a kayıtlı + doğru. ✅
3. **Tutarlılık**: yeni sayfalar mevcut desene uyumlu (Modal/react-query/toast; admin
   route `admin:read` ile gate'li, buton-seviyesi gate yok — KullanicilarPage vb. ile aynı). ✅
4. **Hata yönetimi**: tüm mutation'larda onError + backend `detail` çıkarımı + toast. ✅
5. **Test**: rol_repo update/delete/count için 6 yeni unit test (mock-session) → 10/10 GREEN.
   API-seviyesi rol PUT/DELETE testleri DB-gated (test_admin_roles.py'ye CI'da eklenebilir).

## Kapsam kararları (CTO)
- **Ayrı "arıza bildir" akışı kurulmadı**: arıza zaten maintenance `bakim_tipi=ARIZA`
  ile giriliyor (arac_bakimlari → vehicle-health `open_ariza`). Paralel manuel-anomali
  endpoint'i redundant + veri-modeli karışıklığı olurdu (anomaliler istatistiksel oto-tespit).
- **Rol update = full-replace** (RolCreate şeması): UI tam rol nesnesini gönderir.

## Doğrulama kapıları (hepsi geçti)
- `vite build` ✅ · `tsc -p tsconfig.app.json` ✅ (ürün sıfır hata) · `eslint --max-warnings 0` ✅
- `ruff check` ✅ · rol_repo 10/10 ✅ · 107 admin+nav frontend testi ✅

## Açık kalan (düşük öncelik, opsiyonel)
- API-seviyesi rol PUT/DELETE entegrasyon testleri (DB gerektirir; test_admin_roles.py'ye eklenebilir).
- İsteğe bağlı: admin yazım butonlarını RequirePermission ile gate'lemek (UX iyileştirmesi;
  güvenlik backend'de zaten var). Mevcut tüm admin sayfalarıyla tutarlı olması için şimdilik yapılmadı.
