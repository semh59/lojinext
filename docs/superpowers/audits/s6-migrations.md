# S6 — Alembic Migrations Bulguları

Kapsam: alembic/env.py + alembic/versions/*.py (27 migration). Plan S6.
Denetim odağı: model↔migration drift, downgrade tersinirliği, yıkıcı op/veri kaybı, idempotency.

## S6 — alembic (env.py + 27 migration) — 3 bulgu

**Genel kalite yüksek.** Çoğu migration idempotent (IF EXISTS / information_schema guard), naming-convention
uyumlu FK adları, dökümanlı veri-kaybı (0019 traffic drop). env.py örnek: sync-URL dönüşümü, partition/MV
`_include_object` skip, geometry `_compare_type` skip, NullPool. 0002 seed idempotent upsert + ADMIN_PASSWORD
zorunlu (AUDIT-115 backdoor ayrı; seed doğru yol). 0005/0023 drift düzeltmeleri guard'lı. 0011 partition +
on-demand retry. 0016/0017/0020 route-sim şeması CLAUDE.md kolon adlarıyla birebir.

**Düşük gözlemler (bulgu değil):** (a) 0004 `outbox_events.dispatched` ve `prediction_results.arac_id/tarih`
var-olmayan kolonlara index dener → guard yüzünden hiç tetiklenmez (ölü niyet; gerçek `processed` index'i 9728'de
zaten var). (b) 0011 dosya adı `0011_` ama `revision="2f052e500be8"` (hash) — chain çalışır, kozmetik tutarsızlık.
(c) 9728 zincir churn: JSONB→JSON sonra 0005 JSON→JSONB'ye geri çevirir; guzergah_id NOT NULL sonra 0005 drop —
net durum doğru ama gereksiz gidip-gelme. (d) 0012 `acknowledged_by`/`resolved_by` FK'sız (AUDIT-008 ailesi).
(e) 0021 partition'lar Ekim 2026'ya kadar sabit — beat task + on-demand retry ile telafi.

### AUDIT-163 — 0022 downgrade'i bozuk: İngilizce veriye Türkçe CHECK ekliyor → mevcut satırlar ihlal → downgrade hata verir
- Şiddet: low
- Sınıf: bug
- Konum: 0022_durum_canonical_english.py:118-130
- Durum: confirmed
- Kanıt:
    ```python
    def downgrade():
        # Data remapping (Turkish->English) is NOT reversed ...
        op.execute("ALTER TABLE seferler ADD CONSTRAINT check_sefer_durum_enum "
                   "CHECK (durum IN ('Bekliyor','Planlandı',...,'İptal'));")  # veri hala İngilizce
    ```
  Downgrade veriyi İngilizce→Türkçe geri çevirmeden Türkçe CHECK ekliyor; mevcut `Planned/Completed/Cancelled`
  satırları bu Türkçe CHECK'i ihlal eder → PostgreSQL ADD CONSTRAINT mevcut satırları doğruladığı için
  **downgrade ADD CONSTRAINT'te patlar**. Docstring'deki gerekçe ters ("Türkçe değerleri yok" diyor ama sorun
  İngilizce değerlerin Türkçe set'te olmaması). Aynı aile: 9728 downgrade `is_real` NOT NULL default'suz re-add
  (dolu tabloda patlar); 0005 downgrade `SET NOT NULL` NULL varsa patlar. Downgrade'ler prod'da nadir → düşük.
- Önerilen düzeltme: downgrade'de önce İngilizce→Türkçe remap UPDATE'i yap, sonra constraint ekle; ya da
  CHECK'i `NOT VALID` ile ekle.
- Bağımlılık: AUDIT-164, trip_status canonical.

### AUDIT-164 — seferler.durum server_default='Tamam' (Türkçe) — 0022 sonrası İngilizce-only CHECK ile çelişir; default'a güvenen insert ihlal eder + model'le drift
- Şiddet: medium
- Sınıf: data-integrity
- Konum: 0001_baseline_manual.py:966-971,1023-1026 + 0022 (default değişmedi) + models.py:561
- Durum: confirmed
- Kanıt:
    ```python
    # baseline: durum server_default 'Tamam' + CHECK Türkçe
    sa.Column("durum", sa.String(20), nullable=False, server_default=sa.text("'Tamam'"))
    # 0022: CHECK'i İngilizce'ye çevirir AMA server_default'a DOKUNMAZ → hala 'Tamam'
    # models.py:561: server_default=text("'Planned'")   ← migration ('Tamam') ile DRIFT
    ```
  0022 CHECK'i `IN ('Planned','Completed','Cancelled')` yaptı ama `seferler.durum`'un server_default'ını
  'Tamam' (Türkçe) olarak bıraktı → migration-built şemada durum kolonu DEFAULT 'Tamam', CHECK ise yalnız
  İngilizce kabul ediyor → durum belirtmeyen ham bir INSERT/COPY 'Tamam' alır ve CHECK'i **ihlal eder**.
  ORM her zaman durum='Planned' gönderdiği için pratik etki ORM yolunda maskeli; ham SQL/dış insert'lerde
  patlar. Ayrıca model server_default'u 'Planned' → migration 'Tamam' ile drift; `alembic check`
  `compare_server_default` kapalı olduğu için bunu yakalamaz (CI sessiz geçer).
- Önerilen düzeltme: 0022'ye (veya yeni migration'a) `ALTER TABLE seferler ALTER COLUMN durum SET DEFAULT
  'Planned'` ekle; model ile hizala.
- Bağımlılık: AUDIT-163, trip_status, BUG-002 durum-drift teması.

### AUDIT-165 — yakit_alimlari.durum CHECK yalnız ASCII 'Onaylandi' kabul ediyor; uygulama Türkçe 'Onaylandı' yazıyorsa onay UPDATE'i ihlal eder
- Şiddet: medium
- Sınıf: data-integrity
- Konum: 0006_fk_indexes_and_checks.py:45-49
- Durum: needs-verification
- Kanıt:
    ```python
    ("yakit_alimlari", "check_yakit_durum_enum", "durum IN ('Bekliyor', 'Onaylandi')")  # ASCII i
    ```
  CHECK yalnız 'Bekliyor' ve 'Onaylandi' (ASCII i) kabul ediyor. AUDIT-107 yakit şemasında hem 'Onaylandi'
  hem 'Onaylandı' (Türkçe ı) Literal'inin birlikte bulunduğunu tespit etti. Onay yolu durum='Onaylandı'
  (Türkçe) yazıyorsa UPDATE bu CHECK'i ihlal eder → yakıt onayı 500/constraint hatası. Hangi değerin
  yazıldığı (yakit_service approve) doğrulanmalı.
- Önerilen düzeltme: CHECK'e iki varyantı da ekle veya kanonik tek değere indir (AUDIT-107 ile birlikte);
  uygulamayı CHECK ile aynı string'e sabitle.
- Bağımlılık: AUDIT-107 (yakit durum Literal duplike), yakit_service approve.
