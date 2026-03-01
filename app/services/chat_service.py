import json
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

            # 4. Get AI Answer via RAG Service
            rag_res = await self.rag_service.query(query)
            answer = rag_res.answer

            # 5. Check for Live Chat Escalation Trigger
            # (Re-using logic from original main.py)
            escalate = False
            if "menghubungkan Anda dengan spesialis produk kami" in answer.lower():
                escalate = True
            
            response_data = {
                "answer": answer,
                "attachment": attachment_meta,
                "confidence": rag_res.confidence
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
