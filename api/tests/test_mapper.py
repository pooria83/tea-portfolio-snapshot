"""Tests for scripts/scrapers/mapper.py category resolution.

Covers the keyword rules and CATEGORY_MAP defaults that keep Zara
shoes/accessories products from being dropped as unmapped.
"""

from __future__ import annotations

import pytest

from scripts.scrapers.mapper import (
    _ACCESSORY_RULES,
    CATEGORY_MAP,
    HOME_SECTION,
    KEYWORD_OVERRIDE_RULES,
    resolve_category,
    resolve_category_from_analytics,
)


@pytest.mark.parametrize(
    ("source_category", "product_name", "expected"),
    [
        # woman/shoes keywords previously unmapped
        ("woman/shoes", "SUEDE BALLERINAS", ("Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes")),
        ("woman/shoes", "LEATHER SLINGBACK SHOES", ("Heels & Dress Shoes", "Pumps", "heels_dress_shoes")),
        ("woman/shoes", "SOFT LEATHER DERBY SHOES", ("Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes")),
        ("woman/shoes", "LIMITED EDITION LEATHER WEDGES WITH STUD DETAIL", ("Heels & Dress Shoes", "High Heels", "heels_dress_shoes")),
        ("woman/shoes", "METALLIC LEATHER SHOES", ("Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes")),
        # vowel-less Zara abbreviations
        ("man/shoes", "LTHR TRNRS", ("Athletic & Sneakers", "Trainers", "athletic_sneakers")),
        ("woman/shoes", "CMBND LTHR SNDL", ("Sandals & Slippers", "Sandals", "sandals_slippers")),
        ("man/shoes", "CMBND LTHR SNDL", ("Sandals & Slippers", "Sandals", "sandals_slippers")),
        ("woman/shoes", "TRNRS WITH VELCRO", ("Athletic & Sneakers", "Trainers", "athletic_sneakers")),
        # woman/shoes defaults when no keyword matches at all
        ("woman/shoes", "CMBND LTHR ML", ("Heels & Dress Shoes", "Pumps", "heels_dress_shoes")),
        ("man/shoes", "CMBND LTHR ML", ("Heels & Dress Shoes", "Pumps", "heels_dress_shoes")),
        # man/accessories previously unmapped
        ("man/accessories", "LIGHTWEIGHT ABSTRACT PRINT TECHNICAL CAP", ("Head Accessories", "Caps", "head_accessories")),
        ("man/accessories", "RECTANGULAR SUNGLASSES", ("Sunglasses & Eyewear", "Sunglasses", "eyewear")),
        ("man/accessories", "PACK OF 3 COORDINATING METAL NECKLACES", ("Necklaces & Pendants", "Necklaces", "necklaces_pendants")),
        ("man/accessories", "CONTRAST STONE SIGNET RING", ("Rings", "Rings", "rings")),
        ("man/accessories", "COMBINED PEARL BRACELET", ("Bracelets & Anklets", "Bracelets", "bracelets_anklets")),
        ("man/accessories", "TEXTURED BRIEFCASE", ("Bags & Handbags", "Handbags", "bags")),
        ("man/accessories", "TRAVEL SUITCASE", ("Bags & Handbags", "Handbags", "bags")),
        ("man/accessories", "GRAINED LEATHER WALLET", ("Belts & Leather Goods", "Wallets", "belts_leather_goods")),
        ("man/accessories", "FOLDING UMBRELLA", ("Specialty Accessories", "Umbrellas", "specialty_accessories")),
        # woman/accessories previously unmapped
        ("woman/accessories", "NUDE BOUQUET INTENSE PARFUM 100 ML / 3.38 oz", ("Fragrance & Perfume", "Perfumes", "fragrance")),
        ("woman/accessories", "RED ZARA TEMPTATION TOBACCO EXTRAIT DE PARFUM 50ML / 1.7 FL. OZ.", ("Fragrance & Perfume", "Perfumes", "fragrance")),
        ("woman/accessories", "PACK OF 4 BICYCLE, BREAD, SARDINE AND BUS PINS", ("Head Accessories", "Pins & Brooches", "head_accessories")),
        ("woman/accessories", "WOVEN FAN WITH TASSELS", ("Specialty Accessories", None, "specialty_accessories")),
        ("woman/accessories", "PACK OF 2 SATIN HEADBANDS", ("Head Accessories", "Hair Accessories", "head_accessories")),
        ("woman/accessories", "GOLD EAR CUFF", ("Earrings", "Earrings", "earrings")),
        # accessories default bucket when nothing matches
        ("woman/accessories", "MYSTERY GADGET", ("Specialty Accessories", None, "specialty_accessories")),
        ("man/accessories", "MYSTERY GADGET", ("Specialty Accessories", None, "specialty_accessories")),
        # regression: pre-existing mappings still win
        ("man/accessories", "KNIT SWEATER", ("Tops & Blouses", "Sweaters & Knitwear", "tops")),
        ("woman/accessories", "LEATHER HANDBAG", ("Bags & Handbags", "Handbags", "bags")),
        ("woman/accessories", "RED ZARA TEMPTATION EDP 30ML", ("Fragrance & Perfume", "Perfumes", "fragrance")),
        ("man/shoes", "WHITE SNEAKERS", ("Athletic & Sneakers", "Sneakers", "athletic_sneakers")),
        ("woman/shoes", "LEATHER SANDALS", ("Sandals & Slippers", "Sandals", "sandals_slippers")),
        ("woman/shoes", "HIGH HEEL SANDALS", ("Sandals & Slippers", "Sandals", "sandals_slippers")),
        # keyword precedence inside the shared rules
        ("woman/accessories", "PEARL EARRING AND RING SET", ("Earrings", "Earrings", "earrings")),
        ("man/accessories", "LOGO CAP WITH SUNGLASS STRAP", ("Sunglasses & Eyewear", "Sunglasses", "eyewear")),
    ],
)
def test_resolve_category(source_category: str, product_name: str, expected: tuple[str | None, str | None, str | None]) -> None:
    assert resolve_category(source_category, product_name) == expected


