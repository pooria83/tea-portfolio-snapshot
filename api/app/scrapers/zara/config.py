import re

STORE_ID = "11750"

BASE_URL = "https://www.zara.com/{country}/{lang}"

HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "TE": "trailers",
}

AJAX_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.zara.com/kw/",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=4",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "TE": "trailers",
}

CATEGORIES: dict[str, list[dict[str, str]]] = {
    "woman": [
        {"name": "new_in", "path": "woman-l1180.html", "id": "l1180"},
        {"name": "dresses", "path": "woman-dresses-l1066.html", "id": "l1066"},
        {"name": "tops", "path": "woman-tops-l1322.html", "id": "l1322"},
        {"name": "shirts", "path": "woman-shirts-l1217.html", "id": "l1217"},
        {"name": "knitwear", "path": "woman-knitwear-l1252.html", "id": "l1252"},
        {"name": "jackets", "path": "woman-jackets-l1114.html", "id": "l1114"},
        {"name": "coats", "path": "woman-coats-l1185.html", "id": "l1185"},
        {"name": "jeans", "path": "woman-jeans-l1119.html", "id": "l1119"},
        {"name": "trousers", "path": "woman-trousers-l1335.html", "id": "l1335"},
        {"name": "skirts", "path": "woman-skirts-l1295.html", "id": "l1295"},
        {"name": "shorts", "path": "woman-shorts-l1362.html", "id": "l1362"},
        {"name": "jumpsuits", "path": "woman-jumpsuits-l1167.html", "id": "l1167"},
        {"name": "lingerie", "path": "woman-lingerie-l1134.html", "id": "l1134"},
        {"name": "loungewear", "path": "woman-loungewear-l1197.html", "id": "l1197"},
        {"name": "swimwear", "path": "woman-swimwear-l1162.html", "id": "l1162"},
        {"name": "shoes", "path": "woman-shoes-l1251.html", "id": "l1251"},
        {"name": "bags", "path": "woman-bags-l1027.html", "id": "l1027"},
        {"name": "accessories", "path": "woman-accessories-l1003.html", "id": "l1003"},
    ],
    "man": [
        {"name": "new_in", "path": "man-l746.html", "id": "l746"},
        {"name": "t-shirts", "path": "man-tshirts-l855.html", "id": "l855"},
        {"name": "shirts", "path": "man-shirts-l737.html", "id": "l737"},
        {"name": "polos", "path": "man-polos-l733.html", "id": "l733"},
        {"name": "sweatshirts", "path": "man-sweatshirts-l821.html", "id": "l821"},
        {"name": "knitwear", "path": "man-knitwear-l685.html", "id": "l685"},
        {"name": "jackets", "path": "man-jackets-l640.html", "id": "l640"},
        {"name": "coats", "path": "man-coats-l728.html", "id": "l728"},
        {"name": "jeans", "path": "man-jeans-l659.html", "id": "l659"},
        {"name": "trousers", "path": "man-trousers-l838.html", "id": "l838"},
        {"name": "shorts", "path": "man-shorts-l734.html", "id": "l734"},
        {"name": "suits", "path": "man-suits-l819.html", "id": "l819"},
        {"name": "shoes", "path": "man-shoes-l769.html", "id": "l769"},
        {"name": "accessories", "path": "man-accessories-l681.html", "id": "l681"},
    ],
    "kids": [
        {"name": "new_in", "path": "kids-l1021.html", "id": "l1021"},
        {"name": "girl", "path": "girl-l359.html", "id": "l359"},
        {"name": "boy", "path": "boy-l352.html", "id": "l352"},
        {"name": "baby_girl", "path": "baby-girl-l370.html", "id": "l370"},
        {"name": "baby_boy", "path": "baby-boy-l363.html", "id": "l363"},
    ],
    "beauty": [
        {"name": "all", "path": "zara-beauty-l5818.html", "id": "l5818"},
    ],
}


def category_url(country: str, lang: str, category_path: str) -> str:
    return f"{BASE_URL.format(country=country, lang=lang)}/{category_path}"


def product_detail_url(country: str, lang: str, relative_path: str) -> str:
    clean_path = relative_path.lstrip("/")
    return f"{BASE_URL.format(country=country, lang=lang)}/{clean_path}"


def extra_detail_url(product_id: str) -> str:
    return f"https://www.zara.com/kw/en/product/id/{product_id}/extra-detail?ajax=true"


def extra_detail_url_lang(product_id: str, lang: str) -> str:
    return f"https://www.zara.com/kw/{lang}/product/id/{product_id}/extra-detail?ajax=true"


def availability_url(product_id: str) -> str:
    return f"https://www.zara.com/itxrest/1/catalog/store/{STORE_ID}/product/id/{product_id}/availability"


def size_guide_url(product_id: str) -> str:
    return f"https://www.zara.com/itxrest/4/catalog/store/{STORE_ID}/product/{product_id}/size-measure-guide?locale=en_GB"


def image_meta_url(image_path: str) -> str:
    base = image_path.rstrip("/").split("?")[0].rstrip("/")
    base = re.sub(r"/w\w+/", "/", base)
    grandparent = base.rsplit("/", 2)[0] if base.count("/") >= 2 else base
    return grandparent.rstrip("/") + "/meta.json"


def extract_access_token(cookie_str: str) -> str | None:
    match = re.search(r"access_token=([^;]+)", cookie_str)
    if match:
        return match.group(1)
    return None
