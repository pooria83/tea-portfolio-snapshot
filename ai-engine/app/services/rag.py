import math
import re
import unicodedata
from typing import Any, cast

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Modifier,
    PointStruct,
    Prefetch,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import Settings
from app.schemas.chat import ProductRef
from app.services.search_tools import _case_variants

MIN_SCORE_THRESHOLD = 0.3

# Reranking bonus (added to the vector score) when the candidate shares at
# least one color family with the reference product.
SIMILAR_COLOR_FAMILY_BONUS = 0.2

# Reranking bonus (added to the vector score) when a relaxed-tier candidate's
# payload carries a size the user asked for, so size-matching products outrank
# closer vector hits that are not available in the requested size.
SEARCH_SIZE_BONUS = 0.2

# Named sparse vector holding per-point BM25-style term frequencies. Qdrant
# applies the IDF modifier at search time from collection statistics, so no
# external corpus stats are needed (engine-side sparse, no new infra).
SPARSE_VECTOR_NAME = "text_bm25"

# Hybrid dense+sparse query: each prefetch retrieves a wider pool so the
# Reciprocal Rank Fusion (Qdrant's Fusion.RRF, k defaults to 60 server-side)
# has material to merge. Both the fusion strategy and pool size are
# runtime-tunable on RAGService (search quality plan item 7) so golden-set
# eval can pick the best combination.
HYBRID_POOL_MULTIPLIER = 3
HYBRID_POOL_MAX = 100

# Dense cosine score threshold. 0.3 was tuned for Qwen3-0.6B (1024-dim);
# larger models produce more contrastive scores, so the bar relaxes with
# vector size (search quality plan item 2 — verify against eval coverage).
MIN_SCORE_THRESHOLD = 0.3
SCORE_THRESHOLDS_BY_DIM: dict[int, float] = {1024: 0.3, 2560: 0.25}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u0600-\u06FF]+")
_ARABIC_TOKEN_RE = re.compile(r"^[\u0600-\u06FF]+$")

# Function words carry no lexical signal in either language (search quality
# plan item 4). Forms are post-NFKD (hamza/diacritics stripped, lowercase).
_STOPWORDS = frozenset(
    {
        # English
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "so",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "as",
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "may",
        "might",
        "must",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "me",
        "my",
        "we",
        "us",
        "our",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "they",
        "them",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "too",
        "very",
        "just",
        # Arabic (normalized: hamza stripped, so "الى" not "إلى")
        "في",
        "من",
        "على",
        "الى",
        "عن",
        "ان",
        "ما",
        "لا",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "مع",
        "عند",
        "بعد",
        "قبل",
        "بين",
        "حتى",
        "اذا",
        "ثم",
        "قد",
        "هل",
        "لم",
        "لن",
        "لكن",
        "حيث",
        "ايضا",
        "كل",
        "بعض",
        "اي",
        "نحو",
        "التي",
        "الذي",
        "الذين",
        "هو",
        "هي",
        "هم",
        "هن",
        "كان",
        "كانت",
        "يكون",
        "لدى",
        "او",
        "ليس",
        "ليست",
        "فقط",
        "جدا",
    }
)

# Arabic suffix stripper and a very light English stemmer. Both are applied
# identically to stored passages and queries, so matching stays consistent
# (search quality plan item 6 — e.g. فستان/فستانات, dress/dresses).
_AR_SUFFIXES = ("ات", "ين", "ون", "ة", "ه", "ي")


def _stem_english(token: str) -> str:
    if len(token) < 4:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 7:
        return token[:-3]
    if token.endswith("ed") and len(token) > 5:
        return token[:-2]
    if token.endswith("es") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and not token.endswith("us"):
        return token[:-1]
    return token


def _stem_arabic(token: str) -> str:
    if len(token) <= 3:
        return token
    for suffix in _AR_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _stem_token(token: str) -> str:
    if _ARABIC_TOKEN_RE.match(token):
        return _stem_arabic(token)
    if token.isascii() and token.isalpha():
        return _stem_english(token)
    return token