def test_shared_accessory_rules_assigned_to_both_genders() -> None:
    assert KEYWORD_OVERRIDE_RULES["woman/accessories"] is _ACCESSORY_RULES
    man_rules = KEYWORD_OVERRIDE_RULES["man/accessories"]
    assert man_rules[:5] == [
        ("jumper", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("sweater", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("knit", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("shirt", "Tops & Blouses", "Formal Shirts", "tops"),
        ("vest", "Tops & Blouses", "Vests & Tank Tops", "tops"),
    ]
    assert list(man_rules[5:]) == list(_ACCESSORY_RULES)


def test_earring_precedes_ring_in_shared_rules() -> None:
    keywords = [kw for kw, *_ in _ACCESSORY_RULES]
    assert keywords.index("earring") < keywords.index("ring")


def test_shoes_catchall_is_last() -> None:
    for cat in ("woman/shoes", "man/shoes"):
        assert KEYWORD_OVERRIDE_RULES[cat][-1][0] == "shoe"


def test_category_map_defaults_are_resolvable_product_types() -> None:
    seeded = {
        "heels_dress_shoes",
        "sandals_slippers",
        "athletic_sneakers",
        "boots",
        "bags",
        "belts_leather_goods",
        "head_accessories",
        "textile_accessories",
        "specialty_accessories",
        "necklaces_pendants",
        "bracelets_anklets",
        "earrings",
        "rings",
        "watches",
        "eyewear",
        "fragrance",
        "tops",
    }
    for cat in ("woman/shoes", "man/shoes", "woman/accessories", "man/accessories"):
        root_en, child_en, pt_code = CATEGORY_MAP[cat]
        assert pt_code in seeded, cat
        assert root_en is not None, cat


def test_resolve_category_empty_inputs() -> None:
    assert resolve_category("", "") == (None, None, None)
    assert resolve_category("woman/shoes", "") == ("Heels & Dress Shoes", None, "heels_dress_shoes")


@pytest.mark.parametrize(
    ("section", "family", "subfamily", "product_name", "expected"),
    [
        # MAN section: previously missing families
        ("MAN", "BAÑO", "", "SWIMMING TRUNKS", "man/swimwear"),
        ("MAN", "CALCETIN", "", "STRIPED SOCKS", "man/accessories"),
        ("MAN", "BRAGA/CALZONCILLO", "", "PACK OF BRIEFS", "man/lingerie"),
        ("MAN", "ACCESORIOS", "", "LEATHER BELT", "man/accessories"),
        ("MAN", "COMPLEMENTOS", "", "WOOL SCARF", "man/accessories"),
        ("MAN", "SOBRECAMISA", "", "OVERSHIRT JACKET", "man/shirts"),
        ("MAN", "EAU DE TOILETTE", "PERFU-PACK", "GIFT SET", "man/accessories"),
        ("MAN", "EAU DE PERFUME", "PERFU-L", "GIFT SET", "man/accessories"),
        ("MAN", "GABARDINA IMPERMEA", "F. Abrigo/Gab", "TRENCH COAT", "man/coats"),
        ("MAN", "CAMISON/PIJAMA", "", "PYJAMA SET", "man/lingerie"),
        ("MAN", "BILLETERAS", "", "CARD HOLDER", "man/accessories"),
        ("MAN", "TIRANTES", "", "BRACES", "man/accessories"),
        ("MAN", "MONO", "L. MONO", "JUMPSUIT", "man/t-shirts"),
        # KID section: baby + shoe families
        ("KID", "PANTALON BEBE", "KD-A PANT.DENIM", "BABY JEANS", "kids/boy"),
        ("KID", "ZAPATO", "Z3K:ZAPATO", "KIDS' SHOES", "kids/boy"),
        ("KID", "BAMBAS", "Z3SA:BAMBA", "KIDS' SNEAKERS", "kids/boy"),
        ("KID", "BOTA", "Z3KO:BOTA", "KIDS' BOOTS", "kids/boy"),
        ("KID", "CALCETIN", "", "KIDS' SOCKS", "kids/boy"),
        ("KID", "COMPLEMENTOS", "COMPLEMENTO", "HAIR CLIPS", "kids/boy"),
        ("KID", "JERSEY BEBE", "BABY PUNTO", "BABY KNIT", "kids/boy"),
        ("KID", "PRENDA EXT.BEBE", "KD-O P.EXTERIOR", "BABY COAT", "kids/boy"),
        ("KID", "HOME", "Z3A:HOME", "PANDA SLIPPERS", "kids/boy"),
        # WOMAN section
        ("WOMAN", "PAÑOLETAS/FOULARD", "PAÑUELO PEQUEÑO", "SILK SCARF", "woman/accessories"),
        ("WOMAN", "COSMETICA PELO", "CARE-HAIR", "HAIR OIL", "woman/accessories"),
        # Empty family: suit keyword fallback via product name
        ("MAN", "", "", "REGULAR FIT WOOL BLEND SUIT", "man/suits"),
        ("MAN", "", "", "100% WOOL SUIT AARON LEVINE X ZARA", "man/suits"),
    ],
)
def test_resolve_category_from_analytics_new_families(section: str, family: str, subfamily: str, product_name: str, expected: str) -> None:
    assert resolve_category_from_analytics(section, family, subfamily, product_name) == expected


@pytest.mark.parametrize(
    ("family", "subfamily", "product_name", "expected"),
    [
        # Beach-capsule fashion misfiled under HOME by Zara
        ("BOLSOS", "H1:ACC BEACHWEA", "PAPER TOTE BAG", "woman/accessories"),
        ("SANDALIA PLANA", "H1:ZAPATO CALLE", "MINIMALIST LEATHER SANDALS", "woman/shoes"),
        ("ZAPATO PLANO", "H2:CAPSULAS", "LEATHER SNEAKERS", "woman/shoes"),
        ("PRENDAS BAÑO", "TRAJES DE BAÑO", "ANIMAL PRINT BEACH BIKINI TOP", "woman/swimwear"),
        ("CAMISA/BLUSA", "CAMISA", "POPLIN SHIRT", "woman/tops"),
        ("BERMUDAS/SHORTS", "SHORT", "CHECKED SHORTS", "woman/shorts"),
        ("PANTALON", "PANTALÓN", "STRIPED TROUSERS", "woman/trousers"),
        ("TOP Y OTRAS P.", "CAMISETA", "STRIPED STRAPPY TOP", "woman/tops"),
        ("PRENDAS BEBE", "BAÑADOR NIÑA", "KIDS' FLORAL SWIMSUIT", "kids/swimwear"),
        ("PRENDAS BEBE", "BAÑADOR NIÑO", "KIDS' CHECK BEACH SWIMMING TRUNKS", "kids/swimwear"),
        ("PRENDAS BEBE", "OVERALL", "FLORAL BABY BEACH DUNGAREES", "kids/boy"),
        ("PRENDAS BEBE", "VESTIDO KDS", "KIDS' FLORAL BEACH DRESS", "kids/boy"),
        ("ROPA", "VESTIDO", "COTTON TERRY BEACH PONCHO", "woman/dresses"),
        ("ROPA", "SHORT", "COTTON TERRY BEACH SHORTS", "woman/shorts"),
        ("TEXTIL VARIOS", "COMPLEMENTOS", "KIDS' BALLERINAS WITH BOW", "kids/boy"),
        ("BOLSAS Y MOCHILAS", "BOLSAS TXT KDS", "KIDS' PENCIL CASE", "kids/boy"),
        # Genuine Zara Home -> excluded (empty string)
        ("VAJILLAS", "PLATO HONDO", "BONE CHINA SOUP PLATE", ""),
        ("MANTELERIA", "MANTELES", "FISH PRINT COTTON TABLECLOTH", ""),
        ("CRISTALERIA", "COPA", "CONICAL CRYSTALLINE WINE GLASS", ""),
        ("TOP Y OTRAS P.", "DELANTALES", "STRIPED COTTON APRON", ""),
        ("ACCESORIOS DECORAC", "SOPORTE MACETA", "METAL FLOWERPOT", ""),
        ("ILUMINACION", "LAMPARAS", "WOOD AND METAL TABLE LAMP", ""),
        ("PAPELERIA", "LIBRETAS", "DAILY VIEW DIARY", ""),
    ],
)
def test_resolve_category_home_section(family: str, subfamily: str, product_name: str, expected: str) -> None:
    assert resolve_category_from_analytics("HOME", family, subfamily, product_name) == expected


def test_swimwear_and_lingerie_keys_present() -> None:
    assert CATEGORY_MAP["man/swimwear"] == ("Swimwear", None, "swimwear")
    assert CATEGORY_MAP["woman/swimwear"] == ("Swimwear", None, "swimwear")
    assert CATEGORY_MAP["kids/swimwear"] == ("Swimwear", None, "swimwear")
    assert CATEGORY_MAP["man/lingerie"] == ("Lingerie & Sleepwear", None, "lingerie_sleepwear")


def test_home_section_constant() -> None:
    assert HOME_SECTION == "HOME"


def test_modesty_for_new_categories() -> None:
    from scripts.scrapers.mapper import infer_modesty_level

    assert infer_modesty_level("man/swimwear") == "revealing"
    assert infer_modesty_level("woman/swimwear") == "revealing"
    assert infer_modesty_level("kids/swimwear") == "full_coverage"
    assert infer_modesty_level("man/lingerie") == "revealing"
