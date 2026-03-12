import json
import re
from typing import Optional, List, Dict, Any
from fastapi import UploadFile
from app.core.database import db_manager
from app.core.logging import logger, LogLatency
from app.utils.file_handler import save_upload
from app.services.rag_service import RAGService
from app.services.prompt_service import prompt_service
from app.models.models import AIInteraction
from datetime import datetime, timezone
from app.services.guardrail_service import guardrail_service
from app.utils.pii_scrubber import scrub_pii
from app.utils.async_db import run_sync

def _sanitize_text(text: str) -> str:
    """Remove invalid surrogate characters that break UTF-8 encoding."""
    if not text:
        return text
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')

class ChatService:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service
        self._sessions = {}

    # --- Language Support ---
    LANG_STRINGS = {
        'id': {
            'ask_language': "Halo! 👋 Selamat datang di *Edgeworks Support*.\n\nSecara default kami menggunakan Bahasa Indonesia, namun Anda bisa mengubahnya:\n*Please select your preferred language:*\n*请选择您的语言：*\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nBalas dengan angka / Reply with 1, 2, or 3 😊",
            'ask_name': "Boleh kami tahu dengan siapa kami berbicara (Nama Anda)? 😊",
            'invalid_name': "Mohon maaf, boleh ketikkan nama lengkap Anda? 😊",
            'ask_details': "Salam kenal, {name}! 👋\nAgar kami bisa membantu dengan lebih baik, boleh minta tolong lengkapi data berikut? (Silakan ketik dalam 4 baris ya):\n\n🏢 Nama Perusahaan:\n🏬 Nama Outlet:\n📱 No. HP (WhatsApp):\n📧 Email:\n\nContoh:\nEdgeworks\nBugis\n08123456789\nhalo@email.com",
            'invalid_details': "Mohon maaf, sepertinya datanya belum lengkap 🙏\nBoleh minta tolong ketik ulang informasi ini dalam 4 baris bersusun?\n\n🏢 Nama Perusahaan:\n🏬 Nama Outlet:\n📱 No. HP (WhatsApp):\n📧 Email:\n\nContoh:\nEdgeworks\nBugis\n08123456789\nhalo@email.com",
            'confirm_details': "Terima kasih! Boleh kami pastikan datanya sudah benar?\n\n👤 Nama: {name}\n🏢 Perusahaan: {company}\n🏬 Outlet: {outlet}\n📱 HP: {phone}\n📧 Email: {email}\n\nKetik *Ya* jika sudah benar, atau *Tidak* jika mau diubah.",
            'onboard_complete': "Terima kasih, {name}! ✅\nData Anda sudah kami simpan.\n\nSekarang, ada yang bisa kami bantu hari ini? 😊",
            'confirm_retry': "Baik, mohon ketik ulang data Anda ya:\n\n🏢 Nama Perusahaan:\n🏬 Nama Outlet:\n📱 No. HP (WhatsApp):\n📧 Email:",
            'welcome_back': "Halo {name} dari {company}! 👋\nSelamat datang kembali di Edgeworks Support.\nAda yang bisa kami bantu hari ini? 😊",
        },
        'en': {
            'ask_language': "Hello! 👋 Welcome to *Edgeworks Support*.\n\nPlease select your preferred language:\n*Silakan pilih bahasa Anda:*\n*请选择您的语言：*\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "May I know your name please? 😊",
            'invalid_name': "Could you please tell us your full name? 😊",
            'ask_details': "Nice to meet you, {name}! 👋\nTo help us assist you better, could you please provide these details in 4 lines?\n\n🏢 Company Name:\n🏬 Outlet Name:\n📱 Mobile Number (WhatsApp):\n📧 Email Address:\n\nExample:\nEdgeworks\nBugis\n+6581234567\nhello@email.com",
            'invalid_details': "Sorry, it seems we missed some details 🙏\nCould you please type them out in 4 lines?\n\n🏢 Company Name:\n🏬 Outlet Name:\n📱 Mobile Number (WhatsApp):\n📧 Email Address:\n\nExample:\nEdgeworks\nBugis\n+6581234567\nhello@email.com",
            'confirm_details': "Thank you! Just to confirm, are these details correct?\n\n👤 Name: {name}\n🏢 Company: {company}\n🏬 Outlet: {outlet}\n📱 Mobile: {phone}\n📧 Email: {email}\n\nPlease type *Yes* or *No*.",
            'onboard_complete': "Thank you, {name}! ✅\nYour details have been saved.\n\nHow can we help you today? 😊",
            'confirm_retry': "No problem, please resend your details:\n\n🏢 Company Name:\n🏬 Outlet Name:\n📱 Mobile Number (WhatsApp):\n📧 Email Address:",
            'welcome_back': "Welcome back, {name} from {company}! 👋\nHow can we help you today? 😊",
        },
        'zh': {
            'ask_language': "您好！👋 欢迎来到 *Edgeworks Support*。\n\n请选择您的语言：\n*Silakan pilih bahasa Anda:*\n*Please select your preferred language:*\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\n请回复 / Reply with 1, 2, or 3 😊",
            'ask_name': "请问怎么称呼您？😊",
            'invalid_name': "抱歉，可以请您输入全名吗？😊",
            'ask_details': "很高兴认识您，{name}！👋\n为了更好地协助您，请分4行提供以下信息：\n\n🏢 公司名称：\n🏬 门店名称：\n📱 手机号码 (WhatsApp)：\n📧 电子邮箱：\n\n例如：\nEdgeworks\nBugis\n+6581234567\nhello@email.com",
            'invalid_details': "抱歉，好像缺少了一些信息 🙏\n请分4行提供以下完整信息：\n\n🏢 公司名称：\n🏬 门店名称：\n📱 手机号码 (WhatsApp)：\n📧 电子邮箱：\n\n例如：\nEdgeworks\nBugis\n+6581234567\nhello@email.com",
            'confirm_details': "谢谢！请确认您的信息是否正确：\n\n👤 姓名：{name}\n🏢 公司：{company}\n🏬 门店：{outlet}\n📱 手机：{phone}\n📧 邮箱：{email}\n\n如果正确请输入 *是 (Yes)*，如果不正确请输入 *否 (No)*。",
            'onboard_complete': "谢谢您，{name}！✅\n您的信息已保存。\n\n请问今天有什么我可以帮您的？😊",
            'confirm_retry': "没问题，请重新发送您的信息：\n\n🏢 公司名称：\n🏬 门店名称：\n📱 手机号码 (WhatsApp)：\n📧 电子邮箱：",
            'welcome_back': "欢迎回来，{company} 的 {name}！👋\n请问今天有什么可以帮您的？😊",
        }
    }

    @staticmethod
    def detect_language(text: str) -> str | None:
        if not text: return None
        t = text.strip().lower()
        if t in ('1', 'bahasa', 'indonesia', 'id'): return 'id'
        if t in ('2', 'english', 'en'): return 'en'
        if t in ('3', 'chinese', 'zh', '中文'): return 'zh'
        for ch in t:
            if '\u4e00' <= ch <= '\u9fff': return 'zh'
        return None

    def _get_lang_str(self, lang: str, key: str, **kwargs) -> str:
        strings = self.LANG_STRINGS.get(lang, self.LANG_STRINGS['en'])
        template = strings.get(key, self.LANG_STRINGS['en'].get(key, ''))
        return template.format(**kwargs) if kwargs else template

    def _get_user_state(self, user_id: str) -> dict:
        user = db_manager.get_user(user_id)
        if not user: return {'state': 'new', 'user': None}
        db_state = user.get('state', '')

        # Active onboarding states
        if db_state in ('new', 'asking_language', 'asking_name', 'asking_details', 'asking_company', 'confirming_details'):
            # Migrate old 'asking_company' state to new 'asking_details'
            if db_state == 'asking_company':
                db_state = 'asking_details'
            return {'state': db_state, 'user': user}        # Returning user: already completed onboarding (state=complete/idle/ready)
        # These users should NOT be re-asked for language/name/company
        if user.get('name') and user.get('company'):
            return {'state': 'complete', 'user': user}
        
        # User exists but incomplete profile — restart onboarding
        if user.get('name'):
            return {'state': 'asking_details', 'user': user}
        if user.get('language'):
            return {'state': 'asking_name', 'user': user}
        return {'state': 'asking_language', 'user': user}

    async def _get_user_state_async(self, user_id: str) -> dict:
        """Async wrapper for _get_user_state."""
        return await run_sync(self._get_user_state, user_id)

    @staticmethod
    def _parse_contact_details(text: str) -> dict:
        """
        Parse company, outlet, phone, and email from user's multi-line response.
        Supports formats like:
          Edgeworks
          Bugis
          08123456789
          hello@email.com
        """
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]

        company = None
        outlet = None
        phone = None
        email = None
        remaining_lines = []

        # Label prefix patterns to strip
        label_re = re.compile(r'^(?:🏢|🏬|📱|📧|company|outlet|perusahaan|hp|phone|mobile|no\.?\s*hp|telepon|email|e-mail)[:\s/]*', re.IGNORECASE)

        for line in lines:
            cleaned = label_re.sub('', line).strip()
            if not cleaned:
                continue

            # Detect email (contains @ and .)
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', cleaned)
            if email_match and not email:
                email = email_match.group(0).lower()
                continue

            # Detect phone (starts with 0, +, or is mostly digits)
            phone_match = re.search(r'(?:\+?\d[\d\s\-().]{6,})', cleaned)
            if phone_match and not phone:
                phone = re.sub(r'[\s\-().]+', '', phone_match.group(0))
                continue

            # Otherwise it's company or outlet
            remaining_lines.append(cleaned)

        if len(remaining_lines) >= 1:
            company = remaining_lines[0]
        if len(remaining_lines) >= 2:
            outlet = remaining_lines[1]
        elif len(remaining_lines) == 1:
            if '/' in company:
                parts = company.split('/', 1)
                company = parts[0].strip()
                outlet = parts[1].strip()
            elif '-' in company:
                parts = company.split('-', 1)
                company = parts[0].strip()
                outlet = parts[1].strip()
            else:
                outlet = company # Default to company name if outlet is not specified separately

        return {'company': company, 'outlet': outlet, 'phone': phone, 'email': email}

    async def _handle_onboarding(self, user_id: str, query: str, state_info: dict) -> Optional[str]:
        state = state_info['state']
        user = state_info.get('user', {})
        lang = (user.get('language') if user else None) or 'en'

        quick_greetings = {'hi', 'halo', 'hello', 'hey', 'p', 'ping', 'test', 'tes', 'hai', 'hy', 'hola', 'start'}
        is_greeting = query.strip().lower() in quick_greetings

        # ── Complete user: quick greeting or bypass ──
        if state == 'complete':
            if is_greeting:
                return self._get_lang_str(lang, 'welcome_back', name=user.get('name', 'User'), company=user.get('company', ''))
            return None  # Go straight to AI
            
        # If user hasn't finished onboarding but starts with a generic greeting, restart flow
        if is_greeting and state not in ('new', 'asking_language'):
            state = 'new'
            await run_sync(db_manager.create_or_update_user, user_id, state='new')

        if state == 'new':
            detected = self.detect_language(query)
            if detected:
                await run_sync(db_manager.create_or_update_user, user_id, state='asking_name', language=detected)
                return self._get_lang_str(detected, 'ask_name')
            await run_sync(db_manager.create_or_update_user, user_id, state='asking_language')
            return self._get_lang_str('en', 'ask_language')

        if state == 'asking_language':
            detected = self.detect_language(query)
            if not detected: return self._get_lang_str('en', 'ask_language')
            await run_sync(db_manager.create_or_update_user, user_id, state='asking_name', language=detected)
            return self._get_lang_str(detected, 'ask_name')

        if state == 'asking_name':
            name = query.strip().title()
            if len(name) < 2: return self._get_lang_str(lang, 'invalid_name')
            await run_sync(db_manager.create_or_update_user, user_id, name=name, state='asking_details', language=lang)
            return self._get_lang_str(lang, 'ask_details', name=name)

        if state in ('asking_details', 'asking_company'):
            # Parse company, outlet, phone, email from the response
            parsed = self._parse_contact_details(query)
            company = parsed.get('company')
            outlet = parsed.get('outlet')
            phone = parsed.get('phone')
            email = parsed.get('email')

            if not company or not outlet or not phone or not email:
                return self._get_lang_str(lang, 'invalid_details')

            name = user.get('name', 'Customer')
            # Save pending data and ask for confirmation
            await run_sync(db_manager.create_or_update_user, user_id, company=company, outlet_pos=outlet, mobile=phone, email=email, state='confirming_details', language=lang)
            return self._get_lang_str(lang, 'confirm_details',
                                      name=name, company=company, outlet=outlet, phone=phone, email=email)

        if state == 'confirming_details':
            answer = query.strip().lower()
            name = user.get('name', 'Customer')
            
            # Using broader acceptance lists for yes/no
            yes_words = {'ya', 'yes', 'y', 'ok', 'oke', 'benar', 'betul', 'correct', 'yep', 'yup', 'sure', 'confirm', '是', '对', 'iya', 'si', 'iya benar', 'sudah benar', 'betul sekali', 'okay'}
            no_words = {'no', 'tidak', 'salah', 'wrong', 'bukan', 'nope', 'nah', '否', '不对', 'belum', 'koreksi', 'ubah', 'ganti', 'ngga', 'nggak'}
            
            # Clean string for word matching
            clean_answer = re.sub(r'[^\w\s]', '', answer)
            words = set(clean_answer.split())
            
            # Quick check exact matches first
            is_yes = answer in yes_words or words.intersection(yes_words)
            is_no = answer in no_words or words.intersection(no_words)
            
            # If both are matched (e.g., "tidak benar"), default to No.
            if is_no:
                await run_sync(db_manager.create_or_update_user, user_id, company="", outlet_pos="", mobile="", email="", state='asking_details', language=lang)
                return self._get_lang_str(lang, 'confirm_retry')
            elif is_yes:
                company = user.get('company')
                if not company:
                    # Fallback: re-ask if DB data lost
                    await run_sync(db_manager.create_or_update_user, user_id, state='asking_details', language=lang)
                    return self._get_lang_str(lang, 'confirm_retry')
                
                await run_sync(db_manager.create_or_update_user,
                    user_id, state='complete', language=lang
                )
                return self._get_lang_str(lang, 'onboard_complete', name=name)
            else:
                # Unrecognized — show confirmation again
                return self._get_lang_str(lang, 'confirm_details',
                                          name=name, company=user.get('company', '?'), outlet=user.get('outlet_pos', '?'), phone=user.get('mobile', '?'), email=user.get('email', '?'))

        return None

    def get_user_language(self, user_id: str) -> str:
        user = db_manager.get_user(user_id)
        return (user.get('language') if user else None) or 'en'

    # ── Smart Category Detection ────────────────────────────────────

    # Keyword → category mapping (checked in priority order)
    _CATEGORY_RULES = [
        # Special personas (exact triggers)
        ({"pos-guardian", "pos guardian"}, "pos_guardian"),
        ({"heart-guardian", "heart guardian"}, "heart_guardian"),
        ({"relationship-comms", "comms assistant"}, "relationship_comms"),
        ({"love-agent", "love agent", "relationship coach"}, "love_agent"),
        # Hardware
        ({"printer", "print", "receipt", "cetak", "struk", "kds", "display", "kiosk",
          "scanner", "barcode", "cash drawer", "laci"}, "printer"),
        # Payment
        ({"payment", "transaction", "bayar", "refund", "void", "nets", "fomopay",
          "edc", "terminal", "pembayaran", "transaksi", "charge", "settlement"}, "payment"),
        # Voucher/Promo
        ({"voucher", "kupon", "promo", "discount", "diskon", "reward", "loyalty",
          "redeem", "coupon", "campaign"}, "voucher"),
        # Inventory
        ({"inventory", "stock", "stok", "barang", "item", "produk", "product",
          "recipe", "bom", "restock"}, "diagnose"),
    ]

    @staticmethod
    def _detect_message_language(text: str) -> Optional[str]:
        """
        Detect the language of the CURRENT message, not the onboarding preference.
        This ensures the AI replies in the same language the user is typing in.
        Returns 'en', 'id', 'zh', or None if uncertain.
        """
        if not text or len(text.strip()) < 3:
            return None

        t = text.lower().strip()

        # Chinese detection: any CJK characters
        for ch in t:
            if '\u4e00' <= ch <= '\u9fff':
                return 'zh'

        # Bahasa Indonesia markers (common words that don't appear in English)
        id_markers = {
            'bagaimana', 'tolong', 'bisa', 'tidak', 'sudah', 'belum', 'mohon',
            'terima', 'kasih', 'silakan', 'cara', 'kenapa', 'dimana', 'kapan',
            'apakah', 'saya', 'kami', 'anda', 'punya', 'mau', 'harus', 'perlu',
            'masalah', 'error', 'gimana', 'gak', 'gk', 'nga', 'dong', 'deh',
            'lagi', 'udah', 'blm', 'minta', 'bantu', 'apa', 'ini', 'itu',
            'sedang', 'dengan', 'dari', 'untuk', 'atau', 'juga', 'masih',
            'caranya', 'settingnya', 'printnya', 'bayarnya',
        }
        words = set(re.split(r'\W+', t))
        id_count = len(words & id_markers)

        # If more than 1 Bahasa word detected (or it's a short message with 1), it's Indonesian
        if id_count >= 2 or (id_count >= 1 and len(words) <= 4):
            return 'id'

        # Default to English for Latin-script messages
        return 'en'

    @classmethod
    def _detect_category(cls, query: str) -> str:
        """
        Detect the intent category from the user's query using multi-keyword
        matching. More keywords = more accurate routing.
        """
        q_lower = query.lower()
        for keywords, category in cls._CATEGORY_RULES:
            for kw in keywords:
                if kw in q_lower:
                    return category
        return "diagnose"

    def _log_ai_interaction_sync(self, user_id: str, query: str, response_data: dict, rag_res: Any):
        """Self-Learning Pipeline: Log every AI interaction for future review/extraction (sync, run via run_sync)."""
        try:
            from app.repositories.base import TenantContext
            session = db_manager.get_session()
            log = AIInteraction(
                user_id=user_id,
                query=scrub_pii(query),
                response=scrub_pii(response_data.get("answer", "")),
                retrieved_docs=json.dumps(response_data.get("sources", [])),
                tools_used=json.dumps(response_data.get("tools_used", [])),
                confidence=response_data.get("confidence", 0.0),
                resolution_status="pending",
                tenant_id=TenantContext.get()  # P1 Fix: Use TenantContext instead of nonexistent attribute
            )
            session.add(log)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to log AI interaction: {e}")
        finally:
            db_manager.Session.remove()

    async def _log_ai_interaction(self, user_id: str, query: str, response_data: dict, rag_res: Any):
        """Async wrapper for AI interaction logging."""
        await run_sync(self._log_ai_interaction_sync, user_id, query, response_data, rag_res)

    async def process_portal_message(self, query: str, user_id: str, file: Optional[UploadFile] = None, language: str = None):
        with LogLatency("chat_service", "process_portal_message"):
            attachment_meta = None
            if file:
                file_bytes = await file.read()
                attachment_meta = save_upload(file_bytes, file.filename, destination="chat")
            
            if not query and attachment_meta:
                query = f"[Uploaded {attachment_meta['category']}: {attachment_meta['original_name']}]"
            
            if not query: return {"error": "Message required"}, 400

            # --- Guardrail: Input Validation ---
            if not guardrail_service.validate_input(query):
                return {"answer": "I apologize, but your message contains content that I cannot process. Please try asking about your POS system help!", "confidence": 1.0}, 200

            await run_sync(db_manager.save_message, user_id, "user", query, None if not attachment_meta else json.dumps([attachment_meta]))

            state_info = await self._get_user_state_async(user_id)
            onboarding_response = await self._handle_onboarding(user_id, query, state_info)
            if onboarding_response:
                await run_sync(db_manager.save_message, user_id, "bot", onboarding_response)
                return {"answer": onboarding_response, "confidence": 1.0, "onboarding": True}, 200

            # --- Enterprise Agentic Flow ---
            user = state_info.get('user', {}) if isinstance(state_info, dict) else {}
            # Fallback if state_info missing user
            if not user and state_info.get('state') != 'new':
                user = db_manager.get_user(user_id) or {}
                
            user_context = {
                "name": user.get('name', 'User'),
                "company": user.get('company', 'Unknown'),
                "outlet": user.get('outlet_pos', 'Unknown'),
                "position": user.get('position', 'Staff')
            }

            # 1. Smart Intent/Category Detection for Persona Switching
            category = self._detect_category(query)

            # 2. Get Advanced System Prompt
            system_msg = prompt_service.get_system_message(category, user_context)

            # 3. RAG Query (Advanced Retriever: Hybrid + Rerank)
            # Detect language from the CURRENT message (not just onboarding preference)
            # This ensures if user types in English, AI replies in English even if they onboarded in Bahasa
            detected_lang = self._detect_message_language(query)
            user_lang = language or detected_lang or self.get_user_language(user_id)
            
            # Smart context injection: Only append context if the message is long/technical
            # Keep greetings "clean" so they hit the fast path in RAGService
            query_to_send = query
            if len(query.split()) > 3 and category not in ("pos_guardian", "heart_guardian", "relationship_comms", "love_agent"):
                query_to_send += f" (Context: {user_context['company']} - {user_context['outlet']})"

            # Fetch recent conversation history for context-aware AI responses
            conversation_history = await run_sync(db_manager.get_messages, user_id)
            # Limit to last 8 messages to keep prompt size manageable
            recent_history = conversation_history[-8:] if conversation_history else []

            rag_res = await self.rag_service.query(
                query_to_send,
                language=user_lang,
                system_prompt=system_msg,
                conversation_history=recent_history
            )            # 4. LLM Completion
            answer = _sanitize_text(rag_res.answer)
            
            # --- Guardrail: Output Validation ---
            answer = guardrail_service.validate_output(answer)

            if not answer or not str(answer).strip():
                answer = "I’m sorry—I couldn’t generate a clear reply just now. Please try again."
            
            logger.info(f"ChatService Answer: {answer[:100]} (len={len(answer)})")
            await run_sync(db_manager.save_message, user_id, "bot", answer)

            response_data = {
                "answer": answer,
                "confidence": rag_res.confidence,
                "sources": rag_res.source_documents,
                "persona_used": category,
                "tools_used": ["hybrid_search", "reranker"]
            }

            # 5. Log for Self-Learning
            await self._log_ai_interaction(user_id, query, response_data, rag_res)

            return response_data, 200

    async def close_chat(self, user_id: str, option: str = "close") -> dict:
        """
        Close a portal chat session.
        Options:
          - "close": Resolved. Clear messages without creating a ticket.
          - "ticket": Create a ticket and keep history there.
          - "ticket_and_notify": Create a ticket and send notification.
        """
        try:
            # 1. Get portal message history (non-blocking)
            history_objs = await run_sync(db_manager.get_messages, user_id)

            # Only fetch WhatsApp history if user_id looks like a phone number
            import re as _re
            wa_history = {"messages": []}
            if _re.match(r'^\+?\d{8,15}$', user_id.replace(' ', '')):
                wa_history = await run_sync(db_manager.get_whatsapp_messages, user_id, per_page=100)

            transcript_parts = []
            if history_objs:
                transcript_parts.append("--- PORTAL HISTORY ---")
                transcript_parts.append("\n".join([f"[{m['role'].upper()}] {m['content']}" for m in history_objs]))

            if wa_history.get("messages"):
                transcript_parts.append("--- WHATSAPP HISTORY ---")
                transcript_parts.append("\n".join([f"[{m['direction'].upper()}] {m['content']}" for m in wa_history["messages"]]))

            transcript = "\n\n".join(transcript_parts) if transcript_parts else "No messages"

            # 2. Handle options
            ticket_id = None
            if option in ("ticket", "ticket_and_notify", 1, "1"):
                from app.services.ticket_service import TicketService
                # Create a summary from the last message
                summary_source = history_objs if history_objs else wa_history.get("messages", [])
                last_msg_content = "Chat Session"
                if summary_source:
                    last_msg = summary_source[-1]
                    last_msg_content = last_msg.get('content', 'Chat Session') if isinstance(last_msg, dict) else getattr(last_msg, 'content', 'Chat Session')

                summary = f"[Support] {str(last_msg_content)[:100]}"

                ticket_res = await TicketService.create_ticket(user_id, summary, transcript)
                ticket_id = ticket_res.id

                # Link WA messages to ticket if they exist (only for phone-number users)
                if wa_history.get("messages"):
                    await run_sync(db_manager.link_whatsapp_messages_to_ticket, user_id, ticket_id)

            # 3. ALWAYS Clear portal messages after closing (non-blocking)
            await run_sync(db_manager.clear_messages, user_id)

            # 4. Reset user state to idle (non-blocking)
            await run_sync(db_manager.create_or_update_user, user_id, state='idle')

            logger.info(f"Chat closed for {user_id} with option={option}, ticket={ticket_id}")

            return {
                "status": "closed",
                "option": option,
                "ticket_id": ticket_id,
                "ticket_created": bool(ticket_id),
                "message": "Chat session ended successfully"
            }
        except Exception as e:
            logger.error(f"Error closing chat for {user_id}: {e}", exc_info=True)
            # Still try to clear messages and reset state on error
            try:
                await run_sync(db_manager.clear_messages, user_id)
                await run_sync(db_manager.create_or_update_user, user_id, state='idle')
            except Exception:
                pass
            return {"status": "closed", "option": option, "ticket_id": None, "ticket_created": False, "message": "Chat ended (with partial error)"}
