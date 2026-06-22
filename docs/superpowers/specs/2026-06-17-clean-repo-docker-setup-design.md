# LojiNext — Temiz Repo + Docker + CI Kurulum Speci

**Tarih:** 2026-06-17
**Durum:** Uygulandı

## Hedef

Mevcut iki kirli remote (semh59/LOJINEXT + semh59/lojinext-v2) silinir.
Yeni `semh59/lojinext` reposu oluşturulur.
Tüm commit geçmişi tek bir "initial commit"e squash edilir.
Docker Compose lokal doğrulanır, CI gerçekten yeşil geçer.
0 mock, 0 hayali kod, 0 yalan.

## Başarı Kriterleri

- `git log --oneline | wc -l` → 1
- `docker compose ps` → tüm service'ler healthy
- `curl -f http://localhost:8000/api/v1/health/` → 200
- GitHub Actions `hard-gates` job → green
- `publish` job → continue-on-error (GHCR_TOKEN gerekir, opsiyonel)

## Uygulama Adımları

1. **Lokal temizlik** — orphan branch squash, 25 stale branch sil, eski remote'ları kaldır
2. **Docker doğrulaması** — `docker compose build && docker compose up -d`, health check, API smoke
3. **Yeni repo** — `gh repo create semh59/lojinext --private`, remote ekle, push
4. **CI izleme** — `gh run watch` ile yeşil doğrula
5. **Secrets** — TELEGRAM_OPS_BOT_TOKEN, TELEGRAM_OPS_CHAT_ID, GHCR_TOKEN, INTERNAL_API_SECRET

## Mimari Değişiklik Yok

Docker Compose, Dockerfile, CI workflow değişmez — sadece remote kayıt yeri değişir.
