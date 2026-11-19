"""Prepare the provided transparent mascot, preserving the original source."""
from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parents[1]
with Image.open(root / 'ImagesForCoding/cat.png') as image:
    image.thumbnail((420, 526))
    image.save(root / 'static/images/cat.webp', 'WEBP', quality=88, method=6)
