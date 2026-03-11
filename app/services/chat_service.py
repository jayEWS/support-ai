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
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "Siapa nama kamu? 😊",
            'invalid_name': "Hmm, boleh tulis nama lengkap kamu? 😊",
            'ask_details': "Hai {name}! 👋\nMohon lengkapi data berikut ya (ketik sesuai format):\n\n🏢 Perusahaan/Outlet:\n📱 No. HP:\n📧 Email:\n\nContoh:\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'invalid_details': "Mohon lengkapi ketiga data berikut ya 🙏\n\n🏢 Perusahaan/Outlet:\n📱 No. HP:\n📧 Email:\n\nKetik 3 baris, contoh:\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'confirm_details': "Mohon konfirmasi data berikut:\n\n👤 Nama: {name}\n🏢 Outlet: {company}\n📱 HP: {phone}\n📧 Email: {email}\n\nApakah sudah benar? Ketik *Ya* atau *Tidak*",
            'onboard_complete': "Terima kasih {name}! ✅\nData kamu sudah disimpan.\n\nSekarang, ada yang bisa saya bantu hari ini? 😊",
            'confirm_retry': "Baik, silakan kirim ulang data kamu:\n\n🏢 Perusahaan/Outlet:\n📱 No. HP:\n📧 Email:",
            'welcome_back': "Selamat datang kembali, {name}! 👋\nAda yang bisa saya bantu hari ini? 😊",
        },
        'en': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "What is your name? 😊",
            'invalid_name': "Could you please type your full name? 😊",
            'ask_details': "Hi {name}! 👋\nPlease provide the following details (type in this format):\n\n🏢 Company/Outlet:\n📱 Mobile Number:\n📧 Email:\n\nExample:\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'invalid_details': "Please provide all three details 🙏\n\n🏢 Company/Outlet:\n📱 Mobile Number:\n📧 Email:\n\nType 3 lines, example:\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'confirm_details': "Please confirm your details:\n\n👤 Name: {name}\n🏢 Outlet: {company}\n📱 Mobile: {phone}\n📧 Email: {email}\n\nIs this correct? Type *Yes* or *No*",
            'onboard_complete': "Thank you {name}! ✅\nYour data has been saved.\n\nHow can I help you today? 😊",
            'confirm_retry': "OK, please resend your details:\n\n🏢 Company/Outlet:\n📱 Mobile Number:\n📧 Email:",
            'welcome_back': "Welcome back, {name}! 👋\nHow can I help you today? 😊",
        },
        'zh': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "请问您的名字是？😊",
            'invalid_name': "请输入您的全名 😊",
            'ask_details': "{name} 您好！👋\n请提供以下信息（按格式输入）：\n\n🏢 公司/门店名称：\n📱 手机号码：\n📧 电子邮箱：\n\n例如：\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'invalid_details': "请提供以下三项信息 🙏\n\n🏢 公司/门店：\n📱 手机号码：\n📧 邮箱：\n\n输入3行，例如：\nPT Jaya Wijaya\n08123456789\nandru@email.com",
            'confirm_details': "请确认以下信息：\n\n👤 姓名：{name}\n🏢 门店：{company}\n📱 手机：{phone}\n📧 邮箱：{email}\n\n是否正确？输入 *是* 或 *否*",
            'onboard_complete': "谢谢 {name}！✅\n您的信息已保存。\n\n请问今天有什么可以帮助您的？😊",
            'confirm_retry': "好的，请重新发送您的信息：\n\n🏢 公司/门店：\n📱 手机号码：\n📧 邮箱：",
            'welcome_back': "欢迎回来，{name}！👋\n请问今天有什么可以帮助您的？😊",
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
        if db_state in ('asking_language', 'asking_name', 'asking_details', 'asking_company', 'confirming_details'):
            # Migrate old 'asking_company' state to new 'asking_details'
            if db_state == 'asking_company':
                db_state = 'asking_details'
            return {'state': db_state, 'user': user}
        
        # Returning user: already completed onboarding (state=complete/idle/ready)
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
        Parse company, phone, and email from user's multi-line response.
        Supports formats like:
          PT Jaya Wijaya
          08123456789
          andru@email.com
        Also handles labeled formats like:
          Company: PT Jaya
          Phone: 0812...
          Email: a@b.com
        """
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        
        company = None
        phone = None
        email = None
        remaining_lines = []
        
        # Label prefix patterns to strip
        label_re = re.compile(r'^(?:🏢|📱|📧|company|outlet|perusahaan|hp|phone|mobile|no\.?\s*hp|telepon|email|e-mail)[:\s/]*', re.IGNORECASE)
        
        for line in lines:
            cleaned = label_re.sub('', line).strip()
            if not cleaned:
                continue
            
            # Detect email (contains @)
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', cleaned)
            if email_match and not email:
                email = email_match.group(0).lower()
                continue
            
            # Detect phone (starts with 0, +, or is mostly digits)
            phone_match = re.search(r'(?:\+?\d[\d\s\-().]{6,})', cleaned)
            if phone_match and not phone:
                phone = re.sub(r'[\s\-().]+', '', phone_match.group(0))
                continue
            
            # Otherwise it's the company name
            remaining_lines.append(cleaned)
        
        if remaining_lines and not company:
            company = ' '.join(remaining_lines)
        
        return {'company': company, 'phone': phone, 'email': email}

    def _handle_onboarding(self, user_id: str, query: str, state_info: dict) -> Optional[str]:
        state = state_info['state']
        user = state_info.get('user')
        lang = (user.get('language') if user else None) or 'en'
        
        # ── Returning user: skip all onboarding ──
        if state == 'complete':
            return None  # Go straight to AI
        
        if state == 'new':
            detected = self.detect_language(query)
            if detected:
                db_manager.create_or_update_user(user_id, state='asking_name', language=detected)
                return self._get_lang_str(detected, 'ask_name')
            db_manager.create_or_update_user(user_id, state='asking_language')
            return self._get_lang_str('en', 'ask_language')
        
        if state == 'asking_language':
            detected = self.detect_language(query)
            if not detected: return self._get_lang_str('en', 'ask_language')
            db_manager.create_or_update_user(user_id, state='asking_name', language=detected)
            return self._get_lang_str(detected, 'ask_name')
        
        if state == 'asking_name':
            name = query.strip().title()
            if len(name) < 2: return self._get_lang_str(lang, 'invalid_name')
            db_manager.create_or_update_user(user_id, name=name, state='asking_details', language=lang)
            return self._get_lang_str(lang, 'ask_details', name=name)

        if state in ('asking_details', 'asking_company'):
            # Parse company, phone, email from the response
            parsed = self._parse_contact_details(query)
            company = parsed.get('company')
            phone = parsed.get('phone')
            email = parsed.get('email')
            
            if not company or not phone or not email:
                return self._get_lang_str(lang, 'invalid_details')
            
            name = user.get('name', 'Customer')
            # Store pending data and ask for confirmation
            self._sessions[user_id] = {'pending_company': company, 'pending_phone': phone, 'pending_email': email}
            db_manager.create_or_update_user(user_id, state='confirming_details', language=lang)
            return self._get_lang_str(lang, 'confirm_details',
                                      name=name, company=company, phone=phone, email=email)

        if state == 'confirming_details':
            answer = query.strip().lower()
            name = user.get('name', 'Customer')
            yes_words = ('ya', 'yes', 'y', 'ok', 'oke', 'benar', 'betul', 'correct', 'yep', 'yup', 'sure', 'confirm', '是', '对', 'iya', 'si', 'iya benar', 'sudah benar')
            no_words = ('no', 'tidak', 'salah', 'wrong', 'bukan', 'nope', 'nah', '否', '不对', 'belum', 'koreksi', 'ubah', 'ganti')
            
            if answer in yes_words:
                # Save the confirmed data
                pending = self._sessions.pop(user_id, {})
                company = pending.get('pending_company', '')
                phone = pending.get('pending_phone', '')
                email = pending.get('pending_email', '')
                if not company:
                    # Fallback: re-ask if session data lost
                    db_manager.create_or_update_user(user_id, state='asking_details', language=lang)
                    return self._get_lang_str(lang, 'confirm_retry')
                db_manager.create_or_update_user(
                    user_id, name=name, company=company, outlet_pos=company,
                    mobile=phone, email=email, state='complete', language=lang
                )
                return self._get_lang_str(lang, 'onboard_complete', name=name)
            elif answer in no_words:
                self._sessions.pop(user_id, None)
                db_manager.create_or_update_user(user_id, state='asking_details', language=lang)
                return self._get_lang_str(lang, 'confirm_retry')
            else:
                # Unrecognized — show confirmation again
                pending = self._sessions.get(user_id, {})
                company = pending.get('pending_company', '?')
                phone = pending.get('pending_phone', '?')
                email = pending.get('pending_email', '?')
                return self._get_lang_str(lang, 'confirm_details',
                                          name=name, company=company, phone=phone, email=email)
        
        return None

    def get_user_language(self, user_id: str) -> str:
        user = db_manager.get_user(user_id)
        return (user.get('language') if user else None) or 'en'

    def _log_ai_interaction(self, user_id: str, query: str, response_data: dict, rag_res: Any):
        """Self-Learning Pipeline: Log every AI interaction for future review/extraction."""
        try:
            session = db_manager.get_session()
            log = AIInteraction(
                user_id=user_id,
                query=scrub_pii(query),
                response=scrub_pii(response_data.get("answer", "")),
                retrieved_docs=json.dumps(response_data.get("sources", [])),
                tools_used=json.dumps(response_data.get("tools_used", [])),
                confidence=response_data.get("confidence", 0.0),
                resolution_status="pending",
                tenant_id=getattr(db_manager, 'current_tenant_id', None)
            )
            session.add(log)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to log AI interaction: {e}")
        finally:
            db_manager.Session.remove()

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
            onboarding_response = self._handle_onboarding(user_id, query, state_info)
            if onboarding_response:
                await run_sync(db_manager.save_message, user_id, "bot", onboarding_response)
                return {"answer": onboarding_response, "confidence": 1.0, "onboarding": True}, 200

            # --- Enterprise Agentic Flow ---
            user = state_info.get('user', {})
            user_context = {
                "name": user.get('name', 'User'),
                "outlet": user.get('company', 'Unknown'),
                "position": user.get('position', 'Staff')
            }

            # 1. Intent/Category Detection for Persona Switching
            category = "diagnose"
            q_lower = query.lower()
            if "pos-guardian" in q_lower or "pos guardian" in q_lower: 
                category = "pos_guardian"
            elif "heart-guardian" in q_lower or "heart guardian" in q_lower: 
                category = "heart_guardian"
            elif "relationship-comms" in q_lower or "comms assistant" in q_lower:
                category = "relationship_comms"
            elif "love-agent" in q_lower or "relationship coach" in q_lower or "love agent" in q_lower:
                category = "love_agent"
            elif "printer" in q_lower: 
                category = "printer"
            elif any(x in q_lower for x in ["payment", "transaction", "bayar"]): 
                category = "payment"
            elif any(x in q_lower for x in ["voucher", "kupon", "promo"]): 
                category = "voucher"

            # 2. Get Advanced System Prompt
            system_msg = prompt_service.get_system_message(category, user_context)

            # 3. RAG Query (Advanced Retriever: Hybrid + Rerank)
            user_lang = language or self.get_user_language(user_id)
            
            # Smart context injection: Only append context if the message is long/technical
            # Keep greetings "clean" so they hit the fast path in RAGService
            query_to_send = query
            if len(query.split()) > 3 and category not in ("pos_guardian", "heart_guardian", "relationship_comms", "love_agent"):
                query_to_send += f" (Context: {user_context['outlet']})"
                
            rag_res = await self.rag_service.query(query_to_send, language=user_lang, system_prompt=system_msg)
            
            # 4. LLM Completion
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
            self._log_ai_interaction(user_id, query, response_data, rag_res)

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
            # 1. Get history for ticket creation if needed
            # Support both Portal (Message) and WhatsApp (WhatsAppMessage) history
            history_objs = db_manager.get_messages(user_id)
            wa_history = db_manager.get_whatsapp_messages(user_id, per_page=100)
            
            transcript_parts = []
            if history_objs:
                transcript_parts.append("--- PORTAL HISTORY ---")
                transcript_parts.append("\n".join([f"[{m['role'].upper()}] {m['content']}" for m in history_objs]))
            
            if wa_history.get("messages"):
                transcript_parts.append("--- WHATSAPP HISTORY ---")
                transcript_parts.append("\n".join([f"[{m['direction'].upper()}] {m['content']}" for m in wa_history["messages"]]))

            transcript = "\n\n".join(transcript_parts)

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
                
                # Link WA messages to ticket if they exist
                if wa_history.get("messages"):
                    db_manager.link_whatsapp_messages_to_ticket(user_id, ticket_id)

            # 3. ALWAYS Clear portal messages after closing
            db_manager.clear_messages(user_id)
            
            # 4. Reset user state to idle
            db_manager.create_or_update_user(user_id, state='idle')

            return {
                "status": "closed",
                "option": option,
                "ticket_id": ticket_id,
                "ticket_created": bool(ticket_id),
                "message": "Chat session ended successfully"
            }
        except Exception as e:
            logger.error(f"Error closing chat for {user_id}: {e}")
            return {"status": "error", "message": str(e)}
