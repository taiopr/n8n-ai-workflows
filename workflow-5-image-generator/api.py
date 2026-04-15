import json
import copy
import time
import requests
import httpx
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import uvicorn
from dotenv import load_dotenv
import os

load_dotenv()

# ── Import your existing pipeline components ─────────────
from prompt_variations import PromptVariation

# ── Config ───────────────────────────────────────────────
COMFY_URL = "http://127.0.0.1:8000"
WORKFLOW_PATH = "workflow_api.json"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Your confirmed node IDs
POSITIVE_PROMPT_NODE = "6"
NEGATIVE_PROMPT_NODE = "7"
KSAMPLER_NODE = "3"

# Slack config — replace with your actual values

SLACK_TOKEN = os.getenv("SLACK_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# ── FastAPI app ──────────────────────────────────────────
app = FastAPI(
    title="ComfyUI Generation API",
    description="Wraps ComfyUI pipeline for n8n integration",
    version="1.0.0"
)


# ── Request/Response models ──────────────────────────────
class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = "blurry, bad anatomy, watermark, text"
    seed: Optional[int] = -1
    callback_url: Optional[str] = None


class GenerateResponse(BaseModel):
    status: str
    job_id: str
    message: str


# ── ComfyUI pipeline helpers ─────────────────────────────
def load_workflow() -> dict:
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def configure_workflow(
    workflow: dict,
    prompt: str,
    negative_prompt: str,
    seed: int
) -> dict:
    import random
    wf = copy.deepcopy(workflow)
    wf[POSITIVE_PROMPT_NODE]["inputs"]["text"] = prompt
    wf[NEGATIVE_PROMPT_NODE]["inputs"]["text"] = negative_prompt
    wf[KSAMPLER_NODE]["inputs"]["seed"] = (
        random.randint(0, 2**32) if seed == -1 else seed
    )
    return wf


def submit_to_comfy(workflow: dict) -> str:
    response = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow}
    )
    response.raise_for_status()
    return response.json()["prompt_id"]


def wait_for_comfy(prompt_id: str, poll_interval: int = 2) -> dict:
    timeout = 300
    elapsed = 0
    while elapsed < timeout:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}")
        history = response.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"ComfyUI job {prompt_id} timed out after {timeout}s")


def get_output_image(history_entry: dict) -> Optional[str]:
    for node_id, node_output in history_entry.get("outputs", {}).items():
        if "images" in node_output:
            return node_output["images"][0]["filename"]
    return None


def download_from_comfy(filename: str, save_path: Path) -> None:
    response = requests.get(
        f"{COMFY_URL}/view",
        params={"filename": filename}
    )
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)


# ── Block 6: Slack image upload ──────────────────────────
def upload_to_slack(
    image_path: Path,
    job_id: str,
    prompt: str,
    slack_token: str,
    channel_id: str
) -> None:
    """
    Upload image to Slack using the new 2024 API (files.getUploadURLExternal).
    Three step process: get URL → upload file → complete upload.
    """
    print(f"[{job_id}] Uploading image to Slack...")

    # Step 1: Get upload URL
    filename = f"{job_id}.png"
    file_size = image_path.stat().st_size

    url_response = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers={"Authorization": f"Bearer {slack_token}"},
        data={
            "filename": filename,
            "length": file_size
        }
    )

    url_data = url_response.json()
    if not url_data.get("ok"):
        print(f"[{job_id}] Slack upload failed (get URL): {url_data.get('error')}")
        return

    upload_url = url_data["upload_url"]
    file_id = url_data["file_id"]

    # Step 2: Upload file to the provided URL
    with open(image_path, "rb") as img_file:
        upload_response = requests.post(
            upload_url,
            data=img_file,
            headers={"Content-Type": "image/png"}
        )

    if upload_response.status_code != 200:
        print(f"[{job_id}] Slack upload failed (upload): {upload_response.status_code}")
        return

    # Step 3: Complete the upload and share to channel
    complete_response = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers={
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json"
        },
        json={
            "files": [{"id": file_id}],
            "channel_id": channel_id,
            "initial_comment": (
                f"🎨 *New image generated*\n"
                f"*Prompt:* {prompt}\n"
                f"*Job ID:* {job_id}"
            )
        }
    )

    complete_data = complete_response.json()
    if complete_data.get("ok"):
        print(f"[{job_id}] Image uploaded to Slack successfully")
    else:
        print(f"[{job_id}] Slack upload failed (complete): {complete_data.get('error')}")


