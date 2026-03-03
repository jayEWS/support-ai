import json
import re
from typing import Optional
from fastapi import UploadFile
from app.core.database import db_manager
from app.core.logging import logger, LogLatency
from app.utils.file_handler import save_upload
from app.services.rag_service import RAGService
from app.services.websocket_manager import manager

class ChatService:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

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

            # 5. Customer is onboarded - get personalized context
            user = state_info.get('user', {})
            customer_name = user.get('name', '') if user else ''
            customer_context = ""
            if customer_name:
                company = user.get('company', '') or user.get('outlet_pos', '')
                customer_context = f" (Customer: {customer_name}, Outlet: {company})"

            # 6. Get AI Answer via RAG Service
            rag_query = query + customer_context if customer_context else query
            rag_res = await self.rag_service.query(rag_query)
            answer = rag_res.answer

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
                    
                    if not agent_id:
                        db_manager.add_to_queue(ticket_id, priority_level=2)
                        response_data.update({
                            "live_session_started": False,
                            "status": "queued",
                            "message": "All agents are currently busy. You have been placed in a queue."
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
                            "agent_id": agent_id
                        })
                except Exception as e:
                    logger.error(f"Failed to escalate in chat_service: {e}")

            return response_data, 200
