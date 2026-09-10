"""Download brand SVG logos from Wikipedia Commons, with fallback to placeholders."""

import asyncio
import json
import urllib.parse
from pathlib import Path

import httpx

SEED_DIR = Path(__file__).parent / "seed_data"
STATIC_DIR = Path(__file__).parent.parent / "static" / "brands"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/192.0.2.10 Safari/537.36",
}

# Brand code -> Wikipedia page title (for API lookup)
WIKI_TITLES: dict[str, str] = {
    "zara": "Zara (retailer)",
    "massimo-dutti": "Massimo Dutti",
    "bershka": "Bershka",
    "pull-bear": "Pull&Bear",
    "stradivarius": "Stradivarius",
    "oysho": "Oysho",
    "zara-home": "Zara Home",
    "hm": "H&M",
    "cos": "COS (clothing)",
    "arket": "Arket",
    "other-stories": "& Other Stories",
    "monki": "Monki",
    "mango": "Mango (clothing)",
    "uniqlo": "Uniqlo",
    "gap": "Gap Inc.",
    "old-navy": "Old Navy",
    "forever-21": "Forever 21",
    "primark": "Primark",
    "next": "Next (clothing)",
    "ca": "C&A",
    "lululemon": "Lululemon Athletica",
    "on": "On (company)",
    "converse": "Converse (shoe company)",
    "vans": "Vans",
    "skechers": "Skechers",
    "asics": "ASICS",
    "salomon": "Salomon Group",
    "columbia": "Columbia Sportswear",
    "patagonia": "Patagonia, Inc.",
    "arcteryx": "Arc'teryx",
    "champion": "Champion (sportswear)",
    "ellesse": "Ellesse",
    "kappa": "Kappa (company)",
    "levis": "Levi Strauss & Co.",
    "diesel": "Diesel (brand)",
    "wrangler": "Wrangler (jeans)",
    "lee": "Lee (jeans)",
    "gucci": "Gucci",
    "prada": "Prada",
    "versace": "Versace",
    "burberry": "Burberry",
    "balenciaga": "Balenciaga",
    "saint-laurent": "Yves Saint Laurent (brand)",
    "fendi": "Fendi",
    "givenchy": "Givenchy",
    "valentino": "Valentino (fashion house)",
    "dolce-gabbana": "Dolce & Gabbana",
    "giorgio-armani": "Giorgio Armani",
    "louis-vuitton": "Louis Vuitton",
    "dior": "Christian Dior",
    "chanel": "Chanel",
    "hermes": "Hermès",
    "bottega-veneta": "Bottega Veneta",
    "off-white": "Off-White (company)",
    "balmain": "Balmain (fashion house)",
    "alexander-mcqueen": "Alexander McQueen (brand)",
    "calvin-klein": "Calvin Klein",
    "tommy-hilfiger": "Tommy Hilfiger (company)",
    "ralph-lauren": "Ralph Lauren Corporation",
    "lacoste": "Lacoste",
    "superdry": "Superdry",
    "carhartt": "Carhartt",
    "fred-perry": "Fred Perry",
    "gant": "Gant",
    "nautica": "Nautica",
    "dockers": "Dockers (clothing)",
    "timberland": "Timberland",
    "drmartens": "Dr. Martens",
    "ugg": "UGG (brand)",
    "crocs": "Crocs",
    "clarks": "Clarks (shoe company)",
    "gymshark": "Gymshark",
    "alo-yoga": "Alo Yoga",
    "sweaty-betty": "Sweaty Betty",
    "splash": "Splash (fashion)",
    "max-fashion": "Max Fashion",
    "centrepoint": "Centrepoint (retail)",
    "red-tag": "Red Tag",
}


async def get_wikipedia_logo_url(client: httpx.AsyncClient, wiki_title: str) -> str | None:
    """Try to get an SVG logo URL from Wikipedia Commons."""
    params = {
        "action": "query",
        "titles": wiki_title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 200,
    }
    try:
        resp = await client.get("https://en.wikipedia.org/w/api.php", params=params, headers=HEADERS)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            image_name = page.get("pageimage")
            if image_name and image_name.lower().endswith(".svg"):
                # Construct Wikimedia Commons URL
                return f"https://upload.wikimedia.org/wikipedia/commons/{_hash_prefix(image_name)}/{urllib.parse.quote(image_name, safe='')}"
    except Exception:
        pass
    return None


def _hash_prefix(filename: str) -> str:
    """Compute the MD5 hash prefix for Wikimedia file paths."""
    import hashlib

    h = hashlib.md5(filename.encode()).hexdigest()
    return f"{h[0]}/{h[0:2]}"


def create_placeholder(code: str, name: str) -> str:
    """Create a simple SVG placeholder with brand initials."""
    clean = name.replace("&", "").replace(",", "").replace(".", "").replace("'", "")
    initials = "".join(w[0].upper() for w in clean.split()[:2] if w)
    color = "#64748b"
    bg = "#e2e8f0"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="12" fill="{bg}"/>
  <text x="50" y="54" text-anchor="middle" dominant-baseline="central"
        font-family="system-ui, sans-serif" font-size="28" font-weight="700"
        fill="{color}">{initials}</text>
</svg>"""


async def main() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    path = SEED_DIR / "05_brands.json"
    with open(path) as f:
        data = json.load(f)

    brands = data.get("brands", [])
    wikipedia = 0
    placeholders = 0
    missing: list[str] = []

    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        for b in brands:
            code = b["code"]
            name = b["name_en"]
            filepath = STATIC_DIR / f"{code}.svg"
            if filepath.exists():
                continue

            # Try Wikipedia Commons
            wiki_title = WIKI_TITLES.get(code)
            if wiki_title:
                svg_url = await get_wikipedia_logo_url(client, wiki_title)
                if svg_url:
                    try:
                        resp = await client.get(svg_url, follow_redirects=True, headers=HEADERS)
                        if resp.status_code == 200 and "<svg" in resp.text:
                            filepath.write_text(resp.text)
                            wikipedia += 1
                            print(f"  ✓ {code} (wikipedia)")
                            continue
                    except Exception:
                        pass

            # Fallback: create placeholder
            svg = create_placeholder(code, name)
            filepath.write_text(svg)
            placeholders += 1
            print(f"  ◇ {code} (placeholder)")
            missing.append(f"{code} ({name})")

    print(f"\nWikipedia: {wikipedia}, Placeholders: {placeholders}")
    if missing:
        print(f"Brands with placeholders ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    asyncio.run(main())
