#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绘制 APP 图标并生成 icon.icns。

设计：朱砂红圆角方块（macOS squircle）+ 金色描边 + 楷体「吉」字 + 四角星光。
运行：python3 build_icon.py
产出：icon_1024.png（运行时也用它换 Dock 图标）和 icon.icns
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024
HERE = os.path.dirname(os.path.abspath(__file__))

FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/STKaiti.ttc", 0),  # 楷体，最有算命味
    ("/System/Library/Fonts/STKaiti.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 2),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
]

def load_font(size):
    for path, idx in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size, index=idx)
                print("font:", path)
                return f
            except Exception:
                continue
    print("font: builtin default")
    return ImageFont.load_default()

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)

def sparkle(draw, cx, cy, r, color):
    k = 0.22
    pts = [
        (cx, cy - r), (cx + r * k, cy - r * k), (cx + r, cy), (cx + r * k, cy + r * k),
        (cx, cy + r), (cx - r * k, cy + r * k), (cx - r, cy), (cx - r * k, cy - r * k),
    ]
    draw.polygon(pts, fill=color)

def main():
    radius = 230  # ≈ macOS 圆角比例

    # 竖向渐变底：朱砂红 → 深绛红
    top = (222, 82, 65)
    bottom = (140, 34, 24)
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=lerp(top, bottom, y / (S - 1)))

    # squircle 蒙版
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40],
                                           radius=radius, fill=255)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    # 顶部高光（柔和）
    hi = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hi).ellipse([150, -300, S - 150, 330], fill=(255, 238, 210, 55))
    hi = hi.filter(ImageFilter.GaussianBlur(70))
    merged = Image.alpha_composite(img, hi)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(merged, (0, 0), mask)

    d = ImageDraw.Draw(img)

    # 内圈金环
    d.rounded_rectangle([74, 74, S - 74, S - 74], radius=radius - 34,
                        outline=(233, 199, 105, 255), width=10)

    # 「吉」字：深色投影 + 金色字面
    font = load_font(600)
    text = "吉"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (S - tw) / 2 - bbox[0]
    y = (S - th) / 2 - bbox[1] + 26
    d.text((x + 9, y + 12), text, font=font, fill=(96, 20, 12, 170))
    d.text((x, y), text, font=font, fill=(246, 214, 112, 255))

    # 星光点缀
    gold = (255, 231, 156, 255)
    sparkle(d, 205, 250, 44, gold)
    sparkle(d, 822, 292, 32, gold)
    sparkle(d, 776, 782, 40, gold)
    sparkle(d, 258, 768, 24, gold)

    out_png = os.path.join(HERE, "icon_1024.png")
    img.save(out_png)
    print("saved:", out_png)

    # iconset → icns
    iconset = os.path.join(HERE, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    entries = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for name, size in entries.items():
        im = img.resize((size, size), Image.LANCZOS)
        im.save(os.path.join(iconset, name))
    icns = os.path.join(HERE, "icon.icns")
    subprocess.check_call(["iconutil", "-c", "icns", iconset, "-o", icns])
    print("saved:", icns)

if __name__ == "__main__":
    main()
