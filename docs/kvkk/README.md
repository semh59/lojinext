# KVKK Mini Paketi (Faz 11)

> **TASLAK — hukuki inceleme gerekir.** Bu belgeler teknik ekibin sistemdeki
> kişisel veri işleme gerçeğini şeffaf belgelemesidir; yürürlüğe girmeden önce
> bir hukuk danışmanı/veri sorumlusu tarafından onaylanmalıdır. Sistemde gerçekten
> tutulan alanlara dayanır (uydurma yok); metinler örnek/şablondur.

İçindekiler:
1. [Veri Envanteri](#1-veri-envanteri) — hangi kişisel veri nerede
2. [Sürücü Aydınlatma Metni (taslak)](#2-sürücü-aydınlatma-metni-taslak)
3. [Saklama Süresi Kararı](#3-saklama-süresi-kararı)

---

## 1. Veri Envanteri

Sistemde **kişisel veri** içeren tablolar (kaynak: `app/database/models.py`):

| Tablo | Alan | Veri tipi | İşleme amacı | Hukuki dayanak (taslak) |
|-------|------|-----------|--------------|--------------------------|
| `soforler` | `ad_soyad` | Kimlik | Sefer ataması, performans skoru | Sözleşmenin ifası |
| `soforler` | `telefon` | İletişim | Operasyonel iletişim | Meşru menfaat |
| `soforler` | `ehliyet_sinifi` | Mesleki | Araç-sürücü uygunluğu | Yasal yükümlülük (ulaştırma) |
| `kullanicilar` | `email` | İletişim/kimlik | Hesap + giriş | Sözleşmenin ifası |
| `kullanicilar` | `ad_soyad` | Kimlik | Hesap sahibi | Sözleşmenin ifası |
| `admin_audit_log` | `kullanici_email`, `kullanici_id` | Kimlik | Güvenlik denetim izi | Meşru menfaat (güvenlik) |
| `bildirim_gecmisi` / push | abonelik token | Cihaz | Bildirim teslimi | Açık rıza (push opt-in) |

**Hassas veri (özel nitelikli) YOK** — sağlık, biyometrik, din vb. işlenmiyor.
**Konum verisi:** Güzergah koordinatları (lokasyon/sefer) **araca/güzergaha** aittir,
sürücünün gerçek-zamanlı konumu değildir (AVL entegrasyonu opsiyonel + ayrı rıza
gerektirir; default kapalı).

**Veri akışı dışarı:** Mapbox (rota geometrisi — koordinat, sürücü PII'ı değil),
Open-Meteo (hava/yükseklik — koordinat), Groq (LLM — anonim metrik/metin), Sentry
(hata — PIIFilter + `scrub_pii` ile maskelenir), Telegram OPS (hata/feedback —
kullanıcı adı içerebilir). Üçüncü taraf aktarımları aydınlatma metninde belirtilmeli.

## 2. Sürücü Aydınlatma Metni (taslak)

> Şirket/veri sorumlusu adı, iletişim ve başvuru kanalı hukuk onayında doldurulur.

**Değerli Sürücümüz,**

[Şirket Adı] olarak, filo operasyonlarının yürütülmesi amacıyla aşağıdaki kişisel
verilerinizi işliyoruz:

- **Kimlik ve iletişim:** ad-soyad, telefon, ehliyet sınıfı.
- **Operasyonel:** size atanan seferler, sürüş performans skoru (yakıt verimliliği
  bazlı), araç kullanımı.

**Amaç:** Sefer planlama ve atama, yakıt/maliyet analizi, performans değerlendirmesi
ve yasal raporlama yükümlülükleri.

**Hukuki sebep:** İş sözleşmesinin ifası, ulaştırma mevzuatından doğan yasal
yükümlülükler ve filo güvenliğine ilişkin meşru menfaat.

**Aktarım:** Verileriniz yurt içinde barındırılır. Rota hesaplaması için yalnızca
**araç/güzergah koordinatları** (kimlik bilgisi olmadan) harita hizmeti sağlayıcısına
iletilir. Kişisel kimlik verileriniz üçüncü taraflarla pazarlama amacıyla
paylaşılmaz.

**Saklama:** Bölüm 3'teki sürelere göre saklanır; süre sonunda silinir/anonimleştirilir.

**Haklarınız (KVKK m.11):** Verilerinize erişme, düzeltme, silme, işlemeye itiraz
etme haklarına sahipsiniz. Başvuru: [veri sorumlusu iletişim kanalı].

## 3. Saklama Süresi Kararı

| Veri | Saklama süresi | Gerekçe | Sistemdeki uygulama |
|------|----------------|---------|----------------------|
| Sürücü/araç ana kayıtları | İş ilişkisi + yasal zamanaşımı süresi | Mevzuat (ticari/iş hukuku) | Soft-delete (`is_deleted`/`aktif`); kalıcı silme manuel |
| Sefer / yakıt işlem verisi | Mali/ticari mevzuat süresi | Vergi/denetim | Kalıcı (operasyonel geçmiş) |
| Kullanım analitiği (`page_views`) | **90 gün** | Sadece UX iyileştirme; kişi-bazlı değil | `ANALYTICS_RETENTION_DAYS=90` → gece task `analytics.prune_page_views` otomatik siler |
| Denetim izi (`admin_audit_log`) | Güvenlik politikası süresi | Güvenlik/uyum | Süre kararı hukuk onayında netleşir |
| Yedekler | **30 gün** | Felaket kurtarma | `BACKUP_RETENTION_DAYS=30` (operasyonel; runbook §4) |

**Karar:** Analitik (90g) ve yedek (30g) süreleri teknik olarak uygulanmıştır.
Ana kayıt + denetim izi saklama süreleri **hukuk onayı bekliyor** — netleşince bu
tabloya yazılır ve gerekirse otomatik prune task'i eklenir (analitikteki gibi).
