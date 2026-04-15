import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptVariation:
    """
    Represents one prompt variation with all its generation parameters.
    Using a dataclass gives you a clean, typed object instead of a dict.
    """
    positive: str
    negative: str
    seed: int
    variation_id: int
    label: str


# ── Style modifiers ──────────────────────────────────────
LIGHTING_STYLES = [
    "dramatic side lighting",
    "soft golden hour lighting",
    "harsh midday sun",
    "blue hour twilight",
    "neon city lights",
]

ARTISTIC_STYLES = [
    "photorealistic, 8k",
    "oil painting style",
    "cinematic film still",
    "concept art, detailed",
    "watercolour illustration",
]

MOOD_MODIFIERS = [
    "moody and atmospheric",
    "vibrant and colourful",
    "desaturated, gritty",
    "ethereal and dreamy",
    "stark and minimalist",
]

NEGATIVE_BASE = (
    "blurry, bad anatomy, watermark, text, deformed, "
    "ugly, low quality, jpeg artifacts, cropped"
)


# ── Variation strategies ─────────────────────────────────
def vary_by_style(base_prompt: str, n: int) -> list[PromptVariation]:
    """
    Strategy 1: Keep the subject fixed, cycle through style combinations.
    Each variation gets a different lighting + artistic style + mood.
    """
    variations = []
    
    for i in range(n):
        lighting = LIGHTING_STYLES[i % len(LIGHTING_STYLES)]
        style = ARTISTIC_STYLES[i % len(ARTISTIC_STYLES)]
        mood = MOOD_MODIFIERS[i % len(MOOD_MODIFIERS)]
        
        positive = f"{base_prompt}, {lighting}, {style}, {mood}"
        
        variations.append(PromptVariation(
            positive=positive,
            negative=NEGATIVE_BASE,
            seed=random.randint(0, 2**32),
            variation_id=i,
            label=f"style_{i}_{style.split(',')[0].replace(' ', '_')}"
        ))
    
    return variations


def vary_by_seed(base_prompt: str, n: int) -> list[PromptVariation]:
    """
    Strategy 2: Keep the prompt identical, change only the seed.
    Shows how much variation comes from randomness alone.
    """
    variations = []
    
    for i in range(n):
        variations.append(PromptVariation(
            positive=base_prompt,
            negative=NEGATIVE_BASE,
            seed=random.randint(0, 2**32),
            variation_id=i,
            label=f"seed_variation_{i}"
        ))
    
    return variations


def vary_by_subject(base_prompt: str, subjects: list[str]) -> list[PromptVariation]:
    """
    Strategy 3: Swap the subject, keep the style.
    Useful for generating a consistent style across different subjects.
    """
    variations = []
    style = "cinematic lighting, photorealistic, 8k, detailed"
    
    for i, subject in enumerate(subjects):
        positive = f"{subject}, {style}"
        
        variations.append(PromptVariation(
            positive=positive,
            negative=NEGATIVE_BASE,
            seed=random.randint(0, 2**32),
            variation_id=i,
            label=f"subject_{subject.split()[0].replace(' ', '_')}"
        ))
    
    return variations


# ── Main variation generator ─────────────────────────────
def generate_variations(
    base_prompt: str,
    n: int = 5,
    strategy: str = "style"
) -> list[PromptVariation]:
    """
    Entry point. Returns N PromptVariation objects using the chosen strategy.
    
    strategies:
        "style"  → different style combinations
        "seed"   → same prompt, different seeds
        "subject" → not available via this function, use vary_by_subject directly
    """
    if strategy == "style":
        return vary_by_style(base_prompt, n)
    elif strategy == "seed":
        return vary_by_seed(base_prompt, n)
    else:
        raise ValueError(f"Unknown strategy: {strategy}. Use 'style' or 'seed'.")


# ── Preview variations without generating ────────────────
def preview_variations(variations: list[PromptVariation]) -> None:
    """Print all variations so you can review before generating."""
    print(f"\n{len(variations)} variations:\n")
    for v in variations:
        print(f"  [{v.variation_id}] {v.label}")
        print(f"      Prompt: {v.positive[:80]}...")
        print(f"      Seed:   {v.seed}\n")


if __name__ == "__main__":
    # Test the variation engine standalone
    variations = generate_variations(
        base_prompt="a lone wolf standing on a mountain peak",
        n=5,
        strategy="style"
    )
    preview_variations(variations)