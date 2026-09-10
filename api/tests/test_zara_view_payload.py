import json
from collections.abc import Mapping, Sequence

import pytest

from app.scrapers.zara.exceptions import ScraperAuthError
from app.scrapers.zara.parser import (
    extract_analytics_section,
    extract_product_data,
    extract_view_payload,
    view_payload_to_json_ld,
)

SAMPLE_VIEW_PAYLOAD: dict = {
    "noIndex": False,
    "product": {
        "id": 545478009,
        "kind": "Wear",
        "name": "ZW COLLECTION PLEATED HALTER TOP",
        "section": 1,
        "sectionName": "WOMAN",
        "familyId": 76,
        "familyName": "CAMISA",
        "subfamilyId": 337,
        "subfamilyName": "W.CAMISA",
        "detail": {
            "reference": "02678002-I2026",
            "displayReference": "2678/002",
            "colors": [
                {
                    "id": 101,
                    "hexCode": "#E6E6DF",
                    "productId": 562452056,
                    "name": "Pearl / Beige",
                    "reference": "C02678002101071-I2026",
                    "price": 1990,
                    "pricing": {"price": {"value": 1990, "currency": {"code": "KWD", "exponent": -2}}},
                    "description": "Model height: 179 cm\n\nHalter neck top with an open back.",
                    "rawDescription": "Model height: 179 cm<br/><br/>Halter neck top with an open back.",
                    "mainImgs": [
                        {
                            "datatype": "xmedia",
                            "kind": "full",
                            "url": "https://static.zara.net/assets/public/201f/a36e/02678002101-070-p.jpg?ts=1&w={width}",
                            "extraInfo": {"deliveryUrl": "https://static.zara.net/assets/public/201f/a36e/02678002101-070-p.jpg?ts=1"},
                        },
                        {
                            "datatype": "xmedia",
                            "kind": "other",
                            "url": "https://static.zara.net/assets/public/31ae/1e1f/02678002101-1-a1.jpg?ts=2&w={width}",
                        },
                    ],
                    "sizes": [
                        {"name": "XS", "sku": 545478010, "price": 1990, "availability": "in_stock"},
                        {"name": "S", "sku": 545478011, "price": 1990, "availability": "in_stock"},
                    ],
                }
            ],
            "detailedComposition": {
                "parts": [
                    {
                        "description": "OUTER SHELL",
                        "components": [{"material": "polyester", "percentage": "100%"}],
                    },
                    {
                        "description": "LINING",
                        "components": [{"material": "polyester", "percentage": "100%"}],
                    },
                ]
            },
        },
    },
    "analyticsData": {
        "pageType": "PRODUCT_DETAILS",
        "section": "WOMAN",
        "family": "CAMISA",
        "subfamily": "W.CAMISA",
        "colorCode": "101",
    },
}


def _html_with_view_payload(payload: dict) -> str:
    return "<!DOCTYPE html><html><body><script>window.zara.viewPayload = " + json.dumps(payload) + ";</script></body></html>"


class TestExtractViewPayload:
    def test_extracts_nested_json(self) -> None:
        html = _html_with_view_payload(SAMPLE_VIEW_PAYLOAD)
        payload = extract_view_payload(html)
        assert payload is not None
        assert payload["product"]["id"] == 545478009

    def test_missing_marker(self) -> None:
        assert extract_view_payload("<html>no payload here</html>") is None

    def test_invalid_json(self) -> None:
        html = "<script>window.zara.viewPayload = {broken;</script>"
        assert extract_view_payload(html) is None

    def test_string_with_braces_inside(self) -> None:
        html = "<script>window.zara.viewPayload = " + json.dumps({"product": {"name": "a } b { c"}}) + ";</script>"
        payload = extract_view_payload(html)
        assert payload is not None
        assert payload["product"]["name"] == "a } b { c"


