"""자막 그림 묶음(ports.StripImages): 자막 그림을 번호와 빨간 경계선을 넣어 세로로 이어 붙인다(AI에 한 장으로 보낸다)."""
import hashlib

from PIL import Image, ImageDraw, ImageFont

GUTTER = 72
DIVIDER = 4
FONTS = ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(size=30):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


class PillowStripImages:
    def fingerprint(self, paths):
        h = hashlib.sha1()
        for p in paths:
            with open(p, "rb") as f:
                h.update(f.read())
        return h.hexdigest()[:16]

    def build(self, crop_paths, out_path):
        ims = [Image.open(p).convert("RGB") for p in crop_paths]
        w = max(i.width for i in ims) + GUTTER
        h = sum(i.height for i in ims) + DIVIDER * (len(ims) + 1)
        strip = Image.new("RGB", (w, h), (255, 0, 0))
        draw = ImageDraw.Draw(strip)
        font = _font()
        y = DIVIDER
        for k, im in enumerate(ims, 1):
            draw.rectangle([0, y, GUTTER - 1, y + im.height - 1], fill=(255, 255, 255))
            draw.text((8, y + im.height // 2 - 17), str(k), fill=(0, 0, 0), font=font)
            strip.paste(im, (GUTTER, y))
            y += im.height + DIVIDER
        strip.save(out_path, quality=92)
        return out_path
