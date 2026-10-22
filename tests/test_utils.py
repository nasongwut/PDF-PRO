from pdfpro.utils import hex2rgb, int2hex, norm_name


def test_colors_roundtrip():
    assert hex2rgb("#ff0000") == (1.0, 0.0, 0.0)
    assert int2hex(0x112233) == "#112233"


def test_norm_name():
    assert norm_name("TH Sarabun-New Bold") == "thsarabunnewbold"
