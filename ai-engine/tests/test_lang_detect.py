from app.services.lang_detect import detect_locale, response_locale_hint


class TestDetectLocale:
    def test_english(self) -> None:
        assert detect_locale("Show me red dresses") == "en"

    def test_arabic(self) -> None:
        assert detect_locale("هل عندكم توب صيفي؟") == "ar"

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


class TestResponseLocaleHint:
    def test_detected_language_wins_over_locale(self) -> None:
        assert response_locale_hint("en", "هل عندكم توب صيفي؟") == "Respond in Arabic."

    def test_detected_farsi_wins(self) -> None:
        assert response_locale_hint("en", "پیراهن قرمز میخواهم") == "Respond in Farsi."

    def test_detected_english_wins(self) -> None:
        assert response_locale_hint("ar", "Show me red dresses") == "Respond in English."

    def test_inconclusive_falls_back_to_locale(self) -> None:
        assert response_locale_hint("ar", "🛍️") == "Respond in Arabic."
        assert response_locale_hint("en", "🛍️") == "Respond in English."

    def test_unknown_locale_mirrors_user_language(self) -> None:
        assert response_locale_hint("fr", "🛍️") == "Respond in the same language as the user's most recent message."

    def test_no_text_falls_back_to_locale(self) -> None:
        assert response_locale_hint("ar", None) == "Respond in Arabic."
