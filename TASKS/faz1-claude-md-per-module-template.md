# FAZ1 (çatı) — Modül-başı CLAUDE.md Şablonu

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz.

**Amaç:** Her `app/modules/<x>/` dizinine, o modüle özel bir CLAUDE.md yerleştirmek; Claude Code'un alt-dizin CLAUDE.md'sini ne zaman okuduğuna dair davranış farkını telafi eden bir okuma tetikleyicisi kurmak.

**Giriş kriteri:** Bir modülün iskeleti oluşturulmuş olmalı (dizin var).
**Çıkış kriteri:** 15 modülün + shared_kernel'in her birinde doldurulmuş CLAUDE.md var; root CLAUDE.md güncellendi.

---

## Şablon (her modül görev dosyasının 7. maddesinde bu başlıklarla doldurulur)

```markdown
# Modül: <ad>

## Sorumluluk sınırı
<ne yapar / ne YAPMAZ — modül görev dosyasının 1-2. maddelerinden>

## Public API
<public.py'daki fonksiyon/sınıf imzaları>

## Yayınladığı / dinlediği event'ler
<events.py DTO'ları + EventType eşlemesi>

## Senkron konuştuğu modüller
<MEMORY/PROGRESS.md §2.3'ten bu modülün satırları + gerekçe>

## Şema & tablo sahipliği
<MEMORY/PROGRESS.md §2.2'den bu modülün tabloları + çapraz FK'ları>

## İzin verilen / yasak importlar
<import-linter kontratının bu modüle ait özeti>

## Domain terimleri (TR↔EN sözlüğü)
<FAZ3 girdisi — bu modüldeki Türkçe kimliklerin İngilizce karşılıkları, henüz UYGULANMAMIŞ, yalnız sözlük>

## Modüle özel iş kuralları & gotcha'lar
<CHECK constraint'ler, transaction sınırları, N+1 tuzakları — heavy-split haritalarından>

## Test stratejisi
<slice/entegrasyon test dosyalarının konumu>
```

## Okunma tetikleyicisi (görevin açık notu — davranış farkı)

Claude Code alt-dizin CLAUDE.md'sini **oturum başında yüklemez**, yalnız o dizinde bir dosya `Read` edildiğinde devreye girer; `/compact` sonrası otomatik yeniden enjekte etmez. Bu yüzden:

1. Her `TASKS/modules/<modul>.md` dosyasının **1. adımı**: "Önce `app/modules/<modul>/CLAUDE.md`'yi Read ile oku."
2. Root `CLAUDE.md`'ye şu bölüm eklenir (FAZ1'in ilk PR'ında):
   ```markdown
   ## Modüler monolit — modül CLAUDE.md'leri

   `app/modules/<x>/` dizinlerinin her biri kendi CLAUDE.md'sine sahiptir.
   O modülde çalışmaya başlamadan önce (dosya okumadan/düzenlemeden ÖNCE)
   `app/modules/<x>/CLAUDE.md`'yi Read ile oku — oturum başında otomatik
   yüklenmez, `/compact` sonrası da yeniden enjekte edilmez.

   | Modül | Sorumluluk (1 satır) |
   |---|---|
   | trip | sefer yaşam döngüsü |
   | fleet | araç+dorse+bakım |
   | ... | ... (15 satır, modül görev dosyalarından) |
   ```

## Kabul Kriterleri
- [ ] Şablon tüm 9 başlığı içeriyor, hiçbiri boş bırakılmamış (placeholder yasak — görevin "No Placeholders" kuralı)
- [ ] Root CLAUDE.md'ye modül tablosu + okuma-tetikleyici talimatı eklendi
- [ ] Her modül taşındığında CLAUDE.md'si o PR'ın parçası (ayrı PR değil — modülle birlikte doğar)
