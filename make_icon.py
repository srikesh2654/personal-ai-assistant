"""Generate SERENE's app icon: a violet->cyan gradient 'S' on a dark rounded
tile, saved as a multi-resolution .ico (plus a .png preview)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 256
VIOLET = (124, 58, 237)    # #7c3aed
CYAN   = (34, 211, 238)    # #22d3ee


def diagonal_gradient():
    g = Image.new("RGB", (SIZE, SIZE))
    px = g.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * SIZE - 2)          # 0 (top-left) -> 1 (bottom-right)
            px[x, y] = (
                int(VIOLET[0] + (CYAN[0] - VIOLET[0]) * t),
                int(VIOLET[1] + (CYAN[1] - VIOLET[1]) * t),
                int(VIOLET[2] + (CYAN[2] - VIOLET[2]) * t),
            )
    return g


def load_bold_font(size):
    for path in (r"C:\Windows\Fonts\ariblk.ttf",      # Arial Black (chunky)
                 r"C:\Windows\Fonts\segoeuib.ttf",    # Segoe UI Bold
                 r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def s_mask():
    font = load_bold_font(210)
    mask = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(mask)
    box = d.textbbox((0, 0), "S", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x = (SIZE - w) // 2 - box[0]
    y = (SIZE - h) // 2 - box[1]
    d.text((x, y), "S", fill=255, font=font)
    return mask


def build():
    grad = diagonal_gradient()
    mask = s_mask()

    # dark rounded tile background
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(icon).rounded_rectangle(
        [6, 6, SIZE - 6, SIZE - 6], radius=56, fill=(13, 18, 28, 255))

    # soft glow of the gradient S
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow.paste(grad, (0, 0), mask)
    icon.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))

    # crisp gradient S on top
    crisp = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    crisp.paste(grad, (0, 0), mask)
    icon.alpha_composite(crisp)

    icon.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48),
                                 (64, 64), (128, 128), (256, 256)])
    icon.save("icon_preview.png")
    print("wrote icon.ico and icon_preview.png")


if __name__ == "__main__":
    build()
