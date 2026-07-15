# BUG — 3 modülde route handler'ları `application/` katmanını atlayıp doğrudan repo/ORM çağırıyor

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Bu bir modül taşıma görevi DEĞİL.** FAZ1'in 17 dalga sırasının dışında,
bağımsız bir katman-disiplini temizliği. 3 modül (notification/dalga 2,
fleet/dalga 3, auth_rbac/dalga 6) zaten taşınmış ve main'de yeşil; bu
görev o modüllerin İÇİNDE `route (`api/`) → application/ → repo` akış
disiplinini tamamlıyor. Herhangi bir oturumda, dalga sırası beklenmeden
ele alınabilir.

**Giriş kriteri:** yok (bağımsız). **Çıkış kriteri:** aşağıdaki 5
handler'ın hepsi yalnız `application/`'daki bir use-case fonksiyonunu
çağırıyor; hiçbiri doğrudan `uow.<repo>`/`db.get`/`select(...)` çalıştırmıyor.

---

## Bulgu (2026-07-15, dalga-1-6-detaylı dedektif denetiminde bulundu — dalga 8/anomaly'nin kendi denetimi tamamlandıktan sonra, kullanıcı talebiyle "ilk 8 dalga"yı kapsayan 6 bağımsız-ajan taraması)

Bu 3 modülün geri kalanı (`>90%` dosya) `api/` katmanının **yalnızca**
`application/` fonksiyonlarını çağırdığı disiplinine sıkı uyuyor —
aşağıdaki 5 handler bu deseni bozan istisna:

### a) `v2/modules/notification/api/notification_routes.py:50-142`
`list_rules`/`create_rule`/`update_rule`/`delete_rule` — `uow.notification_repo`'yu
doğrudan çağırıyor, `application/` katmanında karşılık gelen bir
`{list,create,update,delete}_notification_rule.py` yok.

### b) `v2/modules/notification/api/push_routes.py:61-121`
`subscribe`/`unsubscribe` — `uow.session`/`uow.notification_repo`'ya
doğrudan erişiyor + upsert iş kararını (satır ~75-78, synthetic-admin
id≤0 guard'ı dahil) route içinde barındırıyor.

### c) `v2/modules/fleet/api/admin_maintenance_routes.py:214-231`
`download_ics` — `UnitOfWork` açıp `select(AracBakim)`/`select(Arac)`
ORM sorgularını route içinde doğrudan çalıştırıyor.

### d) `v2/modules/fleet/api/vehicle_routes.py:312-322,325-348` ve
`v2/modules/fleet/api/trailer_routes.py:242-252,255-280`
`read_arac`/`update_arac`/`read_dorse`/`update_dorse` — tekil-kayıt
GET/refresh işlemleri `db.get(Arac,...)`/`select(Arac)` ile doğrudan ORM
üzerinden yapılıyor; `public.py`'de zaten mevcut olan `get_vehicle_by_id`
gibi use-case'ler kullanılmıyor.

### e) `v2/modules/auth_rbac/api/admin_role_routes.py` (tüm dosya)
`RolRepository`'yi doğrudan örnekliyor (satır 23, 34, 62, 108, 142);
`application/role_service.py` diye bir dosya hiç yok — modülün diğer 5
route dosyası (`auth_routes.py`, `admin_user_routes.py`,
`preference_routes.py`, `user_routes.py`, `ws_ticket_routes.py`) her
zaman `application/*_service.py`'ye delege ederken bu dosya delege
etmiyor. Ayrıca privilege-escalation guard iş kuralı
(`_assert_no_privilege_escalation`, satır 82-97) `create_role` içinde
(satır 48-60) neredeyse birebir TEKRARLANMIŞ — küçük bir DRY ihlali de
var, aynı düzeltmede ele alınmalı.

## Neden önemli

B.1'in "her dosya tek görev" ilkesi teknik olarak ihlal edilmiyor (repo
sınıfları hâlâ tek sorumluluk taşıyor) ama modüllerin kendi CLAUDE.md'lerinde
dokümante edilen "route → application → repo" akış sözleşmesi bu 5
handler'da tutmuyor. FAZ1'in import-linter/davranışsal-mimari-test gate'i
(henüz aktif değil, "çatı görevleri" listesinde) devreye girdiğinde bu
muhtemelen otomatik yakalanacak bir ihlal sınıfı — şimdiden dokümante
edilmesi o gate'in kurulumunu kolaylaştırır.

## Düzeltme taslağı (öneri, kesinleştirilmemiş)

- (a)/(b): `v2/modules/notification/application/{manage_notification_rules,manage_push_subscription}.py` gibi 1-2 yeni dosya.
- (c): `v2/modules/fleet/application/get_maintenance_ics_data.py` yeni dosya.
- (d): mevcut `public.py` export'larını (`get_vehicle_by_id` vb.) kullanacak şekilde route'ları düzelt — muhtemelen yeni dosya gerekmez.
- (e): `v2/modules/auth_rbac/application/role_service.py` yeni dosya (diğer `*_service.py` free-function deseniyle tutarlı), `_assert_no_privilege_escalation`'ı tek yerden kullanacak şekilde `create_role`'daki tekrarı kaldır.

Her değişiklik davranış-değiştirmeden (mekanik taşıma) yapılmalı, gerçek
DB'ye karşı ilgili modülün mevcut test suite'i (0 regresyon) + OpenAPI
drift kontrolü ile doğrulanmalı.
