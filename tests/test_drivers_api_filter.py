import asyncio


async def test():
    # We need to bypass auth or use the skara admin token.
    # I'll just check the DB directly to see if get_all_paged handles it.
    from app.core.services.sofor_service import get_sofor_service

    service = get_sofor_service()

    print("Fetching ACTIVE only:")
    active = await service.get_all_paged(aktif_only=True)
    for a in active:
        print(f" - {a['id']}: {a['ad_soyad']} (Aktif: {a['aktif']})")

    print("\nFetching ALL (active_only=False):")
    all_drivers = await service.get_all_paged(aktif_only=False)
    for a in all_drivers:
        print(f" - {a['id']}: {a['ad_soyad']} (Aktif: {a['aktif']})")


if __name__ == "__main__":
    asyncio.run(test())