def _tokenize(text: str) -> list[str]:
    """Deterministic multilingual tokenizer for BM25-style sparse scoring.

    Lowercases, normalizes combining marks away (NFKD), splits on
    non-alphanumeric runs keeping English words, digits and Arabic script
    tokens of length >= 2, then applies light stemming (English suffixes,
    Arabic suffixes) and drops function-word stopwords. Applied identically
    to stored passages and queries so sparse indices always align.
    """
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(normalized):
        stem = _stem_token(raw)
        if len(stem) >= 2 and stem not in _STOPWORDS:
            tokens.append(stem)
    return tokens


def _fnv1a(term: str) -> int:
    """FNV-1a 32-bit hash: stable term -> sparse index mapping across restarts."""
    h = 0x811C9DC5
    for b in term.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _sparse_tf_vector(
    tokens: list[str],
    boost_tokens: list[str] | None = None,
    boost_weight: float = 2.0,
) -> SparseVector | None:
    """Build a sparse vector of term frequencies (BM25-style, TF only).

    Values are raw term counts; the collection's ``Modifier.IDF`` makes Qdrant
    weight them by collection-wide inverse document frequency at query time.
    ``boost_tokens`` (e.g. the product name, search quality plan item 5) are
    counted ``boost_weight`` times so the strongest lexical signal ranks
    higher. Indices are sorted and unique as Qdrant requires.
    """
    counts: dict[int, float] = {}
    for t in tokens:
        key = _fnv1a(t)
        counts[key] = counts.get(key, 0.0) + 1.0
    for t in boost_tokens or []:
        key = _fnv1a(t)
        counts[key] = counts.get(key, 0.0) + boost_weight - 1.0
    if not counts:
        return None
    indices = sorted(counts)
    return SparseVector(indices=indices, values=[counts[i] for i in indices])


def _payload_name(payload: dict[str, object] | None, lang: str) -> str | None:
    """Product name for the given point language, from its bilingual payload."""
    if not payload:
        return None
    product_data = payload.get("product_data")
    if not isinstance(product_data, dict):
        return None
    lang_data = product_data.get(lang)
    if not isinstance(lang_data, dict):
        lang_data = product_data.get("en")
    if not isinstance(lang_data, dict):
        return None
    name = lang_data.get("name")
    return str(name) if name else None


def _family_overlap(reference: list[str], payload: dict[str, Any] | None) -> int:
    """Return 1 when the candidate shares a color family with the reference."""
    if not reference:
        return 0
    candidate = [str(v) for v in (payload or {}).get("_color_family", []) if v]
    if not candidate:
        return 0
    return 1 if set(reference) & set(candidate) else 0


def _size_overlap(size_tokens: list[str], payload: dict[str, Any] | None) -> int:
    """Return 1 when the candidate payload lists any of the queried sizes."""
    if not size_tokens:
        return 0
    candidate = [str(v) for v in (payload or {}).get("_size", []) if v]
    if not candidate:
        return 0
    return 1 if set(size_tokens) & set(candidate) else 0


def _vec_stats(query: list[float] | str) -> str:
    """Compact trace stats for a query: dim/norm/head for vectors, id for refs."""
    if isinstance(query, str):
        return f"ref_id={query}"
    norm = math.sqrt(sum(float(v) * float(v) for v in query)) or 0.0
    return f"dim={len(query)} norm={round(norm, 4)} head={query[:5]}"


def _hit_trace(hit: Any) -> str:
    """Render one raw Qdrant hit as a compact trace string (payload + score)."""
    payload = hit.payload or {}
    pid = str(payload.get("product_id") or hit.id)
    score = hit.score if getattr(hit, "score", None) is not None else None
    data = payload.get("product_data") or {}
    en = data.get("en", {}) or {}
    ar = data.get("ar", {}) or {}
    name = en.get("name") or ar.get("name") or payload.get("name_en") or payload.get("name_ar")
    brand = en.get("brand") or payload.get("_brand")
    price = en.get("price") or payload.get("_price")
    family = payload.get("_color_family")
    return f"id={pid} name={name!r} brand={brand!r} price={price} family={family} score={score}"


