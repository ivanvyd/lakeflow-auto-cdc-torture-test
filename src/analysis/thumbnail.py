"""Build the branded hero and publication thumbnails from source artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.analysis.branding import add_databricks_lockup, brand_image_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = PROJECT_ROOT / "article" / "media"
SOURCE_DIR = MEDIA_DIR / "source"
HERO_SOURCE = SOURCE_DIR / "lakeflow-auto-cdc-torture-test-hero.png"
HERO_OUTPUT = MEDIA_DIR / "lakeflow-auto-cdc-torture-test-hero.png"
THUMBNAIL_OUTPUT = MEDIA_DIR / "lakeflow-auto-cdc-torture-test-thumbnail.png"
TITLED_SOURCE = SOURCE_DIR / "lakeflow-auto-cdc-torture-test-thumbnail-titled.png"
TITLED_OUTPUT = MEDIA_DIR / "lakeflow-auto-cdc-torture-test-thumbnail-titled.png"
TARGET_SIZE = (1200, 630)


def build_thumbnail() -> Path:
    """Create a social-card crop without changing the hero's visual content."""
    with Image.open(HERO_SOURCE) as image:
        source = add_databricks_lockup(image)
        source_width, source_height = source.size
        target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]
        source_ratio = source_width / source_height

        if source_ratio < target_ratio:
            crop_height = round(source_width / target_ratio)
            top = (source_height - crop_height) // 2
            crop_box = (0, top, source_width, top + crop_height)
        else:
            crop_width = round(source_height * target_ratio)
            left = (source_width - crop_width) // 2
            crop_box = (left, 0, left + crop_width, source_height)

        thumbnail = source.crop(crop_box).resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        thumbnail.save(THUMBNAIL_OUTPUT, format="PNG", optimize=True)

    return THUMBNAIL_OUTPUT


def build_publication_media() -> tuple[Path, Path, Path]:
    """Build every article-facing illustration from its unbranded source."""
    hero = brand_image_file(HERO_SOURCE, HERO_OUTPUT)
    thumbnail = build_thumbnail()
    titled = brand_image_file(TITLED_SOURCE, TITLED_OUTPUT)
    return hero, thumbnail, titled


def main() -> None:
    print("wrote " + ", ".join(str(path) for path in build_publication_media()))


if __name__ == "__main__":
    main()
