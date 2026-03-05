"""
Shopify-Inspired Advanced Query Understanding Engine
=====================================================
Implements multi-stage query processing inspired by Shopify Sidekick's
architecture: intent classification, query expansion, decomposition,
and JIT (Just-In-Time) instruction routing.

Architecture:
  Raw Query → Intent Classification → Query Expansion → HyDE Generation → Decomposition (if complex)
"""

import asyncio
import re
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
from app.core.logging import logger


class QueryIntent(str, Enum):
    """Query intent types for JIT instruction routing (Shopify pattern)"""
    GREETING = "greeting"
    SIMPLE_FAQ = "simple_faq"           # Direct KB lookup
    HOW_TO = "how_to"                   # Step-by-step instructions
    TROUBLESHOOTING = "troubleshooting" # Problem diagnosis
    COMPARISON = "comparison"           # Compare features/options
    CONFIGURATION = "configuration"     # Setup/config help
    BILLING_TAX = "billing_tax"         # Payment/tax/GST queries
    INTEGRATION = "integration"         # Third-party integrations
    COMPLEX_MULTI = "complex_multi"     # Multi-part question
    STATUS_CHECK = "status_check"       # System/order status
    UNKNOWN = "unknown"


@dataclass
class ProcessedQuery:
    """Result of query understanding pipeline"""
    original_query: str
    intent: QueryIntent
    intent_confidence: float
    expanded_query: str               # Semantically expanded
    hyde_passage: Optional[str]       # Hypothetical document (HyDE)
    sub_queries: List[str]            # Decomposed sub-questions
    language: str
    jit_instructions: str             # Just-In-Time prompt instructions
    topic_tags: List[str]             # Detected topic categories
    is_greeting: bool = False
    requires_multi_retrieval: bool = False


# ── JIT Instructions (Shopify Pattern) ──────────────────────────────
# Instead of bloating the system prompt, serve context-relevant instructions
# only when needed. This is the core Shopify Sidekick architecture insight.

JIT_INSTRUCTION_MAP = {
    QueryIntent.SIMPLE_FAQ: """INSTRUCTIONS (FAQ):
- Answer directly from the document context
- Keep response under 3 sentences unless detail is needed
- Cite the source document name
- If not found, say so clearly""",

    QueryIntent.HOW_TO: """INSTRUCTIONS (HOW-TO):
- Provide numbered step-by-step instructions
- Include specific menu paths (e.g., Setup > Payment Mode > NETS)
- Mention prerequisites before the steps
- Add a "Troubleshooting Tips" section at the end
- Reference the source guide name""",

    QueryIntent.TROUBLESHOOTING: """INSTRUCTIONS (TROUBLESHOOTING):
- Start with the most common cause
- Use a diagnostic flow: Check A → If not, Check B → If not, Check C
- Include specific error messages or symptoms to look for
- Provide both quick fix and root cause solutions
- Ask clarifying questions if the problem description is vague""",

    QueryIntent.COMPARISON: """INSTRUCTIONS (COMPARISON):
- Present information in a clear comparison format
- Highlight key differences and similarities
- Recommend the best option based on common use cases
- Include pricing/plan differences if relevant""",

    QueryIntent.CONFIGURATION: """INSTRUCTIONS (CONFIGURATION):
- Provide exact navigation paths in the system
- Include default values and recommended settings
- Warn about settings that require system restart
- Mention any prerequisites (licenses, permissions)""",

    QueryIntent.BILLING_TAX: """INSTRUCTIONS (TAX/BILLING):
- Be precise with tax rates and effective dates
- Reference official sources (IRAS, regulations)
- Include POS-specific configuration steps
- Warn about compliance requirements
- Distinguish between GST-registered and non-registered businesses""",

    QueryIntent.INTEGRATION: """INSTRUCTIONS (INTEGRATION):
- Cover prerequisites (accounts, API keys, permissions)
- Provide step-by-step connection guide
- Include sync settings and recommended defaults
- List common integration errors and fixes
- Mention data mapping requirements""",

    QueryIntent.COMPLEX_MULTI: """INSTRUCTIONS (MULTI-PART):
- Address each part of the question separately with clear headers
- Ensure all sub-questions are answered
- Cross-reference between parts when relevant
- Summarize at the end""",

    QueryIntent.STATUS_CHECK: """INSTRUCTIONS (STATUS):
- Check for any reported system issues
- Provide the current status clearly
- If unavailable, explain what alternative steps the user can take""",
}

