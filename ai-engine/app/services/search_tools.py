"""Search tool schema, normalization maps, and filter normalization."""

import re
from typing import Any

GENDER_NORMALIZE_MAP: dict[str, str] = {
    "male": "men",
    "men": "men",
    "man": "men",
    "female": "women",
    "women": "women",
    "woman": "women",
    "girls": "girls",
    "girl": "girls",
    "boys": "boys",
    "boy": "boys",
    "babies": "babies",
    "baby": "babies",
    "kids": "kids",
    "child": "kids",
    "children": "kids",
    "unisex": "unisex",
    "رجال": "men",
    "نساء": "women",
    "بنات": "girls",
    "أولاد": "boys",
    "اولاد": "boys",
    "أطفال": "kids",
    "اطفال": "kids",
    "رضع": "babies",
    "للجنسين": "unisex",
}

COLOR_FAMILY_MAP: dict[str, list[str]] = {
    "red": ["reds-pinks"],
    "pink": ["reds-pinks"],
    "rose": ["reds-pinks"],
    "maroon": ["reds-pinks"],
    "burgundy": ["reds-pinks"],
    "crimson": ["reds-pinks"],
    "coral": ["reds-pinks"],
    "orange": ["yellows-oranges"],
    "orange-red": ["reds-pinks"],
    "gold": ["metallics"],
    "silver": ["metallics"],
    "copper": ["metallics"],
    "bronze": ["metallics"],
    "yellow": ["yellows-oranges"],
    "lemon": ["yellows-oranges"],
    "olive": ["greens"],
    "lime": ["greens"],
    "green": ["greens"],
    "teal": ["blues"],
    "turquoise": ["blues"],
    "cyan": ["blues"],
    "blue": ["blues"],
    "navy": ["blues"],
    "royal blue": ["blues"],
    "indigo": ["purples"],
    "purple": ["purples"],
    "violet": ["purples"],
    "magenta": ["purples"],
    "lavender": ["purples"],
    "mauve": ["purples"],
    "black": ["blacks-grays"],
    "gray": ["blacks-grays"],
    "grey": ["blacks-grays"],
    "white": ["whites-creams"],
    "cream": ["whites-creams"],
    "ivory": ["whites-creams"],
    "beige": ["beiges-browns"],
    "brown": ["beiges-browns"],
    "tan": ["beiges-browns"],
    "camel": ["beiges-browns"],
    "taupe": ["beiges-browns"],
    "chestnut": ["beiges-browns"],
    "blush": ["reds-pinks"],
    "moccasin": ["beiges-browns"],
    "nude": ["whites-creams"],
    "peach": ["yellows-oranges"],
    "mint": ["blues"],
    "multicolor": ["specialty"],
    "printed": ["specialty"],
    "مطبوع": ["specialty"],
}

COLOR_FAMILY_NAMES: set[str] = {family for families in COLOR_FAMILY_MAP.values() for family in families}

COLOR_FAMILY_ENUM: list[str] = [
    "reds-pinks",
    "blues",
    "greens",
    "yellows-oranges",
    "purples",
    "blacks-grays",
    "whites-creams",
    "beiges-browns",
    "metallics",
    "specialty",
]

_SIZE_WORD_MAP: dict[str, str] = {
    "small": "s",
    "medium": "m",
    "large": "l",
    "extra large": "xl",
    "x large": "xl",
    "extra small": "xs",
    "x small": "xs",
    "one size": "one size",
    "os": "one size",
    "free size": "one size",
    "free": "one size",
    "adjustable": "one size",
    "standard": "one size",
    "standard size": "one size",
}

_SIZE_LETTER_RE = re.compile(r"^(?:x{1,3})?[sml]$")


