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

    def _get_user_state(self, user_id: str) -> dict:
        """Get user profile and onboarding state from DB"""
        user = db_manager.get_user(user_id)
        if user and user.get('name') and user.get('company'):
            return {'state': 'complete', 'user': user}
        elif user and user.get('name'):
            return {'state': 'asking_company', 'user': user}
        elif user:
            return {'state': 'asking_name', 'user': user}
        return {'state': 'new', 'user': None}

    def _handle_onboarding(self, user_id: str, query: str, state_info: dict) -> Optional[str]:
        """Handle customer onboarding flow. Returns response string or None to continue to RAG."""
        state = state_info['state']
        
        if state == 'new':
            # First time user - create record and ask for name
            db_manager.create_or_update_user(user_id, name=None, state='asking_name')
            return ("Halo! \ud83d\udc4b Selamat datang di Edgeworks Support.\n\n"
                    "Sebelum mulai, boleh kenalan dulu?\n"
                    "Siapa nama kamu?")
        
        if state == 'asking_name':
            # User is providing their name
            name = query.strip().title()
            if len(name) < 2 or len(name) > 100:
                return "Hmm, boleh tulis nama lengkap kamu? \ud83d\ude0a"
            db_manager.create_or_update_user(user_id, name=name, state='asking_company')
            return f"Hai {name}! \ud83d\udc4b\nNama perusahaan atau outlet kamu apa ya?\n(contoh: PT ABC / Warung Makan XYZ)"

        if state == 'asking_company':
            # User is providing company/outlet name
            company = query.strip()
            if len(company) < 2:
                return "Boleh tulis nama perusahaan atau outlet kamu?"
            user = state_info['user']
            db_manager.create_or_update_user(user_id, name=user.get('name'), company=company, outlet_pos=company, state='complete')
            name = user.get('name', 'Kak')
            return (f"Terima kasih {name}! \u2705\n"
                    f"Data kamu sudah kami simpan:\n"
                    f"\u2022 Nama: {name}\n"
                    f"\u2022 Outlet: {company}\n\n"
                    f"Sekarang, ada yang bisa saya bantu hari ini? \ud83d\ude0a")
        
        # state == 'complete' -> no onboarding needed
        return None

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
                    return (f"📋 Kak, sepertinya masalah ini masih dalam proses di Tiket #{ticket_id} "
                            f"(dibuat {created}, status: {status}). "
                            f"Apakah ada update baru atau kendala yang sama masih berlanjut?")
                else:
                    return (f"📋 Kak, masalah serupa pernah ditangani di Tiket #{ticket_id} ({created}). "
                            f"Apakah masalah yang sama muncul lagi, atau ada kendala baru?")

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
            rag_res = await self.rag_service.query(rag_query)
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

        if option == 'close':
            # AI resolved it - just close, no ticket
            db_manager.save_message(user_id, "bot", "Chat ditutup. Terima kasih sudah menghubungi Edgeworks Support! \ud83d\ude4f")
            # Clear session tracking
            self._sessions.pop(user_id, None)
            return {
                "status": "closed",
                "ticket_created": False,
                "message": "Chat ditutup. Terima kasih sudah menghubungi Edgeworks Support! \ud83d\ude4f",
                "message_count": msg_count
            }

        elif option in ('ticket', 'ticket_and_notify'):
            # Need ticket - escalation or unresolved issue
            if not messages:
                return {"status": "error", "message": "Tidak ada percakapan untuk dibuatkan tiket."}

            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])

            try:
                from app.services.rag_engine import rag_engine
                if not rag_engine:
                    return {"status": "error", "message": "RAG Engine belum siap."}

                # Use LLM to summarize and determine priority
                res = await rag_engine.llm.ainvoke(
                    "Kamu adalah support ticket summarizer. Buat JSON dengan field:\n"
                    "- 'summary': ringkasan masalah dalam 1-2 kalimat Bahasa Indonesia\n"
                    "- 'priority': salah satu dari Urgent, High, Medium, Low\n"
                    "- 'category': kategori masalah (POS, Closing, Hardware, Network, dll)\n\n"
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
                name = user.get('name', 'Kak') if user else 'Kak'

                if option == 'ticket_and_notify':
                    notify_msg = (
                        f"Tiket #{ticket_id} sudah dibuat \ud83d\udcdd\n"
                        f"\u2022 Masalah: {ticket_data.get('summary', '-')}\n"
                        f"\u2022 Prioritas: {ticket_data.get('priority', 'Medium')}\n"
                        f"\u2022 Target selesai: {due_at.strftime('%d %b %Y %H:%M') if due_at else '-'}\n\n"
                        f"Tim kami akan follow up ya {name}. Terima kasih! \ud83d\ude4f"
                    )
                    db_manager.save_message(user_id, "bot", notify_msg)
                else:
                    db_manager.save_message(user_id, "bot", f"Tiket #{ticket_id} dibuat. Chat ditutup.")

                self._sessions.pop(user_id, None)
                return {
                    "status": "closed",
                    "ticket_created": True,
                    "ticket_id": ticket_id,
                    "priority": ticket_data.get('priority', 'Medium'),
                    "summary": ticket_data.get('summary', ''),
                    "category": ticket_data.get('category', ''),
                    "due_at": due_at.strftime('%Y-%m-%d %H:%M') if due_at else None,
                    "message": f"Tiket #{ticket_id} berhasil dibuat.",
                    "message_count": msg_count
                }
            except Exception as e:
                logger.error(f"Smart close error: {e}")
                return {"status": "error", "message": f"Gagal membuat tiket: {str(e)}"}

        return {"status": "error", "message": "Invalid option"}
