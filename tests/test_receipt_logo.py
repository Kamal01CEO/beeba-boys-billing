import pytest
from PIL import Image
from app.receipt_logo import get_receipt_logo


def test_missing_file_returns_none(tmp_path):
    assert get_receipt_logo(384, str(tmp_path / "nope.png")) is None


def test_dark_logo_inverted_and_sized(tmp_path):
    # dark background (value 15) with a bright square
    img = Image.new("L", (100, 120), color=15)
    for x in range(40, 60):
        for y in range(50, 70):
            img.putpixel((x, y), 240)
    p = str(tmp_path / "logo.png")
    img.save(p)

    out = get_receipt_logo(384, p)
    assert out is not None
    assert out.mode == "1"
    assert out.size[0] == 384                 # resized to width
    # dark bg -> inverted -> paper (background) is predominantly white
    data = list(out.getdata())
    white_ratio = sum(1 for v in data if v) / len(data)
    assert white_ratio > 0.5
