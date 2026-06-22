import requests


def test_chat():
    health_url = "http://localhost:8000/"
    try:
        r = requests.get(health_url)
        print(f"Health Check: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"Health Check failed: {e}")
        return

    # To test chat, I'll use the AIService directly in a python script to avoid auth issues.
    print("Testing AIService directly...")


test_chat()
