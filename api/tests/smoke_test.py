import os
import sys
import json
import urllib.request
import urllib.error

def run_smoke_test():
    url = os.environ.get("DEPLOY_URL", "http://127.0.0.1:8000").rstrip("/")
    print(f"Starting smoke tests against target: {url}")
    
    # Check 1: Root UI Delivery
    try:
        req = urllib.request.Request(f"{url}/")
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            assert resp.status == 200
            assert b"USYD" in content or b"Planner" in content
            print("[PASS] Check 1: UI served successfully.")
    except Exception as e:
        print(f"[FAIL] Check 1: Root UI unreachable. {e}")
        sys.exit(1)
        
    # Check 2: API Catalogue Search
    try:
        req = urllib.request.Request(f"{url}/api/units?query=COMP&page_size=1")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert isinstance(data, list)
            print("[PASS] Check 2: API Catalogue querying functional.")
    except Exception as e:
        print(f"[FAIL] Check 2: Catalog search failed. {e}")
        sys.exit(1)
        
    # Check 3: Stateless Validation Endpoint
    try:
        payload = {
            "mode": "free",
            "start_year": 2026,
            "placements": [
                {"year": 1, "term": "sem1", "codes": ["INFO1110"]}
            ]
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/validate-plan",
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert "valid" in data
            print("[PASS] Check 3: Validation engine online.")
    except Exception as e:
        print(f"[FAIL] Check 3: Validation endpoint failed. {e}")
        sys.exit(1)
        
    print("All smoke tests passed successfully!")

if __name__ == "__main__":
    run_smoke_test()