def _size_variants(values: list[str]) -> list[str]:
    """Normalize size filter values to canonical lowercase tokens.

    Mirrors the payload ``_size`` tokens written by the API embed step, so a
    user request like ``size M`` or ``EU 42`` hits the stored canonical tokens
    exactly. Letters/words collapse (``M``/``medium`` -> ``m``), free sizes
    collapse to ``one size``, numeric sizes stay raw, and system-prefixed
    values expand to both the bare number and the system-tagged form
    (``EU 42`` -> ``["42", "eu:42"]``).
    """
    tokens: list[str] = []
    for val in values:
        raw = " ".join(str(val).strip().lower().split())
        if not raw:
            continue
        mapped = _SIZE_WORD_MAP.get(raw)
        if mapped:
            tokens.extend([mapped, raw])
            continue
        if _SIZE_LETTER_RE.fullmatch(raw):
            tokens.append(raw)
            continue
        prefixed = re.fullmatch(r"([a-z]{2})\s+(\d+(?:[.,]\d+)?)", raw)
        if prefixed:
            sys_name, num = prefixed.group(1), prefixed.group(2)
            tokens.extend([num, f"{sys_name}:{num}"])
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?", raw):
            tokens.append(raw)
            continue
        tokens.append(raw)
    return list(dict.fromkeys(tokens))


SEARCH_PRODUCTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": (
            "Search the fashion product catalog for items matching the user's request. "
            "Resolve implicit references before calling: e.g. 'the red dress I mentioned' "
            "becomes query 'red dress'; 'shorter' adds a length filter; 'that same brand' "
            "carries the brand forward. Keep the query concise for vector similarity search. "
            "IMPORTANT: whenever the user explicitly mentions an attribute (color, material, "
            "category, brand, gender, size), include it BOTH in the query (kept for vector "
            "similarity) AND in the matching 'filters' key below — never omit filters for an "
            "explicitly mentioned attribute. Example: user: 'i want a green lace dress in size M' → "
            'query: "green lace dress size M", filters: {"color": ["green"], "category": ["Dresses"], "size": ["M"]}'
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product search query, with attribute words kept for vector similarity (e.g. 'green lace dress')",
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "Exact filters for attributes the user explicitly mentioned. Always include a "
                        "color filter when a color is mentioned: put the exact color word in 'color' "
                        "(e.g. green) — the engine maps it to a family bucket. Also fill material, "
                        "category, brand, gender, size when mentioned. Optional keys: color, material, "
                        "category, brand, gender, color_family, size."
                    ),
                    "properties": {
                        "color": {"type": "array", "items": {"type": "string"}},
                        "material": {"type": "array", "items": {"type": "string"}},
                        "category": {"type": "array", "items": {"type": "string"}},
                        "brand": {"type": "array", "items": {"type": "string"}},
                        "gender": {"type": "array", "items": {"type": "string", "enum": ["men", "women", "girls", "boys", "babies", "kids", "unisex"]}},
                        "color_family": {
                            "type": "array",
                            "items": {"type": "string", "enum": COLOR_FAMILY_ENUM},
                            "description": "Family bucket for a color (greens, reds-pinks, blues, ...). Prefer the exact word in 'color'; use this only for family-level requests.",
                        },
                        "size": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exact size labels the user asked for, as the user said them (e.g. ['M'], ['XL'], ['42'], ['EU 42'], ['One Size']).",
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["query"],
        },
    },
}


def _case_variants(values: list[str]) -> list[str]:
    """Expand filter values with common casings so MatchAny matches payload display values."""
    variants: list[str] = []
    for val in values:
        stripped = val.strip()
        if not stripped:
            continue
        variants.extend([stripped, stripped.lower(), stripped.title(), stripped.upper()])
    return list(dict.fromkeys(variants))


def _expand_color_families(values: list[str]) -> list[str]:
    """Accept family names as-is, expand concrete colors to their family buckets."""
    expanded: list[str] = []
    for val in values:
        color_val = val.strip().lower()
        families = COLOR_FAMILY_MAP.get(color_val)
        if families:
            expanded.extend(families)
        elif color_val in COLOR_FAMILY_NAMES:
            expanded.append(color_val)
    return list(dict.fromkeys(expanded))


