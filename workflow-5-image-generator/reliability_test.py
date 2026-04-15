import requests
import time
import json
from pathlib import Path
from datetime import datetime

# ── Config ───────────────────────────────────────────────
N8N_WEBHOOK = "http://localhost:5678/webhook/generate-image"
FASTAPI_URL = "http://127.0.0.1:8080"
OUTPUT_DIR = Path("output")
RUNS = 10
DELAY_BETWEEN_RUNS = 5  # seconds

TEST_PROMPTS = [
    "a red fox in a snowy forest, cinematic lighting",
    "a futuristic Tokyo street at night, neon lights",
    "a lone wolf on a mountain peak at dawn",
    "an ancient temple in a jungle, golden hour",
    "a cyberpunk city skyline, rain and reflections",
    "a lighthouse on a rocky cliff during a storm",
    "a medieval castle on a hill, misty morning",
    "a desert oasis at sunset, warm colours",
    "a snowy mountain village, cosy and warm",
    "a forest path in autumn, fallen leaves",
]

# ── Test runner ──────────────────────────────────────────
def run_test(run_number: int, prompt: str) -> dict:
    """
    Run one generation and return a result dict.
    """
    start = time.time()
    result = {
        "run": run_number,
        "prompt": prompt,
        "timestamp": datetime.now().isoformat(),
        "status": None,
        "duration_seconds": None,
        "error": None
    }

    print(f"\n[Run {run_number}/10] {prompt[:50]}...")

    try:
        # Check FastAPI is up
        health = requests.get(f"{FASTAPI_URL}/health", timeout=5)
        if health.status_code != 200:
            raise ConnectionError("FastAPI not healthy")

        # Check ComfyUI is up
        comfy = requests.get(f"{FASTAPI_URL}/comfy-status", timeout=10)
        if comfy.status_code != 200:
            raise ConnectionError("ComfyUI not reachable")

        # Fire the webhook
        response = requests.post(
            N8N_WEBHOOK,
            json={
                "prompt": prompt,
                "negative_prompt": "blurry, bad anatomy, watermark, text"
            },
            timeout=10
        )

        if response.status_code not in [200, 201]:
            raise RuntimeError(f"Webhook returned {response.status_code}")

        # Wait for generation
        # ComfyUI takes 20-60s depending on your hardware
        print(f"  Waiting for generation...")
        time.sleep(45)

        # Verify output exists — check FastAPI output folder
        # We can't easily check the exact file without the job_id
        # so we check that new files appeared in the last 60 seconds
        recent_files = [
            f for f in OUTPUT_DIR.glob("*.png")
            if (time.time() - f.stat().st_mtime) < 120
        ]

        if not recent_files:
            raise RuntimeError("No output image found after generation")

        result["status"] = "success"
        result["output_file"] = str(sorted(recent_files, key=lambda f: f.stat().st_mtime)[-1])
        print(f"  ✓ Success — {result['output_file']}")

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        print(f"  ✗ Failed — {e}")

    result["duration_seconds"] = round(time.time() - start, 1)
    return result


def run_reliability_test():
    """Run 10 consecutive generations and report results."""
    print(f"\n{'='*50}")
    print(f"Reliability Test — {RUNS} consecutive runs")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    results = []

    for i, prompt in enumerate(TEST_PROMPTS[:RUNS], 1):
        result = run_test(i, prompt)
        results.append(result)

        if i < RUNS:
            print(f"  Waiting {DELAY_BETWEEN_RUNS}s before next run...")
            time.sleep(DELAY_BETWEEN_RUNS)

    # ── Report ───────────────────────────────────────────
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    avg_duration = sum(r["duration_seconds"] for r in results) / len(results)

    print(f"\n{'='*50}")
    print(f"RESULTS")
    print(f"{'='*50}")
    print(f"Successes:    {successes}/{RUNS}")
    print(f"Failures:     {failures}/{RUNS}")
    print(f"Success rate: {(successes/RUNS)*100:.0f}%")
    print(f"Avg duration: {avg_duration:.1f}s")

    if failures > 0:
        print(f"\nFailed runs:")
        for r in results:
            if r["status"] == "failed":
                print(f"  Run {r['run']}: {r['error']}")

    # Save report
    report_path = OUTPUT_DIR / "reliability_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "summary": {
                "total_runs": RUNS,
                "successes": successes,
                "failures": failures,
                "success_rate": f"{(successes/RUNS)*100:.0f}%",
                "avg_duration_seconds": avg_duration
            },
            "runs": results
        }, f, indent=2)

    print(f"\nReport saved: {report_path}")
    return successes == RUNS


if __name__ == "__main__":
    all_passed = run_reliability_test()
    if all_passed:
        print("\n✓ Pipeline is reliable — ready for portfolio.")
    else:
        print("\n✗ Pipeline has failures — fix before publishing.")