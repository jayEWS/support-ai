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
            'ask_company': "Hai {name}! 👋\nNama perusahaan atau outlet kamu apa ya?\n(contoh: PT ABC / Warung Makan XYZ)",
            'invalid_company': "Boleh tulis nama perusahaan atau outlet kamu?",
            'onboard_complete': "Terima kasih {name}! ✅\nData kamu sudah kami simpan:\n• Nama: {name}\n• Outlet: {company}\n\nSekarang, ada yang bisa saya bantu hari ini? 😊",
        },
        'en': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "What is your name? 😊",
            'invalid_name': "Could you please type your full name? 😊",
            'ask_company': "Hi {name}! 👋\nWhat is your company or outlet name?\n(e.g. PT ABC / Restaurant XYZ)",
            'invalid_company': "Could you please type your company or outlet name?",
            'onboard_complete': "Thank you {name}! ✅\nYour data has been saved:\n• Name: {name}\n• Outlet: {company}\n\nHow can I help you today? 😊",
        },
        'zh': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "请问您的名字是？😊",
            'invalid_name': "请输入您的全名 😊",
            'ask_company': "{name} 您好！👋\n请问您的公司或门店名称是什么？\n（例如：PT ABC / 餐厅 XYZ）",
            'invalid_company': "请输入您的公司或门店名称",
            'onboard_complete': "谢谢 {name}！✅\n您的信息已保存：\n• 姓名：{name}\n• 门店：{company}\n\n请问今天有什么可以帮助您的？😊",
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
        if db_state in ('asking_language', 'asking_name', 'asking_company'):
            return {'state': db_state, 'user': user}
        if db_state == 'complete' and user.get('name') and user.get('company'):
            return {'state': 'complete', 'user': user}
        return {'state': 'asking_language', 'user': user}

    async def _get_user_state_async(self, user_id: str) -> dict:
        """Async wrapper for _get_user_state."""
        return await run_sync(self._get_user_state, user_id)

    def _handle_onboarding(self, user_id: str, query: str, state_info: dict) -> Optional[str]:
        state = state_info['state']
        user = state_info.get('user')
        lang = (user.get('language') if user else None) or 'en'
        
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
            db_manager.create_or_update_user(user_id, name=name, state='asking_company', language=lang)
            return self._get_lang_str(lang, 'ask_company', name=name)

        if state == 'asking_company':
            company = query.strip()
            if len(company) < 2: return self._get_lang_str(lang, 'invalid_company')
            name = user.get('name', 'Customer')
            db_manager.create_or_update_user(user_id, name=name, company=company, outlet_pos=company, state='complete', language=lang)
            return self._get_lang_str(lang, 'onboard_complete', name=name, company=company)
        
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
