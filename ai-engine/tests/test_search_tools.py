from app.services.search_tools import (
    SEARCH_PRODUCTS_TOOL,
    _size_variants,
    inject_color_filter,
    normalize_filters,
)


def test_size_variants_letters() -> None:
    assert _size_variants(["M", "XL", "XS", "XXL"]) == ["m", "xl", "xs", "xxl"]


def test_size_variants_words_collapse_to_canonical() -> None:
    assert _size_variants(["Medium", "Extra Large"]) == ["m", "medium", "xl", "extra large"]


def test_size_variants_numeric() -> None:
    assert _size_variants(["42", "40.5"]) == ["42", "40.5"]


def test_size_variants_system_prefixed() -> None:
    assert _size_variants(["EU 42", "US 8.5"]) == ["42", "eu:42", "8.5", "us:8.5"]


def test_size_variants_one_size() -> None:
    assert _size_variants(["One Size", "OS"]) == ["one size", "os"]


def test_size_variants_dedupes_and_lowercases() -> None:
    assert _size_variants(["M", "m", " M "]) == ["m"]


def test_size_variants_empty_and_freeform() -> None:
    assert _size_variants(["", "longline", "   "]) == ["longline"]


def test_normalize_filters_size() -> None:
    assert normalize_filters({"size": ["M"]}) == {"size": ["m"]}
    assert normalize_filters({"size": ["EU 42"]}) == {"size": ["42", "eu:42"]}


def test_normalize_filters_size_kept_with_other_filters() -> None:
    result = normalize_filters({"category": ["Dresses"], "size": ["Medium"]})
    assert result == {"category": ["Dresses", "dresses", "DRESSES"], "size": ["m", "medium"]}


def test_search_tool_schema_includes_size() -> None:
    props = SEARCH_PRODUCTS_TOOL["function"]["parameters"]["properties"]["filters"]["properties"]
    assert "size" in props
    assert props["size"]["type"] == "array"


def test_normalize_filters_none_returns_none() -> None:
    assert normalize_filters(None) is None
    assert normalize_filters({}) is None


def test_normalize_filters_gender_dedupe_preserves_order() -> None:
    result = normalize_filters({"gender": ["men", "Male", "man", "male"]})
    assert result == {"gender": ["men"]}


def test_normalize_filters_gender_arabic() -> None:
    assert normalize_filters({"gender": ["رجال"]}) == {"gender": ["men"]}
    assert normalize_filters({"gender": ["نساء"]}) == {"gender": ["women"]}


def test_normalize_filters_color_family_first_no_duplicates() -> None:
    result = normalize_filters({"color_family": ["reds-pinks"], "color": ["Red"]})
    assert result == {"color_family": ["reds-pinks"]}


def test_normalize_filters_merges_concrete_color_with_different_explicit_family() -> None:
    result = normalize_filters({"color_family": ["blues"], "color": ["Red"]})
    assert result == {"color_family": ["blues", "reds-pinks"]}


def test_normalize_filters_reverse_order_merges_identically() -> None:
    forward = normalize_filters({"color_family": ["blues"], "color": ["Red"]})
    reverse = normalize_filters({"color": ["Red"], "color_family": ["blues"]})
    assert forward is not None and reverse is not None
    assert set(forward["color_family"]) == set(reverse["color_family"]) == {"blues", "reds-pinks"}


def test_normalize_filters_multi_concrete_colors_deduped() -> None:
    result = normalize_filters({"color": ["Red", "rose", "red"], "color_family": ["reds-pinks"]})
    assert result == {"color_family": ["reds-pinks"]}


def test_normalize_filters_case_variants_for_material() -> None:
    result = normalize_filters({"material": ["cotton"]})
    assert result == {"material": ["cotton", "Cotton", "COTTON"]}


def test_inject_color_filter_adds_family_when_filters_none() -> None:
    assert inject_color_filter("green lace dress", None) == {"color_family": ["greens"]}


def test_inject_color_filter_preserves_existing_filters() -> None:
    result = inject_color_filter("green lace dress", {"material": ["Lace"]})
    assert result == {"color_family": ["greens"], "material": ["Lace"]}


def test_inject_color_filter_never_overrides_existing_color() -> None:
    filters = {"color": ["green"]}
    assert inject_color_filter("green dress", filters) is filters


def test_inject_color_filter_never_overrides_existing_family() -> None:
    filters = {"color_family": ["blues"]}
    assert inject_color_filter("navy dress", filters) is filters


def test_inject_color_filter_no_color_word_returns_input() -> None:
    assert inject_color_filter("cotton dress", None) is None
    filters = {"material": ["Cotton"]}
    assert inject_color_filter("cotton dress", filters) is filters


def test_inject_color_filter_case_insensitive() -> None:
    assert inject_color_filter("I want a GREEN dress", None) == {"color_family": ["greens"]}


def test_inject_color_filter_multiword_color() -> None:
    assert inject_color_filter("royal blue dress", None) == {"color_family": ["blues"]}
    assert inject_color_filter("navy blue jacket", None) == {"color_family": ["blues"]}


def test_inject_color_filter_word_boundary() -> None:
    assert inject_color_filter("golden retriever shirt", None) is None
