"""
Background Worker for AI Platform
================================
Handles asynchronous tasks:
- Document embedding and indexing
- Auto-resolver analysis
- Knowledge base updates
- System maintenance
"""

import asyncio
import os
import sys
import time
import signal
from contextlib import asynccontextmanager

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.core.logging import logger
from app.core.database import get_db_manager
from app.services.qdrant_store import get_qdrant_store
from app.utils.embeddings import get_embeddings

class BackgroundWorker:
    """Main worker class for background AI tasks"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
        self.db_manager = None
        self.qdrant_store = None
        self.embeddings = None
        
    async def initialize(self):
        """Initialize worker services"""
        try:
            # Initialize database
            self.db_manager = get_db_manager()
            
            # Initialize vector store
            self.qdrant_store = get_qdrant_store()
            
            # Initialize embeddings
            self.embeddings = get_embeddings()
            
            logger.info("[Worker] Initialized successfully")
            
        except Exception as e:
            logger.error(f"[Worker] Initialization failed: {e}")
            raise
            
    async def start(self):
        """Start the background worker"""
        self.running = True
        logger.info("[Worker] Starting background tasks...")
        
        # Start periodic tasks
        self.tasks = [
            asyncio.create_task(self._embedding_processor()),
            asyncio.create_task(self._auto_resolver_trainer()),
            asyncio.create_task(self._system_maintenance()),
        ]
        
        # Wait for tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("[Worker] Tasks cancelled")
        except Exception as e:
            logger.error(f"[Worker] Task error: {e}")
            
    async def stop(self):
        """Gracefully stop the worker"""
        logger.info("[Worker] Stopping...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
            
        # Wait for cancellation
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
    async def _embedding_processor(self):
        """Process pending documents for embedding"""
        while self.running:
            try:
                # Check for new documents to embed
                if self.db_manager:
                    with self.db_manager.Session() as session:
                        # Get unprocessed knowledge files
                        knowledge_dir = settings.KNOWLEDGE_DIR
                        if os.path.exists(knowledge_dir):
                            # Process new files
                            await self._process_knowledge_updates()
                            
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"[Worker] Embedding processor error: {e}")
                await asyncio.sleep(60)
                
    async def _auto_resolver_trainer(self):
        """Train auto-resolver based on successful resolutions"""
        while self.running:
            try:
                # Analyze successful chat resolutions
                # Update confidence scores
                # Retrain models if needed
                
                logger.debug("[Worker] Auto-resolver training cycle")
                await asyncio.sleep(300)  # Every 5 minutes
                
            except Exception as e:
                logger.error(f"[Worker] Auto-resolver trainer error: {e}")
                await asyncio.sleep(600)
                
    async def _system_maintenance(self):
        """Perform system maintenance tasks"""
        while self.running:
            try:
                # Clean up old logs
                # Optimize vector store
                # Update system metrics
                
                logger.debug("[Worker] System maintenance cycle")
                await asyncio.sleep(3600)  # Every hour
                
            except Exception as e:
                logger.error(f"[Worker] System maintenance error: {e}")
                await asyncio.sleep(3600)
                
    async def _process_knowledge_updates(self):
        """Process updated knowledge files"""
        try:
            knowledge_dir = settings.KNOWLEDGE_DIR
            if not os.path.exists(knowledge_dir):
                return
                
            # Check for updated files
            # Re-embed and update vector store
            # This would integrate with the knowledge extraction service
            
            logger.debug("[Worker] Processed knowledge updates")
            
        except Exception as e:
            logger.error(f"[Worker] Knowledge processing error: {e}")

# Signal handlers for graceful shutdown
worker_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    if worker_instance:
        asyncio.create_task(worker_instance.stop())

async def main():
    """Main worker entry point"""
    global worker_instance
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start worker
    worker_instance = BackgroundWorker()
    
    try:
        await worker_instance.initialize()
        await worker_instance.start()
    except KeyboardInterrupt:
        logger.info("[Worker] Received interrupt signal")
    except Exception as e:
        logger.error(f"[Worker] Fatal error: {e}")
    finally:
        if worker_instance:
            await worker_instance.stop()

if __name__ == "__main__":
    asyncio.run(main())