# ── Topic Detection Patterns ────────────────────────────────────────

TOPIC_PATTERNS = {
    "pos_backend": r"\b(backend|admin|user\s*management|database|server|api|cron|backup)\b",
    "pos_frontend": r"\b(cashier|checkout|pos\s*screen|receipt|barcode|scan|till|register)\b",
    "payment": r"\b(payment|nets|visa|master|credit\s*card|debit|e-?wallet|fomopay|grabpay|paynow)\b",
    "reports": r"\b(report|analytics|sales\s*report|z[\s-]?report|x[\s-]?report|dashboard|revenue|profit)\b",
    "tax_gst": r"\b(tax|gst|iras|invoice|gst[\s-]?registered|input\s*tax|output\s*tax|f[578]|filing)\b",
    "integration": r"\b(integrat|xero|accounting|foodpanda|deliveroo|grabfood|sync)\b",
    "nets_machine": r"\b(nets|terminal|tid|mid|tms|settlement|batch)\b",
    "closing": r"\b(closing|end[\s-]?of[\s-]?day|eod|settlement|cash[\s-]?up|z[\s-]?reading)\b",
    "inventory": r"\b(inventory|stock|item|product|sku|category|modifier|variant|importer)\b",
    "promo": r"\b(promo|discount|voucher|coupon|happy[\s-]?hour|bundle)\b",
    "whatsapp": r"\b(whatsapp|wa|message|chat|notification)\b",
    "order": r"\b(order|web[\s-]?order|purchase[\s-]?order|po|delivery[\s-]?order|table[\s-]?order)\b",
}

# ── Query Expansion Synonyms ────────────────────────────────────────

EXPANSION_SYNONYMS = {
    "pos": ["point of sale", "equip", "equipweb", "cashier system"],
    "gst": ["goods and services tax", "tax", "9%", "IRAS"],
    "nets": ["NETS terminal", "NETS machine", "card terminal", "payment terminal"],
    "xero": ["xero accounting", "accounting integration", "bookkeeping sync"],
    "closing": ["end of day", "EOD", "Z-report", "daily settlement", "cash up"],
    "promo": ["promotion", "discount", "special offer", "happy hour"],
    "fomopay": ["FomoPay", "QR payment", "e-wallet payment"],
    "foodpanda": ["foodpanda", "food delivery", "delivery integration"],
    "error": ["issue", "problem", "bug", "not working", "failed"],
    "setup": ["configure", "install", "initialize", "connect"],
    "report": ["analytics", "statistics", "dashboard", "data export"],
}


class LRUCache:
    """Simple LRU cache for query results"""
    def __init__(self, maxsize=256):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[any]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: any):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)


