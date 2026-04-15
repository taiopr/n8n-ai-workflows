import json
import copy
import time as time_module
import requests
from pathlib import Path
from prompt_variations import generate_variations, preview_variations, PromptVariation
from image_processor import process_image

# ── Config ───────────────────────────────────────────────
COMFY_URL = "http://127.0.0.1:8000"
WORKFLOW_PATH = "workflow_api.json"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Node IDs confirmed from workflow_api.json
POSITIVE_PROMPT_NODE = "6"
NEGATIVE_PROMPT_NODE = "7"
KSAMPLER_NODE = "3"


# ── Workflow helpers ─────────────────────────────────────
def load_workflow(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def configure_workflow(workflow: dict, variation: PromptVariation) -> dict:
    """
    Inject a PromptVariation into the workflow JSON.
    deepcopy prevents variations from mutating the shared base workflow.
    """
    wf = copy.deepcopy(workflow)
    wf[POSITIVE_PROMPT_NODE]["inputs"]["text"] = variation.positive
    wf[NEGATIVE_PROMPT_NODE]["inputs"]["text"] = variation.negative
    wf[KSAMPLER_NODE]["inputs"]["seed"] = variation.seed
    return wf


def submit_prompt(workflow: dict) -> str:
    response = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow}
    )
    response.raise_for_status()
    prompt_id = response.json()["prompt_id"]
    return prompt_id


def wait_for_completion(prompt_id: str, poll_interval: int = 3) -> dict:
    while True:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}")
        history = response.json()
        if prompt_id in history:
            return history[prompt_id]
        time_module.sleep(poll_interval)


def get_output_filenames(history_entry: dict) -> list:
    filenames = []
    for node_id, node_output in history_entry.get("outputs", {}).items():
        if "images" in node_output:
            for image in node_output["images"]:
                filenames.append(image["filename"])
    return filenames


def download_image(filename: str, save_path: Path) -> None:
    response = requests.get(
        f"{COMFY_URL}/view",
        params={"filename": filename}
    )
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)


# ── Generate one variation ───────────────────────────────
def generate_one(
    workflow_base: dict,
    variation: PromptVariation
) -> list[Path]:
    """
    Run the full pipeline for a single variation.
    Returns list of saved file paths.
    """
    print(f"\n  [{variation.variation_id}] Generating: {variation.label}")
    print(f"      Prompt: {variation.positive[:70]}...")

    wf = configure_workflow(workflow_base, variation)
    prompt_id = submit_prompt(wf)
    print(f"      Submitted: {prompt_id}")

    history = wait_for_completion(prompt_id)
    filenames = get_output_filenames(history)

    saved = []
    for filename in filenames:
        suffix = Path(filename).suffix
        save_path = OUTPUT_DIR / f"{variation.label}{suffix}"
        download_image(filename, save_path)
        print(f"      Saved: {save_path}")
        saved.append(save_path)

    return saved


# ── Run report ───────────────────────────────────────────
def generate_report(
    all_saved: list[Path],
    base_prompt: str,
    strategy: str,
    elapsed_seconds: float
) -> None:
    """
    Write a plain text report summarising the pipeline run.
    """
    report_path = OUTPUT_DIR / "run_report.txt"

    lines = [
        f"Pipeline Run Report",
        f"===================",
        f"Base prompt:   {base_prompt}",
        f"Strategy:      {strategy}",
        f"Images:        {len(all_saved)}",
        f"Time elapsed:  {elapsed_seconds:.1f}s",
        f"Avg per image: {elapsed_seconds / max(len(all_saved), 1):.1f}s",
        f"",
        f"Output files:",
    ]

    for path in all_saved:
        lines.append(f"  {path}")

    report = "\n".join(lines)
    report_path.write_text(report)
    print(report)
    print(f"\nReport saved to: {report_path}")


# ── Run all variations ───────────────────────────────────
def run_pipeline(
    base_prompt: str,
    n: int = 5,
    strategy: str = "style"
) -> list[Path]:
    """
    Full pipeline:
    1. Generate N prompt variations
    2. Submit each to ComfyUI in sequence
    3. Download all outputs
    4. Pass each to the processing script
    5. Generate run report with timing
    Returns all saved file paths.
    """
    print(f"\n{'='*50}")
    print(f"Pipeline starting — {n} variations")
    print(f"Base prompt: {base_prompt}")
    print(f"Strategy:    {strategy}")
    print(f"{'='*50}")

    start = time_module.time()

    # Load workflow once — reuse for all variations
    workflow_base = load_workflow(WORKFLOW_PATH)

    # Generate variation objects
    variations = generate_variations(base_prompt, n, strategy)
    preview_variations(variations)

    input("Press Enter to start generation, or Ctrl+C to cancel...")

    all_saved = []

    for variation in variations:
        saved_paths = generate_one(workflow_base, variation)

        # Pass each generated image to processing script
        for path in saved_paths:
            process_image(path, variation)

        all_saved.extend(saved_paths)

    elapsed = time_module.time() - start

    print(f"\n{'='*50}")
    print(f"Pipeline complete. {len(all_saved)} images generated.")
    print(f"{'='*50}\n")

    generate_report(all_saved, base_prompt, strategy, elapsed)

    return all_saved


# ── Entry point ──────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline(
        base_prompt="a lone wolf standing on a mountain peak at dawn",
        n=5,
        strategy="style"
    )