"""Pure mapping functions for Zara scraper data -> system values.

No DB dependency -- all functions are stateless transforms.
"""

from typing import Any

CATEGORY_MAP: dict[str, tuple[str | None, str | None, str | None]] = {
    "woman/dresses": ("Dresses", None, "dresses"),
    "woman/tops": ("Tops & Blouses", None, "tops"),
    "woman/shirts": ("Tops & Blouses", "Blouses", "tops"),
    "woman/trousers": ("Pants & Bottoms", "Pants", "bottoms"),
    "woman/shorts": ("Pants & Bottoms", "Shorts", "bottoms"),
    "woman/lingerie": ("Lingerie & Sleepwear", "Lingerie", "lingerie_sleepwear"),
    "woman/jeans": ("Pants & Bottoms", "Jeans", "bottoms"),
    "woman/skirts": ("Skirts", None, "skirts"),
    "woman/jumpsuits": ("Dresses", None, "dresses"),
    "woman/jackets": ("Outerwear", "Jackets", "outerwear"),
    "woman/loungewear": ("Outerwear", None, "outerwear"),
    "woman/swimwear": ("Swimwear", None, "swimwear"),
    "woman/shoes": ("Heels & Dress Shoes", None, "heels_dress_shoes"),
    "woman/accessories": ("Specialty Accessories", None, "specialty_accessories"),
    "woman/new_in": (None, None, None),
    "man/t-shirts": ("Tops & Blouses", "T-Shirts", "tops"),
    "man/coats": ("Outerwear", "Coats", "outerwear"),
    "man/jackets": ("Outerwear", "Jackets", "outerwear"),
    "man/trousers": ("Pants & Bottoms", "Pants", "bottoms"),
    "man/shirts": ("Tops & Blouses", "Formal Shirts", "tops"),
    "man/accessories": ("Specialty Accessories", None, "specialty_accessories"),
    "man/jeans": ("Pants & Bottoms", "Jeans", "bottoms"),
    "man/shoes": ("Heels & Dress Shoes", None, "heels_dress_shoes"),
    "man/sweatshirts": ("Tops & Blouses", "Sweatshirts", "tops"),
    "man/polos": ("Tops & Blouses", "Polos", "tops"),
    "man/suits": ("Suits & Formalwear", None, "suits_formalwear"),
    "man/swimwear": ("Swimwear", None, "swimwear"),
    "man/lingerie": ("Lingerie & Sleepwear", None, "lingerie_sleepwear"),
    "kids/boy": ("Tops & Blouses", None, "tops"),
    "kids/swimwear": ("Swimwear", None, "swimwear"),
    "kids/new_in": (None, None, None),
}

# Gender-neutral accessory rules shared by woman/accessories and man/accessories.
# Order matters: resolve_category returns the FIRST keyword hit, so specific
# keywords must precede their substrings (e.g. earring before ring).
_ACCESSORY_RULES: list[tuple[str, str, str | None, str]] = [
    ("sunglass", "Sunglasses & Eyewear", "Sunglasses", "eyewear"),
    ("eyewear", "Sunglasses & Eyewear", "Sunglasses", "eyewear"),
    ("glasses", "Sunglasses & Eyewear", "Sunglasses", "eyewear"),
    ("watch", "Watches", "Analog", "watches"),
    ("necklace", "Necklaces & Pendants", "Necklaces", "necklaces_pendants"),
    ("choker", "Necklaces & Pendants", "Chokers", "necklaces_pendants"),
    ("pendant", "Necklaces & Pendants", "Necklaces", "necklaces_pendants"),
    ("earring", "Earrings", "Earrings", "earrings"),
    ("ear cuff", "Earrings", "Earrings", "earrings"),
    ("bracelet", "Bracelets & Anklets", "Bracelets", "bracelets_anklets"),
    ("anklet", "Bracelets & Anklets", "Bracelets", "bracelets_anklets"),
    ("brooch", "Necklaces & Pendants", "Brooches", "necklaces_pendants"),
    ("ring", "Rings", "Rings", "rings"),
    ("parfum", "Fragrance & Perfume", "Perfumes", "fragrance"),
    ("perfum", "Fragrance & Perfume", "Perfumes", "fragrance"),
    ("edp", "Fragrance & Perfume", "Perfumes", "fragrance"),
    ("edt", "Fragrance & Perfume", "Perfumes", "fragrance"),
    ("fragrance", "Fragrance & Perfume", "Perfumes", "fragrance"),
    ("backpack", "Bags & Handbags", "Backpacks", "bags"),
    ("clutch", "Bags & Handbags", "Clutches", "bags"),
    ("minaudière", "Bags & Handbags", "Clutches", "bags"),
    ("minaudiere", "Bags & Handbags", "Clutches", "bags"),
    ("crossbody", "Bags & Handbags", "Crossbody Bags", "bags"),
    ("bucket", "Bags & Handbags", "Handbags", "bags"),
    ("shldr", "Bags & Handbags", "Shoulder Bags", "bags"),
    ("briefcase", "Bags & Handbags", "Handbags", "bags"),
    ("suitcase", "Bags & Handbags", "Handbags", "bags"),
    ("luggage", "Bags & Handbags", "Handbags", "bags"),
    ("trolley", "Bags & Handbags", "Handbags", "bags"),
    ("tote", "Bags & Handbags", "Handbags", "bags"),
    (" bg ", "Bags & Handbags", "Handbags", "bags"),
    ("bag", "Bags & Handbags", "Handbags", "bags"),
    ("wallet", "Belts & Leather Goods", "Wallets", "belts_leather_goods"),
    ("belt", "Belts & Leather Goods", "Belts", "belts_leather_goods"),
    ("scarf", "Textile Accessories", "Scarves", "textile_accessories"),
    ("bandana", "Textile Accessories", "Bandanas", "textile_accessories"),
    ("glove", "Textile Accessories", "Gloves", "textile_accessories"),
    ("tie", "Textile Accessories", "Ties", "textile_accessories"),
    ("visor", "Head Accessories", "Hats", "head_accessories"),
    ("skullcap", "Head Accessories", "Caps", "head_accessories"),
    ("beanie", "Head Accessories", "Beanies", "head_accessories"),
    ("headband", "Head Accessories", "Hair Accessories", "head_accessories"),
    ("headpiece", "Head Accessories", "Headpieces", "head_accessories"),
    ("cap", "Head Accessories", "Caps", "head_accessories"),
    ("hat", "Head Accessories", "Hats", "head_accessories"),
    ("hair", "Head Accessories", "Hair Accessories", "head_accessories"),
    ("umbrella", "Specialty Accessories", "Umbrellas", "specialty_accessories"),
    ("keychain", "Specialty Accessories", "Keychains", "specialty_accessories"),
    ("keyring", "Specialty Accessories", "Keychains", "specialty_accessories"),
    ("phone case", "Specialty Accessories", "Phone Cases", "specialty_accessories"),
    (" fan ", "Specialty Accessories", None, "specialty_accessories"),
    ("pins", "Head Accessories", "Pins & Brooches", "head_accessories"),
]

