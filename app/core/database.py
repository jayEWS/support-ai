from sqlalchemy import create_engine, func, or_, desc, literal_column, case
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload
from app.models.models import (
    Base, User, Message, Ticket, Agent, ChatSession, ChatMessage, 
    AgentPresence, SLARule, TicketQueue, Macro, CSATSurvey, 
    KnowledgeMetadata, AuditLog, Role, Permission, AuthMFAChallenge, 
    AuthRefreshToken, AuthMagicLink, WhatsAppMessage, SystemSetting,
    Outlet, POSDevice, POSTransaction, Voucher, Membership, 
    InventoryItem, AIInteraction, IS_MSSQL, IS_POSTGRES, IS_SQLITE
)
from app.core.config import settings
from app.core.logging import logger
import json
from datetime import datetime, timezone
from typing import List, Optional

class DatabaseManager:
    def __init__(self):
        # Build engine kwargs based on DB type
        engine_kwargs = {
            "pool_pre_ping": True,       # Auto-recover stale connections
            "pool_size": 20,             # Increased for production (was 10)
            "max_overflow": 10,          # Burst capacity
            "pool_recycle": 3600,        # Recycle connections every hour
        }

        if IS_MSSQL:
            engine_kwargs["connect_args"] = {"connect_timeout": 10}
        elif IS_POSTGRES:
            engine_kwargs["connect_args"] = {"connect_timeout": 10, "options": "-c timezone=utc"}
        elif IS_SQLITE:
            # SQLite doesn't support pool_size / max_overflow
            engine_kwargs = {}

        db_label = "PostgreSQL" if IS_POSTGRES else "SQL Server" if IS_MSSQL else "SQLite"
        logger.info(f"Initializing {db_label} database engine...")

        self.engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self._init_db()

    def _init_db(self):
        """Create all tables if they don't exist."""
        try:
            Base.metadata.create_all(self.engine)
            db_label = "PostgreSQL" if IS_POSTGRES else "SQL Server" if IS_MSSQL else "SQLite"
            logger.info(f"{db_label} database tables verified/created.")
            # Cleanup expired tokens on startup
            self._cleanup_expired_tokens()
        except Exception as e:
            logger.error(f"Error initializing SQL Server: {e}")

    def _cleanup_expired_tokens(self):
        """Remove expired MFA challenges, refresh tokens, and magic links to prevent table bloat."""
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)
            deleted_mfa = session.query(AuthMFAChallenge).filter(AuthMFAChallenge.expires_at < now).delete(synchronize_session=False)
            deleted_refresh = session.query(AuthRefreshToken).filter(
                or_(AuthRefreshToken.expires_at < now, AuthRefreshToken.revoked_at.isnot(None))
            ).delete(synchronize_session=False)
            deleted_magic = session.query(AuthMagicLink).filter(AuthMagicLink.expires_at < now).delete(synchronize_session=False)
            session.commit()
            total = deleted_mfa + deleted_refresh + deleted_magic
            if total > 0:
                logger.info(f"Cleaned up expired tokens: {deleted_mfa} MFA, {deleted_refresh} refresh, {deleted_magic} magic links")
        except Exception as e:
            session.rollback()
            logger.warning(f"Token cleanup skipped: {e}")
        finally:
            self.Session.remove()

    def get_session(self):
        return self.Session()

    # ============ RBAC Management ============
    def create_permission(self, name: str, description: str = None, category: str = "General"):
        session = self.get_session()
        try:
            perm = session.query(Permission).filter_by(name=name).first()
            if not perm:
                perm = Permission(name=name, description=description, category=category)
                session.add(perm)
                session.commit()
            return perm
        finally:
            self.Session.remove()

    def create_role(self, name: str, description: str = None, permissions: List[str] = []):
        session = self.get_session()
        try:
            role = session.query(Role).filter_by(name=name).first()
            if not role:
                role = Role(name=name, description=description)
                session.add(role)
            
            if permissions:
                perm_objs = session.query(Permission).filter(Permission.name.in_(permissions)).all()
                role.permissions = perm_objs
            
            session.commit()
            return role
        finally:
            self.Session.remove()

    def assign_role_to_agent(self, username: str, role_name: str):
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(user_id=username).first()
            role = session.query(Role).filter_by(name=role_name).first()
            if agent and role:
                if role not in agent.roles:
                    agent.roles.append(role)
                    session.commit()
            return True
        finally:
            self.Session.remove()

    def update_agent_direct_permissions(self, username: str, permission_names: List[str]):
        """Individual user privilege overrides (userprivileges)"""
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(user_id=username).first()
            if agent:
                perms = session.query(Permission).filter(Permission.name.in_(permission_names)).all()
                agent.direct_permissions = perms
                session.commit()
            return True
        finally:
            self.Session.remove()

    def get_agent_effective_permissions(self, username: str) -> List[str]:
        """Effective permissions: (Group Perms) + (Individual Perms)"""
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(user_id=username).first()
            if not agent: return []
            
            effective = set()
            for role in agent.roles:
                for p in role.permissions:
                    effective.add(p.name)
            for p in agent.direct_permissions:
                effective.add(p.name)
            return list(effective)
        finally:
            self.Session.remove()

    def get_all_roles(self):
        session = self.get_session()
        try:
            roles = session.query(Role).all()
            return [{"id": r.id, "name": r.name, "description": r.description, "perms": [p.name for p in r.permissions]} for r in roles]
        finally:
            self.Session.remove()

    def get_all_permissions(self):
        session = self.get_session()
        try:
            perms = session.query(Permission).all()
            return [{"id": p.id, "name": p.name, "category": p.category, "description": p.description} for p in perms]
        finally:
            self.Session.remove()

    # ============ Auth (MFA + Refresh Tokens) ============
    def create_mfa_challenge(self, user_id: str, code_hash: str, expires_at: datetime):
        session = self.get_session()
        try:
            challenge = AuthMFAChallenge(user_id=user_id, code_hash=code_hash, expires_at=expires_at)
            session.add(challenge)
            session.commit()
            session.refresh(challenge)
            return challenge.id
        finally:
            self.Session.remove()

    def get_mfa_challenge(self, challenge_id: int):
        session = self.get_session()
        try:
            c = session.get(AuthMFAChallenge, challenge_id)
            if not c:
                return None
            return {
                "id": c.id,
                "user_id": c.user_id,
                "code_hash": c.code_hash,
                "expires_at": c.expires_at,
                "attempts": c.attempts,
                "created_at": c.created_at
            }
        finally:
            self.Session.remove()

    def get_latest_mfa_challenge(self, user_id: str):
        session = self.get_session()
        try:
            c = session.query(AuthMFAChallenge).filter_by(user_id=user_id).order_by(desc(AuthMFAChallenge.created_at)).first()
            if not c:
                return None
            return {
                "id": c.id,
                "user_id": c.user_id,
                "code_hash": c.code_hash,
                "expires_at": c.expires_at,
                "attempts": c.attempts,
                "created_at": c.created_at
            }
        finally:
            self.Session.remove()

    def increment_mfa_attempts(self, challenge_id: int):
        session = self.get_session()
        try:
            c = session.get(AuthMFAChallenge, challenge_id)
            if c:
                c.attempts = (c.attempts or 0) + 1
                session.commit()
        finally:
            self.Session.remove()

    def delete_mfa_challenge(self, challenge_id: int):
        session = self.get_session()
        try:
            session.query(AuthMFAChallenge).filter_by(id=challenge_id).delete()
            session.commit()
        finally:
            self.Session.remove()

    def create_refresh_token(self, user_id: str, token_hash: str, expires_at: datetime, user_agent: str = None):
        session = self.get_session()
        try:
            t = AuthRefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at, user_agent=user_agent)
            session.add(t)
            session.commit()
            return True
        finally:
            self.Session.remove()

    def get_refresh_token(self, token_hash: str):
        session = self.get_session()
        try:
            t = session.query(AuthRefreshToken).filter_by(token_hash=token_hash).first()
            if not t:
                return None
            return {
                "id": t.id,
                "user_id": t.user_id,
                "token_hash": t.token_hash,
                "expires_at": t.expires_at,
                "revoked_at": t.revoked_at,
                "created_at": t.created_at,
                "user_agent": t.user_agent
            }
        finally:
            self.Session.remove()

    def revoke_refresh_token(self, token_hash: str):
        session = self.get_session()
        try:
            t = session.query(AuthRefreshToken).filter_by(token_hash=token_hash).first()
            if t and not t.revoked_at:
                t.revoked_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            self.Session.remove()

    # ============ Knowledge Base ============
    def save_knowledge_metadata(self, filename: str, file_path: str, uploaded_by: str = None, status: str = "Processing", source_url: str = None):
        session = self.get_session()
        try:
            meta = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if meta:
                meta.file_path = file_path
                meta.upload_date = datetime.now(timezone.utc)
                meta.uploaded_by = uploaded_by or meta.uploaded_by
                meta.status = status
                if source_url is not None:
                    meta.source_url = source_url
            else:
                meta = KnowledgeMetadata(filename=filename, file_path=file_path, uploaded_by=uploaded_by, status=status, source_url=source_url)
                session.add(meta)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving knowledge metadata: {e}")
        finally:
            self.Session.remove()

    def get_all_knowledge(self):
        session = self.get_session()
        try:
            items = session.query(KnowledgeMetadata).order_by(desc(KnowledgeMetadata.upload_date)).all()
            return [ { 
                "id": i.id, 
                "filename": i.filename, 
                "file_path": i.file_path, 
                "upload_date": i.upload_date.isoformat() if i.upload_date else None,
                "uploaded_by": i.uploaded_by,
                "status": i.status,
                "source_url": getattr(i, 'source_url', None)
            } for i in items ]
        finally:
            self.Session.remove()

    def update_knowledge_status(self, filename: str, status: str):
        session = self.get_session()
        try:
            meta = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if meta:
                meta.status = status
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating knowledge status: {e}")
        finally:
            self.Session.remove()

    def get_knowledge_metadata(self, filename: str):
        session = self.get_session()
        try:
            return session.query(KnowledgeMetadata).filter_by(filename=filename).first()
        finally:
            self.Session.remove()

    def delete_knowledge_metadata(self, filename: str):
        session = self.get_session()
        try:
            session.query(KnowledgeMetadata).filter_by(filename=filename).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting knowledge: {e}")
        finally:
            self.Session.remove()

    # ============ Messages ============
    def _ensure_user_exists(self, user_id: str, session):
        """Ensure a User record exists for the given user_id (auto-create if missing)."""
        from app.models.models import User
        existing = session.query(User).filter_by(identifier=user_id).first()
        if not existing:
            user = User(identifier=user_id, name=None)
            session.add(user)
            session.flush()

    def save_message(self, user_id: str, role: str, content: str, attachments: str = None):
        session = self.get_session()
        try:
            # Sanitize content to remove surrogate characters
            if content:
                content = content.encode('utf-8', errors='replace').decode('utf-8')
            self._ensure_user_exists(user_id, session)
            msg = Message(user_id=user_id, role=role, content=content, attachments=attachments)
            session.add(msg)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving message: {e}")
        finally:
            self.Session.remove()

    def get_messages(self, user_id: str):
        session = self.get_session()
        try:
            msgs = session.query(Message).filter_by(user_id=user_id).order_by(Message.timestamp).all()
            return [ { "role": m.role, "content": m.content, "attachments": m.attachments, "timestamp": m.timestamp } for m in msgs ]
        finally:
            self.Session.remove()

    def clear_messages(self, user_id: str):
        """Clear all portal messages for a user (after session ends and ticket is created)."""
        session = self.get_session()
        try:
            session.query(Message).filter_by(user_id=user_id).delete()
            session.commit()
            logger.info(f"Cleared messages for user {user_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error clearing messages for {user_id}: {e}")
        finally:
            self.Session.remove()

    def get_active_portal_chats(self):
        """Get users with active portal messages (live chats not yet closed).
        Returns list of active chat sessions with user info and last message preview."""
        session = self.get_session()
        try:
            from sqlalchemy import func as sa_func

            # Subquery: aggregate stats per user
            active_users = session.query(
                Message.user_id,
                sa_func.count(Message.id).label('msg_count'),
                sa_func.max(Message.timestamp).label('last_msg_time'),
            ).group_by(Message.user_id).subquery()

            # Join with User table for name/company
            results = session.query(
                active_users.c.user_id,
                active_users.c.msg_count,
                active_users.c.last_msg_time,
                User.name,
                User.company,
            ).outerjoin(User, active_users.c.user_id == User.identifier) \
             .order_by(active_users.c.last_msg_time.desc()).all()

            if not results:
                return []

            # Batch-fetch all last messages & last user messages in 2 queries instead of 2N
            user_ids = [r.user_id for r in results]

            # Last message per user (any role)
            last_msgs = {}
            for uid in user_ids:
                m = session.query(Message).filter_by(user_id=uid) \
                    .order_by(Message.timestamp.desc()).first()
                if m:
                    last_msgs[uid] = m

            # Last user (customer) message per user
            last_user_msgs = {}
            for uid in user_ids:
                m = session.query(Message).filter_by(user_id=uid, role='user') \
                    .order_by(Message.timestamp.desc()).first()
                if m:
                    last_user_msgs[uid] = m

            chats = []
            for r in results:
                last_msg = last_msgs.get(r.user_id)
                last_user_msg = last_user_msgs.get(r.user_id)

                chats.append({
                    "user_id": r.user_id,
                    "name": r.name or "Anonymous",
                    "company": r.company or "",
                    "message_count": r.msg_count,
                    "last_message": last_msg.content[:100] if last_msg and last_msg.content else "",
                    "last_message_role": last_msg.role if last_msg else "",
                    "last_user_message": last_user_msg.content[:100] if last_user_msg and last_user_msg.content else "",
                    "last_activity": r.last_msg_time.isoformat() if r.last_msg_time else "",
                    "status": "waiting" if (last_msg and last_msg.role == 'user') else "replied"
                })
            return chats
        except Exception as e:
            logger.error(f"Error getting active portal chats: {e}")
            return []
        finally:
            self.Session.remove()

    def get_unified_history(self, user_id: str, ticket_id: Optional[int] = None):
        """Merges messages from both bot portal and live chat for a full view."""
        session = self.get_session()
        try:
            # 1. Fetch portal messages (may be empty if cleared after close)
            portal_msgs = session.query(
                literal_column("'bot'").label("source"),
                Message.role.label("role"),
                Message.content.label("content"),
                Message.timestamp.label("time")
            ).filter(Message.user_id == user_id).all()

            # 2. Fetch live chat messages
            live_msgs = []
            if ticket_id:
                live_msgs = session.query(
                    literal_column("'live'").label("source"),
                    ChatMessage.sender_type.label("role"),
                    ChatMessage.content.label("content"),
                    ChatMessage.sent_at.label("time")
                ).join(ChatSession, ChatMessage.session_id == ChatSession.id) \
                 .filter(ChatSession.ticket_id == ticket_id).all()

            # Merge and sort
            all_msgs = []
            for m in portal_msgs + live_msgs:
                role = m.role
                if role == 'user': role = 'customer'
                if role == 'assistant' or role == 'ai': role = 'bot'
                all_msgs.append({
                    "source": m.source,
                    "role": role,
                    "content": m.content,
                    "timestamp": m.time.isoformat() if m.time else None
                })
            
            # 3. Fallback: if no messages found but ticket exists, parse from ticket's full_history
            if not all_msgs and ticket_id:
                ticket = session.query(Ticket).filter_by(id=ticket_id).first()
                if ticket and ticket.full_history:
                    for line in ticket.full_history.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("USER:"):
                            all_msgs.append({"source": "bot", "role": "user", "content": line[5:].strip(), "timestamp": None})
                        elif line.startswith("BOT:") or line.startswith("ASSISTANT:"):
                            prefix_len = 4 if line.startswith("BOT:") else 10
                            all_msgs.append({"source": "bot", "role": "bot", "content": line[prefix_len:].strip(), "timestamp": None})

            return sorted(all_msgs, key=lambda x: x['timestamp'] or '')
        finally:
            self.Session.remove()

    # ============ Tickets ============
    def create_ticket(self, user_id: str, summary: str, full_history: str, priority: str = 'Medium', due_at: datetime = None, status: str = 'open'):
        session = self.get_session()
        try:
            ticket = Ticket(user_id=user_id, summary=summary, full_history=full_history, priority=priority, due_at=due_at, status=status)
            session.add(ticket)
            session.flush() # Get ID before commit
            
            # Auto-add to queue for Milestone 3 automated routing
            prio_level = 1
            if priority == "Urgent": prio_level = 4
            elif priority == "High": prio_level = 3
            elif priority == "Medium": prio_level = 2
            
            self.add_to_queue(ticket.id, priority_level=prio_level, _session=session)
            
            session.commit()
            return ticket.id
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating ticket: {e}")
            return None
        finally:
            self.Session.remove()

    def add_to_queue(self, ticket_id: int, priority_level: int = 1, _session=None):
        """Internal helper to add ticket to queue.
        When called from create_ticket, pass _session to reuse the parent session."""
        own_session = _session is None
        session = _session or self.get_session()
        try:
            existing = session.query(TicketQueue).filter_by(ticket_id=ticket_id).first()
            if not existing:
                q_item = TicketQueue(ticket_id=ticket_id, priority_level=priority_level)
                session.add(q_item)
                if own_session:
                    session.commit()
        except Exception as e:
            if own_session:
                session.rollback()
            logger.error(f"Error adding to queue: {e}")
        finally:
            if own_session:
                self.Session.remove()

    def get_ticket_metrics(self):
        session = self.get_session()
        try:
            # Single query with conditional aggregation instead of 5 separate queries
            now = datetime.now(timezone.utc)
            row = session.query(
                func.count(Ticket.id).label('total'),
                func.sum(case((Ticket.status == 'open', 1), else_=0)).label('open_count'),
                func.sum(case((Ticket.status == 'resolved', 1), else_=0)).label('resolved'),
                func.sum(case(
                    (Ticket.status != 'resolved', case((Ticket.due_at < now, 1), else_=0)),
                    else_=0
                )).label('overdue'),
            ).first()
            csat_avg = session.query(func.avg(CSATSurvey.rating)).scalar() or 0
            return {
                "total": row.total or 0, "open": int(row.open_count or 0),
                "resolved": int(row.resolved or 0), "overdue": int(row.overdue or 0),
                "csat_avg": round(float(csat_avg), 1)
            }
        finally:
            self.Session.remove()

    def get_ticket_counts(self):
        session = self.get_session()
        try:
            # Single query with conditional aggregation instead of 3 separate queries
            row = session.query(
                func.count(Ticket.id).label('total'),
                func.sum(case((Ticket.assigned_to == None, 1), else_=0)).label('unassigned'),
                func.sum(case((Ticket.assigned_to != None, 1), else_=0)).label('assigned'),
            ).filter(Ticket.status.in_(['open', 'pending'])).first()
            return {
                "all": row.total or 0,
                "unassigned": int(row.unassigned or 0),
                "assigned": int(row.assigned or 0),
                "no_reply": 0
            }
        finally:
            self.Session.remove()

    def get_all_tickets(self, filter_type: str = 'all'):
        session = self.get_session()
        try:
            query = session.query(Ticket, User.name, User.company, ChatSession.id.label("session_id")) \
                .join(User, Ticket.user_id == User.identifier) \
                .outerjoin(ChatSession, (Ticket.id == ChatSession.ticket_id) & (ChatSession.ended_at == None))
            
            if filter_type == 'all':
                query = query.filter(Ticket.status.in_(['open', 'pending']))
            elif filter_type == 'unassigned':
                query = query.filter(Ticket.status.in_(['open', 'pending']), Ticket.assigned_to == None)
            elif filter_type == 'assigned':
                query = query.filter(Ticket.status.in_(['open', 'pending']), Ticket.assigned_to != None)
            elif filter_type == 'resolved':
                query = query.filter(Ticket.status == 'resolved')
            elif filter_type == 'closed':
                query = query.filter(Ticket.status == 'closed')
            elif filter_type == 'pending_investigator':
                query = query.filter(Ticket.status == 'pending_investigator')
            elif filter_type == 'pending_programmer':
                query = query.filter(Ticket.status == 'pending_programmer')

            results = query.order_by(desc(Ticket.created_at)).all()
            tickets = []
            for t, uname, ucomp, sid in results:
                d = {
                    "id": t.id,
                    "user_id": t.user_id,
                    "summary": t.summary,
                    "full_history": t.full_history,
                    "status": t.status,
                    "priority": t.priority,
                    "assigned_to": t.assigned_to,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "name": uname,
                    "company": ucomp,
                    "session_id": sid
                }
                tickets.append(d)
            return tickets
        finally:
            self.Session.remove()

    def update_ticket_status(self, ticket_id: int, status: str):
        session = self.get_session()
        try:
            ticket = session.get(Ticket, ticket_id)
            if ticket:
                ticket.status = status
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating ticket status: {e}")
        finally:
            self.Session.remove()

    def get_tickets_by_user(self, user_id: str, limit: int = 20):
        """Get all tickets for a specific customer, newest first."""
        session = self.get_session()
        try:
            tickets = session.query(Ticket).filter_by(user_id=user_id) \
                .order_by(desc(Ticket.created_at)).limit(limit).all()
            return [{
                "id": t.id,
                "summary": t.summary,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "assigned_to": t.assigned_to
            } for t in tickets]
        finally:
            self.Session.remove()

    def get_customer_context(self, user_id: str) -> dict:
        """Get full customer context for agent panel: profile + ticket history + stats."""
        session = self.get_session()
        try:
            user = session.get(User, user_id)
            if not user:
                return {"found": False}

            tickets = session.query(Ticket).filter_by(user_id=user_id) \
                .order_by(desc(Ticket.created_at)).all()

            total_tickets = len(tickets)
            open_tickets = sum(1 for t in tickets if t.status in ('open', 'pending'))
            resolved_tickets = sum(1 for t in tickets if t.status == 'resolved')

            # Recent tickets (last 5)
            recent = [{
                "id": t.id,
                "summary": t.summary,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None
            } for t in tickets[:5]]

            # Recurring categories
            categories = {}
            for t in tickets:
                cat = t.category or "Support"
                categories[cat] = categories.get(cat, 0) + 1
            top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]

            # Message count
            msg_count = session.query(func.count(Message.id)).filter_by(user_id=user_id).scalar() or 0

            return {
                "found": True,
                "profile": {
                    "name": user.name,
                    "company": user.company,
                    "outlet": user.outlet_pos,
                    "position": user.position,
                    "member_since": user.created_at.isoformat() if user.created_at else None
                },
                "stats": {
                    "total_tickets": total_tickets,
                    "open_tickets": open_tickets,
                    "resolved_tickets": resolved_tickets,
                    "total_messages": msg_count
                },
                "recent_tickets": recent,
                "top_categories": [{"category": c, "count": n} for c, n in top_categories],
                "is_recurring_customer": total_tickets > 1
            }
        except Exception as e:
            logger.error(f"Error getting customer context: {e}")
            return {"found": False, "error": str(e)}
        finally:
            self.Session.remove()

    def update_ticket_sla(self, ticket_id: int, priority: str, due_at: datetime = None):
        session = self.get_session()
        try:
            ticket = session.get(Ticket, ticket_id)
            if ticket:
                ticket.priority = priority
                if due_at: ticket.due_at = due_at
                session.commit()
        except Exception as e:
            session.rollback()
        finally:
            self.Session.remove()

    # ============ Users ============
    def get_user(self, identifier: str):
        session = self.get_session()
        try:
            u = session.get(User, identifier)
            return { 
                "identifier": u.identifier,
                "account_id": u.account_id,
                "name": u.name, 
                "email": u.email,
                "mobile": u.mobile,
                "company": u.company, 
                "position": u.position,
                "outlet_pos": u.outlet_pos,
                "outlet_address": u.outlet_address,
                "category": u.category,
                "language": u.language,
                "state": u.state 
            } if u else None
        finally:
            self.Session.remove()

    def get_all_users(self, page: int = 1, per_page: int = 50):
        session = self.get_session()
        try:
            users = (
                session.query(User)
                .order_by(User.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            return [ { 
                "identifier": u.identifier,
                "account_id": u.identifier,
                "name": u.name, 
                "email": u.email,
                "mobile": u.mobile or '',
                "company": u.company,
                "position": u.position,
                "outlet_pos": u.outlet_pos,
                "outlet_address": u.outlet_address,
                "category": u.category
            } for u in users ]
        finally:
            self.Session.remove()

    # ============ System Settings ============
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        from app.models.models import SystemSetting
        session = self.get_session()
        try:
            s = session.query(SystemSetting).filter_by(key=key).first()
            return s.value if s else default
        finally:
            self.Session.remove()

    def set_setting(self, key: str, value: str):
        from app.models.models import SystemSetting
        session = self.get_session()
        try:
            s = session.query(SystemSetting).filter_by(key=key).first()
            if s:
                s.value = value
            else:
                session.add(SystemSetting(key=key, value=value))
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting {key}: {e}")
        finally:
            self.Session.remove()

    def get_all_settings(self) -> dict:
        from app.models.models import SystemSetting
        session = self.get_session()
        try:
            rows = session.query(SystemSetting).all()
            return {r.key: r.value for r in rows}
        finally:
            self.Session.remove()

    def _get_next_account_id(self, session):
        """Generate next EWS account ID (EWS1, EWS2, ...) by finding the current max."""
        from sqlalchemy import func as sa_func
        import re
        # Get all existing account_ids that match EWS pattern
        existing = session.query(User.account_id).filter(
            User.account_id.isnot(None),
            User.account_id.like('EWS%')
        ).all()
        max_num = 0
        for (aid,) in existing:
            m = re.match(r'^EWS(\d+)$', aid)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
        return f"EWS{max_num + 1}"

    def create_or_update_user(self, identifier: str, name: str = None, company: str = None, position: str = None, outlet_pos: str = None, state: str = 'idle', email: str = None, mobile: str = None, outlet_address: str = None, category: str = None, language: str = None):
        import re
        from sqlalchemy.exc import IntegrityError
        # Auto-fill mobile from identifier if it looks like a phone number
        if not mobile and identifier and re.match(r'^\+?\d{8,15}$', identifier.replace(' ','')):
            mobile = identifier
            
        max_retries = 3
        for attempt in range(max_retries):
            session = self.get_session()
            try:
                user = session.get(User, identifier)
                if user:
                    if name: user.name = name
                    if company: user.company = company
                    if position: user.position = position
                    if outlet_pos: user.outlet_pos = outlet_pos
                    if email: user.email = email
                    if mobile: user.mobile = mobile
                    if outlet_address: user.outlet_address = outlet_address
                    if category: user.category = category
                    if language: user.language = language
                    user.state = state
                    # Auto-assign account_id if missing
                    if not user.account_id:
                        user.account_id = self._get_next_account_id(session)
                    # Auto-fill mobile from identifier if still empty
                    if not user.mobile and re.match(r'^\+?\d{8,15}$', identifier.replace(' ','')):
                        user.mobile = identifier
                else:
                    account_id = self._get_next_account_id(session)
                    user = User(identifier=identifier, account_id=account_id, name=name, company=company, position=position, outlet_pos=outlet_pos, state=state, email=email, mobile=mobile, outlet_address=outlet_address, category=category, language=language)
                    session.add(user)
                    
                session.commit()
                break  # Success
            except IntegrityError as e:
                session.rollback()
                if attempt == max_retries - 1:
                    logger.error(f"Race condition saving user {identifier} after {max_retries} retries: {e}")
                else:
                    logger.warning(f"Race condition saving user {identifier}, retrying ({attempt + 1}/{max_retries})...")
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving user {identifier}: {e}")
                break
            finally:
                self.Session.remove()

    # ============ Agents ============
    def create_or_get_agent(self, user_id: str, name: str = None, email: str = None, department: str = "Support", skills: str = "[]", google_id: str = None):
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(user_id=user_id).first()
            if not agent:
                agent = Agent(user_id=user_id, name=name or user_id, email=email, department=department, google_id=google_id)
                session.add(agent)
                session.commit()
                session.refresh(agent)
            return { 
                "user_id": agent.user_id, 
                "name": agent.name, 
                "email": agent.email, 
                "department": agent.department,
                "role": getattr(agent, "role", "agent"),
                "google_id": agent.google_id if hasattr(agent, "google_id") else None
            }
        except Exception as e:
            session.rollback()
            return None
        finally:
            self.Session.remove()

    def get_agent(self, user_id: str):
        session = self.get_session()
        try:
            a = session.query(Agent).filter_by(user_id=user_id).first()
            if not a: return None
            p = session.query(AgentPresence).filter_by(agent_id=user_id).first()
            
            roles = [r.name for r in a.roles]
            permissions = self.get_agent_effective_permissions(user_id)
            legacy_role = "admin" if ("System Admin" in roles or "Admin" in roles) else "agent"

            return { 
                "user_id": a.user_id, "name": a.name, "email": a.email, 
                "department": a.department, "hashed_password": a.hashed_password,
                "active_chat_count": p.active_chat_count if p else 0,
                "roles": roles, "role": legacy_role, "permissions": permissions
            }
        finally:
            self.Session.remove()

    def get_agent_by_email(self, email: str):
        session = self.get_session()
        try:
            a = session.query(Agent).filter_by(email=email).first()
            if not a: return None
            roles = [r.name for r in a.roles]
            legacy_role = "admin" if ("System Admin" in roles or "Admin" in roles) else "agent"
            return { "user_id": a.user_id, "email": a.email, "hashed_password": a.hashed_password, "role": legacy_role }
        finally:
            self.Session.remove()

    def get_all_agents(self):
        session = self.get_session()
        try:
            # Single query with LEFT JOIN instead of N+1 (one presence query per agent)
            agents = session.query(Agent, AgentPresence) \
                .outerjoin(AgentPresence, Agent.user_id == AgentPresence.agent_id) \
                .options(joinedload(Agent.roles)).all()
            result = []
            for a, p in agents:
                result.append({
                    "user_id": a.user_id, "name": a.name, "email": a.email,
                    "department": a.department,
                    "active_chat_count": p.active_chat_count if p else 0,
                    "roles": [r.name for r in a.roles]
                })
            return result
        finally:
            self.Session.remove()

    def update_agent_auth(self, user_id: str, hashed_password: str = None, google_id: str = None):
        session = self.get_session()
        try:
            a = session.query(Agent).filter_by(user_id=user_id).first()
            if a:
                if hashed_password:
                    a.hashed_password = hashed_password
                if google_id and hasattr(a, 'google_id'):
                    a.google_id = google_id
                session.commit()
        finally:
            self.Session.remove()

    def update_agent_department(self, user_id: str, department: str):
        session = self.get_session()
        try:
            a = session.query(Agent).filter_by(user_id=user_id).first()
            if a:
                a.department = department
                session.commit()
        finally:
            self.Session.remove()

    def update_agent_presence(self, agent_id: str, status: str, active_chat_count: int = None):
        session = self.get_session()
        try:
            p = session.query(AgentPresence).filter_by(agent_id=agent_id).first()
            if p:
                p.status = status
                if active_chat_count is not None: p.active_chat_count = active_chat_count
            else:
                p = AgentPresence(agent_id=agent_id, status=status, active_chat_count=active_chat_count or 0)
                session.add(p)
            session.commit()
        finally:
            self.Session.remove()

    def get_available_agents(self):
        session = self.get_session()
        try:
            agents = session.query(Agent).join(AgentPresence, Agent.user_id == AgentPresence.agent_id).filter(
                AgentPresence.status == 'available'
            ).all()
            return [ { "user_id": a.user_id, "name": a.name } for a in agents ]
        finally:
            self.Session.remove()

    # ============ Chat Sessions ============
    def create_chat_session(self, ticket_id: int, agent_id: str, customer_id: str):
        session = self.get_session()
        try:
            s = ChatSession(ticket_id=ticket_id, agent_id=agent_id, customer_id=customer_id)
            session.add(s)
            if ticket_id:
                t = session.get(Ticket, ticket_id)
                if t: t.assigned_to = agent_id
            session.commit()
            return s.id
        except Exception as e:
            session.rollback()
            return None
        finally:
            self.Session.remove()

    def get_chat_session(self, session_id: int):
        session = self.get_session()
        try:
            s = session.get(ChatSession, session_id)
            return { "id": s.id, "ticket_id": s.ticket_id, "agent_id": s.agent_id, "customer_id": s.customer_id } if s else None
        finally:
            self.Session.remove()

    def close_chat_session(self, session_id: int):
        session = self.get_session()
        try:
            s = session.get(ChatSession, session_id)
            if s:
                s.ended_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            self.Session.remove()

    def save_chat_message(self, session_id: int, sender_id: str, sender_type: str, content: str, attachment_url: str = None):
        session = self.get_session()
        try:
            m = ChatMessage(session_id=session_id, sender_id=sender_id, sender_type=sender_type, content=content, attachment_url=attachment_url)
            session.add(m)
            session.commit()
            return m.id
        finally:
            self.Session.remove()

    def get_chat_history(self, session_id: int, limit: int = 50):
        session = self.get_session()
        try:
            msgs = session.query(ChatMessage).filter_by(session_id=session_id).order_by(desc(ChatMessage.sent_at)).limit(limit).all()
            return [ { "sender_type": m.sender_type, "content": m.content, "sent_at": m.sent_at } for m in reversed(msgs) ]
        finally:
            self.Session.remove()

    # ============ Macros & Others ============
    def create_macro(self, name: str, content: str, category: str = 'General'):
        session = self.get_session()
        try:
            m = session.query(Macro).filter_by(name=name).first()
            if m:
                m.content = content
                m.category = category
            else:
                m = Macro(name=name, content=content, category=category)
                session.add(m)
            session.commit()
        finally:
            self.Session.remove()

    def get_macros(self):
        session = self.get_session()
        try:
            macros = session.query(Macro).order_by(Macro.category).all()
            return [ { "id": m.id, "name": m.name, "content": m.content, "category": m.category } for m in macros ]
        finally:
            self.Session.remove()

    def delete_macro(self, macro_id: int):
        session = self.get_session()
        try:
            session.query(Macro).filter_by(id=macro_id).delete()
            session.commit()
        finally:
            self.Session.remove()

    def submit_csat(self, ticket_id: int, rating: int, feedback: str = None):
        session = self.get_session()
        try:
            c = CSATSurvey(ticket_id=ticket_id, rating=rating, feedback=feedback)
            session.add(c)
            session.commit()
        except:
            session.rollback()
        finally:
            self.Session.remove()

    def create_sla_rule(self, name: str, priority: str, first_response: int, resolution: int):
        session = self.get_session()
        try:
            r = session.query(SLARule).filter_by(priority=priority).first()
            if r:
                r.name = name
                r.first_response_minutes = first_response
                r.resolution_minutes = resolution
            else:
                r = SLARule(name=name, priority=priority, first_response_minutes=first_response, resolution_minutes=resolution)
                session.add(r)
            session.commit()
        finally:
            self.Session.remove()

    def get_recent_summaries(self, limit: int = 50):
        session = self.get_session()
        try:
            items = session.query(Ticket).order_by(desc(Ticket.created_at)).limit(limit).all()
            return [ t.summary for t in items ]
        finally:
            self.Session.remove()

    def get_queue(self):
        session = self.get_session()
        try:
            q = session.query(TicketQueue, Ticket.summary, Ticket.priority) \
                .join(Ticket, TicketQueue.ticket_id == Ticket.id) \
                .filter(TicketQueue.assigned_at == None) \
                .order_by(desc(TicketQueue.priority_level), TicketQueue.queued_at).all()
            return [ { "ticket_id": item[0].ticket_id, "summary": item[1], "priority": item[2], "queued_at": item[0].queued_at } for item in q ]
        finally:
            self.Session.remove()

    def log_action(self, agent_id: str, action: str, target_type: str, target_id: str, details: str = None):
        session = self.get_session()
        try:
            log = AuditLog(agent_id=agent_id, action=action, target_type=target_type, target_id=str(target_id), details=details)
            session.add(log)
            session.commit()
        finally:
            self.Session.remove()

    def get_audit_logs(self, page: int = 1, per_page: int = 50):
        session = self.get_session()
        try:
            logs = session.query(AuditLog, Agent.name) \
                .outerjoin(Agent, AuditLog.agent_id == Agent.user_id) \
                .order_by(AuditLog.timestamp.desc()) \
                .offset((page - 1) * per_page) \
                .limit(per_page) \
                .all()
            return [ { "timestamp": l[0].timestamp, "agent_name": l[1] or "System", "action": l[0].action, "target_type": l[0].target_type, "target_id": l[0].target_id } for l in logs ]
        finally:
            self.Session.remove()

    # ============ New Auth Methods (Google & Magic Link) ============
    def get_agent_by_google_id(self, google_id: str):
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(google_id=google_id).first()
            if not agent: return None
            return {
                "user_id": agent.user_id,
                "name": agent.name,
                "email": agent.email,
                "role": agent.roles[0].name if agent.roles else "agent",
                "google_id": agent.google_id
            }
        finally:
            self.Session.remove()

    def link_google_account(self, username: str, google_id: str):
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(user_id=username).first()
            if agent:
                agent.google_id = google_id
                session.commit()
                return True
            return False
        finally:
            self.Session.remove()

    def create_magic_link(self, email: str, token_hash: str, expires_at: datetime):
        """Create a magic link for email-based authentication"""
        session = self.get_session()
        try:
            # Get or create agent by email
            agent = session.query(Agent).filter_by(email=email).first()
            if not agent:
                # Create temporary agent for new email
                import uuid
                agent = Agent(
                    user_id=f"ml_{uuid.uuid4().hex[:16]}",
                    name=email.split("@")[0],
                    email=email,
                    department="Support"
                )
                session.add(agent)
                session.flush()  # Get the agent ID before creating link
            
            link = AuthMagicLink(user_id=agent.user_id, token_hash=token_hash, expires_at=expires_at)
            session.add(link)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            self.Session.remove()

    def get_magic_link(self, email: str, token_hash: str):
        """Get magic link by email and token hash"""
        session = self.get_session()
        try:
            # Find agent by email first
            agent = session.query(Agent).filter_by(email=email).first()
            if not agent:
                return None
            
            link = session.query(AuthMagicLink).filter_by(
                user_id=agent.user_id, 
                token_hash=token_hash
            ).first()
            
            if not link:
                return None
            
            return {
                "id": link.id,
                "user_id": link.user_id,
                "expires_at": link.expires_at
            }
        finally:
            self.Session.remove()

    def revoke_magic_link(self, email: str, token_hash: str):
        """Revoke/delete a magic link"""
        session = self.get_session()
        try:
            agent = session.query(Agent).filter_by(email=email).first()
            if agent:
                session.query(AuthMagicLink).filter_by(
                    user_id=agent.user_id,
                    token_hash=token_hash
                ).delete()
                session.commit()
        finally:
            self.Session.remove()

    def delete_magic_link(self, link_id: int):
        session = self.get_session()
        try:
            session.query(AuthMagicLink).filter_by(id=link_id).delete()
            session.commit()
        finally:
            self.Session.remove()

    # ============ WhatsApp Messages ============

    def save_whatsapp_message(self, phone_number: str, direction: str, content: str,
                              message_type: str = "text", external_message_id: str = None,
                              ticket_id: int = None, status: str = None):
        """Save a WhatsApp message (inbound or outbound) to the database."""
        session = self.get_session()
        try:
            msg = WhatsAppMessage(
                external_message_id=external_message_id,
                phone_number=phone_number,
                direction=direction,
                content=content,
                message_type=message_type,
                status=status or ('received' if direction == 'inbound' else 'sent'),
                ticket_id=ticket_id
            )
            session.add(msg)
            session.commit()
            return msg.id
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving WhatsApp message: {e}")
            return None
        finally:
            self.Session.remove()

    def get_whatsapp_conversations(self, search: str = None, page: int = 1, per_page: int = 50):
        """Get WhatsApp conversations grouped by phone number."""
        session = self.get_session()
        try:
            from sqlalchemy import func as sqla_func, case
            # Subquery: latest message per phone number
            subq = session.query(
                WhatsAppMessage.phone_number,
                sqla_func.count(WhatsAppMessage.id).label('message_count'),
                sqla_func.max(WhatsAppMessage.created_at).label('last_message_at'),
                sqla_func.sum(case((WhatsAppMessage.direction == 'inbound', 1), else_=0)).label('inbound_count'),
                sqla_func.sum(case((WhatsAppMessage.direction == 'outbound', 1), else_=0)).label('outbound_count'),
            ).group_by(WhatsAppMessage.phone_number)

            if search:
                escaped_search = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                subq = subq.filter(WhatsAppMessage.phone_number.ilike(f'%{escaped_search}%', escape='\\'))

            total = subq.count()
            conversations = subq.order_by(desc(sqla_func.max(WhatsAppMessage.created_at))).offset((page - 1) * per_page).limit(per_page).all()

            # Get the last message content for each conversation
            result = []
            for conv in conversations:
                last_msg = session.query(WhatsAppMessage).filter_by(
                    phone_number=conv.phone_number
                ).order_by(desc(WhatsAppMessage.created_at)).first()

                # Try to get customer name from Users table
                user = session.query(User).filter_by(identifier=conv.phone_number).first()
                customer_name = user.name if user and user.name else None

                result.append({
                    'phone_number': conv.phone_number,
                    'customer_name': customer_name,
                    'message_count': conv.message_count,
                    'inbound_count': conv.inbound_count,
                    'outbound_count': conv.outbound_count,
                    'last_message_at': str(conv.last_message_at) if conv.last_message_at else None,
                    'last_message': last_msg.content[:100] if last_msg else '',
                    'last_direction': last_msg.direction if last_msg else ''
                })

            return {'conversations': result, 'total': total, 'page': page, 'per_page': per_page}
        finally:
            self.Session.remove()

    def get_whatsapp_messages(self, phone_number: str, page: int = 1, per_page: int = 100):
        """Get all messages for a specific phone number (conversation thread)."""
        session = self.get_session()
        try:
            query = session.query(WhatsAppMessage).filter_by(phone_number=phone_number)
            total = query.count()
            messages = query.order_by(WhatsAppMessage.created_at.asc()).offset((page - 1) * per_page).limit(per_page).all()
            return {
                'phone_number': phone_number,
                'total': total,
                'messages': [{
                    'id': m.id,
                    'external_message_id': m.external_message_id,
                    'direction': m.direction,
                    'content': m.content,
                    'message_type': m.message_type,
                    'status': m.status,
                    'ticket_id': m.ticket_id,
                    'created_at': str(m.created_at) if m.created_at else None
                } for m in messages]
            }
        finally:
            self.Session.remove()

    def get_whatsapp_stats(self):
        """Get WhatsApp messaging statistics."""
        session = self.get_session()
        try:
            from sqlalchemy import func as sqla_func
            # Single query instead of 4 separate queries
            row = session.query(
                sqla_func.count(WhatsAppMessage.id).label('total'),
                sqla_func.sum(case((WhatsAppMessage.direction == 'inbound', 1), else_=0)).label('inbound'),
                sqla_func.sum(case((WhatsAppMessage.direction == 'outbound', 1), else_=0)).label('outbound'),
                sqla_func.count(sqla_func.distinct(WhatsAppMessage.phone_number)).label('contacts')
            ).first()
            return {
                'total_messages': row.total or 0,
                'total_inbound': int(row.inbound or 0),
                'total_outbound': int(row.outbound or 0),
                'unique_contacts': row.contacts or 0
            }
        finally:
            self.Session.remove()

    def link_whatsapp_messages_to_ticket(self, phone_number: str, ticket_id: int):
        """Link all WhatsApp messages from a phone number to a ticket."""
        session = self.get_session()
        try:
            session.query(WhatsAppMessage).filter(
                WhatsAppMessage.phone_number == phone_number,
                WhatsAppMessage.ticket_id.is_(None)
            ).update({"ticket_id": ticket_id}, synchronize_session=False)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error linking WhatsApp messages to ticket: {e}")
        finally:
            self.Session.remove()

    def execute_safe_query(self, table_name: str, filters: dict = None, limit: int = 10):
        """
        Executes a safe, read-only query on whitelisted tables for AI Tools.
        Args:
            table_name: Table name (tickets, users, etc)
            filters: Dictionary of equality filters {column: value}
            limit: Max rows to return
        """
        session = self.get_session()
        try:
            # Whitelist allowed tables to prevent arbitrary access
            allowed_tables = {
                "tickets": Ticket,
                "users": User,
                "messages": Message,
                "audit_logs": AuditLog,
                "whatsapp_messages": WhatsAppMessage,
                "outlets": Outlet,
                "pos_devices": POSDevice,
                "pos_transactions": POSTransaction,
                "vouchers": Voucher,
                "memberships": Membership,
                "inventory_items": InventoryItem
            }
            
            if table_name not in allowed_tables:
                raise ValueError(f"Table '{table_name}' is not accessible via AI tools.")
            
            model = allowed_tables[table_name]
            query = session.query(model)
            
            if filters:
                for col, val in filters.items():
                    if hasattr(model, col):
                        query = query.filter(getattr(model, col) == val)
            
            results = query.limit(limit).all()
            
            # Serialize results
            serialized = []
            for r in results:
                # Convert model to dict, handling datetime
                row_dict = {}
                for col in r.__table__.columns:
                    val = getattr(r, col.name)
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    row_dict[col.name] = val
                serialized.append(row_dict)
                
            return serialized
        finally:
            self.Session.remove()

try:
    db_manager = DatabaseManager()
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to initialize DatabaseManager: {e}. App will start but DB features will be unavailable.")
    db_manager = None
