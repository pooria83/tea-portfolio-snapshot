from app.core.lang_detect import detect_locale


class TestDetectLocale:
    def test_english(self) -> None:
        assert detect_locale("Show me red dresses") == "en"

    def test_arabic(self) -> None:
        assert detect_locale("هل عندكم توب صيفي؟") == "ar"

    def test_arabic_without_hamza(self) -> None:
        assert detect_locale("عندكم فستان احمر؟") == "ar"

    def test_farsi(self) -> None:
        assert detect_locale("پیراهن قرمز میخواهم") == "fa"

    def test_farsi_preferred_over_generic_arabic_script(self) -> None:
        assert detect_locale("این لباس قرمز است") == "fa"

    def test_mixed_script_uses_non_latin(self) -> None:
        assert detect_locale("فستان أحمر please") == "ar"

    def test_empty(self) -> None:
        assert detect_locale("") is None

    def test_whitespace_only(self) -> None:
        assert detect_locale("   ") is None

    def test_numbers_only(self) -> None:
        assert detect_locale("123 456") is None

    def test_emoji_only(self) -> None:
        assert detect_locale("🛍️") is None
