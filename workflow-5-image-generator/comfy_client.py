import json
import requests
import time
import sys
from pathlib import Path

# ── Config ──────────────────────────────────────────────
COMFY_URL = "http://127.0.0.1:8000"
WORKFLOW_PATH = "pipeline_api.json"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Update these IDs from your pipeline_api.json ────────
POSITIVE_PROMPT_NODE = "14"
NEGATIVE_PROMPT_NODE = "15"
KSAMPLER_1_NODE = "13"    # txt2img sampler
KSAMPLER_2_NODE = "21"    # img2img sampler
LATENT_NODE = "18"


# ── Load workflow ────────────────────────────────────────
def load_workflow(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


# ── Inject parameters ────────────────────────────────────
def configure_workflow(
    workflow: dict,
    positive_prompt: str,
    negative_prompt: str = "blurry, bad anatomy, watermark",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.0,
    denoise_img2img: float = 0.5,
    seed: int = -1
) -> dict:
    """
    Inject all configurable parameters into the workflow.
    Each parameter maps to a specific node and field.
    """
    import random

    # Prompts
    workflow[POSITIVE_PROMPT_NODE]["inputs"]["text"] = positive_prompt
    workflow[NEGATIVE_PROMPT_NODE]["inputs"]["text"] = negative_prompt

    # Image dimensions
    workflow[LATENT_NODE]["inputs"]["width"] = width
    workflow[LATENT_NODE]["inputs"]["height"] = height

    # Sampler 1 (txt2img)
    workflow[KSAMPLER_1_NODE]["inputs"]["steps"] = steps
    workflow[KSAMPLER_1_NODE]["inputs"]["cfg"] = cfg
    workflow[KSAMPLER_1_NODE]["inputs"]["denoise"] = 1.0
    workflow[KSAMPLER_1_NODE]["inputs"]["seed"] = (
        random.randint(0, 2**32) if seed == -1 else seed
    )

    # Sampler 2 (img2img) — same seed for consistency
    workflow[KSAMPLER_2_NODE]["inputs"]["steps"] = steps
    workflow[KSAMPLER_2_NODE]["inputs"]["cfg"] = cfg
    workflow[KSAMPLER_2_NODE]["inputs"]["denoise"] = denoise_img2img
    workflow[KSAMPLER_2_NODE]["inputs"]["seed"] = (
        random.randint(0, 2**32) if seed == -1 else seed + 1
    )

    return workflow


# ── Submit, poll, download (same as yesterday) ───────────
def submit_prompt(workflow: dict) -> str:
    response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
    response.raise_for_status()
    prompt_id = response.json()["prompt_id"]
    print(f"Job submitted. prompt_id: {prompt_id}")
    return prompt_id


def wait_for_completion(prompt_id: str, poll_interval: int = 2) -> dict:
    print("Waiting for generation...")
    while True:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}")
        history = response.json()
        if prompt_id in history:
            print("Complete.")
            return history[prompt_id]
        print(f"  Still processing... retrying in {poll_interval}s")
        time.sleep(poll_interval)


def get_output_filenames(history_entry: dict) -> list:
    filenames = []
    for node_id, node_output in history_entry.get("outputs", {}).items():
        if "images" in node_output:
            for image in node_output["images"]:
                filenames.append(image["filename"])
    return filenames


def download_image(filename: str, save_path: Path) -> None:
    response = requests.get(f"{COMFY_URL}/view", params={"filename": filename})
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)
    print(f"Saved: {save_path}")


# ── Main pipeline ────────────────────────────────────────
def generate(
    positive_prompt: str,
    negative_prompt: str = "blurry, bad anatomy, watermark",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.0,
    denoise_img2img: float = 0.5
) -> list:
    print(f"\nPrompt: '{positive_prompt}'")
    print("-" * 50)

    workflow = load_workflow(WORKFLOW_PATH)
    workflow = configure_workflow(
        workflow,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        denoise_img2img=denoise_img2img
    )

    prompt_id = submit_prompt(workflow)
    history_entry = wait_for_completion(prompt_id)
    filenames = get_output_filenames(history_entry)

    saved = []
    for filename in filenames:
        save_path = OUTPUT_DIR / filename
        download_image(filename, save_path)
        saved.append(save_path)

    print(f"\nDone. {len(saved)} image(s) saved.")
    return saved


# ── Entry point ──────────────────────────────────────────
if __name__ == "__main__":
    generate(
        positive_prompt="a cinematic portrait of an astronaut on Mars, dramatic lighting, photorealistic",
        negative_prompt="blurry, bad anatomy, watermark, text",
        width=512,
        height=512,
        steps=20,
        cfg=7.0,
        denoise_img2img=0.5
    )