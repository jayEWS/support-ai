import asana
from app.core.config import settings
from app.core.logging import logger

class AsanaHandler:
    def __init__(self):
        if settings.ASANA_ENABLED and settings.ASANA_ACCESS_TOKEN:
            self.client = asana.Client.access_token(settings.ASANA_ACCESS_TOKEN)
            self.project_gid = settings.ASANA_PROJECT_GID
        else:
            self.client = None

    def create_task_from_ticket(self, ticket_id: int, customer_name: str, summary: str, history: str, priority: str):
        """Create a new task in Asana for a support ticket."""
        if not self.client:
            return None
        
        try:
            # Map Priority to Asana (Optional: you can use custom fields if they exist)
            task_name = f"Support Ticket #{ticket_id}: {customer_name}"
            notes = f"SUMMARY: {summary}

CHAT HISTORY:
{history}"
            
            result = self.client.tasks.create_task({
                'name': task_name,
                'notes': notes,
                'projects': [self.project_gid],
                'pretty': True
            })
            
            logger.info(f"Asana task created: {result['gid']} for Ticket #{ticket_id}")
            return result['gid']
        except Exception as e:
            logger.error(f"Error creating Asana task: {e}")
            return None

    def sync_task_status(self, asana_task_gid: str):
        """Check if Asana task is completed and return status."""
        if not self.client:
            return None
        
        try:
            task = self.client.tasks.get_task(asana_task_gid)
            return "resolved" if task.get("completed") else "open"
        except Exception as e:
            logger.error(f"Error syncing Asana task: {e}")
            return None

asana_handler = AsanaHandler()
