"""Centralized LLM prompts for the chat/description/summary flows."""

DESCRIPTION_SYSTEM_PROMPT = (
    "You are a product description writer for a fashion e-commerce platform.\n"
    "Generate a compelling short product description (2-3 sentences) in English and Arabic.\n"
    'Return ONLY valid JSON with keys "en" and "ar".\n\n'
    "Product:\n{product_text}\n\n"
    "Requirements:\n"
    "- Highlight key features (material, fit, occasion/style)\n"
    "- Arabic: natural phrasing, not translated-sounding\n"
    "- Professional but approachable tone\n"
    "- Do NOT invent details not provided"
)

PARSE_SEARCH_QUERY_PROMPT = (
    "You are a product search optimizer for a fashion e-commerce platform.\n"
    "Given a user's search query, extract product attributes and rewrite the query "
    "for optimal vector similarity search.\n\n"
    "User query: {raw_query}\n\n"
    "Respond with JSON with these fields:\n"
    '- "rewritten_query": string — the query rewritten for vector search. '
    "Keep EVERY style, design and feature word the user mentions — neckline, "
    "sleeve type, fit, occasion, movement type, fragrance notes, materials, "
    "features — because those are matched by the embedding, not by filters. "
    'Only strip words already captured in the "filters" object.\n'
    '- "filters": object with optional keys: "color", "material", "category", "brand", "gender", "color_family", "size" — '
    "each is a list of string values extracted from the query.\n"
    "Translate all filter values to English (e.g. the Arabic query "
    '"فستان أحمر" must produce "color": ["Red"]).\n'
    "Gender values must be one of: men, women, girls, boys, babies, kids, unisex.\n"
    '"color_family": when a color is mentioned, also map it to the closest value '
    "from: red, pink, blue, navy, green, black, gray, white, beige, brown, camel, "
    "gold, silver, purple, orange, yellow, multicolor.\n"
    "Only include filter keys that were explicitly mentioned. "
    "If no filters are found, set filters to an empty object.\n\n"
    "Examples:\n"
    '{{"rewritten_query": "lace sleepwear midi dress comfortable", '
    '"filters": {{"color": ["Red"], "material": ["Lace"], "category": ["Dresses"]}}}}\n'
    '{{"rewritten_query": "cotton t-shirt casual", '
    '"filters": {{"material": ["Cotton"], "category": ["T-Shirts"]}}}}\n'
    '{{"rewritten_query": "black leather jacket in size L", '
    '"filters": {{"color": ["Black"], "category": ["Jackets"], "size": ["L"]}}}}\n'
    '{{"rewritten_query": "zara jacket black", '
    '"filters": {{"brand": ["Zara"], "category": ["Jackets"], "color": ["Black"], "color_family": ["black"]}}}}\n'
    '{{"rewritten_query": "elegant evening dress", '
    '"filters": {{"category": ["Dresses"], "gender": ["women"]}}}}\n'
    '{{"rewritten_query": "casual sneakers", '
    '"filters": {{"category": ["Sneakers"], "gender": ["kids"]}}}}\n'
    '{{"rewritten_query": "فستان قطن أنيق", '
    '"filters": {{"material": ["Cotton"], "category": ["Dresses"]}}}}\n'
    '{{"rewritten_query": "حذاء عنابي مريح", '
    '"filters": {{"category": ["Shoes"], "color": ["Burgundy"], "color_family": ["red"]}}}}\n'
    '{{"rewritten_query": "evening dress elegant", '
    '"filters": {{}}}}\n'
    '{{"rewritten_query": "automatic chronograph watch sapphire glass", '
    '"filters": {{"category": ["Watches"]}}}}\n'
    '{{"rewritten_query": "long lasting vanilla oud perfume", '
    '"filters": {{"category": ["Perfumes"]}}}}\n'
)

FASHION_ASSISTANT_INSTRUCTIONS = (
    "You are a fashion assistant. Help the user find the right product based on the available products.\n"
    "IMPORTANT: the product list is already displayed to the user in the app, "
    "so DO NOT list or enumerate the products in your answer "
    "(no numbered lists, no '1. Name - Price - Brand' lines, no bullet lists of products).\n"
    "Answer conversationally to guide the user instead: briefly describe the best-matching products "
    "(name, brand, price, why it fits their request) and help them decide. "
    "If no products match, suggest alternatives or ask clarifying questions."
)

ROUTER_PROMPT = (
    "You are a conversation router for a fashion e-commerce assistant.\n"
    "Classify the user's intent into exactly one of: greeting, search, or general.\n"
    "Rules:\n"
    '- "greeting": social openers with no product request — hello, hi, how are you, '
    "thanks, welcome, small talk, any typo/variant of these.\n"
    '- "search": any request that asks for, mentions, or implies products to find, '
    "including implicit references like 'the red dress I mentioned' or follow-ups "
    "about specific items (color, size, brand, price, style, category).\n"
    '- "general": everything else — fashion advice, recommendations about what to '
    "wear for an occasion, store/return questions, unrelated questions.\n"
    "When in doubt between search and general, choose search.\n"
    'Respond with ONLY valid JSON: {{"intent": "greeting" | "search" | "general"}}\n\n'
    "Last user message: {query}"
)

CHAT_SYSTEM_PROMPT = FASHION_ASSISTANT_INSTRUCTIONS

FASHION_ASSISTANT_PROMPT = FASHION_ASSISTANT_INSTRUCTIONS + ("\n\nAvailable products:\n{products_context}\n\nUser question: {user_query}\n\n{locale_hint}")

SUMMARIZE_PROMPT = (
    "You are a chat summarizer for a fashion shopping assistant.\n"
    "Maintain a running summary of the conversation. The summary must keep:\n"
    "- what products the user is looking for (category, color, size, brand, price range)\n"
    "- what products were recommended/shown and the user's reaction (liked, disliked, bought)\n"
    "- any preferences, clarifications, or constraints expressed\n"
    "Write compact bullet points. Do not include the previous summary text verbatim — merge it.\n\n"
    "Previous summary:\n{previous_summary or '(none)'}\n\n"
    "New messages:\n{history_text}\n\n"
    "{locale_hint}"
)

TITLE_PROMPT = (
    "You are a chat titler for a fashion shopping assistant.\n"
    "Create a short conversation title (2 to 6 words, no quotes, no punctuation at the end) "
    "from the first user message. The title summarizes the user's shopping intent "
    "(e.g. category, color, style). Reply with the title only.\n\n"
    "First user message: {query}\n\n"
    "{locale_hint}"
)

EVAL_QUERIES_PROMPT = (
    "You are a search-query designer for a fashion e-commerce platform.\n"
    "Generate exactly {count} diverse, realistic product-search queries a shopper "
    "might type, so the team can evaluate search quality.\n\n"
    "Catalog context (use these categories, brands, colors, materials, attributes, "
    "sizes and languages to ground every query in the actual catalog):\n{catalog_context}\n\n"
    "Rules:\n"
    "- Mix of specific and broad queries: exact categories, colors, sizes, brands, "
    "materials, style/feature words (neckline, sleeve, fit, occasion, movement type, "
    "fragrance notes, ...).\n"
    "- Prefer natural shopper phrasing over search-engine syntax.\n"
    "- Spread the {count} queries across these locales: {locales}.\n"
    "- Query text must be written in the query's own locale (English or Arabic).\n"
    "- No duplicates (case/translation variants still count as duplicates).\n"
    "Respond with ONLY valid JSON: "
    '{{"queries": [{{"text": "query text", "locale": "en"}}, '
    '{{"text": "نص الاستعلام", "locale": "ar"}}]}}'
)
