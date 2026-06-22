import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.core.services.excel_service import ExcelService


def test_excel():
    try:
        data = [
            {
                "Tarih": "2024-01-01",
                "Plaka": "06 ABC 123",
                "Litre": 100,
                "Birim Fiyat (TL)": 40.5,
            }
        ]
        print("Testing Excel export...")
        content = ExcelService.export_data(data, type="yakit_listesi")
        print(f"Success! Generated {len(content)} bytes.")

        with open("test_export.xlsx", "wb") as f:
            f.write(content)
        print("Saved to test_export.xlsx")

    except Exception as e:
        print(f"FAILED with error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_excel()
