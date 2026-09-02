"""Shared brand treatment for publication images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOCKUP_PATH = PROJECT_ROOT / "article" / "media" / "databricks-lockup-full-color.png"


def add_databricks_lockup(
    image: Image.Image,
    *,
    width_fraction: float = 0.105,
    margin_fraction: float = 0.03,
) -> Image.Image:
    """Place the official full-color lockup at the upper right.

    The logo artwork is composited without recoloring or reconfiguration. The
    outer margin provides clear space on the warm publication canvas.
    """
    canvas = image.convert("RGBA")
    target_width = round(canvas.width * width_fraction)
    margin = round(canvas.width * margin_fraction)

    with Image.open(LOCKUP_PATH) as source:
        lockup = source.convert("RGBA")
        target_height = round(lockup.height * target_width / lockup.width)
        lockup = lockup.resize((target_width, target_height), Image.Resampling.LANCZOS)

    position = (canvas.width - margin - target_width, margin)
    canvas.alpha_composite(lockup, position)
    return canvas.convert("RGB")


def brand_image_file(source: Path, output: Path) -> Path:
    """Create a branded publication image from an immutable source asset."""
    with Image.open(source) as image:
        branded = add_databricks_lockup(image)
        branded.save(output, format="PNG", optimize=True)
    return output
