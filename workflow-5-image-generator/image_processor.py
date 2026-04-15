from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from pathlib import Path
import json
from prompt_variations import PromptVariation

PROCESSED_DIR = Path("output/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

METADATA_DIR = Path("output/metadata")
METADATA_DIR.mkdir(parents=True, exist_ok=True)


def enhance_image(img: Image.Image) -> Image.Image:
    """
    Apply post-processing enhancements.
    Each step is a separate operation — easy to add, remove, or reorder.
    """
    # Slight contrast boost
    img = ImageEnhance.Contrast(img).enhance(1.1)
    
    # Slight sharpness boost
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    
    # Slight saturation boost
    img = ImageEnhance.Color(img).enhance(1.05)
    
    return img


def add_metadata_overlay(
    img: Image.Image,
    variation: PromptVariation
) -> Image.Image:
    """
    Add a small metadata label to the bottom of the image.
    Useful for reviewing batches — you can see which variation is which.
    """
    draw = ImageDraw.Draw(img)
    
    label = f"[{variation.variation_id}] {variation.label} | seed: {variation.seed}"
    
    # Draw text at bottom left — white text with black shadow
    x, y = 10, img.height - 25
    draw.text((x+1, y+1), label, fill=(0, 0, 0))       # shadow
    draw.text((x, y), label, fill=(255, 255, 255))      # text
    
    return img


def save_metadata(
    variation: PromptVariation,
    input_path: Path,
    output_path: Path
) -> None:
    """
    Save generation metadata as JSON alongside the image.
    This is how you keep a record of what generated what.
    """
    metadata = {
        "variation_id": variation.variation_id,
        "label": variation.label,
        "positive_prompt": variation.positive,
        "negative_prompt": variation.negative,
        "seed": variation.seed,
        "input_file": str(input_path),
        "output_file": str(output_path)
    }
    
    meta_path = METADATA_DIR / f"{variation.label}.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"      Metadata saved: {meta_path}")


def process_image(input_path: Path, variation: PromptVariation) -> Path:
    """
    Full processing pipeline for one image:
    1. Load
    2. Enhance
    3. Add metadata overlay
    4. Save processed version
    5. Save metadata JSON
    """
    print(f"\n  Processing: {input_path.name}")
    
    # Load
    img = Image.open(input_path).convert("RGB")
    original_size = img.size
    
    # Enhance
    img = enhance_image(img)
    
    # Add overlay
    img = add_metadata_overlay(img, variation)
    
    # Save
    output_path = PROCESSED_DIR / f"processed_{input_path.name}"
    img.save(output_path, quality=95)
    print(f"      Processed image saved: {output_path}")
    print(f"      Original size: {original_size}")
    
    # Save metadata
    save_metadata(variation, input_path, output_path)
    
    return output_path