"""End-to-end smoke test exercising all primary API endpoints in mock mode."""

import sys

from fastapi.testclient import TestClient

from skeptid.main import create_app


def run_smoke_tests() -> int:
    print("[SKEPTID Smoke] Initializing application in mock mode...")
    app = create_app()
    client = TestClient(app)

    # 1. Health probe
    print("Testing /healthz...")
    r = client.get("/healthz")
    if r.status_code != 200 or r.json().get("status") != "ok":
        print(f"Health check failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    # 2. Text analysis
    print("Testing /api/analyze/text...")
    payload = {"text": "URGENT: Please verify your bank account password immediately."}
    r = client.post("/api/analyze/text", json=payload)
    if r.status_code != 200:
        print(f"Text analysis failed: {r.status_code} {r.text}")
        return 1
    data = r.json()
    if not (data.get("mock") is True and "risk" in data and "label" in data):
        print(f"Unexpected response structure: {data}")
        return 1
    print(f"  -> Passed (label={data['label']}, risk={data['risk']}, level={data['level']})")

    # 3. Feedback submission
    print("Testing /api/feedback...")
    r = client.post(
        "/api/feedback",
        json={"analysis_id": data["id"], "correct": True},
    )
    if r.status_code != 200 or r.json().get("status") != "recorded":
        print(f"Feedback endpoint failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    # 4. Metrics retrieval
    print("Testing /api/metrics...")
    r = client.get("/api/metrics")
    if r.status_code != 200 or "models" not in r.json():
        print(f"Metrics endpoint failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    # 5. Providers status
    print("Testing /api/providers/status...")
    r = client.get("/api/providers/status")
    if r.status_code != 200 or "providers" not in r.json():
        print(f"Providers status failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    print("\n[SKEPTID Smoke] All smoke tests passed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_tests())
