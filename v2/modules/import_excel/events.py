"""Events ilgili import_excel modülüne.

Bu modülün kendi CRUD event'i YOK — import edilen entity'lerin (arac/
surucu/sefer/yakit/lokasyon) ADDED event'lerini kendi sahibi modülleri
zaten publish ediyor (veya diğer modüllerdeki ölü-kod deseninde olduğu
gibi hiç publish etmiyor). ``execute_import``'un sefer dalı gerçekten
``EventType.SEFER_UPDATED`` publish ediyor (trip'in kendi event'i,
``application/execute_import.py``'de doğrudan ``event_bus.publish_async``
ile) — bu modülün SAHİBİ OLMADIĞI bir event.
"""

__all__: list = []