# ── Block 7: send callback ───────────────────────────────
def send_callback(
    job_id: str,
    image_path: Optional[Path],
    callback_url: str,
    prompt: str,
    success: bool,
    error: Optional[str] = None
) -> None:
    print(f"[{job_id}] Sending callback to: {callback_url}")

    if success and image_path:
        with open(image_path, "rb") as img_file:
            files = {"image": (f"{job_id}.png", img_file, "image/png")}
            data = {"job_id": job_id, "prompt": prompt, "status": "success"}
            response = requests.post(callback_url, files=files, data=data)
    else:
        response = requests.post(callback_url, json={
            "job_id": job_id,
            "prompt": prompt,
            "status": "error",
            "error": error
        })

    print(f"[{job_id}] Callback response: {response.status_code}")


# ── Block 7: full generation with error handling ─────────
def run_generation(
    job_id: str,
    prompt: str,
    negative_prompt: str,
    seed: int,
    callback_url: Optional[str]
) -> None:
    print(f"\n[{job_id}] Starting generation")
    print(f"[{job_id}] Prompt: {prompt[:60]}...")

    try:
        # Check ComfyUI is available before starting
        try:
            requests.get(f"{COMFY_URL}/system_stats", timeout=5)
        except Exception:
            raise ConnectionError("ComfyUI is not reachable")

        # Step 1: Configure and submit workflow
        workflow = load_workflow()
        workflow = configure_workflow(workflow, prompt, negative_prompt, seed)

        try:
            comfy_prompt_id = submit_to_comfy(workflow)
        except Exception as e:
            raise RuntimeError(f"Failed to submit to ComfyUI: {e}")

        print(f"[{job_id}] Submitted to ComfyUI: {comfy_prompt_id}")

        # Step 2: Wait for completion
        try:
            history = wait_for_comfy(comfy_prompt_id)
        except TimeoutError:
            raise TimeoutError("ComfyUI generation timed out")

        print(f"[{job_id}] Generation complete")

        # Step 3: Download output image
        filename = get_output_image(history)
        if not filename:
            raise ValueError("ComfyUI completed but produced no output image")

        save_path = OUTPUT_DIR / f"{job_id}.png"
        download_from_comfy(filename, save_path)
        print(f"[{job_id}] Image saved: {save_path}")

        # Step 4: Upload image to Slack directly from FastAPI
        if SLACK_TOKEN != "xoxb-your-token-here" and SLACK_CHANNEL_ID != "C-your-channel-id-here":
            upload_to_slack(save_path, job_id, prompt, SLACK_TOKEN, SLACK_CHANNEL_ID)
        else:
            print(f"[{job_id}] Slack credentials not configured — skipping upload")

        # Step 5: Send result back to n8n via callback
        if callback_url:
            send_callback(job_id, save_path, callback_url, prompt, success=True)
        else:
            print(f"[{job_id}] No callback URL — image saved locally only")

    except Exception as e:
        print(f"[{job_id}] FAILED: {type(e).__name__}: {e}")
        if callback_url:
            send_callback(
                job_id, None, callback_url, prompt,
                success=False, error=f"{type(e).__name__}: {e}"
            )


# ── Routes ───────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "comfy_url": COMFY_URL}


@app.get("/comfy-status")
def comfy_status():
    try:
        response = requests.get(f"{COMFY_URL}/system_stats", timeout=5)
        return {"status": "ok", "comfy_response": response.json()}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ComfyUI unreachable: {str(e)}"
        )


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    import uuid
    job_id = str(uuid.uuid4())[:8]

    print(f"\nNew request — job_id: {job_id}")
    print(f"Prompt: {request.prompt}")
    print(f"Callback: {request.callback_url}")

    background_tasks.add_task(
        run_generation,
        job_id=job_id,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        seed=request.seed,
        callback_url=request.callback_url
    )

    return GenerateResponse(
        status="queued",
        job_id=job_id,
        message=f"Generation started. Job ID: {job_id}"
    )


@app.get("/image/{job_id}")
def get_image(job_id: str):
    image_path = OUTPUT_DIR / f"{job_id}.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/png")


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)