import asyncio

from app.core.services.sofor_service import get_sofor_service


async def test_delete(sofor_id):
    service = get_sofor_service()
    try:
        print(f"Attempting to delete driver ID: {sofor_id}")
        success = await service.delete_sofor(sofor_id)
        print(f"Success: {success}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import sys

    ids = [65]  # Test Deletion
    if len(sys.argv) > 1:
        ids = [int(x) for x in sys.argv[1:]]
    for sid in ids:
        asyncio.run(test_delete(sid))
