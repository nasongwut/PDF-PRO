from pdfpro.core.thai import has_thai, normalize_thai


def test_normalize_private_use_marks():
    assert normalize_thai("สวน บันทึกขอความ") == "ส่วน บันทึกข้อความ"


def test_normalize_sara_am():
    assert normalize_thai("สํานักงาน จํานวน") == "สำนักงาน จำนวน"


def test_has_thai():
    assert has_thai("abc ก")
    assert not has_thai("abc 123")
