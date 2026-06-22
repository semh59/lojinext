# Repo Geneli Kritik Takip Backlogu (Seferler Dışı)

Bu backlog, Seferler dışındaki kritik riskleri iki dala ayırır.

Sprint Referans Baz Tarihi: `2026-03-15`
S+1 = ilk release sonrası sprint
S+2 = S+1'den sonraki sprint

## Hemen Düzelt (Prod Riskli)

1. **Encoding/Mojibake metinleri API/UI cevaplarında**

- Etki: kullanıcıya bozuk mesaj, sözleşme metinlerinde tutarsızlık.
- Kanıt: `app/api/v1/endpoints/trips.py` ve bazı endpoint mesajlarında bozuk karakterler.
- Fix: UTF-8 standardizasyonu + metin sabitlerinin normalize edilmesi + smoke test.
- Test: endpoint message snapshot + frontend render assertion.
- Owner: Backend Lead
- Hedef sprint: S+1.
- Remediation ref: Faz 5 (F5-01, F5-02, F5-03)

2. **Geniş `except Exception` + doğrudan `500` dönüşleri**

- Etki: kök hata sınıflandırması kayboluyor, gözlemlenebilirlik düşüyor.
- Kanıt: çok sayıda endpointte `except Exception as e` kalıbı.
- Fix: domain hata sınıfları (4xx/5xx ayrımı), merkezi error mapping.
- Test: hata senaryo testleri (validation, not found, forbidden, internal).
- Owner: Backend Lead
- Hedef sprint: S+1.
- Remediation ref: Faz 3 (F3-08)

3. **Auth/Permission tutarlılığı**

- Etki: endpoint bazında RBAC davranışı drift riski.
- Kanıt: endpointlerde farklı dependency patternleri (`get_current_user`, `get_current_active_admin`, `require_permissions` karışık).
- Fix: endpoint policy matrisi çıkar, her route için tek policy standardı uygula.
- Test: RBAC integration matrix.
- Owner: Backend Lead
- Hedef sprint: S+1.
- Remediation ref: Faz 2 (F2-01, F2-02, F2-04)

## Sonraki Sprint (Yüksek ama Lokal)

1. **Background job cleanup eksikliği**

- Etki: job tablosu/bellek birikimi.
- Kanıt: `app/infrastructure/background/job_manager.py` TODO.
- Fix: TTL cleanup + scheduled prune.
- Test: job lifecycle + retention test.
- Owner: Backend Lead
- Hedef sprint: S+2.
- Remediation ref: program dışı

2. **AI/ML servislerinde geniş hata yutma kalıpları**

- Etki: sessiz degrade, izleme zayıf.
- Kanıt: `app/core/ai/*` ve `app/core/ml/*` içinde yaygın broad-exception.
- Fix: structured logging + failure reason codes + fallback telemetrisi.
- Test: model unavailable, feature mismatch, fallback path assertions.
- Owner: Backend Lead
- Hedef sprint: S+2.
- Remediation ref: program dışı

3. **Endpoint kontrat snapshot kapsamının dar olması**

- Etki: istemci kırıkları geç fark edilir.
- Fix: kritik endpointler için response key snapshot testleri genişlet.
- Test: contract snapshot suite (api/v1 core modüller).
- Owner: QA/Release Owner
- Hedef sprint: S+2.
- Remediation ref: Faz 3 (F3-10)

## Standart Takip Kaydı Şablonu

- Başlık
- Etki (kullanıcı/operasyon/veri)
- Tekrar üretim adımı
- Teknik kök neden
- Fix yaklaşımı
- Test gereksinimi
- Owner
- Hedef sprint
- Remediation ref
