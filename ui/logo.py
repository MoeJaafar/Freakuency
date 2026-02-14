"""
Logo rendering — generates the FREAKUENCY neon logo and app icon using Pillow.
No external SVG dependencies needed; recreates the look from the SVG source.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# Colors from the SVG
_TRANSPARENT = (0, 0, 0, 0)
_GLOW_COLOR = (191, 90, 242)          # #bf5af2
_TEXT_COLOR = (232, 192, 255, 255)     # #e8c0ff (bright core)
_TAG_COLOR = (191, 90, 242, 100)       # #bf5af2 at ~40% opacity


def _load_mono_bold(size):
    """Try to load a bold monospace font, fall back gracefully."""
    for name in ("consolab.ttf", "consola.ttf", "courbd.ttf", "cour.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _load_mono(size):
    """Try to load a regular monospace font."""
    for name in ("consola.ttf", "cour.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_logo_banner(width=500, height=110):
    """
    Render the FREAKUENCY neon logo banner as a PIL RGBA Image.
    Transparent background with purple glow text and tagline.
    """
    img = Image.new("RGBA", (width, height), _TRANSPARENT)

    font = _load_mono_bold(int(height * 0.52))
    tag_font = _load_mono(int(height * 0.11))

    text_y = int(height * 0.38)
    tag_y = int(height * 0.78)

    # Layer 1: soft background glow
    glow_bg = Image.new("RGBA", (width, height), _TRANSPARENT)
    d = ImageDraw.Draw(glow_bg)
    d.text((width // 2, text_y), "FREAKUENCY", font=font,
           fill=(*_GLOW_COLOR, 70), anchor="mm")
    glow_bg = glow_bg.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, glow_bg)

    # Layer 2: sharper neon glow
    glow = Image.new("RGBA", (width, height), _TRANSPARENT)
    d = ImageDraw.Draw(glow)
    d.text((width // 2, text_y), "FREAKUENCY", font=font,
           fill=(*_GLOW_COLOR, 180), anchor="mm")
    glow = glow.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, glow)

    # Layer 3: bright core text
    core = Image.new("RGBA", (width, height), _TRANSPARENT)
    d = ImageDraw.Draw(core)
    d.text((width // 2, text_y), "FREAKUENCY", font=font,
           fill=_TEXT_COLOR, anchor="mm")
    img = Image.alpha_composite(img, core)

    # Tagline
    draw = ImageDraw.Draw(img)
    draw.text((width // 2, tag_y), "$ route --per-app", font=tag_font,
              fill=_TAG_COLOR, anchor="mm")

    return img


def render_app_icon(size=64):
    """
    Render a small app icon: bold 'F' with purple glow on transparent background.
    Suitable for the window title bar icon.
    """
    img = Image.new("RGBA", (size, size), _TRANSPARENT)

    font = _load_mono_bold(int(size * 1.0))

    cx, cy = size // 2, size // 2

    # Glow
    glow = Image.new("RGBA", (size, size), _TRANSPARENT)
    d = ImageDraw.Draw(glow)
    d.text((cx, cy), "F", font=font, fill=(*_GLOW_COLOR, 180), anchor="mm")
    blur_radius = max(2, size // 16)
    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
    img = Image.alpha_composite(img, glow)

    # Bright text
    core = Image.new("RGBA", (size, size), _TRANSPARENT)
    d = ImageDraw.Draw(core)
    d.text((cx, cy), "F", font=font, fill=_TEXT_COLOR, anchor="mm")
    img = Image.alpha_composite(img, core)

    return img


def generate_ico(output_path):
    """
    Generate a multi-resolution .ico file for the Windows executable.
    Contains 16x16, 32x32, 48x48, and 256x256 sizes.
    """
    sizes = [16, 32, 48, 256]
    images = [render_app_icon(s) for s in sizes]
    images[-1].save(output_path, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
