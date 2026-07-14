import asyncio

from v2.modules.driver.application.delete_sofor import delete_sofor


async def test_delete(sofor_id):
    try:
        print(f"Attempting to delete driver ID: {sofor_id}")
        success = await delete_sofor(sofor_id)
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
