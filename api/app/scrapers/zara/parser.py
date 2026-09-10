import json
import re
from typing import Any, cast

from app.scrapers.zara.config import image_meta_url

_VIEW_PAYLOAD_RE = re.compile(r"window\.zara\.viewPayload\s*=\s*")

IMAGE_WIDTH = "560"


def extract_json_ld(html: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            data = cast("dict[str, Any]", json.loads(match.group(1)))
            results.append(data)
        except json.JSONDecodeError:
            continue
    return results


def extract_view_payload(html: str) -> dict[str, Any] | None:
    """Extract the JSON assigned to window.zara.viewPayload (new-front pages)."""
    match = _VIEW_PAYLOAD_RE.search(html)
    if not match:
        return None
    start = match.end()
    depth = 0
    in_string = False
    escaped = False
    i = start
    while i < len(html):
        char = html[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if depth != 0:
        return None
    try:
        payload = json.loads(html[start : i + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def view_payload_to_json_ld(view_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert the new-front window.zara.viewPayload into the legacy JSON-LD shape.

    Zara migrated from JSON-LD to a React app that embeds all product data in
    window.zara.viewPayload. This adapter produces a dict with the same keys the
    rest of the pipeline expects (name, description, productGroupID, image,
    hasVariant with size/color/sku/offers, material, additionalProperty) so all
    downstream consumers keep working unchanged.
    """
    product = view_payload.get("product")
    if not isinstance(product, dict):
        return None
    detail = product.get("detail")
    if not isinstance(detail, dict):
        return None
    colors = detail.get("colors")
    if not isinstance(colors, list) or not colors:
        return None

    variants = _build_variants_from_colors(colors)
    first_color = colors[0]
    images = _build_images(first_color)
    return {
        "@type": "Product",
        "productGroupID": str(product.get("id") or ""),
        "name": product.get("name", ""),
        "description": _color_description(first_color),
        "image": images,
        "images": images,
        "hasVariant": variants,
        "variesBy": ["color"] if len(colors) > 1 else [],
        "material": _main_material(detail),
        "additionalProperty": _composition_properties(detail),
        "offers": {"price": _price_value(first_color)},
    }


def extract_product_data(html: str) -> dict[str, Any] | None:
    view_payload = extract_view_payload(html)
    if view_payload is not None:
        adapted = view_payload_to_json_ld(view_payload)
        if adapted is not None:
            return adapted
    json_ld_list = extract_json_ld(html)
    for data in json_ld_list:
        if isinstance(data, dict) and data.get("@type") in ("Product", "ProductGroup", "product"):
            return data
    return None


def _build_variants_from_colors(colors: list[Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for color in colors:
        if not isinstance(color, dict):
            continue
        color_id = str(color.get("id") or "")
        color_name = str(color.get("name") or "")
        product_id = str(color.get("productId") or "")
        sizes = color.get("sizes")
        if not isinstance(sizes, list) or not sizes:
            continue
        base_price = _price_value(color)
        for size in sizes:
            if not isinstance(size, dict):
                continue
            sku = str(size.get("sku") or "")
            variants.append(
                {
                    "sku": f"{product_id}-{sku}" if product_id else sku,
                    "mpn": sku,
                    "size": str(size.get("name") or ""),
                    "color": {"id": color_id, "name": color_name},
                    "offers": {
                        "price": _size_price(size, base_price),
                        "url": f"https://www.zara.com/kw/en/?v1={product_id}",
                    },
                }
            )
    variants.sort(key=_variant_sort_key)
    return variants


def _variant_sort_key(variant: dict[str, Any]) -> tuple[int, str]:
    mpn = variant.get("mpn", "")
    try:
        return (int(mpn), str(variant.get("sku", "")))
    except (TypeError, ValueError):
        return (0, str(variant.get("sku", "")))


def _price_value(color: dict[str, Any]) -> float | None:
    pricing = color.get("pricing")
    if isinstance(pricing, dict):
        price = pricing.get("price")
        if isinstance(price, dict) and isinstance(price.get("value"), (int, float)):
            currency = price.get("currency")
            exponent = currency.get("exponent", 0) if isinstance(currency, dict) else 0
            return float(price["value"]) * (10**exponent)
    price = color.get("price")
    if price is not None:
        return float(price) / 100.0
    return None


def _size_price(size: dict[str, Any], fallback: float | None) -> float | None:
    price = size.get("price")
    if price is not None:
        return float(price) / 100.0
    return fallback


def _build_images(color: dict[str, Any]) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()
    items = color.get("mainImgs")
    if not isinstance(items, list):
        items = color.get("xmedia")
    if not isinstance(items, list):
        return images
    for item in items:
        if not isinstance(item, dict):
            continue
        url = _image_url(item)
        if url and url not in seen:
            seen.add(url)
            images.append(url)
    return images


def _image_url(item: dict[str, Any]) -> str:
    url = item.get("url")
    if isinstance(url, str) and url:
        return url.replace("{width}", IMAGE_WIDTH)
    extra = item.get("extraInfo")
    if isinstance(extra, dict):
        delivery = extra.get("deliveryUrl")
        if isinstance(delivery, str) and delivery:
            return delivery
    return ""


def _color_description(color: dict[str, Any]) -> str:
    description = color.get("description")
    if isinstance(description, str) and description:
        return description
    raw = color.get("rawDescription")
    if isinstance(raw, str) and raw:
        return raw.replace("<br/>", "\n").replace("<br>", "\n")
    return ""


def _composition_parts(detail: dict[str, Any]) -> list[dict[str, Any]]:
    composition = detail.get("detailedComposition")
    if not isinstance(composition, dict):
        return []
    parts = composition.get("parts")
    return parts if isinstance(parts, list) else []


def _main_material(detail: dict[str, Any]) -> str:
    for part in _composition_parts(detail):
        components = part.get("components", [])
        if not isinstance(components, list):
            continue
        for component in components:
            if isinstance(component, dict):
                material = component.get("material")
                if isinstance(material, str) and material:
                    return material
    return ""


def _composition_properties(detail: dict[str, Any]) -> list[dict[str, str]]:
    props: list[dict[str, str]] = []
    for part in _composition_parts(detail):
        name = part.get("description")
        components = part.get("components", [])
        if not isinstance(name, str) or not name or not isinstance(components, list):
            continue
        values: list[str] = []
        for component in components:
            if not isinstance(component, dict):
                continue
            material = component.get("material")
            percentage = component.get("percentage")
            value = f"{percentage} {material}".strip() if isinstance(material, str) else ""
            if value:
                values.append(value)
        if values:
            props.append({"name": name, "value": ", ".join(values)})
    return props


def extract_product_urls_from_category(html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for match in re.finditer(r'href=["\'](/[^"\']*p\d{5,}[^"\']*?)["\']', html):
        path = match.group(1)
        full_url = f"{base_url.rstrip('/')}{path}"
        if full_url not in urls:
            urls.append(full_url)
    return urls


def extract_relative_product_urls(html: str) -> list[dict[str, str]]:
    urls: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'href=["\'](/[^"\']*p(\d{5,})[^"\']*?)["\']', html):
        path = match.group(1)
        product_id = match.group(2)
        if product_id not in seen:
            seen.add(product_id)
            urls.append({"path": path, "product_id": product_id})
    return urls


def extract_product_id(json_ld: dict[str, Any]) -> str:
    pid = json_ld.get("productGroupID") or json_ld.get("sku") or json_ld.get("mpn", "")
    return str(pid)


def get_unique_colors(json_ld: dict[str, Any]) -> list[dict[str, str]]:
    colors: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    variants = json_ld.get("hasVariant", [])
    if isinstance(variants, dict):
        variants = [variants]
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        color = variant.get("color")
        if isinstance(color, dict):
            code = str(color.get("id", ""))
            name = str(color.get("name", ""))
        else:
            code = str(color or "")
            name = code
        if code and code not in seen_codes:
            seen_codes.add(code)
            colors.append({"code": code, "name": name})
    return colors


def sku_pattern(json_ld: dict[str, Any], product_id: str) -> str:
    varies_by = json_ld.get("variesBy", [])
    if isinstance(varies_by, str):
        varies_by = [varies_by]
    if "color" in varies_by:
        return "multi_color"
    return "single_color"


def derive_v1_url(sku: str) -> str | None:
    if not sku:
        return None
    parts = sku.split("-")
    if len(parts) >= 2:
        return f"?v1={parts[0]}&v2={parts[1]}"
    return f"?v1={parts[0]}"


def parse_extra_detail(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return {
            "materials": _extract_materials(data),
            "care_instructions": data.get("careInstructions", ""),
            "country_of_origin": data.get("countryOfOrigin", ""),
        }
    return {}


def _extract_materials(data: dict[str, Any]) -> list[dict[str, str]]:
    materials: list[dict[str, str]] = []
    details = data.get("detail", {})
    sections = details.get("sections", []) if isinstance(details, dict) else []
    for section in sections:
        if not isinstance(section, dict):
            continue
        composition = section.get("composition", []) if isinstance(section.get("composition"), list) else []
        for comp in composition:
            if not isinstance(comp, dict):
                continue
            materials.append(
                {
                    "name": str(comp.get("name", comp.get("value", ""))),
                    "percentage": str(comp.get("percentage", "")),
                }
            )
    return materials


def parse_availability(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    result: list[dict[str, Any]] = []
    for sku_id, info in data.items():
        if not isinstance(info, dict):
            continue
        result.append(
            {
                "sku": str(sku_id),
                "availability": info.get("availability", ""),
                "quantity": info.get("quantity", 0),
            }
        )
    return result


def parse_size_guide(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    result: list[dict[str, Any]] = []
    for size_id, info in data.items():
        if not isinstance(info, dict):
            continue
        entry: dict[str, Any] = {"size_id": str(size_id)}
        for key, value in info.items():
            if isinstance(value, (int, float)):
                entry[key] = value
        result.append(entry)
    return result


def parse_image_meta(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    alt_texts: dict[str, str] = {}
    public_metadata = data.get("publicMetadata", {})
    if isinstance(public_metadata, dict):
        alt_texts_data = public_metadata.get("altTexts", {})
        if isinstance(alt_texts_data, dict):
            for locale, alt_text in alt_texts_data.items():
                if isinstance(alt_text, str):
                    alt_texts[locale] = alt_text
    return {"alt_texts": alt_texts}


def get_image_meta_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    return image_meta_url(image_url)


def extract_product_images(json_ld: dict[str, Any]) -> list[str]:
    raw_images = json_ld.get("image", json_ld.get("images", []))
    if isinstance(raw_images, str):
        raw_images = [raw_images]
    images: list[str] = []
    for img in raw_images:
        if isinstance(img, str):
            images.append(img)
    return images


def extract_colors_from_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    colors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for v in variants:
        if not isinstance(v, dict):
            continue
        color = v.get("color", {})
        code = str(color.get("id", "")) if isinstance(color, dict) else str(color)
        if code and code not in seen:
            seen.add(code)
            colors.append(v)
    return colors


def extract_text_content(html: str, tag: str = "meta", attr: str = "name", attr_value: str = "description", content_attr: str = "content") -> str | None:
    pattern = rf'<{tag}[^>]*{attr}=["\']{re.escape(attr_value)}["\'][^>]*{content_attr}=["\']([^"\']*)["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_analytics_section(html: str) -> dict[str, str]:
    """Extract section/family/subfamily from zara.analyticsData or viewPayload."""
    m = re.search(r"zara\.analyticsData\s*=\s*({.*?});", html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict) and data.get("section"):
                return {
                    "section": str(data.get("section") or ""),
                    "family": str(data.get("family") or ""),
                    "subfamily": str(data.get("subfamily") or ""),
                }
        except json.JSONDecodeError:
            pass
    view_payload = extract_view_payload(html)
    if view_payload is not None:
        product = view_payload.get("product")
        product = product if isinstance(product, dict) else {}
        analytics = view_payload.get("analyticsData")
        analytics = analytics if isinstance(analytics, dict) else {}
        return {
            "section": str(analytics.get("section") or product.get("sectionName") or ""),
            "family": str(analytics.get("family") or product.get("familyName") or ""),
            "subfamily": str(analytics.get("subfamily") or product.get("subfamilyName") or ""),
        }
    return {"section": "", "family": "", "subfamily": ""}