def _normalize_color_filter(values: list[str]) -> tuple[list[str], list[str]]:
    """Map concrete colors to family buckets; unknown colors kept as case-variant exact values.

    Returns ``(families, exact_values)``. The caller merges ``families`` into
    the ``color_family`` filter and keeps ``exact_values`` as the ``color``
    filter (or drops color entirely when any family was mapped).
    """
    families: list[str] = []
    exact: list[str] = []
    for val in values:
        mapped = COLOR_FAMILY_MAP.get(val.strip().lower())
        if mapped:
            families.extend(mapped)
        else:
            exact.append(val)
    return families, _case_variants(exact)


_color_pattern: re.Pattern[str] | None = None


def _color_word_pattern() -> re.Pattern[str]:
    """Compile once: match any known color word at word boundaries, longest first."""
    global _color_pattern
    if _color_pattern is None:
        keys = sorted(COLOR_FAMILY_MAP, key=len, reverse=True)
        _color_pattern = re.compile(
            r"(?<![a-z])(" + "|".join(re.escape(k) for k in keys) + r")(?![a-z])",
            re.IGNORECASE,
        )
    return _color_pattern


def inject_color_filter(
    query: str,
    filters: dict[str, list[str]] | None,
) -> dict[str, list[str]] | None:
    """Guarantee an explicit color-family filter when the query mentions a known
    color word but no color/color_family filter was emitted.

    Safety net for the tool-calling and parse-fallback paths: even if the model
    skips ``filters`` for a color it put in the query, the search still filters
    on the exact family bucket instead of relying on vector similarity alone.
    Existing ``color``/``color_family`` filters are never overridden.
    """
    if not query or (filters and (filters.get("color") or filters.get("color_family"))):
        return filters
    match = _color_word_pattern().search(query)
    if match is None:
        return filters
    families = COLOR_FAMILY_MAP.get(match.group(1).lower())
    if not families:
        return filters
    merged = dict(filters or {})
    merged["color_family"] = list(dict.fromkeys(merged.get("color_family", []) + families))
    return merged


def normalize_filters(raw_filters: dict[str, object] | None) -> dict[str, list[str]] | None:
    """Normalize raw filter values into typed, case-variant filter lists.

    Shared by the tool-calling path (search_products arguments) and the
    parse fallback path (LLM-rewritten query filters). Concrete colors are
    mapped to their ``color_family`` buckets and merged with any explicit
    ``color_family`` values (order-independent), then every list is deduped
    preserving first-seen order.
    """
    if not raw_filters:
        return None
    typed: dict[str, list[str]] = {}
    for k, v in raw_filters.items():
        if isinstance(v, list):
            values = [str(x) for x in v if x]
        elif isinstance(v, str):
            values = [v]
        else:
            values = []
        if k == "gender":
            normalized: list[str] = []
            for val in values:
                mapped = GENDER_NORMALIZE_MAP.get(val.strip().lower())
                if mapped and mapped not in normalized:
                    normalized.append(mapped)
            values = normalized
        if k == "size":
            values = _size_variants(values)
        if k == "color":
            families, exact = _normalize_color_filter(values)
            if families:
                typed.setdefault("color_family", []).extend(families)
                values = []
            else:
                values = exact
        if k == "color_family":
            expanded = _expand_color_families(values)
            merged = list(dict.fromkeys(typed.get("color_family", []) + expanded))
            if merged:
                typed["color_family"] = merged
            values = []
        if k in ("material", "category", "brand") and values:
            values = _case_variants(values)
        if values:
            typed[k] = values
    for key, vals in list(typed.items()):
        typed[key] = list(dict.fromkeys(vals))
    if "color_family" in typed:
        typed.pop("color", None)
    return typed or None


def normalize_tool_args(args: dict[str, Any]) -> tuple[str, dict[str, list[str]] | None]:
    """Validate and normalize search_products arguments into (query, filters)."""
    raw_query = args.get("query")
    query = str(raw_query).strip() if raw_query else ""
    filters = normalize_filters(args.get("filters"))
    return (query, filters)
