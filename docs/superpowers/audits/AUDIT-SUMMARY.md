# AUDIT-SUMMARY — Yönetici Özeti (Faz 1)

> Tek sayfa, bütün resim. Detaylar: `AUDIT-INDEX.md` (183 bulgu master tablo) + `s1..s9-*.md` (modül bulguları).
> Düzeltme kuralları: `AUDIT-FIX-PROTOCOL.md` (Faz 2'ye girmeden ÖNCE okunmalı).

**Tarih:** 2026-06-16 · **Dal:** `audit/fullcode-2026-06-14` · **Faz:** 1 (salt tespit, kod değişmedi)

---

## Teşhis (tek cümle)

Sistem **özellik açısından zengin ama olgunluk açısından eşitsiz**: çok şey "yazılmış" görünüyor, ama önemli
bir kısmı **sessizce çalışmıyor ve bunu fark ettirmiyor**. Risk neredeyse tamamen **backend + altyapı + script**
tarafında; frontend gerçekten sağlam.

## Kapsam ve sayılar

| | |
|---|---|
| Denetlenen | **660 / 1275 dosya** — TÜM üretim kodu |
| Kapsam dışı | 615 dosya = yalnız S10 testler (kullanıcı kararı `s10 dahil değil`) |
| Toplam bulgu | **183** — 19 high · 101 medium · 63 low |
| Doğrulama | 156 confirmed · **27 needs-verification** (çalışma zamanında doğrulanmalı) |
| Yöntem | Statik (satır-satır okuma). Runtime/pentest YAPILMADI. |

## Kalite haritası (uçurum asıl bulgu)

| Katman | Durum | Bulgu yoğunluğu |
|---|---|---|
| **Frontend (sunum+mantık, ~263 dosya)** | **Örnek/güçlü** — XSS yüzeyi tertemiz (`dangerouslySetInnerHTML`/`eval` YOK), tutarlı desenler, iyi güvenlik UX'i | **1** yeni bulgu (AUDIT-183) |
| **Backend servis/altyapı** | **Kırılgan** — async/DB-session disiplini tutarsız, sessiz-ölü altsistemler | High'ların ~tamamı |
| **Script / dev araçları** | **Bakımsız** — sabit-kodlu parolalar, bozuk/şema-ıraksak script'ler | 168, 170, 180… |

## Bütün resmi anlatan 4 sistemik tema

**1. Sessiz başarısızlık / "vitrin özellik" — EN BASKIN tema.**
Özellik kablolanmış ama gerçekte hiçbir şey yapmıyor; 503/boş/0-satır ile maskeleniyor.
- `TimeSeriesService` session'sız → tüm zaman-serisi altsistemi **ölü**, 503 ardında gizli (**131**)
- Periyot yeniden-hesabı sessizce ölü (**061**)
- `backfill_route_pairs` her koşuda **0 satır** (`is None`→`WHERE false`) (**180**)
- Auto-train sonrası cache/RAG invalidation **hiç** tetiklenmiyor (var-olmayan metot) (**179**)
- Outbox handler hatasında event'i "işlendi" işaretliyor (**142**)
> "%95 tamamlandı" raporlarının neden yanıltıcı olduğunu açıklar (bkz. sahte "TAMAMLANDI" raporları geçmişi).

**2. Async + DB-session disiplini sistematik zayıf.**
Aynı sınıf defalarca: session'sız singleton raw-SQL crash (**084/085/094/131**); `gather` içinde paylaşılan
AsyncSession (**044/099/128**); event-loop'u bloklayan senkron ML/Redis (**063/126/148**). UoW deseni var ama
tutarlı uygulanmıyor — mimari-disiplin açığı, tek tek bug değil.

**3. Tek kavramsal hata, ~15 yerde tezahür: durum (TR↔EN).**
Backend canonical İngilizce, frontend Türkçe, DB CHECK kimi yerde ASCII. Tek tasarım çelişkisi (iki sözlük) tüm
sefer UI + filtre + form-submit + yakıt durumu boyunca akıyor (**174/165/058**). Konsept basit, yüzeyi geniş.

**4. Güvenlik: cephe sağlam, arka kapı açık.**
Somut olanlar backend/script'te: repo'da sabit-kodlu parolalar (**168**), env super-admin backdoor (**115**),
plaintext reset-token (**022**), PII-maskeleme boşlukları (**121/122/127/144**), WS token'ı URL'de (**175** +
monitoring genişlemesi). Frontend tersine örnek (ticket'li SSE, safeHref).

## Risk nerede yoğunlaşıyor

- **Veri kaybı:** yakıt=0 günde tüketimi 0'a ezme (**037**, kalıcı); bulk-override yalnız ilk satır (**081**);
  response-heal constraint ihlali (**105**).
- **Gizli ölü özellik:** tema-1 — en sinsi, demo'da "çalışıyor gibi" görünür.
- **Sızdıran sır:** committed parolalar (168) + env backdoor (115) — tek başına prod-engelleyici.

## Karar: bugünkü haliyle PROD'A HAZIR DEĞİL (ama felaket değil)

İskelet makul, frontend güçlü. Hazır olması için sıra:
1. **Sırlar:** committed parolalar + backdoor (anında — 168, 115)
2. **Sessiz-ölü altsistemler:** yanlış güven veriyor (131, 061, 179, 180, 142)
3. **Async/DB-session disiplini:** (084/085/094/131, 044/099/128, 063/126/148)
4. **Durum birliği:** (174/165/058)
5. **Veri-kaybı:** (037, 081, 105)

**Faz-2 blocker seti:** `174, 081, 076, 057, 022, 168, 037, 115`.

## Dürüst kısıtlar

- Statik denetim — **27 bulgu nv**, runtime'da doğrulanmalı; bazıları düşebilir/kapanabilir.
- 101 medium = "belirli koşulda ısırır" — patlamaz ama biriken borç.
- Bulgular yazıldığı andaki kod halini yansıtır; fix öncesi her biri yeniden doğrulanmalı (`AUDIT-FIX-PROTOCOL.md`).
