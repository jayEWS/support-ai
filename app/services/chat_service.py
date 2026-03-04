import json
import re
from typing import Optional
from fastapi import UploadFile
from app.core.database import db_manager
from app.core.logging import logger, LogLatency
from app.utils.file_handler import save_upload
from app.services.rag_service import RAGService
from app.services.websocket_manager import manager

def _sanitize_text(text: str) -> str:
    """Remove invalid surrogate characters that break UTF-8 encoding."""
    if not text:
        return text
    # Encode with surrogatepass then decode with replace to strip surrogates
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')

class ChatService:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service
        # Track active chat sessions: user_id -> {message_count, has_escalation, ticket_id}
        self._sessions = {}

    # ============ Multi-Language Support ============
    LANG_STRINGS = {
        'id': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "Siapa nama kamu? 😊",
            'invalid_name': "Hmm, boleh tulis nama lengkap kamu? 😊",
            'ask_company': "Hai {name}! 👋\nNama perusahaan atau outlet kamu apa ya?\n(contoh: PT ABC / Warung Makan XYZ)",
            'invalid_company': "Boleh tulis nama perusahaan atau outlet kamu?",
            'onboard_complete': "Terima kasih {name}! ✅\nData kamu sudah kami simpan:\n• Nama: {name}\n• Outlet: {company}\n\nSekarang, ada yang bisa saya bantu hari ini? 😊",
            'welcome_back': "Hai {name}! 👋 Senang ketemu lagi.\nAda yang bisa saya bantu hari ini?",
            'welcome_back_no_name': "Halo! 👋 Senang ketemu lagi.\nAda yang bisa saya bantu hari ini?",
        },
        'en': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "What is your name? 😊",
            'invalid_name': "Could you please type your full name? 😊",
            'ask_company': "Hi {name}! 👋\nWhat is your company or outlet name?\n(e.g. PT ABC / Restaurant XYZ)",
            'invalid_company': "Could you please type your company or outlet name?",
            'onboard_complete': "Thank you {name}! ✅\nYour data has been saved:\n• Name: {name}\n• Outlet: {company}\n\nHow can I help you today? 😊",
            'welcome_back': "Hi {name}! 👋 Great to see you again.\nHow can I help you today?",
            'welcome_back_no_name': "Hello! 👋 Great to see you again.\nHow can I help you today?",
        },
        'zh': {
            'ask_language': "👋 Welcome to *Edgeworks Support*!\n\nPlease select your preferred language:\nSilakan pilih bahasa Anda:\n请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊",
            'ask_name': "请问您的名字是？😊",
            'invalid_name': "请输入您的全名 😊",
            'ask_company': "{name} 您好！👋\n请问您的公司或门店名称是什么？\n（例如：PT ABC / 餐厅 XYZ）",
            'invalid_company': "请输入您的公司或门店名称",
            'onboard_complete': "谢谢 {name}！✅\n您的信息已保存：\n• 姓名：{name}\n• 门店：{company}\n\n请问今天有什么可以帮助您的？😊",
            'welcome_back': "{name} 您好！👋 很高兴再次见到您。\n请问今天有什么可以帮助您的？",
            'welcome_back_no_name': "您好！👋 很高兴再次见到您。\n请问今天有什么可以帮助您的？",
        }
    }

    @staticmethod
    def detect_language(text: str) -> str | None:
        """Detect language from text. Returns 'id', 'en', 'zh', or None if ambiguous."""
        if not text:
            return None
        t = text.strip().lower()
        
        # Check for language selection (1/2/3)
        if t in ('1', 'bahasa', 'indonesia', 'bahasa indonesia', 'indo', 'id'):
            return 'id'
        if t in ('2', 'english', 'eng', 'en', 'inggris'):
            return 'en'
        if t in ('3', 'chinese', 'mandarin', '中文', 'zh', 'cina'):
            return 'zh'
        
        # Check for Chinese characters
        for ch in t:
            if '\u4e00' <= ch <= '\u9fff':
                return 'zh'
        
        # Check for strong Indonesian indicators
        indo_words = {'bagaimana', 'cara', 'tolong', 'bantu', 'apa', 'gimana', 'bisa', 'saya', 'mau',
                      'tidak', 'sudah', 'belum', 'kenapa', 'mengapa', 'dimana', 'kapan', 'siapa',
                      'terima', 'kasih', 'selamat', 'pagi', 'siang', 'sore', 'malam', 'permisi',
                      'mohon', 'silakan', 'kak', 'mas', 'mba', 'pak', 'bu', 'dengan', 'untuk', 'dari'}
        en_words = {'how', 'what', 'where', 'when', 'why', 'who', 'which', 'please', 'help',
                    'can', 'could', 'would', 'should', 'need', 'want', 'have', 'has', 'the',
                    'is', 'are', 'was', 'were', 'do', 'does', 'did', 'thank', 'thanks', 'yes',
                    'no', 'not', 'but', 'and', 'this', 'that', 'my', 'your', 'with', 'from'}
        
        words = set(t.split())
        indo_score = len(words & indo_words)
        en_score = len(words & en_words)
        
        if indo_score > en_score and indo_score >= 1:
            return 'id'
        if en_score > indo_score and en_score >= 1:
            return 'en'
        
        # Ambiguous short messages like "hi", "hello", "halo" — return None to ask
        return None

    @staticmethod
    def _detect_language_switch(text: str) -> str | None:
        """Detect if user is requesting a language switch (e.g. 'can i use english?', 'english please').
        Returns target language code or None."""
        t = text.strip().lower()
        # Direct language names or switch phrases
        en_triggers = {'english', 'use english', 'can i use english', 'switch to english', 'english please', 'i want english', 'in english'}
        id_triggers = {'indonesia', 'bahasa', 'bahasa indonesia', 'use indonesia', 'use bahasa', 'switch to indonesia', 'indonesian'}
        zh_triggers = {'chinese', 'mandarin', 'use chinese', 'switch to chinese', '中文', '切换中文', '用中文'}
        
        # Remove trailing punctuation for matching
        t_clean = t.rstrip('?!.,')
        
        if t_clean in en_triggers or any(t_clean.startswith(p) for p in ('can i use eng', 'switch to eng', 'i want eng', 'change to eng')):
            return 'en'
        if t_clean in id_triggers or any(t_clean.startswith(p) for p in ('can i use indo', 'switch to indo', 'change to indo', 'can i use bahasa')):
            return 'id'
        if t_clean in zh_triggers or any(t_clean.startswith(p) for p in ('can i use chin', 'switch to chin', 'change to chin', 'can i use mand')):
            return 'zh'
        return None

    def _get_lang_str(self, lang: str, key: str, **kwargs) -> str:
        """Get localized string with fallback to English."""
        strings = self.LANG_STRINGS.get(lang, self.LANG_STRINGS['en'])
        template = strings.get(key, self.LANG_STRINGS['en'].get(key, ''))
        return template.format(**kwargs) if kwargs else template

    def _get_user_state(self, user_id: str) -> dict:
        """Get user profile and onboarding state from DB"""
        user = db_manager.get_user(user_id)
        if not user:
            return {'state': 'new', 'user': None}

        # Check DB state field first (most reliable)
        db_state = user.get('state', '')
        if db_state == 'asking_language':
            return {'state': 'asking_language', 'user': user}
        if db_state == 'asking_name':
            return {'state': 'asking_name', 'user': user}
        if db_state == 'asking_company':
            return {'state': 'asking_company', 'user': user}
        if db_state == 'complete' and user.get('name') and user.get('company'):
            return {'state': 'complete', 'user': user}

        # Fallback: check if name looks like a real name (not auto-generated ID)
        name = user.get('name') or ''
        is_real_name = name and not name.startswith('cust_') and not name.startswith('User ') and name != user.get('identifier', '')

        if is_real_name and user.get('company'):
            return {'state': 'complete', 'user': user}
        elif is_real_name:
            return {'state': 'asking_company', 'user': user}
        elif user.get('language'):
            return {'state': 'asking_name', 'user': user}
        else:
            return {'state': 'asking_language', 'user': user}

    def _handle_onboarding(self, user_id: str, query: str, state_info: dict) -> Optional[str]:
        """Handle customer onboarding flow with multi-language. Returns response string or None to continue to RAG."""
        state = state_info['state']
        user = state_info.get('user')
        lang = (user.get('language') if user else None) or 'en'
        
        if state == 'new':
            # Brand new user — detect language from their first message
            detected_lang = self.detect_language(query)
            if detected_lang:
                # Language is clear from the message — set it and ask name directly
                db_manager.create_or_update_user(user_id, name=None, state='asking_name', language=detected_lang)
                greeting = self._get_lang_str(detected_lang, 'ask_name')
                welcome = {
                    'id': "Halo! 👋 Selamat datang di Edgeworks Support.\nSebelum mulai, boleh kenalan dulu?",
                    'en': "Hello! 👋 Welcome to Edgeworks Support.\nBefore we start, let me get to know you.",
                    'zh': "你好！👋 欢迎来到 Edgeworks 支持中心。\n在开始之前，让我先认识一下您。",
                }
                return f"{welcome.get(detected_lang, welcome['en'])}\n{greeting}"
            else:
                # Ambiguous (e.g. "hi") — ask for language preference
                db_manager.create_or_update_user(user_id, name=None, state='asking_language')
                return self._get_lang_str('en', 'ask_language')
        
        if state == 'asking_language':
            # User is selecting language
            detected_lang = self.detect_language(query)
            if not detected_lang:
                return "Please select your language / Silakan pilih bahasa Anda / 请选择您的语言：\n\n1️⃣ Bahasa Indonesia\n2️⃣ English\n3️⃣ 中文\n\nReply with 1, 2, or 3 😊"
            db_manager.create_or_update_user(user_id, state='asking_name', language=detected_lang)
            welcome = {
                'id': "Halo! 👋 Selamat datang di Edgeworks Support.\nSebelum mulai, boleh kenalan dulu?",
                'en': "Hello! 👋 Welcome to Edgeworks Support.\nBefore we start, let me get to know you.",
                'zh': "你好！👋 欢迎来到 Edgeworks 支持中心。\n在开始之前，让我先认识一下您。",
            }
            return f"{welcome.get(detected_lang, welcome['en'])}\n{self._get_lang_str(detected_lang, 'ask_name')}"
        
        if state == 'asking_name':
            # Check if user is trying to switch language instead of giving name
            switch_lang = self._detect_language_switch(query)
            if switch_lang:
                db_manager.create_or_update_user(user_id, state='asking_name', language=switch_lang)
                return self._get_lang_str(switch_lang, 'ask_name')
            # User is providing their name
            name = query.strip().title()
            if len(name) < 2 or len(name) > 100:
                return self._get_lang_str(lang, 'invalid_name')
            db_manager.create_or_update_user(user_id, name=name, state='asking_company', language=lang)
            return self._get_lang_str(lang, 'ask_company', name=name)

        if state == 'asking_company':
            # Check if user is trying to switch language instead of giving company
            switch_lang = self._detect_language_switch(query)
            if switch_lang:
                db_manager.create_or_update_user(user_id, state='asking_company', language=switch_lang)
                name = user.get('name', 'Customer') if user else 'Customer'
                return self._get_lang_str(switch_lang, 'ask_company', name=name)
            # User is providing company/outlet name
            company = query.strip()
            if len(company) < 2:
                return self._get_lang_str(lang, 'invalid_company')
            name = user.get('name', 'Customer') if user else 'Customer'
            db_manager.create_or_update_user(user_id, name=name, company=company, outlet_pos=company, state='complete', language=lang)
            return self._get_lang_str(lang, 'onboard_complete', name=name, company=company)
        
        if state == 'complete':
            # Detect language from current message and update if clearly different
            detected = self.detect_language(query)
            if detected and detected != (user.get('language') or 'en'):
                db_manager.create_or_update_user(user_id, state='complete', language=detected)
            elif not user.get('language') and detected:
                db_manager.create_or_update_user(user_id, state='complete', language=detected)
            # No onboarding needed
            return None
        
        return None

    def get_user_language(self, user_id: str) -> str:
        """Get user's preferred language. Default to 'en' (English)."""
        user = db_manager.get_user(user_id)
        return (user.get('language') if user else None) or 'en'

    def _check_recurring_issues(self, user_id: str, query: str) -> Optional[str]:
        """Check if customer has asked about similar issues before.
        Returns a context hint string if recurring, or None."""
        try:
            past_tickets = db_manager.get_tickets_by_user(user_id, limit=10)
            if not past_tickets:
                return None

            # Simple keyword matching to find similar past tickets
            query_words = set(query.lower().split())
            # Remove common stop words
            stop_words = {'di', 'ke', 'ya', 'dan', 'yang', 'untuk', 'ini', 'itu', 'ada',
                         'tidak', 'bisa', 'saya', 'mau', 'apa', 'gimana', 'bagaimana',
                         'cara', 'tolong', 'bantu', 'kak', 'mas', 'mba', 'pak', 'bu'}
            query_words -= stop_words

            if not query_words:
                return None

            similar_tickets = []
            for ticket in past_tickets:
                summary = (ticket.get('summary') or '').lower()
                summary_words = set(summary.split())
                overlap = query_words & summary_words
                if len(overlap) >= 2 or (len(query_words) <= 3 and len(overlap) >= 1 and len(query_words) > 0):
                    similar_tickets.append(ticket)

            if similar_tickets:
                latest = similar_tickets[0]
                ticket_id = latest['id']
                status = latest['status']
                created = latest.get('created_at', '')[:10] if latest.get('created_at') else ''

                if status in ('open', 'pending'):
                    return (f"📋 It looks like this issue is still being processed in Ticket #{ticket_id} "
                            f"(created {created}, status: {status}). "
                            f"Is there a new update, or is the same issue still ongoing?")
                else:
                    return (f"📋 A similar issue was previously handled in Ticket #{ticket_id} ({created}). "
                            f"Is the same issue happening again, or is this a new problem?")

            return None
        except Exception as e:
            logger.error(f"Recurring issue check error: {e}")
            return None

    async def process_portal_message(
        self, 
        query: Optional[str], 
        user_id: str, 
        file: Optional[UploadFile] = None,
        language: str = None
    ):
        with LogLatency("chat_service", "process_portal_message"):
            attachment_meta = None
            
            # 1. Handle File Upload
            if file and file.filename:
                file_bytes = await file.read()
                attachment_meta = save_upload(file_bytes, file.filename, destination="chat")
            
            # 2. Normalize Query
            if not query and attachment_meta:
                query = f"[Uploaded {attachment_meta['category']}: {attachment_meta['original_name']}]"
            
            if not query:
                return {"error": "Message required"}, 400

            # 3. Save User Message to DB
            att_json = json.dumps([attachment_meta]) if attachment_meta else None
            db_manager.save_message(user_id, "user", query, attachments=att_json)

            # 4. Check onboarding state
            state_info = self._get_user_state(user_id)
            onboarding_response = self._handle_onboarding(user_id, query, state_info)
            
            if onboarding_response:
                # Still in onboarding flow
                db_manager.save_message(user_id, "bot", onboarding_response)
                return {
                    "answer": onboarding_response,
                    "attachment": attachment_meta,
                    "confidence": 1.0,
                    "onboarding": True
                }, 200

            # 5. Customer is onboarded - track session
            if user_id not in self._sessions:
                self._sessions[user_id] = {'message_count': 0, 'has_escalation': False, 'ticket_id': None}
            self._sessions[user_id]['message_count'] += 1

            user = state_info.get('user', {})
            customer_name = user.get('name', '') if user else ''
            customer_context = ""
            if customer_name:
                company = user.get('company', '') or user.get('outlet_pos', '')
                customer_context = f" (Customer: {customer_name}, Outlet: {company})"

            # 5b. Check for recurring issues (only on first message of session)
            recurring_hint = None
            if self._sessions[user_id]['message_count'] == 1:
                recurring_hint = self._check_recurring_issues(user_id, query)

            # 6. Get AI Answer via RAG Service
            rag_query = query + customer_context if customer_context else query
            user_lang = self.get_user_language(user_id)  # Re-read from DB (may have been updated by onboarding detection)
            rag_res = await self.rag_service.query(rag_query, language=user_lang)
            answer = _sanitize_text(rag_res.answer)

            # Prepend recurring issue notice if found
            if recurring_hint:
                answer = recurring_hint + "\n\n---\n\n" + answer

            # Save bot response
            db_manager.save_message(user_id, "bot", answer)

            # 7. Check for Live Chat Escalation Trigger
            escalate = False
            escalation_triggers = [
                "hubungkan dengan tim",
                "menghubungkan anda dengan spesialis",
                "hubungkan dengan spesialis",
                "tim yang bisa bantu"
            ]
            if any(trigger in answer.lower() for trigger in escalation_triggers):
                escalate = True
            
            response_data = {
                "answer": answer,
                "attachment": attachment_meta,
                "confidence": rag_res.confidence,
                "customer_name": customer_name
            }

            if escalate:
                try:
                    available_agents = db_manager.get_available_agents()
                    agent_id = available_agents[0]["user_id"] if available_agents else None
                    
                    ticket_id = db_manager.create_ticket(user_id, f"Live chat request: {query}", query)
                    self._sessions[user_id]['has_escalation'] = True
                    self._sessions[user_id]['ticket_id'] = ticket_id
                    
                    if not agent_id:
                        db_manager.add_to_queue(ticket_id, priority_level=2)
                        response_data.update({
                            "live_session_started": False,
                            "status": "queued",
                            "message": "All agents are currently busy. You have been placed in a queue.",
                            "ticket_id": ticket_id
                        })
                    else:
                        session_id = db_manager.create_chat_session(ticket_id, agent_id, user_id)
                        agent = db_manager.get_agent(agent_id)
                        if agent:
                            current_count = (agent.get("active_chat_count", 0) or 0) + 1
                            db_manager.update_agent_presence(agent_id, "busy", current_count)
                        
                        response_data.update({
                            "live_session_started": True,
                            "session_id": session_id,
                            "agent_id": agent_id,
                            "ticket_id": ticket_id
                        })
                except Exception as e:
                    logger.error(f"Failed to escalate in chat_service: {e}")

            return response_data, 200

    async def close_chat(self, user_id: str, option: str = "close") -> dict:
        """
        Smart close chat:
        - option='close': AI resolved, no ticket needed, just close & clear
        - option='ticket': Create ticket with AI summary (escalation/investigation)
        - option='ticket_and_notify': Create ticket + send ticket number to user
        """
        session = self._sessions.get(user_id, {})
        messages = db_manager.get_messages(user_id)
        msg_count = len(messages) if messages else 0
        lang = self.get_user_language(user_id)

        close_msgs = {
            'id': "Chat ditutup. Terima kasih sudah menghubungi Edgeworks Support! 🙏",
            'en': "Chat closed. Thank you for contacting Edgeworks Support! 🙏",
            'zh': "聊天已结束。感谢您联系 Edgeworks 支持！🙏",
        }

        if option == 'close':
            close_msg = close_msgs.get(lang, close_msgs['en'])
            db_manager.save_message(user_id, "bot", close_msg)
            self._sessions.pop(user_id, None)
            return {
                "status": "closed",
                "ticket_created": False,
                "message": close_msg,
                "message_count": msg_count
            }

        elif option in ('ticket', 'ticket_and_notify'):
            # Need ticket - escalation or unresolved issue
            if not messages:
                no_msg = {'id': 'Tidak ada percakapan untuk dibuatkan tiket.', 'en': 'No conversation found to create a ticket.', 'zh': '没有对话记录可以创建工单。'}
                return {"status": "error", "message": no_msg.get(lang, no_msg['en'])}

            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])

            try:
                from app.services.rag_engine import rag_engine
                if not rag_engine:
                    return {"status": "error", "message": "RAG Engine is not ready yet."}

                # Use LLM to summarize and determine priority
                res = await rag_engine.llm.ainvoke(
                    "You are a support ticket summarizer. Create a JSON with the following fields:\n"
                    "- 'summary': summarize the issue in 1-2 sentences in English\n"
                    "- 'priority': one of Urgent, High, Medium, Low\n"
                    "- 'category': issue category (POS, Closing, Hardware, Network, etc.)\n\n"
                    "Chat history:\n" + history_text
                )
                import json as _json
                ticket_data = _json.loads(res.content.replace('```json','').replace('```','').strip())

                from app.services.sla_service import SLAService
                due_at = SLAService.calculate_due_date(ticket_data.get('priority', 'Medium'))

                ticket_id = db_manager.create_ticket(
                    user_id,
                    ticket_data.get('summary', 'Support request'),
                    history_text,
                    priority=ticket_data.get('priority', 'Medium'),
                    due_at=due_at
                )

                # Get customer info for response
                user = db_manager.get_user(user_id)
                name = user.get('name', 'Customer') if user else 'Customer'

                if option == 'ticket_and_notify':
                    summary_text = ticket_data.get('summary', '-')
                    priority_text = ticket_data.get('priority', 'Medium')
                    due_text = due_at.strftime('%d %b %Y %H:%M') if due_at else '-'
                    notify_templates = {
                        'id': f"Tiket #{ticket_id} sudah dibuat 📝\n• Masalah: {summary_text}\n• Prioritas: {priority_text}\n• Target selesai: {due_text}\n\nTim kami akan follow up ya {name}. Terima kasih! 🙏",
                        'en': f"Ticket #{ticket_id} has been created 📝\n• Issue: {summary_text}\n• Priority: {priority_text}\n• Target completion: {due_text}\n\nOur team will follow up with you, {name}. Thank you! 🙏",
                        'zh': f"工单 #{ticket_id} 已创建 📝\n• 问题：{summary_text}\n• 优先级：{priority_text}\n• 目标完成时间：{due_text}\n\n我们的团队会跟进，{name}。谢谢！🙏",
                    }
                    notify_msg = notify_templates.get(lang, notify_templates['en'])
                    db_manager.save_message(user_id, "bot", notify_msg)
                else:
                    simple_close = {'id': f'Tiket #{ticket_id} dibuat. Chat ditutup.', 'en': f'Ticket #{ticket_id} created. Chat closed.', 'zh': f'工单 #{ticket_id} 已创建。聊天已结束。'}
                    db_manager.save_message(user_id, "bot", simple_close.get(lang, simple_close['en']))

                self._sessions.pop(user_id, None)
                return {
                    "status": "closed",
                    "ticket_created": True,
                    "ticket_id": ticket_id,
                    "priority": ticket_data.get('priority', 'Medium'),
                    "summary": ticket_data.get('summary', ''),
                    "category": ticket_data.get('category', ''),
                    "due_at": due_at.strftime('%Y-%m-%d %H:%M') if due_at else None,
                    "message": {'id': f'Tiket #{ticket_id} berhasil dibuat.', 'en': f'Ticket #{ticket_id} created successfully.', 'zh': f'工单 #{ticket_id} 创建成功。'}.get(lang, f'Ticket #{ticket_id} created.'),
                    "message_count": msg_count
                }
            except Exception as e:
                logger.error(f"Smart close error: {e}")
                err_msg = {'id': f'Gagal membuat tiket: {str(e)}', 'en': f'Failed to create ticket: {str(e)}', 'zh': f'创建工单失败：{str(e)}'}
                return {"status": "error", "message": err_msg.get(lang, err_msg['en'])}

        return {"status": "error", "message": "Invalid option"}
