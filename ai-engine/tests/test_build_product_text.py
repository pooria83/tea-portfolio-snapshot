from app.routers.description import _build_product_text
from app.schemas.product import Attribute, ProductData


def test_minimal() -> None:
    p = ProductData(name_en="Test")
    result = _build_product_text(p)
    assert result == "Name (EN): Test"


def test_with_name_ar() -> None:
    p = ProductData(name_en="Test", name_ar="اختبار")
    result = _build_product_text(p)
    assert "Name (EN): Test" in result
    assert "Name (AR): اختبار" in result


def test_with_brand() -> None:
    p = ProductData(name_en="Test", brand="Nike")
    result = _build_product_text(p)
    assert "Brand: Nike" in result


def test_with_category() -> None:
    p = ProductData(name_en="Test", category_name="Tops")
    result = _build_product_text(p)
    assert "Category: Tops" in result


def test_with_image_alt_texts() -> None:
    p = ProductData(name_en="Test", image_alt_texts=["Front view", "Back view"])
    result = _build_product_text(p)
    assert "Image descriptions: Front view; Back view" in result


def test_with_attributes() -> None:
    p = ProductData(
        name_en="Test",
        attributes=[Attribute(name="Color", value="Red"), Attribute(name="Size", value="M")],
    )
    result = _build_product_text(p)
    assert "Attributes: Color: Red, Size: M" in result


def test_with_price() -> None:
    p = ProductData(name_en="Test", price=49.99, currency="SAR")
    result = _build_product_text(p)
    assert "Price: 49.99 SAR" in result


def test_price_zero() -> None:
    p = ProductData(name_en="Test", price=0.0)
    result = _build_product_text(p)
    assert "Price: 0.0 SAR" in result


def test_all_fields() -> None:
    p = ProductData(
        name_en="Jacket",
        name_ar="جاكيت",
        brand="Zara",
        category_name="Outerwear",
        image_alt_texts=["Front"],
        attributes=[Attribute(name="Material", value="Wool")],
        price=199.0,
        currency="KWD",
    )
    result = _build_product_text(p)
    lines = result.split("\n")
    assert "Name (EN): Jacket" in lines
    assert "Name (AR): جاكيت" in lines
    assert "Brand: Zara" in lines
    assert "Category: Outerwear" in lines
    assert "Image descriptions: Front" in lines
    assert "Attributes: Material: Wool" in lines
    assert "Price: 199.0 KWD" in lines


def test_empty_image_alt_texts_not_included() -> None:
    p = ProductData(name_en="Test", image_alt_texts=[])
    result = _build_product_text(p)
    assert "Image descriptions" not in result


def test_empty_attributes_not_included() -> None:
    p = ProductData(name_en="Test", attributes=[])
    result = _build_product_text(p)
    assert "Attributes:" not in result


def test_no_name_ar_omits_line() -> None:
    p = ProductData(name_en="Test")
    result = _build_product_text(p)
    assert "Name (AR):" not in result


def test_multiple_image_alts() -> None:
    p = ProductData(name_en="Test", image_alt_texts=["a", "b", "c"])
    result = _build_product_text(p)
    assert "Image descriptions: a; b; c" in result


def test_single_attribute() -> None:
    p = ProductData(name_en="Test", attributes=[Attribute(name="Color", value="Blue")])
    result = _build_product_text(p)
    assert "Attributes: Color: Blue" in result