def _ref_from_hit(hit: Any) -> tuple[str, ProductRef]:
    """Build a ProductRef from one Qdrant hit, returning (product_id, ref)."""
    p = hit.payload or {}
    pid = str(p.get("product_id") or hit.id)
    product_data = cast("dict[str, Any] | None", p.get("product_data"))
    ref = ProductRef(
        id=pid,
        product_data=product_data,
    )
    if product_data:
        lang_data = product_data.get("en", {})
        ref.name = lang_data.get("name") or product_data.get("ar", {}).get("name")
        ref.price = lang_data.get("price")
        ref.currency = lang_data.get("currency", "SAR")
        ref.brand = lang_data.get("brand")
        ref.image_url = lang_data.get("image_url")
        ref.store_id = cast("str | None", product_data.get("store_id"))
    else:
        ref.name = p.get("name_en") or p.get("name_ar") or None
        ref.price = p.get("price")
        ref.currency = p.get("currency", "SAR")
        ref.brand = p.get("brand")
        ref.image_url = p.get("image_url")
    return pid, ref


def _parse_hits(
    results: list[Any],
    seen_ids: set[str] | None = None,
    prefer_lang: str | None = None,
) -> list[ProductRef]:
    """Dedupe scored hits by product id, keeping the best point per product.

    When ``prefer_lang`` is given (search quality plan item 1), a later point
    of the same product whose payload ``lang`` matches is preferred over the
    earlier higher-ranked point, so the retained point's text and vector
    language follows the caller's locale. ``seen_ids`` (shared across search
    tiers) is respected as before.
    """
    out: list[ProductRef] = []
    index: dict[str, int] = {}
    target = prefer_lang.lower() if prefer_lang else None
    for hit in results:
        p = hit.payload or {}
        pid = str(p.get("product_id") or hit.id)
        if seen_ids is not None and pid in seen_ids:
            continue
        idx = index.get(pid)
        if idx is None:
            index[pid] = len(out)
            out.append(_ref_from_hit(hit)[1])
            if seen_ids is not None:
                seen_ids.add(pid)
        elif target and str(p.get("lang", "")).lower() == target:
            out[idx] = _ref_from_hit(hit)[1]
    return out


def _parse_hits_scored(
    results: list[Any],
    seen_ids: set[str] | None = None,
    prefer_lang: str | None = None,
) -> list[tuple[ProductRef, float]]:
    """Like _parse_hits but keeps each hit's vector score for eval tooling."""
    out: list[tuple[ProductRef, float]] = []
    index: dict[str, int] = {}
    target = prefer_lang.lower() if prefer_lang else None
    for hit in results:
        p = hit.payload or {}
        pid = str(p.get("product_id") or hit.id)
        if seen_ids is not None and pid in seen_ids:
            continue
        score = float(hit.score) if getattr(hit, "score", None) is not None else 0.0
        idx = index.get(pid)
        if idx is None:
            parsed = _parse_hits([hit])
            if parsed:
                index[pid] = len(out)
                out.append((parsed[0], score))
                if seen_ids is not None:
                    seen_ids.add(pid)
        elif target and str(p.get("lang", "")).lower() == target:
            parsed = _parse_hits([hit])
            if parsed:
                out[idx] = (parsed[0], score)
    return out