class QueryEngine:
    """
    Shopify-Inspired Query Understanding Pipeline
    
    Implements 5-stage processing:
    1. Intent Classification (rule-based + pattern matching)
    2. Language Detection
    3. Query Expansion (synonym + related terms)
    4. HyDE Generation (Hypothetical Document Embeddings)  
    5. Query Decomposition (for multi-part queries)
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._cache = LRUCache(maxsize=256)
        logger.info("[QueryEngine] Initialized with JIT instruction routing")

    def set_llm(self, llm):
        """Set LLM for HyDE and decomposition (called after startup)"""
        self.llm = llm

    async def process(self, query: str, language: str = "en") -> ProcessedQuery:
        """Full query understanding pipeline"""
        # Check cache
        cache_key = hashlib.md5(f"{query}:{language}".encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # Stage 1: Greeting detection
        is_greeting = self._detect_greeting(query, language)
        if is_greeting:
            result = ProcessedQuery(
                original_query=query,
                intent=QueryIntent.GREETING,
                intent_confidence=1.0,
                expanded_query=query,
                hyde_passage=None,
                sub_queries=[],
                language=language,
                jit_instructions="",
                topic_tags=[],
                is_greeting=True,
            )
            self._cache.set(cache_key, result)
            return result

        # Stage 2: Intent Classification
        intent, intent_confidence = self._classify_intent(query, language)

        # Stage 3: Topic Detection
        topic_tags = self._detect_topics(query)

        # Stage 4: Query Expansion
        expanded_query = self._expand_query(query)

        # Stage 5: HyDE (Hypothetical Document Embedding)
        hyde_passage = None
        if self.llm and intent in (QueryIntent.HOW_TO, QueryIntent.TROUBLESHOOTING, QueryIntent.CONFIGURATION, QueryIntent.SIMPLE_FAQ, QueryIntent.BILLING_TAX, QueryIntent.INTEGRATION):
            try:
                hyde_passage = await self._generate_hyde(query, language)
            except Exception as e:
                logger.debug(f"HyDE generation skipped: {e}")

        # Stage 6: Query Decomposition (for complex queries)
        sub_queries = []
        requires_multi = False
        if intent == QueryIntent.COMPLEX_MULTI:
            sub_queries = self._decompose_query(query)
            requires_multi = len(sub_queries) > 1

        # Stage 7: JIT Instruction Selection (core Shopify pattern)
        jit_instructions = JIT_INSTRUCTION_MAP.get(intent, "")

        result = ProcessedQuery(
            original_query=query,
            intent=intent,
            intent_confidence=intent_confidence,
            expanded_query=expanded_query,
            hyde_passage=hyde_passage,
            sub_queries=sub_queries,
            language=language,
            jit_instructions=jit_instructions,
            topic_tags=topic_tags,
            is_greeting=False,
            requires_multi_retrieval=requires_multi,
        )

        self._cache.set(cache_key, result)
        return result

    # ── Stage 1: Greeting Detection ─────────────────────────────────

    def _detect_greeting(self, query: str, language: str) -> bool:
        """Detect greetings and short conversational queries"""
        q = query.lower().strip()
        words = set(q.split())

        greetings = {
            "en": {"hi", "hello", "hey", "thanks", "thank", "ok", "bye", "test", "good morning", "good afternoon"},
            "id": {"halo", "hai", "selamat", "pagi", "siang", "sore", "malam", "terima", "kasih", "oke", "makasih"},
            "zh": {"你好", "谢谢", "早上好", "晚上好", "嗨"},
        }

        lang_greetings = greetings.get(language, greetings["en"])
        all_greetings = set()
        for g in greetings.values():
            all_greetings.update(g)

        return len(words) <= 3 and bool(words.intersection(all_greetings))

    # ── Stage 2: Intent Classification ──────────────────────────────

    def _classify_intent(self, query: str, language: str) -> Tuple[QueryIntent, float]:
        """Rule-based intent classification with confidence scoring"""
        q = query.lower().strip()

        # Pattern-based classification with confidence
        intent_patterns = [
            # Troubleshooting patterns (highest priority)
            (QueryIntent.TROUBLESHOOTING, 0.90, [
                r"\b(error|issue|problem|bug|fail|crash|not\s*work|broken|stuck|can'?t|unable|wrong)\b",
                r"\b(why\s+(is|does|did|can'?t|won'?t))\b",
                r"\b(help|fix|resolve|troubleshoot|debug)\b",
                r"\b(kenapa|gagal|rusak|masalah|tidak\s*bisa|error)\b",
            ]),
            # How-to patterns
            (QueryIntent.HOW_TO, 0.85, [
                r"\b(how\s+to|how\s+do\s+i|how\s+can\s+i|steps\s+to|guide|tutorial)\b",
                r"\b(setup|set\s*up|configure|install|create|add|enable|disable)\b",
                r"\b(cara|bagaimana|langkah|gimana)\b",
            ]),
            # Billing/Tax patterns
            (QueryIntent.BILLING_TAX, 0.90, [
                r"\b(gst|tax|iras|invoice|billing|price|cost|charge|filing|f[578])\b",
                r"\b(pajak|tagihan|faktur)\b",
            ]),
            # Integration patterns
            (QueryIntent.INTEGRATION, 0.85, [
                r"\b(integrat|connect|sync|xero|fomopay|foodpanda|deliveroo|grab|api)\b",
                r"\b(integrasi|hubungkan|sinkron)\b",
            ]),
            # Configuration patterns
            (QueryIntent.CONFIGURATION, 0.85, [
                r"\b(setting|config|preference|option|parameter|default|permission|role)\b",
                r"\b(pengaturan|konfigurasi|atur)\b",
            ]),
            # Comparison patterns
            (QueryIntent.COMPARISON, 0.80, [
                r"\b(compare|vs|versus|difference|better|which\s+one|or\s+should)\b",
                r"\b(banding|lebih\s+baik|mana\s+yang)\b",
            ]),
            # Status patterns
            (QueryIntent.STATUS_CHECK, 0.85, [
                r"\b(status|check|monitor|uptime|down|outage|running|healthy)\b",
            ]),
        ]

        best_intent = QueryIntent.SIMPLE_FAQ
        best_confidence = 0.6
        match_count = 0

        for intent, confidence, patterns in intent_patterns:
            for pattern in patterns:
                if re.search(pattern, q, re.IGNORECASE):
                    match_count += 1
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
                    break

        # Detect multi-part queries
        multi_markers = [r"\band\b.*\b(also|and)\b", r"\?.*\?", r"\b(first|second|also|additionally)\b",
                         r"\d+\)\s.*\d+\)", r";\s*\w"]
        multi_hits = sum(1 for p in multi_markers if re.search(p, q))
        if multi_hits >= 1 and len(q.split()) > 15:
            best_intent = QueryIntent.COMPLEX_MULTI
            best_confidence = 0.80

        return best_intent, best_confidence

    # ── Stage 3: Topic Detection ────────────────────────────────────

    def _detect_topics(self, query: str) -> List[str]:
        """Detect topic categories from query text"""
        q = query.lower()
        topics = []
        for topic, pattern in TOPIC_PATTERNS.items():
            if re.search(pattern, q, re.IGNORECASE):
                topics.append(topic)
        return topics if topics else ["general"]

    # ── Stage 4: Query Expansion ────────────────────────────────────

    def _expand_query(self, query: str) -> str:
        """Expand query with domain synonyms for better retrieval recall"""
        q_lower = query.lower()
        expansions = []

        for term, synonyms in EXPANSION_SYNONYMS.items():
            if term in q_lower:
                # Add top 2 synonyms that aren't already in the query
                for syn in synonyms[:2]:
                    if syn.lower() not in q_lower:
                        expansions.append(syn)

        if expansions:
            return f"{query} ({', '.join(expansions)})"
        return query

    # ── Stage 5: HyDE (Hypothetical Document Embeddings) ────────────

    async def _generate_hyde(self, query: str, language: str) -> Optional[str]:
        """
        Generate a hypothetical ideal document that would answer the query.
        This is then used as an additional retrieval vector (HyDE technique).
        Dramatically improves retrieval for how-to and troubleshooting queries.
        """
        if not self.llm:
            return None

        hyde_prompt = f"""Write a short technical support article excerpt (3-4 sentences) that would perfectly answer this question. Write as if it's from an Equip POS system documentation.

Question: {query}

Article excerpt:"""

        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(self.llm.invoke, hyde_prompt),
                timeout=8.0
            )
            passage = res.content.strip()
            return passage if len(passage) > 20 else None
        except Exception as e:
            logger.debug(f"HyDE generation failed: {e}")
            return None

    # ── Stage 6: Query Decomposition ────────────────────────────────

    def _decompose_query(self, query: str) -> List[str]:
        """Decompose complex multi-part queries into sub-questions"""
        # Split on common delimiters
        parts = re.split(r'[?;]\s*|\band\s+also\b|\badditionally\b|\bmoreover\b', query)
        sub_queries = []
        for part in parts:
            part = part.strip()
            if len(part) > 10:  # Minimum meaningful length
                if not part.endswith("?"):
                    part += "?"
                sub_queries.append(part)

        return sub_queries if len(sub_queries) > 1 else [query]