KEYWORD_OVERRIDE_RULES: dict[str, list[tuple[str, str, str | None, str]]] = {
    "woman/shoes": [
        ("sandal", "Sandals & Slippers", "Sandals", "sandals_slippers"),
        ("sndl", "Sandals & Slippers", "Sandals", "sandals_slippers"),
        ("sneaker", "Athletic & Sneakers", "Sneakers", "athletic_sneakers"),
        ("trainer", "Athletic & Sneakers", "Trainers", "athletic_sneakers"),
        ("trnrs", "Athletic & Sneakers", "Trainers", "athletic_sneakers"),
        ("boot", "Boots", "Boots", "boots"),
        ("ballerina", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("ballet flat", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("slingback", "Heels & Dress Shoes", "Pumps", "heels_dress_shoes"),
        ("derby", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("oxford", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("brogue", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("wedge", "Heels & Dress Shoes", "High Heels", "heels_dress_shoes"),
        ("heel", "Heels & Dress Shoes", "High Heels", "heels_dress_shoes"),
        ("pump", "Heels & Dress Shoes", "Pumps", "heels_dress_shoes"),
        ("loafer", "Heels & Dress Shoes", "Loafers", "heels_dress_shoes"),
        ("mule", "Heels & Dress Shoes", "Mules", "heels_dress_shoes"),
        ("espadrille", "Sandals & Slippers", "Espadrilles", "sandals_slippers"),
        ("flat", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("slipper", "Sandals & Slippers", "Slippers", "sandals_slippers"),
        ("clog", "Sandals & Slippers", "Clogs", "sandals_slippers"),
        ("deck shoe", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("shoe", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
    ],
    "woman/accessories": _ACCESSORY_RULES,
    "man/accessories": [
        ("jumper", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("sweater", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("knit", "Tops & Blouses", "Sweaters & Knitwear", "tops"),
        ("shirt", "Tops & Blouses", "Formal Shirts", "tops"),
        ("vest", "Tops & Blouses", "Vests & Tank Tops", "tops"),
        *_ACCESSORY_RULES,
    ],
    "woman/loungewear": [
        ("coat", "Outerwear", "Coats", "outerwear"),
        ("jacket", "Outerwear", "Jackets", "outerwear"),
        ("blazer", "Outerwear", "Blazers", "outerwear"),
        ("gilet", "Outerwear", "Gilets", "outerwear"),
        ("puffer", "Outerwear", "Puffer Jackets", "outerwear"),
    ],
    "woman/new_in": [
        ("dress", "Dresses", "Casual Dresses", "dresses"),
        ("top", "Tops & Blouses", "Blouses", "tops"),
        ("trouser", "Pants & Bottoms", "Pants", "bottoms"),
        ("shorts", "Pants & Bottoms", "Shorts", "bottoms"),
        ("jeans", "Pants & Bottoms", "Jeans", "bottoms"),
        ("jacket", "Outerwear", "Jackets", "outerwear"),
        ("coat", "Outerwear", "Coats", "outerwear"),
        ("shoe", "Heels & Dress Shoes", "Pumps", "heels_dress_shoes"),
        ("bag", "Bags & Handbags", "Handbags", "bags"),
        ("skirt", "Skirts", "Midi", "skirts"),
        ("hat", "Head Accessories", "Hats", "head_accessories"),
        ("jumpsuit", "Dresses", "Jumpsuits", "dresses"),
        ("sarouel", "Dresses", "Jumpsuits", "dresses"),
        ("earring", "Earrings", "Earrings", "earrings"),
    ],
    "kids/boy": [
        ("dress", "Dresses", "Casual Dresses", "dresses"),
        ("shirt", "Tops & Blouses", "Formal Shirts", "tops"),
        ("jacket", "Outerwear", "Jackets", "outerwear"),
        ("blazer", "Outerwear", "Blazers", "outerwear"),
        ("jeans", "Pants & Bottoms", "Jeans", "bottoms"),
        ("shorts", "Pants & Bottoms", "Shorts", "bottoms"),
        ("sneaker", "Athletic & Sneakers", "Sneakers", "athletic_sneakers"),
        ("set", "Tops & Blouses", "T-Shirts", "tops"),
        ("top", "Tops & Blouses", "T-Shirts", "tops"),
    ],
    "kids/new_in": [
        ("dress", "Dresses", "Casual Dresses", "dresses"),
        ("top", "Tops & Blouses", "T-Shirts", "tops"),
        ("shorts", "Pants & Bottoms", "Shorts", "bottoms"),
        ("set", "Tops & Blouses", "T-Shirts", "tops"),
        ("jacket", "Outerwear", "Jackets", "outerwear"),
        ("sunglasses", "Sunglasses & Eyewear", "Sunglasses", "eyewear"),
        ("sunglass", "Sunglasses & Eyewear", "Sunglasses", "eyewear"),
    ],
    "man/shoes": [
        ("sandal", "Sandals & Slippers", "Sandals", "sandals_slippers"),
        ("sndl", "Sandals & Slippers", "Sandals", "sandals_slippers"),
        ("sneaker", "Athletic & Sneakers", "Sneakers", "athletic_sneakers"),
        ("trainer", "Athletic & Sneakers", "Trainers", "athletic_sneakers"),
        ("trnrs", "Athletic & Sneakers", "Trainers", "athletic_sneakers"),
        ("boot", "Boots", "Boots", "boots"),
        ("derby", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("oxford", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("brogue", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("blucher", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("deck shoe", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("heel", "Heels & Dress Shoes", "High Heels", "heels_dress_shoes"),
        ("pump", "Heels & Dress Shoes", "Pumps", "heels_dress_shoes"),
        ("loafer", "Heels & Dress Shoes", "Loafers", "heels_dress_shoes"),
        ("mule", "Heels & Dress Shoes", "Mules", "heels_dress_shoes"),
        ("espadrille", "Sandals & Slippers", "Espadrilles", "sandals_slippers"),
        ("flat", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("slipper", "Sandals & Slippers", "Slippers", "sandals_slippers"),
        ("clog", "Sandals & Slippers", "Clogs", "sandals_slippers"),
        ("dress shoe", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
        ("shoe", "Heels & Dress Shoes", "Dress Shoes", "heels_dress_shoes"),
    ],
    "man/suits": [
        ("blazer", "Outerwear", "Blazers", "outerwear"),
        ("waistcoat", "Suits & Formalwear", "Waistcoats", "suits_formalwear"),
        ("vest", "Suits & Formalwear", "Waistcoats", "suits_formalwear"),
        ("trouser", "Pants & Bottoms", "Pants", "bottoms"),
        ("suit", "Suits & Formalwear", "Suits", "suits_formalwear"),
    ],
}

CHILD_KEYWORD_RULES: dict[str, list[tuple[str, str]]] = {
    "Tops & Blouses": [
        ("blouse", "Blouses"),
        ("shirt", "Formal Shirts"),
        ("polo", "Polos"),
        ("sweatshirt", "Sweatshirts"),
        ("jumper", "Sweaters & Knitwear"),
        ("sweater", "Sweaters & Knitwear"),
        ("knit", "Sweaters & Knitwear"),
        ("cardigan", "Sweaters & Knitwear"),
        ("vest", "Vests & Tank Tops"),
        ("tank", "Vests & Tank Tops"),
        ("tunic", "Tunics"),
        ("t-shirt", "T-Shirts"),
    ],
    "Dresses": [
        ("evening", "Evening Dresses"),
        ("wedding", "Wedding Dresses"),
        ("modest", "Modest Dresses"),
        ("maxi", "Evening Dresses"),
        ("midi", "Casual Dresses"),
        ("mini", "Casual Dresses"),
    ],
    "Outerwear": [
        ("coat", "Coats"),
        ("blazer", "Blazers"),
        ("cardigan", "Cardigans"),
        ("gilet", "Gilets"),
        ("puffer", "Puffer Jackets"),
        ("bomber", "Jackets"),
    ],
    "Pants & Bottoms": [
        ("jeans", "Jeans"),
        ("shorts", "Shorts"),
        ("legging", "Leggings"),
        ("trouser", "Pants"),
    ],
    "Lingerie & Sleepwear": [
        ("pajama", "Pajamas"),
        ("lingerie", "Lingerie"),
        ("lounge", "Loungewear"),
        ("night", "Sleepwear"),
        ("sleep", "Sleepwear"),
        ("bra", "Lingerie"),
    ],
    "Heels & Dress Shoes": [
        ("heel", "High Heels"),
        ("pump", "Pumps"),
        ("loafer", "Loafers"),
        ("mule", "Mules"),
    ],
    "Sandals & Slippers": [
        ("sandal", "Sandals"),
        ("espadrille", "Espadrilles"),
        ("clog", "Clogs"),
        ("slipper", "Slippers"),
    ],
    "Athletic & Sneakers": [
        ("sneaker", "Sneakers"),
        ("trainer", "Trainers"),
        ("running", "Trainers"),
    ],
    "Bags & Handbags": [
        ("backpack", "Backpacks"),
        ("clutch", "Clutches"),
        ("shoulder", "Shoulder Bags"),
        ("tote", "Handbags"),
        ("handbag", "Handbags"),
    ],
    "Textile Accessories": [
        ("scarf", "Scarves"),
        ("glove", "Gloves"),
        ("tie", "Ties"),
        ("bandana", "Bandanas"),
        ("headband", "Headbands"),
    ],
    "Necklaces & Pendants": [
        ("choker", "Chokers"),
        ("necklace", "Necklaces"),
        ("pendant", "Necklaces"),
    ],
}

DEFAULT_CHILD: dict[str, str] = {
    "Tops & Blouses": "Blouses",
    "Dresses": "Casual Dresses",
    "Outerwear": "Jackets",
    "Pants & Bottoms": "Pants",
    "Lingerie & Sleepwear": "Sleepwear",
    "Heels & Dress Shoes": "Pumps",
    "Sandals & Slippers": "Sandals",
    "Athletic & Sneakers": "Sneakers",
    "Bags & Handbags": "Handbags",
    "Textile Accessories": "Scarves",
    "Necklaces & Pendants": "Necklaces",
    "Suits & Formalwear": "Suits",
    "Skirts": "Midi",
    "Boots": "Boots",
}

TARGET_CUSTOMER_MAP: dict[str, list[str]] = {
    "woman": ["women", "girls"],
    "man": ["men"],
    "kids": ["boys"],
}

COLOR_ALIASES: dict[str, str] = {
    "grey": "gray",
    "dark-grey": "dark-gray",
    "light-grey": "light-gray",
    "navy": "navy-blue",
    "olive-green": "olive",
    "taupe": "beige",
    "camel": "beige",
    "dusty-pink": "dusty-rose",
    "dusty-blue": "sky-blue",
    "offwhite": "off-white",
    "offwhite/cream": "off-white",
    "cream/offwhite": "cream",
    "beige/camel": "beige",
    "nude": "beige",
    "multicolor": "multi",
    "multi-colour": "multi",
    "multi-color": "multi",
}

TYPE_SPECIFIC_ATTR_MAP: dict[str, dict[str, str]] = {
    "dresses": {
        "sleeve": "sleeve_style",
        "neckline": "neckline",
        "fit": "fit_type",
        "hem": "dress_skirt_length",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "tops": {
        "sleeve": "top_sleeve_style",
        "neckline": "top_neckline",
        "fit": "top_fit_type",
        "hem": "top_length",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "bottoms": {
        "fit": "bottom_fit_type",
        "rise": "waist_rise",
        "hem": "bottom_length",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "outerwear": {
        "sleeve": "outerwear_sleeve_style",
        "neckline": "neckline",
        "fit": "outerwear_fit_type",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "activewear": {
        "sleeve": "activewear_sleeve_style",
        "fit": "activewear_fit_type",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "lingerie_sleepwear": {
        "sleeve": "lingerie_sleeve_style",
        "neckline": "neckline",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "suits_formalwear": {
        "fit": "suit_fit_type",
        "pattern": "pattern",
    },
    "abayas": {
        "sleeve": "abaya_sleeve_style",
        "pattern": "pattern",
    },
    "skirts": {
        "fit": "skirt_fit_type",
        "hem": "dress_skirt_length",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "swimwear": {
        "sleeve": "swimwear_sleeve_style",
        "pattern": "pattern",
        "stretch": "stretch_level",
    },
    "scarves_hijabs": {
        "pattern": "pattern",
    },
}

SLEEVE_KEYWORDS: dict[str, str] = {
    "short sleeve": "short",
    "long sleeve": "long",
    "sleeveless": "sleeveless",
    "cap sleeve": "cap",
    "puff sleeve": "puff",
    "3/4 sleeve": "three_quarter",
    "balloon sleeve": "balloon",
    "raglan sleeve": "raglan",
}

PATTERN_KEYWORDS: dict[str, str] = {
    "striped": "striped",
    "floral": "floral",
    "printed": "printed",
    "checked": "checked",
    "polka": "polka_dot",
    "sequin": "sequined",
    "embroidered": "embroidered",
    "lace": "lace",
    "animal print": "animal_print",
    "geometric": "geometric",
    "abstract": "abstract",
}

FIT_KEYWORDS: dict[str, str] = {
    "regular fit": "regular_fit",
    "slim fit": "slim_fit",
    "loose fit": "loose_fit",
    "oversize": "oversized",
    "relaxed fit": "relaxed",
    "relaxed leg": "relaxed",
    "tailored": "tailored",
    "bodycon": "bodycon",
    "a-line": "a_line",
    "empire waist": "empire_waist",
    "high waist": "high_waist",
    "wide leg": "wide_leg",
    "straight leg": "straight_leg",
    "skinny": "slim_fit",
}

NECKLINE_KEYWORDS: dict[str, str] = {
    "v-neck": "v_neck",
    "round neck": "round",
    "collar": "collar",
    "turtleneck": "turtle",
    "halter": "halter",
    "off-shoulder": "off_shoulder",
    "high-neck": "high_neck",
    "mock neck": "mock_neck",
    "square neck": "square",
    "sweetheart": "sweetheart",
}

HEM_KEYWORDS: dict[str, str] = {
    "mini": "mini",
    "midi": "midi",
    "maxi": "maxi",
    "crop": "mini",
    "floor-length": "floor_length",
    "ankle": "ankle",
}

STRETCH_KEYWORDS: dict[str, str] = {
    "stretchy": "moderate",
    "stretch": "moderate",
    "elastic": "moderate",
    "elastane": "moderate",
    "high stretch": "high",
    "extremely stretchy": "high",
    "4-way stretch": "high",
}

WAIST_RISE_KEYWORDS: dict[str, str] = {
    "mid waist": "mid_rise",
    "mid-waist": "mid_rise",
    "high waist": "high_waist",
    "high-waist": "high_waist",
    "low waist": "low_rise",
    "low-waist": "low_rise",
}

CARE_KEYWORDS: dict[str, str] = {
    "machine wash": "machine_wash",
    "hand wash": "hand_wash",
    "do not use bleach": "no_bleach",
    "do not bleach": "no_bleach",
    "iron at a maximum of 110": "iron_low",
    "iron low": "iron_low",
    "do not tumble dry": "no_tumble",
}

KNOWN_MATERIALS: list[str] = [
    "cotton",
    "polyester",
    "silk",
    "wool",
    "linen",
    "denim",
    "leather",
    "velvet",
    "chiffon",
    "lace",
    "satin",
    "jersey",
    "crepe",
    "organza",
    "tulle",
    "nylon",
    "spandex",
    "viscose",
    "polyamide",
    "elastane",
    "lyocell",
    "polyurethane",
    "raffia",
    "acrylic",
    "cashmere",
    "modal",
    "acetate",
    "polypropylene",
    "polyvinyl chloride",
    "hemp",
    "bamboo",
]


SECTION_TO_GENDER: dict[str, str] = {
    "WOMAN": "woman",
    "MAN": "man",
    "KID": "kids",
}

FAMILY_MAP: dict[str, dict[str, str]] = {
    "WOMAN": {
        "CAMISA": "shirts",
        "CAMISETA": "tops",
        "BLUSA": "tops",
        "CAMISOLA": "tops",
        "POLO": "tops",
        "TOPS Y OTRAS P.": "tops",
        "JERSEY": "tops",
        "SUETER": "tops",
        "CARDIGAN": "tops",
        "PULOVER": "tops",
        "VESTIDO": "dresses",
        "MONO": "jumpsuits",
        "BODY": "jumpsuits",
        "PETO": "jumpsuits",
        "PANTALON": "trousers",
        "BERMUDA": "shorts",
        "SHORT": "shorts",
        "PANTALON CORTO": "shorts",
        "JEANS": "jeans",
        "VAQUERO": "jeans",
        "LEGGINGS": "trousers",
        "PANTALON DEPORTIVO": "trousers",
        "FALDA": "skirts",
        "BLAZER": "jackets",
        "CHAQUETA": "jackets",
        "CHALECO": "jackets",
        "CAZADORA": "jackets",
        "AMERICANA": "jackets",
        "ABRIGO": "jackets",
        "PLUMIFERO": "jackets",
        "PARKA": "jackets",
        "IMPERMEABLE": "jackets",
        "SOBRE TODO": "jackets",
        "ZAPATOS": "shoes",
        "SANDALIA TACON": "shoes",
        "SANDALIA PLANA": "shoes",
        "SANDALIA": "shoes",
        "BOTAS": "shoes",
        "BOTIN": "shoes",
        "DEPORTIVO": "shoes",
        "ZAPATILLA": "shoes",
        "ALPARGATA": "shoes",
        "BOLSOS": "accessories",
        "MOCHILA": "accessories",
        "CINTURON": "accessories",
        "PAÑUELO": "accessories",
        "GORRO": "accessories",
        "GAFAS": "accessories",
        "RELOJ": "accessories",
        "BISUTERIA": "accessories",
        "CALCETINES": "accessories",
        "CARTERA": "accessories",
        "MONEDERO": "accessories",
        "PULSERA": "accessories",
        "COLGANTE": "accessories",
        "ANILLO": "accessories",
        "PARAGUAS": "accessories",
        "LLAVERO": "accessories",
        "ANORAK": "jackets",
        "BAÑO": "lingerie",
        "BIKINI": "lingerie",
        "BAÑADOR": "lingerie",
        "BRAGA/CALZONCILLO": "lingerie",
        "CALCETIN": "accessories",
        "CALZADO DEPORTIVO": "shoes",
        "COMPLEMENTOS": "accessories",
        "CONJUNTO": "tops",
        "CORSETERIA": "lingerie",
        "EAU DE PERFUME": "accessories",
        "GABARDINA IMPERMEA": "jackets",
        "LENCERIA": "lingerie",
        "OCIO Y DEPORTE": "accessories",
        "SUDADERA": "tops",
        "SUJETADOR": "lingerie",
        "SWEATSHIRT": "tops",
        "ZAPATO PLANO": "shoes",
        "PAÑOLETAS/FOULARD": "accessories",
        "COSMETICA PELO": "accessories",
    },
    "MAN": {
        "CAMISA": "shirts",
        "CAMISETA": "t-shirts",
        "CAMISOLA": "t-shirts",
        "POLO": "polos",
        "JERSEY": "t-shirts",
        "SUETER": "t-shirts",
        "CARDIGAN": "t-shirts",
        "PULOVER": "t-shirts",
        "SWEATSHIRT": "sweatshirts",
        "SUDADERA": "sweatshirts",
        "PANTALON": "trousers",
        "BERMUDA": "trousers",
        "SHORT": "trousers",
        "PANTALON CORTO": "trousers",
        "JEANS": "jeans",
        "VAQUERO": "jeans",
        "LEGGINGS": "trousers",
        "PANTALON DEPORTIVO": "trousers",
        "BLAZER": "jackets",
        "CHAQUETA": "jackets",
        "CHALECO": "jackets",
        "CAZADORA": "jackets",
        "AMERICANA": "jackets",
        "ABRIGO": "coats",
        "PLUMIFERO": "coats",
        "PARKA": "coats",
        "IMPERMEABLE": "coats",
        "SOBRE TODO": "coats",
        "ZAPATOS": "shoes",
        "SANDALIA TACON": "shoes",
        "SANDALIA PLANA": "shoes",
        "SANDALIA": "shoes",
        "BOTAS": "shoes",
        "BOTIN": "shoes",
        "DEPORTIVO": "shoes",
        "ZAPATILLA": "shoes",
        "ALPARGATA": "shoes",
        "BOLSOS": "accessories",
        "MOCHILA": "accessories",
        "CINTURON": "accessories",
        "PAÑUELO": "accessories",
        "GORRO": "accessories",
        "GAFAS": "accessories",
        "RELOJ": "accessories",
        "BISUTERIA": "accessories",
        "CALCETINES": "accessories",
        "CARTERA": "accessories",
        "MONEDERO": "accessories",
        "PULSERA": "accessories",
        "COLGANTE": "accessories",
        "ANILLO": "accessories",
        "PARAGUAS": "accessories",
        "LLAVERO": "accessories",
        "CONJUNTO": "t-shirts",
        "TRAJE": "suits",
        "BAÑO": "swimwear",
        "CALCETIN": "accessories",
        "BRAGA/CALZONCILLO": "lingerie",
        "ACCESORIOS": "accessories",
        "COMPLEMENTOS": "accessories",
        "SOBRECAMISA": "shirts",
        "EAU DE TOILETTE": "accessories",
        "EAU DE PERFUME": "accessories",
        "GABARDINA IMPERMEA": "coats",
        "CAMISON/PIJAMA": "lingerie",
        "BILLETERAS": "accessories",
        "TIRANTES": "accessories",
        "MONO": "t-shirts",
    },
    "KID": {
        "CAMISA": "boy",
        "CAMISETA": "boy",
        "BLUSA": "boy",
        "CAMISOLA": "boy",
        "POLO": "boy",
        "TOPS Y OTRAS P.": "boy",
        "JERSEY": "boy",
        "SUETER": "boy",
        "CARDIGAN": "boy",
        "PULOVER": "boy",
        "SWEATSHIRT": "boy",
        "SUDADERA": "boy",
        "VESTIDO": "boy",
        "MONO": "boy",
        "BODY": "boy",
        "PETO": "boy",
        "PANTALON": "boy",
        "BERMUDA": "boy",
        "SHORT": "boy",
        "PANTALON CORTO": "boy",
        "JEANS": "boy",
        "VAQUERO": "boy",
        "LEGGINGS": "boy",
        "PANTALON DEPORTIVO": "boy",
        "FALDA": "boy",
        "BLAZER": "boy",
        "CHAQUETA": "boy",
        "CHALECO": "boy",
        "CAZADORA": "boy",
        "AMERICANA": "boy",
        "ABRIGO": "boy",
        "PLUMIFERO": "boy",
        "PARKA": "boy",
        "IMPERMEABLE": "boy",
        "SOBRE TODO": "boy",
        "ZAPATOS": "boy",
        "SANDALIA TACON": "boy",
        "SANDALIA PLANA": "boy",
        "SANDALIA": "boy",
        "BOTAS": "boy",
        "BOTIN": "boy",
        "DEPORTIVO": "boy",
        "ZAPATILLA": "boy",
        "ALPARGATA": "boy",
        "BOLSOS": "boy",
        "MOCHILA": "boy",
        "CINTURON": "boy",
        "PAÑUELO": "boy",
        "GORRO": "boy",
        "GAFAS": "boy",
        "RELOJ": "boy",
        "BISUTERIA": "boy",
        "CALCETINES": "boy",
        "CARTERA": "boy",
        "MONEDERO": "boy",
        "PULSERA": "boy",
        "COLGANTE": "boy",
        "ANILLO": "boy",
        "PARAGUAS": "boy",
        "LLAVERO": "boy",
        "CONJUNTO": "boy",
        "LENCERIA": "boy",
        "CORSETERIA": "boy",
        "BAÑADOR": "boy",
        "BIKINI": "boy",
        "PANTALON BEBE": "boy",
        "JERSEY BEBE": "boy",
        "PRENDA EXT.BEBE": "boy",
        "PETO BEBE": "boy",
        "CHAQUETA BEBE": "boy",
        "FALDA BEBE": "boy",
        "CHALECO BEBE": "boy",
        "BODY BEBE": "boy",
        "GORRO BEBE": "boy",
        "PELELE BEBE": "boy",
        "BERMUDA BEBE": "boy",
        "CAZADORA BEBE": "boy",
        "CAMISA BEBE": "boy",
        "LEGGINGS BEBE": "boy",
        "CHANDAL BEBE": "boy",
        "ZAPATO": "boy",
        "BAMBAS": "boy",
        "BOTA": "boy",
        "CALCETIN": "boy",
        "COMPLEMENTOS": "boy",
        "HOME": "boy",
    },
}

# Zara files beach-capsule fashion under section=HOME with capsule subfamily
# codes (H1:/H2:/H3:). Families listed here are rescued into real categories;
# every other HOME family is genuine Zara Home and left unresolved so the
# crawler can exclude it.
HOME_SECTION = "HOME"

HOME_FAMILY_RESCUE: dict[str, str] = {
    "BOLSOS": "woman/accessories",
    "SANDALIA PLANA": "woman/shoes",
    "ZAPATO PLANO": "woman/shoes",
    "PRENDAS BAÑO": "woman/swimwear",
    "CAMISA/BLUSA": "woman/tops",
    "BERMUDAS/SHORTS": "woman/shorts",
    "PANTALON": "woman/trousers",
}


def _resolve_home_category(family_upper: str, subfamily_upper: str) -> str:
    """Map a HOME-section product to a fashion category, or '' to exclude it."""
    if family_upper in HOME_FAMILY_RESCUE:
        return HOME_FAMILY_RESCUE[family_upper]
    if family_upper == "TOP Y OTRAS P.":
        return "woman/tops" if subfamily_upper == "CAMISETA" else ""
    if family_upper == "PRENDAS BEBE":
        return "kids/swimwear" if subfamily_upper.startswith("BAÑADOR") else "kids/boy"
    if family_upper == "ROPA":
        return "woman/dresses" if subfamily_upper == "VESTIDO" else "woman/shorts"
    if family_upper in ("TEXTIL VARIOS", "BOLSAS Y MOCHILAS"):
        return "kids/boy"
    return ""


def resolve_category_from_analytics(
    section: str,
    family: str,
    subfamily: str = "",
    product_name: str = "",
) -> str:
    """Convert Zara analyticsData section+family to source_category path.

    Uses FAMILY_MAP (gender-aware) for known codes, falls back to keyword
    matching on product_name for unknown families. HOME-section products are
    resolved via the beach-capsule rescue table; everything else under HOME
    returns empty string (genuine Zara Home -> excluded by the crawler).
    """
    section_upper = section.upper().strip()
    family_upper = family.upper().strip()

    if section_upper == HOME_SECTION:
        return _resolve_home_category(family_upper, (subfamily or "").upper().strip())

    gender = SECTION_TO_GENDER.get(section_upper)
    if not gender:
        return ""

    gender_map = FAMILY_MAP.get(section_upper, {})
    sub_path = gender_map.get(family_upper)
    if sub_path:
        cat_key = f"{gender}/{sub_path}"
        if cat_key in CATEGORY_MAP:
            return cat_key

    # Try keyword fallback on product name
    if product_name:
        name_lower = product_name.lower()
        for cat_key in CATEGORY_MAP:
            if not cat_key.startswith(gender):
                continue
            rules = KEYWORD_OVERRIDE_RULES.get(cat_key, [])
            for keyword, *_ in rules:
                if keyword in name_lower:
                    return cat_key

    return ""


def resolve_category(source_category: str, product_name: str = "") -> tuple[str | None, str | None, str | None]:
    name_lower = (product_name or "").lower()

    if not source_category and name_lower:
        for _cat, rules in KEYWORD_OVERRIDE_RULES.items():
            for keyword, root_en, child_en, pt_code in rules:
                if keyword in name_lower:
                    return (root_en, child_en, pt_code)
        return (None, None, None)

    if not source_category:
        return (None, None, None)

    rules = KEYWORD_OVERRIDE_RULES.get(source_category, [])
    if rules and name_lower:
        for keyword, root_en, child_en, pt_code in rules:
            if keyword in name_lower:
                return (root_en, child_en, pt_code)

    direct = CATEGORY_MAP.get(source_category)
    if direct:
        d_root, d_child, d_pt = direct
        if d_child is None and d_root and name_lower:
            child_rules = CHILD_KEYWORD_RULES.get(d_root)
            if child_rules:
                for keyword, child_name in child_rules:
                    if keyword in name_lower:
                        return (d_root, child_name, d_pt)
                d_child = DEFAULT_CHILD.get(d_root)
        return (d_root, d_child, d_pt)

    return (None, None, None)


def normalize_color(color_name: str) -> str:
    return color_name.strip().lower().replace(" ", "-").replace("_", "-")


def get_normalized_color_options() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for zara_code, system_code in COLOR_ALIASES.items():
        zara_norm = normalize_color(zara_code)
        sys_norm = normalize_color(system_code)
        aliases[zara_norm] = sys_norm
    return aliases


def extract_gender(source_category: str) -> str | None:
    if not source_category or "/" not in source_category:
        return None
    return source_category.split("/")[0]


def resolve_target_customer(source_category: str) -> list[str]:
    gender_prefix = extract_gender(source_category)
    if not gender_prefix:
        return []
    return TARGET_CUSTOMER_MAP.get(gender_prefix, [])


def infer_modesty_level(source_category: str) -> str | None:
    if not source_category:
        return None
    cat = source_category.lower()
    if "kids" in cat:
        return "full_coverage"
    if any(x in cat for x in ("lingerie", "swimwear")):
        return "revealing"
    if any(x in cat for x in ("shorts", "skirts")):
        return "minimal"
    if any(x in cat for x in ("accessories", "shoes", "bags", "jewelry", "belts", "watches", "fragrance", "beauty")):
        return None
    return "moderate"


def extract_main_material_from_jsonld(json_ld: dict[str, Any]) -> str | None:
    material = json_ld.get("material")
    if material and isinstance(material, str):
        result = _match_known_material(material)
        if result:
            return result

    additional_props = json_ld.get("additionalProperty", [])
    if not isinstance(additional_props, list):
        return None
    for prop in additional_props:
        name = (prop.get("name", "") or "").lower()
        value = (prop.get("value", "") or "").lower()
        combined = f"{name} {value}"
        result = _match_known_material(combined)
        if result:
            return result
    return None


def extract_fabric_composition_from_jsonld(json_ld: dict[str, Any]) -> str | None:
    additional_props = json_ld.get("additionalProperty", [])
    if not isinstance(additional_props, list):
        return None
    parts: list[str] = []
    seen: set[str] = set()
    for prop in additional_props:
        name = (prop.get("name", "") or "").strip()
        value = (prop.get("value", "") or "").strip()
        combined = f"{name}: {value}" if name and value else (name or value)
        if combined and combined not in seen:
            seen.add(combined)
            parts.append(combined)
    return ", ".join(parts) if parts else None


def extract_main_material_deprecated(materials: list[dict[str, Any]]) -> str | None:
    if not materials:
        return None
    first = materials[0]
    name = first.get("name", first.get("value", ""))
    if not name:
        return None
    name_lower = name.lower()
    for mat in KNOWN_MATERIALS:
        if mat in name_lower:
            return mat
    return None


def extract_sizes(json_ld: dict[str, Any]) -> list[dict[str, Any]]:
    sizes: list[dict[str, Any]] = []
    seen: set[str] = set()
    variants = json_ld.get("hasVariant", [])
    if isinstance(variants, dict):
        variants = [variants]
    for i, v in enumerate(variants):
        size = v.get("size", "")
        if size and size not in seen:
            seen.add(size)
            sizes.append({"size_label": size, "size_system": "EU", "sort_order": i})
    return sizes


def extract_sleeve(name: str) -> str | None:
    return _match_keyword(name, SLEEVE_KEYWORDS)


def extract_pattern(name: str) -> str | None:
    return _match_keyword(name, PATTERN_KEYWORDS)


def extract_fit(name: str) -> str | None:
    return _match_keyword(name, FIT_KEYWORDS)


def extract_neckline(name: str) -> str | None:
    return _match_keyword(name, NECKLINE_KEYWORDS)


def extract_hem(name: str) -> str | None:
    return _match_keyword(name, HEM_KEYWORDS)


def extract_stretch(name: str) -> str | None:
    return _match_keyword(name, STRETCH_KEYWORDS)


def extract_waist_rise(name: str) -> str | None:
    return _match_keyword(name, WAIST_RISE_KEYWORDS)


def extract_care_items(sections: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    if not isinstance(sections, list):
        return items
    for section in sections:
        if not isinstance(section, dict) or section.get("sectionType") != "care":
            continue
        components = section.get("components", [])
        if not isinstance(components, list):
            continue
        for comp in components:
            if not isinstance(comp, dict) or comp.get("datatype") != "iconList":
                continue
            icon_items = comp.get("items", [])
            if not isinstance(icon_items, list):
                continue
            for icon_item in icon_items:
                if not isinstance(icon_item, dict):
                    continue
                desc = icon_item.get("description", {})
                if isinstance(desc, dict):
                    text = desc.get("value", "")
                    if text:
                        items.append(str(text))
    return items


def match_care_instruction(text: str, keywords: dict[str, str] | None = None) -> str | None:
    return _match_keyword(text, keywords or CARE_KEYWORDS)


def get_per_type_attr_code(attr_type: str | None, pt_code: str, default_code: str) -> str:
    if attr_type is None or pt_code is None:
        return default_code
    type_map = TYPE_SPECIFIC_ATTR_MAP.get(pt_code, {})
    return type_map.get(attr_type, default_code)


def get_applicable_types(pt_code: str) -> list[str | None]:
    type_map = TYPE_SPECIFIC_ATTR_MAP.get(pt_code, {})
    extras: list[str | None] = []
    extras.extend(type_map.keys())
    extras.append(None)
    return extras


def _match_known_material(text: str) -> str | None:
    text_lower = text.lower()
    for mat in KNOWN_MATERIALS:
        if mat in text_lower:
            return mat
    return None


def _match_keyword(name: str, keywords: dict[str, str]) -> str | None:
    if not name:
        return None
    name_lower = name.lower()
    for kw, val in keywords.items():
        if kw in name_lower:
            return val
    return None
