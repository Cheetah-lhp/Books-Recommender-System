import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from book_enrichment import (  # noqa: E402
    clean_isbn,
    is_valid_isbn10,
    is_valid_isbn13,
    isbn10_to_13,
    isbn13_key,
    isbn13_to_10,
    normalize_language_code,
    normalize_languages,
)


def test_isbn_conversion_roundtrip():
    assert isbn10_to_13('0312853122') == '9780312853129'
    assert isbn13_to_10('9780312853129') == '0312853122'
    assert isbn13_to_10('978-0-312-85312-9') == '0312853122'


def test_isbn10_with_x_check_digit():
    assert is_valid_isbn10('080442957X')
    assert isbn10_to_13('080442957X') == '9780804429573'
    assert isbn13_to_10('9780804429573') == '080442957X'


def test_isbn13_979_has_no_isbn10():
    assert is_valid_isbn13('9791032305690')
    assert isbn13_to_10('9791032305690') is None


def test_invalid_isbn_rejected():
    assert isbn10_to_13('0312853123') is None
    assert isbn13_to_10('9780312853128') is None
    assert isbn10_to_13(None) is None
    assert clean_isbn(None) == ''


def test_isbn13_key_prefers_valid_isbn13_then_converts():
    assert isbn13_key('', '9780312853129') == '9780312853129'
    assert isbn13_key('0312853122', '') == '9780312853129'
    assert isbn13_key('0312853122', '9780312853128') == '9780312853129'  # isbn13 sai checksum -> dùng isbn
    assert isbn13_key('', '') is None
    assert isbn13_key(None, None) is None


def test_language_normalization():
    assert normalize_language_code('eng') == 'en'
    assert normalize_language_code('ara') == 'ara'
    assert normalize_language_code('') is None
    assert normalize_language_code('--') is None
    assert normalize_language_code('und') is None
    assert normalize_languages(['eng', 'fre']) == 'en,fr'
    assert normalize_languages(['eng', 'en-US', 'ger']) == 'en,de'
    assert normalize_languages([]) is None
    assert normalize_languages(['und']) is None
