"""End-to-end smoke test exercising all primary API endpoints in mock mode."""

import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

    # 2. Message analysis
    print("Testing /api/message/analyze...")
    payload = {"text": "URGENT: Please verify your bank account password immediately."}
    r = client.post("/api/message/analyze", json=payload)
    if r.status_code != 200:
        print(f"Message analysis failed: {r.status_code} {r.text}")
        return 1
    data = r.json()
    if not (data.get("mock") is True and "risk" in data and "label" in data):
        print(f"Unexpected response structure: {data}")
        return 1
    print(f"  -> Passed (label={data['label']}, risk={data['risk']}, level={data['level']})")

    # 3. Media analysis (Image & Video)
    print("Testing /api/media/analyze (Image)...")
    import io

    from PIL import Image

    from tests.unit.test_video_sampling import create_synthetic_video_bytes

    img = Image.new("RGB", (128, 128), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    r = client.post("/api/media/analyze", files={"file": ("test.jpg", buf.getvalue(), "image/jpeg")})
    if r.status_code != 200:
        print(f"Media image analysis failed: {r.status_code} {r.text}")
        return 1
    media_img_data = r.json()
    if media_img_data.get("modality") != "image" or not any(ev.get("kind") == "heatmap" for ev in media_img_data.get("evidence", [])):
        print(f"Unexpected media image response: {media_img_data}")
        return 1
    print(f"  -> Passed Image (label={media_img_data['label']}, risk={media_img_data['risk']})")

    print("Testing /api/media/analyze (Video)...")
    mp4_bytes = create_synthetic_video_bytes(num_frames=16, fps=10.0)
    r = client.post("/api/media/analyze", files={"file": ("clip.mp4", mp4_bytes, "video/mp4")})
    if r.status_code != 200:
        print(f"Media video analysis failed: {r.status_code} {r.text}")
        return 1
    media_vid_data = r.json()
    if media_vid_data.get("modality") != "video":
        print(f"Unexpected media video response: {media_vid_data}")
        return 1
    print(f"  -> Passed Video (label={media_vid_data['label']}, risk={media_vid_data['risk']}, frames={len(media_vid_data.get('evidence', []))})")

    # 4. Feedback submission
    print("Testing /api/feedback...")
    r = client.post(
        "/api/feedback",
        json={"analysis_id": data["id"], "correct": True},
    )
    if r.status_code != 200 or r.json().get("status") != "recorded":
        print(f"Feedback endpoint failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    # 5. Metrics retrieval
    print("Testing /api/metrics...")
    r = client.get("/api/metrics")
    if r.status_code != 200 or "models" not in r.json():
        print(f"Metrics endpoint failed: {r.status_code} {r.text}")
        return 1
    print("  -> Passed")

    # 6. Providers status
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

