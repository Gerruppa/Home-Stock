"""Draw the app icons: .venv/Scripts/python.exe scripts/make_icons.py

Needs Pillow (the ``build`` extra). The outputs are committed, so run it only when the design changes.
The icon is a white house on a rounded green square, with a pantry shelf of three jars inside.
"""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "src" / "home_stock" / "ui" / "assets"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
# Drawn four times larger, then scaled down for smooth edges
SCALE = 4
SIZE = 256 * SCALE
GREEN = (46, 125, 50, 255)
WHITE = (255, 255, 255, 255)
JARS = [(239, 108, 0, 255), (249, 168, 37, 255), (67, 160, 71, 255)]


def px(value: float) -> int:
    """A coordinate of the 256 px design in the oversized canvas."""
    return round(value * SCALE)


def draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), px(46), fill=GREEN)
    # The house: a roof over a body, white
    draw.polygon([(px(128), px(34)), (px(226), px(120)), (px(30), px(120))], fill=WHITE)
    draw.rectangle((px(56), px(112), px(200), px(220)), fill=WHITE)
    # The pantry: a shelf with three jars standing on it
    draw.rectangle((px(72), px(184), px(184), px(194)), fill=GREEN)
    for index, colour in enumerate(JARS):
        left = px(78 + index * 36)
        draw.rounded_rectangle((left, px(132), left + px(28), px(184)), px(6), fill=colour)
        draw.rectangle((left + px(4), px(126), left + px(24), px(134)), fill=GREEN)
    return image.resize((256, 256), Image.Resampling.LANCZOS)


def main() -> None:
    icon = draw_icon()
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon.save(ASSETS / "home-stock.png")
    icon.save(ASSETS / "home-stock.ico", sizes=ICO_SIZES)


if __name__ == "__main__":
    main()