class TestViewPayloadToJsonLd:
    def test_full_mapping(self) -> None:
        adapted = view_payload_to_json_ld(SAMPLE_VIEW_PAYLOAD)
        assert adapted is not None
        assert adapted["productGroupID"] == "545478009"
        assert adapted["name"] == "ZW COLLECTION PLEATED HALTER TOP"
        assert adapted["description"].startswith("Model height: 179 cm")
        assert adapted["material"] == "polyester"
        assert adapted["variesBy"] == []

    def test_variants_cover_sizes(self) -> None:
        adapted = view_payload_to_json_ld(SAMPLE_VIEW_PAYLOAD)
        assert adapted is not None
        variants = adapted["hasVariant"]
        assert len(variants) == 2
        first = variants[0]
        assert first["size"] == "XS"
        assert first["color"] == {"id": "101", "name": "Pearl / Beige"}
        assert first["sku"].startswith("562452056-")
        assert first["offers"]["price"] == 19.9
        assert first["offers"]["url"].endswith("?v1=562452056")

    def test_images_width_placeholder_replaced(self) -> None:
        adapted = view_payload_to_json_ld(SAMPLE_VIEW_PAYLOAD)
        assert adapted is not None
        images = adapted["image"]
        assert len(images) == 2
        assert all("{width}" not in img for img in images)
        assert images[0].endswith("?ts=1&w=560")

    def test_composition_properties(self) -> None:
        adapted = view_payload_to_json_ld(SAMPLE_VIEW_PAYLOAD)
        assert adapted is not None
        props = adapted["additionalProperty"]
        assert props == [
            {"name": "OUTER SHELL", "value": "100% polyester"},
            {"name": "LINING", "value": "100% polyester"},
        ]

    def test_missing_colors_returns_none(self) -> None:
        assert view_payload_to_json_ld({"product": {"id": 1, "detail": {"colors": []}}}) is None
        assert view_payload_to_json_ld({"product": None}) is None

    def test_price_fallback_from_minor_units(self) -> None:
        payload = json.loads(json.dumps(SAMPLE_VIEW_PAYLOAD))
        del payload["product"]["detail"]["colors"][0]["pricing"]
        adapted = view_payload_to_json_ld(payload)
        assert adapted is not None
        assert adapted["offers"]["price"] == 19.9


class TestExtractProductData:
    def test_prefers_view_payload(self) -> None:
        html = _html_with_view_payload(SAMPLE_VIEW_PAYLOAD)
        data = extract_product_data(html)
        assert data is not None
        assert data["productGroupID"] == "545478009"
        assert data["name"] == "ZW COLLECTION PLEATED HALTER TOP"

    def test_falls_back_to_json_ld(self) -> None:
        html = '<script type="application/ld+json">' + json.dumps({"@type": "Product", "productGroupID": "12345", "name": "Legacy"}) + "</script>"
        data = extract_product_data(html)
        assert data is not None
        assert data["productGroupID"] == "12345"

    def test_no_data_returns_none(self) -> None:
        assert extract_product_data("<html>nothing</html>") is None


class TestExtractAnalyticsSection:
    def test_from_view_payload(self) -> None:
        html = _html_with_view_payload(SAMPLE_VIEW_PAYLOAD)
        analytics = extract_analytics_section(html)
        assert analytics == {"section": "WOMAN", "family": "CAMISA", "subfamily": "W.CAMISA"}

    def test_from_product_level_fields(self) -> None:
        payload = json.loads(json.dumps(SAMPLE_VIEW_PAYLOAD))
        payload.pop("analyticsData")
        html = _html_with_view_payload(payload)
        analytics = extract_analytics_section(html)
        assert analytics == {"section": "WOMAN", "family": "CAMISA", "subfamily": "W.CAMISA"}

    def test_empty_html(self) -> None:
        assert extract_analytics_section("<html></html>") == {"section": "", "family": "", "subfamily": ""}


class TestCookieMintMissingDependency:
    def test_mint_raises_when_camoufox_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        import app.scrapers.zara.cookie_mint as cookie_mint_mod

        real_import = builtins.__import__

        def fake_import(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] | None = (),
            level: int = 0,
        ) -> object:
            if name.startswith("camoufox"):
                raise ImportError("no camoufox installed")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ScraperAuthError, match="camoufox"):
            import asyncio

            asyncio.run(cookie_mint_mod.mint_cookies())
