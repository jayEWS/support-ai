import json
import os
from datetime import datetime, timezone
from app.core.database import db_manager
from app.core.logging import logger
from app.services.rag_service import RAGService

class KnowledgeExtractor:
    """
    Self-Learning Pipeline: Automatically extracts structured knowledge 
    from resolved support tickets to improve the AI's future performance.
    """
    
    def __init__(self, rag_service: RAGService):
        self.rag = rag_service
        self.db = db_manager

    async def extract_from_ticket(self, ticket_id: int):
        """Analyze a closed ticket and generate a new KB entry."""
        session = self.db.get_session()
        try:
            from app.models.models import Ticket
            ticket = session.get(Ticket, ticket_id)
            if not ticket or not ticket.full_history:
                return
            
            # 1. Use LLM to extract structured knowledge
            llm = self.rag._get_llm()
            prompt = f"""Analyze the following support ticket history and extract a structured troubleshooting guide.
Format the output as a clean Markdown KB article.

TICKET HISTORY:
{ticket.full_history}

REQUIRED STRUCTURE:
# [Issue Title]
## Symptoms
## Root Cause
## Resolution Steps
## Category: {ticket.category or 'General'}

Keep it technical, concise, and accurate."""

            res = await llm.ainvoke(prompt)
            kb_content = res.content.strip()
            
            # 2. Save as a new KB file
            filename = f"extracted_ticket_{ticket_id}.md"
            file_path = os.path.join("data", "knowledge", filename)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(kb_content)
            
            # 3. Update Metadata
            self.db.save_knowledge_metadata(
                filename=filename,
                file_path=file_path,
                uploaded_by="System_AI_Extractor",
                status="Processing"
            )
            
            logger.info(f"✅ Knowledge extracted from Ticket #{ticket_id} and saved as {filename}")
            
            # 4. Trigger Re-indexing (Optionally queued)
            return filename
            
        except Exception as e:
            logger.error(f"Failed to extract knowledge from Ticket #{ticket_id}: {e}")
        finally:
            self.db.Session.remove()

# Instantiate extractor
# Note: In a real app, this would be injected via app state
knowledge_extractor = None 