class RAGService:
    def __init__(
        self,
        settings: Settings,
        client: AsyncQdrantClient | None = None,
        hybrid_pool_multiplier: int = HYBRID_POOL_MULTIPLIER,
        hybrid_pool_max: int = HYBRID_POOL_MAX,
        fusion: Fusion = Fusion.RRF,
    ) -> None:
        self.settings = settings
        self.collection = settings.qdrant_collection
        self.dimensions = settings.embedding_dimensions
        self._client = client or AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )
        self._previous_collection: str | None = None
        self._previous_dimensions: int | None = None
        self._sparse_enabled = False
        # Fusion + pool knobs (search quality plan item 7): tunable so the
        # golden-set eval can compare RRF vs DBSF empirically. RRF k stays at
        # Qdrant's default (60) — this qdrant-client build has no k field.
        self.hybrid_pool_multiplier = hybrid_pool_multiplier
        self.hybrid_pool_max = hybrid_pool_max
        self._fusion = fusion
        # Model-aware dense score threshold (search quality plan item 2).
        self.score_threshold = SCORE_THRESHOLDS_BY_DIM.get(self.dimensions, MIN_SCORE_THRESHOLD)

    def set_collection(self, name: str, dimensions: int) -> None:
        """Switch the active collection and expected vector dimensions.

        Used when the embedding model changes at runtime so every subsequent
        operation (upsert, search, ensure) targets the model's own collection.
        The previous (collection, dimensions) are snapshotted so the caller
        can call restore_collection() if the new collection proves unusable.
        """
        self._previous_collection = self.collection
        self._previous_dimensions = self.dimensions
        self.collection = name
        self.dimensions = dimensions
        self.score_threshold = SCORE_THRESHOLDS_BY_DIM.get(dimensions, MIN_SCORE_THRESHOLD)

    def restore_collection(self) -> None:
        """Revert to the collection active before the last set_collection call."""
        if self._previous_collection is None:
            return
        self.collection = self._previous_collection
        self.dimensions = cast("int", self._previous_dimensions)
        self._previous_collection = None
        self._previous_dimensions = None
        logger.info("Restored Qdrant collection: {} (dim={})", self.collection, self.dimensions)

    async def close(self) -> None:
        await self._client.close()

    async def ensure_collection(self) -> None:
        try:
            collections = await self._client.get_collections()
        except Exception:
            logger.exception("Failed to list Qdrant collections")
            raise
        names = [c.name for c in collections.collections]
        if self.collection not in names:
            await self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.dimensions,
                    distance=Distance.COSINE,
                ),
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(
                        modifier=Modifier.IDF,
                        index=SparseIndexParams(on_disk=True),
                    ),
                },
            )
            self._sparse_enabled = True
            logger.info("Created Qdrant collection: {} (dim={}, sparse={})", self.collection, self.dimensions, SPARSE_VECTOR_NAME)
            return

        info = await self._client.get_collection(self.collection)
        vectors_config = info.config.params.vectors
        if vectors_config is None:
            msg = f"Qdrant collection '{self.collection}' has no vector configuration"
            raise RuntimeError(msg)
        if isinstance(vectors_config, dict):
            first = next(iter(vectors_config.values()), None)
            actual_dim = first.size if first else 0
        else:
            actual_dim = vectors_config.size
        if actual_dim != self.dimensions:
            msg = f"Qdrant collection '{self.collection}' has dim={actual_dim} but config expects dim={self.dimensions}. Drop and recreate the collection, then restart."
            raise RuntimeError(msg)

        self._sparse_enabled = False
        sparse_vectors = getattr(info.config.params, "sparse_vectors", None)
        if isinstance(sparse_vectors, dict) and SPARSE_VECTOR_NAME in sparse_vectors:
            self._sparse_enabled = True
        elif isinstance(sparse_vectors, dict):
            try:
                await self._client.update_collection(
                    collection_name=self.collection,
                    sparse_vectors_config={
                        SPARSE_VECTOR_NAME: SparseVectorParams(
                            modifier=Modifier.IDF,
                            index=SparseIndexParams(on_disk=True),
                        ),
                    },
                )
                self._sparse_enabled = True
                logger.info("Added sparse vector '{}' to collection '{}'", SPARSE_VECTOR_NAME, self.collection)
            except Exception:
                logger.exception(
                    "Failed to add sparse vector '{}' to collection '{}' — hybrid search disabled",
                    SPARSE_VECTOR_NAME,
                    self.collection,
                )

        logger.info(
            "Qdrant collection '{}' ready (dim={}, sparse_enabled={})",
            self.collection,
            self.dimensions,
            self._sparse_enabled,
        )

    async def upsert_product(
        self,
        product_id: str,
        vector: list[float],
        payload: dict[str, object],
    ) -> None:
        await self._client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=product_id, vector=vector, payload=payload)],
        )

    async def upsert_embedding(
        self,
        point_id: str,
        vector: list[float],
        product_id: str,
        lang: str,
        text: str,
        payload: dict[str, object] | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> None:
        data: dict[str, object] = {
            "product_id": product_id,
            "lang": lang,
            "text": text,
        }
        if payload:
            data["product_data"] = payload
        if filters:
            data.update(filters)
        sparse = None
        if self._sparse_enabled:
            name = _payload_name(payload, lang)
            sparse = _sparse_tf_vector(_tokenize(text), boost_tokens=_tokenize(name) if name else None)
        vector_arg: list[float] | dict[str, list[float] | SparseVector] = vector
        if sparse is not None:
            vector_arg = {"": vector, SPARSE_VECTOR_NAME: sparse}
        await self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=cast("Any", vector_arg),
                    payload=data,
                ),
            ],
        )

    async def _query_hits(
        self,
        query: list[float] | str,
        limit: int,
        qdrant_filter: Filter | None = None,
        query_text: str | None = None,
    ) -> list[Any]:
        """Run query_points and return the raw scored hits (payload + score).

        When ``query_text`` is given and the collection has the BM25 sparse
        vector configured, runs hybrid dense+sparse retrieval fused with
        Reciprocal Rank Fusion (k=60) so lexical matches the dense path missed
        can still surface. Otherwise the dense path is used unchanged.
        """
        if query_text and self._sparse_enabled and not isinstance(query, str):
            tokens = _tokenize(query_text)
            sparse = _sparse_tf_vector(tokens)
            if sparse is not None:
                return await self._query_hits_hybrid(query, sparse, limit, qdrant_filter, query_text)
        try:
            results = await self._client.query_points(
                collection_name=self.collection,
                query=query,
                limit=limit + 5,
                with_payload=True,
                query_filter=qdrant_filter,
                score_threshold=self.score_threshold,
            )
            points = list(results.points)
            logger.info(
                "TRACE_QDRANT_HITS collection={} query={} filter={} requested_limit={} count={} hits={}",
                self.collection,
                _vec_stats(query),
                qdrant_filter,
                limit,
                len(points),
                ", ".join(_hit_trace(h) for h in points) or "none",
            )
            return points
        except Exception:
            logger.exception("Qdrant query_points failed")
            return []

    async def _query_hits_hybrid(
        self,
        query: list[float],
        sparse: SparseVector,
        limit: int,
        qdrant_filter: Filter | None,
        query_text: str,
    ) -> list[Any]:
        """Run dense+sparse prefetch queries fused with Fusion.RRF / DBSF.

        The fusion strategy, RRF ``k`` and pool size are instance knobs
        (search quality plan item 7) so golden-set eval can tune them.
        """
        try:
            pool = min(limit * self.hybrid_pool_multiplier, self.hybrid_pool_max)
            results = await self._client.query_points(
                collection_name=self.collection,
                prefetch=[
                    Prefetch(
                        query=query,
                        using="",
                        limit=pool,
                        filter=qdrant_filter,
                        score_threshold=self.score_threshold,
                    ),
                    Prefetch(
                        query=sparse,
                        using=SPARSE_VECTOR_NAME,
                        limit=pool,
                        filter=qdrant_filter,
                    ),
                ],
                query=FusionQuery(fusion=self._fusion),
                limit=limit + 5,
                with_payload=True,
            )
            points = list(results.points)
            logger.info(
                "TRACE_QDRANT_HITS_HYBRID collection={} query_text={!r} filter={} requested_limit={} pool={} count={} hits={}",
                self.collection,
                query_text,
                qdrant_filter,
                limit,
                pool,
                len(points),
                ", ".join(_hit_trace(h) for h in points) or "none",
            )
            return points
        except Exception:
            logger.exception("Qdrant hybrid query_points failed")
            return []

    async def _query_scored(
        self,
        query: list[float] | str,
        limit: int,
        qdrant_filter: Filter | None = None,
        query_text: str | None = None,
        prefer_lang: str | None = None,
    ) -> list[tuple[ProductRef, float]]:
        return _parse_hits_scored(
            await self._query_hits(query, limit, qdrant_filter, query_text),
            prefer_lang=prefer_lang,
        )

    @staticmethod
    def _dedupe_fill_scored(
        hits: list[tuple[ProductRef, float]],
        products: list[tuple[ProductRef, float]],
        seen: set[str],
        limit: int,
    ) -> bool:
        """Append hits whose product id is not already ``seen``, stopping at ``limit``.

        Returns True when ``limit`` is reached.
        """
        for product, score in hits:
            if product.id in seen:
                continue
            seen.add(product.id)
            products.append((product, score))
            if len(products) >= limit:
                return True
        return False

    async def _fill_with_size_boost_scored(
        self,
        vector: list[float],
        limit: int,
        seen_ids: set[str],
        size_tokens: list[str],
        relaxed_filters: list[Filter],
        query_text: str | None = None,
        prefer_lang: str | None = None,
    ) -> list[tuple[ProductRef, float]]:
        """Fill to ``limit`` from relaxed tiers, ranking size-matching hits higher.

        Scored variant of the former ``_fill_with_size_boost``: same relaxed
        tiers (color-only, then unfiltered) drop the size condition, candidates
        are ranked with an additive ``SEARCH_SIZE_BONUS`` when their payload
        lists any queried size, but the returned ``(ProductRef, score)`` pairs
        keep the raw vector score so eval tooling can rank and compute metrics.
        """
        candidates: list[tuple[float, Any]] = []
        candidates_seen: set[str] = set(seen_ids)

        def merge(hits: list[Any]) -> bool:
            for hit in hits:
                hit_payload = hit.payload or {}
                pid = str(hit_payload.get("product_id") or hit.id)
                if pid in candidates_seen:
                    continue
                candidates_seen.add(pid)
                score = float(hit.score) if hit.score is not None else 0.0
                candidates.append((score, hit))
            candidates.sort(
                key=lambda item: item[0] + SEARCH_SIZE_BONUS * _size_overlap(size_tokens, item[1].payload),
                reverse=True,
            )
            return len(candidates) >= limit

        for qdrant_filter in relaxed_filters:
            logger.info("SEARCH_SIZE_TIER remaining={}", limit)
            if merge(await self._query_hits(vector, limit, qdrant_filter, query_text)):
                return _parse_hits_scored([hit for _, hit in candidates[:limit]], prefer_lang=prefer_lang)

        logger.info("SEARCH_FALLBACK remaining={}", limit)
        merge(await self._query_hits(vector, limit, query_text=query_text))
        logger.info("SEARCH_FALLBACK_RESULTS total={}", len(candidates))
        return _parse_hits_scored([hit for _, hit in candidates[:limit]], prefer_lang=prefer_lang)

    async def search_scored(
        self,
        vector: list[float],
        limit: int = 10,
        filters: dict[str, list[str]] | None = None,
        query_text: str | None = None,
        prefer_lang: str | None = None,
    ) -> list[tuple[ProductRef, float]]:
        """Filtered search returning ``(ProductRef, score)`` pairs for eval tooling.

        Mirrors ``search`` exactly (same tiering and dedup) but keeps the raw
        vector score per hit so eval endpoints can rank results and compute
        MRR/Recall without re-querying Qdrant. ``search`` delegates here and
        discards the scores. ``query_text`` opts into hybrid dense+sparse
        retrieval (Fusion.RRF/DBSF, see constructor knobs) when the collection
        supports it. ``prefer_lang`` (search quality plan item 1) makes dedupe
        keep the point whose payload ``lang`` matches the caller's locale.
        """
        if filters:
            normalized = {f"_{k}" if not k.startswith("_") else k: v for k, v in filters.items()}
            must_conditions = [FieldCondition(key=key, match=MatchAny(any=values)) for key, values in normalized.items() if values]
            if must_conditions:
                qdrant_filter = Filter(must=cast("list[Any]", must_conditions))
                logger.info("SEARCH_FILTERED filters={}", filters)
                products = await self._query_scored(vector, limit, qdrant_filter, query_text, prefer_lang)
                logger.info("SEARCH_FILTERED_RESULTS count={} limit={}", len(products), limit)
                if len(products) >= limit:
                    return products

                remaining = limit - len(products)
                seen_ids = {p.id for p, _ in products}
                size_tokens = normalized.get("_size") or []
                if size_tokens:
                    relaxed: list[Filter] = []
                    color_values = normalized.get("_color_family") or normalized.get("_color") or []
                    if color_values:
                        color_key = "_color_family" if normalized.get("_color_family") else "_color"
                        relaxed.append(Filter(must=[FieldCondition(key=color_key, match=MatchAny(any=color_values))]))
                    filled = await self._fill_with_size_boost_scored(vector, remaining, seen_ids, size_tokens, relaxed, query_text, prefer_lang)
                    return [*products, *filled]

                # Color tier: relax the AND of all filters to color alone before
                # dropping every constraint, so the fallback is not color-blind.
                color_values = normalized.get("_color_family") or normalized.get("_color") or []
                if color_values:
                    color_key = "_color_family" if normalized.get("_color_family") else "_color"
                    color_filter = Filter(must=[FieldCondition(key=color_key, match=MatchAny(any=color_values))])
                    logger.info("SEARCH_COLOR_TIER remaining={}", remaining)
                    if self._dedupe_fill_scored(await self._query_scored(vector, remaining, color_filter, query_text, prefer_lang), products, seen_ids, limit):
                        return products
                    remaining = limit - len(products)

                logger.info("SEARCH_FALLBACK remaining={}", remaining)
                self._dedupe_fill_scored(await self._query_scored(vector, remaining, None, query_text, prefer_lang), products, seen_ids, limit)
                logger.info("SEARCH_FALLBACK_RESULTS total={}", len(products))
                return products

        logger.info("SEARCH_UNFILTERED limit={}", limit)
        products = await self._query_scored(vector, limit, None, query_text, prefer_lang)
        logger.info("SEARCH_UNFILTERED_RESULTS count={}", len(products))
        return products

    async def search(
        self,
        vector: list[float],
        limit: int = 10,
        filters: dict[str, list[str]] | None = None,
        query_text: str | None = None,
        prefer_lang: str | None = None,
    ) -> list[ProductRef]:
        scored = await self.search_scored(vector, limit, filters, query_text, prefer_lang)
        return [product for product, _ in scored]

    async def similar(
        self,
        product_id: str,
        limit: int = 10,
        categories: list[list[str]] | None = None,
        lang: str = "en",
    ) -> list[ProductRef]:
        """Find products similar to an already-indexed product.

        Metadata-aware: candidates are first constrained to the reference
        product's category chain (leaf -> parent -> root) when provided,
        falling back to the reference payload's own ``_category`` so the hard
        filter is guaranteed non-empty, then relaxed to the same color family
        (category-constrained to avoid off-category leaks), then to unfiltered
        vector search. Filled slots are deduped and the reference is excluded.
        Final ranking: color-family overlap bonus.

        The reference point is chosen deterministically: when multiple points
        share ``product_id`` (one per language), the point whose payload
        ``lang`` matches the requested ``lang`` is preferred so the query
        vector comes from the same language as the caller.
        """
        try:
            scroll = await self._client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]),
                limit=5,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            logger.exception("Qdrant scroll failed product_id={}", product_id)
            return []
        points = scroll[0]
        if not points:
            logger.info("SIMILAR_PRODUCT_NOT_FOUND product_id={}", product_id)
            return []
        reference = next(
            (p for p in points if str((p.payload or {}).get("lang", "")).lower() == lang.lower()),
            points[0],
        )
        reference_id = str(reference.id)
        payload = reference.payload or {}
        reference_product_id = str(payload.get("product_id") or reference_id)
        ref_categories = [str(v) for v in payload.get("_category", []) if v]
        ref_families = [str(v) for v in payload.get("_color_family", []) if v]
        logger.info(
            "TRACE_SIMILAR_SCROLL product_id={} lang={} points={} reference_id={} ref_product={} categories={} color_family={}",
            product_id,
            lang,
            len(points),
            reference_id,
            reference_product_id,
            ref_categories,
            ref_families,
        )

        levels: list[list[str]] = []
        for level in categories or []:
            values = _case_variants(level)
            if values and values not in levels:
                levels.append(values)
        if ref_categories:
            ref_values = _case_variants(ref_categories)
            if ref_values and ref_values not in levels:
                levels.append(ref_values)

        seen: set[str] = set()
        candidates: list[tuple[float, Any]] = []

        def merge(hits: list[Any]) -> None:
            for hit in hits:
                hit_payload = hit.payload or {}
                pid = str(hit_payload.get("product_id") or hit.id)
                if pid in (product_id, reference_product_id) or pid in seen:
                    continue
                seen.add(pid)
                score = float(hit.score) if hit.score is not None else 0.0
                candidates.append((score, hit))

        for values in levels:
            qdrant_filter = Filter(must=[FieldCondition(key="_category", match=MatchAny(any=values))])
            merge(await self._query_hits(reference_id, limit, qdrant_filter))
            if len(candidates) >= limit:
                break

        if len(candidates) < limit and ref_families:
            must_conditions: list[Any] = [FieldCondition(key="_color_family", match=MatchAny(any=ref_families))]
            for values in levels:
                must_conditions.append(FieldCondition(key="_category", match=MatchAny(any=values)))
            qdrant_filter = Filter(must=must_conditions)
            merge(await self._query_hits(reference_id, limit, qdrant_filter))

        if len(candidates) < limit:
            merge(await self._query_hits(reference_id, limit))

        candidates.sort(
            key=lambda item: item[0] + SIMILAR_COLOR_FAMILY_BONUS * _family_overlap(ref_families, item[1].payload),
            reverse=True,
        )
        top_hits = [hit for _, hit in candidates[:limit]]
        logger.info(
            "TRACE_SIMILAR_RESULTS reference_id={} product_id={} count={} products={}",
            reference_id,
            product_id,
            len(top_hits),
            ", ".join(_hit_trace(h) for h in top_hits) or "none",
        )
        return _parse_hits(top_hits)

    @staticmethod
    def format_products_for_prompt(products: list[ProductRef], locale: str = "en") -> str:
        lines: list[str] = []
        for i, p in enumerate(products, 1):
            if p.product_data:
                lang_data = p.product_data.get(locale, p.product_data.get("en", {}))
                parts: list[str] = [f"{i}. {p.name or 'Unnamed'}"]
                if p.brand:
                    parts.append(f"Brand: {p.brand}")
                if p.price is not None:
                    parts.append(f"Price: {p.price} {p.currency}")

                cat = lang_data.get("category", {})
                cat_name = cat.get("name") if isinstance(cat, dict) else (str(cat) if cat else None)
                if cat_name:
                    parts.append(f"Category: {cat_name}")

                attrs = lang_data.get("attributes", [])
                if attrs:
                    attr_strs: list[str] = []
                    for a in attrs:
                        if isinstance(a, dict):
                            an = a.get("name", "")
                            av = a.get("value", "")
                            if an and av:
                                attr_strs.append(f"{an}: {av}")
                    if attr_strs:
                        parts.append(f"Attributes: {' | '.join(attr_strs)}")

                sizes = lang_data.get("available_sizes")
                if sizes:
                    parts.append(f"Sizes: {', '.join(str(s) for s in sizes)}")

                lines.append("  ".join(parts))
            else:
                parts = [f"{i}. {p.name or 'Unnamed'}"]
                if p.brand:
                    parts.append(f"- {p.brand}")
                if p.price is not None:
                    parts.append(f"- {p.price} {p.currency}")
                lines.append(" ".join(parts))
        return "\n".join(lines)
