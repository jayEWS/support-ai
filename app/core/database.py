from sqlalchemy import create_engine, func, or_, desc, literal_column
from sqlalchemy.orm import sessionmaker, scoped_session
from app.models.models import Base, User, Message, Ticket, Agent, ChatSession, ChatMessage, AgentPresence, SLARule, TicketQueue, Macro, CSATSurvey, KnowledgeMetadata, AuditLog, Role, Permission, AuthMFAChallenge, AuthRefreshToken, AuthMagicLink, FreshdeskContact, FreshdeskTicket, WhatsAppMessage
from app.core.config import settings
from app.core.logging import logger
import json
from datetime import datetime, timezone
from typing import List, Optional

class DatabaseManager:
    def __init__(self):
        # SQL Server Engine
        # pool_pre_ping disabled at startup to avoid blocking when DB is unreachable
        # The app will still boot and retry connections on each request
        self.engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=False,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10}  # 10s timeout instead of default 2 min
        )
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self._init_db()

    def _init_db(self):
        """Create all tables in SQL Server if they don't exist."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("SQL Server database tables verified/created.")
        except Exception as e:
            logger.error(f"Error initializing SQL Server: {e}")

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
            c = session.query(AuthMFAChallenge).get(challenge_id)
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
            c = session.query(AuthMFAChallenge).get(challenge_id)
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

    def get_unified_history(self, user_id: str, ticket_id: Optional[int] = None):
        """Merges messages from both bot portal and live chat for a full view."""
        session = self.get_session()
        try:
            # 1. Fetch portal messages
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
            
            self.add_to_queue(ticket.id, priority_level=prio_level)
            
            session.commit()
            return ticket.id
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating ticket: {e}")
            return None
        finally:
            self.Session.remove()

    def add_to_queue(self, ticket_id: int, priority_level: int = 1):
        """Internal helper to add ticket to queue."""
        session = self.get_session()
        try:
            existing = session.query(TicketQueue).filter_by(ticket_id=ticket_id).first()
            if not existing:
                q_item = TicketQueue(ticket_id=ticket_id, priority_level=priority_level)
                session.add(q_item)
                session.commit()
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
        finally:
            # We don't remove session here if called from create_ticket which has its own finally
            pass

    def get_ticket_metrics(self):
        session = self.get_session()
        try:
            total = session.query(Ticket).count()
            open_count = session.query(Ticket).filter_by(status='open').count()
            resolved = session.query(Ticket).filter_by(status='resolved').count()
            overdue = session.query(Ticket).filter(Ticket.status != 'resolved', Ticket.due_at < datetime.now(timezone.utc)).count()
            csat_avg = session.query(func.avg(CSATSurvey.rating)).scalar() or 0
            return {
                "total": total, "open": open_count, "resolved": resolved,
                "overdue": overdue, "csat_avg": round(float(csat_avg), 1)
            }
        finally:
            self.Session.remove()

    def get_ticket_counts(self):
        session = self.get_session()
        try:
            all_active = session.query(Ticket).filter(Ticket.status.in_(['open', 'pending'])).count()
            unassigned = session.query(Ticket).filter(Ticket.status.in_(['open', 'pending']), Ticket.assigned_to == None).count()
            assigned = session.query(Ticket).filter(Ticket.status.in_(['open', 'pending']), Ticket.assigned_to != None).count()
            
            # Simple simulation for no_reply for now
            return { "all": all_active, "unassigned": unassigned, "assigned": assigned, "no_reply": 0 }
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
                    "asana_task_id": t.asana_task_id,
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
            ticket = session.query(Ticket).get(ticket_id)
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
            user = session.query(User).get(user_id)
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

            # Check for linked Freshdesk history
            freshdesk_data = None
            try:
                fd_contact = session.query(FreshdeskContact).filter_by(internal_user_id=user_id).first()
                if fd_contact:
                    fd_tickets = session.query(FreshdeskTicket).filter_by(
                        contact_id=fd_contact.freshdesk_id
                    ).order_by(desc(FreshdeskTicket.created_time)).limit(5).all()
                    freshdesk_data = {
                        "contact_name": fd_contact.full_name,
                        "company": fd_contact.company_name,
                        "total_historical_tickets": fd_contact.total_tickets or 0,
                        "recent_historical": [{
                            "ticket_id": ft.ticket_id,
                            "subject": ft.subject,
                            "type": ft.ticket_type,
                            "status": ft.status,
                            "created": str(ft.created_time) if ft.created_time else None
                        } for ft in fd_tickets]
                    }
            except Exception:
                pass

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
                "is_recurring_customer": total_tickets > 1,
                "freshdesk_history": freshdesk_data
            }
        except Exception as e:
            logger.error(f"Error getting customer context: {e}")
            return {"found": False, "error": str(e)}
        finally:
            self.Session.remove()

    def update_ticket_sla(self, ticket_id: int, priority: str, due_at: datetime = None):
        session = self.get_session()
        try:
            ticket = session.query(Ticket).get(ticket_id)
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
            u = session.query(User).get(identifier)
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

    def get_all_users(self):
        session = self.get_session()
        try:
            users = session.query(User).all()
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
        # Auto-fill mobile from identifier if it looks like a phone number
        if not mobile and identifier and re.match(r'^\+?\d{8,15}$', identifier.replace(' ','')):
            mobile = identifier
        session = self.get_session()
        try:
            user = session.query(User).get(identifier)
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
        except Exception as e:
            session.rollback()
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
            agents = session.query(Agent).all()
            result = []
            for a in agents:
                p = session.query(AgentPresence).filter_by(agent_id=a.user_id).first()
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
                t = session.query(Ticket).get(ticket_id)
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
            s = session.query(ChatSession).get(session_id)
            return { "id": s.id, "ticket_id": s.ticket_id, "agent_id": s.agent_id, "customer_id": s.customer_id } if s else None
        finally:
            self.Session.remove()

    def close_chat_session(self, session_id: int):
        session = self.get_session()
        try:
            s = session.query(ChatSession).get(session_id)
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

    def update_ticket_asana_id(self, ticket_id: int, asana_task_id: str):
        session = self.get_session()
        try:
            ticket = session.query(Ticket).get(ticket_id)
            if ticket:
                ticket.asana_task_id = asana_task_id
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating Asana ID: {e}")
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

    def get_audit_logs(self, limit: int = 50):
        session = self.get_session()
        try:
            logs = session.query(AuditLog, Agent.name) \
                .outerjoin(Agent, AuditLog.agent_id == Agent.user_id) \
                .order_by(desc(AuditLog.timestamp)).limit(limit).all()
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

    # ============ Freshdesk Historical Data ============

    def upsert_freshdesk_contact(self, data: dict):
        """Insert or update a Freshdesk contact."""
        session = self.get_session()
        try:
            contact = session.query(FreshdeskContact).filter_by(
                freshdesk_id=data.get("freshdesk_id")
            ).first()
            if contact:
                for k, v in data.items():
                    if k != "freshdesk_id" and v is not None:
                        setattr(contact, k, v)
            else:
                contact = FreshdeskContact(**data)
                session.add(contact)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting freshdesk contact: {e}")
            return False
        finally:
            self.Session.remove()

    def upsert_freshdesk_ticket(self, data: dict):
        """Insert or update a Freshdesk ticket."""
        session = self.get_session()
        try:
            ticket = session.query(FreshdeskTicket).filter_by(
                ticket_id=data.get("ticket_id")
            ).first()
            if ticket:
                for k, v in data.items():
                    if k != "ticket_id" and v is not None:
                        setattr(ticket, k, v)
            else:
                ticket = FreshdeskTicket(**data)
                session.add(ticket)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting freshdesk ticket: {e}")
            return False
        finally:
            self.Session.remove()

    def bulk_upsert_freshdesk_contacts(self, contacts: list):
        """Bulk upsert freshdesk contacts. Returns (inserted, updated, errors)."""
        session = self.get_session()
        inserted, updated, errors = 0, 0, 0
        try:
            for data in contacts:
                try:
                    existing = session.query(FreshdeskContact).filter_by(
                        freshdesk_id=data.get("freshdesk_id")
                    ).first()
                    if existing:
                        for k, v in data.items():
                            if k != "freshdesk_id" and v is not None:
                                setattr(existing, k, v)
                        updated += 1
                    else:
                        session.add(FreshdeskContact(**data))
                        inserted += 1
                except Exception as e:
                    logger.error(f"Error upserting contact {data.get('freshdesk_id')}: {e}")
                    errors += 1
            session.commit()
            return inserted, updated, errors
        except Exception as e:
            session.rollback()
            logger.error(f"Bulk contact upsert failed: {e}")
            return inserted, updated, errors + len(contacts)
        finally:
            self.Session.remove()

    def bulk_upsert_freshdesk_tickets(self, tickets: list):
        """Bulk upsert freshdesk tickets. Returns (inserted, updated, errors)."""
        session = self.get_session()
        inserted, updated, errors = 0, 0, 0
        try:
            for data in tickets:
                try:
                    existing = session.query(FreshdeskTicket).filter_by(
                        ticket_id=data.get("ticket_id")
                    ).first()
                    if existing:
                        for k, v in data.items():
                            if k != "ticket_id" and v is not None:
                                setattr(existing, k, v)
                        updated += 1
                    else:
                        session.add(FreshdeskTicket(**data))
                        inserted += 1
                except Exception as e:
                    logger.error(f"Error upserting ticket {data.get('ticket_id')}: {e}")
                    errors += 1
            session.commit()
            return inserted, updated, errors
        except Exception as e:
            session.rollback()
            logger.error(f"Bulk ticket upsert failed: {e}")
            return inserted, updated, errors + len(tickets)
        finally:
            self.Session.remove()

    def get_freshdesk_contacts(self, search: str = None, page: int = 1, per_page: int = 50):
        """Get freshdesk contacts with optional search and pagination."""
        session = self.get_session()
        try:
            q = session.query(FreshdeskContact)
            if search:
                search_term = f"%{search}%"
                q = q.filter(or_(
                    FreshdeskContact.full_name.ilike(search_term),
                    FreshdeskContact.email.ilike(search_term),
                    FreshdeskContact.company_name.ilike(search_term),
                    FreshdeskContact.freshdesk_id.ilike(search_term),
                    FreshdeskContact.mobile_phone.ilike(search_term)
                ))
            total = q.count()
            contacts = q.order_by(desc(FreshdeskContact.total_tickets)).offset((page-1)*per_page).limit(per_page).all()
            return {
                "contacts": [{
                    "id": c.id,
                    "freshdesk_id": c.freshdesk_id,
                    "full_name": c.full_name,
                    "email": c.email,
                    "work_phone": c.work_phone,
                    "mobile_phone": c.mobile_phone,
                    "company_name": c.company_name,
                    "industry": c.industry,
                    "total_tickets": c.total_tickets or 0,
                    "internal_user_id": c.internal_user_id,
                    "created_at": str(c.created_at) if c.created_at else None
                } for c in contacts],
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
        finally:
            self.Session.remove()

    def get_freshdesk_contact(self, freshdesk_id: str):
        """Get a single freshdesk contact by freshdesk_id."""
        session = self.get_session()
        try:
            c = session.query(FreshdeskContact).filter_by(freshdesk_id=freshdesk_id).first()
            if not c:
                return None
            return {
                "id": c.id,
                "freshdesk_id": c.freshdesk_id,
                "full_name": c.full_name,
                "email": c.email,
                "work_phone": c.work_phone,
                "mobile_phone": c.mobile_phone,
                "company_name": c.company_name,
                "industry": c.industry,
                "timezone": c.timezone,
                "language": c.language,
                "account_tier": c.account_tier,
                "health_score": c.health_score,
                "total_tickets": c.total_tickets or 0,
                "internal_user_id": c.internal_user_id,
                "created_at": str(c.created_at) if c.created_at else None
            }
        finally:
            self.Session.remove()

    def get_freshdesk_tickets(self, contact_id: str = None, search: str = None,
                              ticket_type: str = None, status: str = None,
                              page: int = 1, per_page: int = 50):
        """Get freshdesk tickets with filters and pagination."""
        session = self.get_session()
        try:
            q = session.query(FreshdeskTicket)
            if contact_id:
                q = q.filter(FreshdeskTicket.contact_id == contact_id)
            if ticket_type:
                q = q.filter(FreshdeskTicket.ticket_type == ticket_type)
            if status:
                q = q.filter(FreshdeskTicket.status == status)
            if search:
                search_term = f"%{search}%"
                q = q.filter(or_(
                    FreshdeskTicket.subject.ilike(search_term),
                    FreshdeskTicket.summary.ilike(search_term),
                    FreshdeskTicket.agent.ilike(search_term)
                ))
            total = q.count()
            tickets = q.order_by(desc(FreshdeskTicket.created_time)).offset((page-1)*per_page).limit(per_page).all()
            return {
                "tickets": [{
                    "id": t.id,
                    "ticket_id": t.ticket_id,
                    "subject": t.subject,
                    "status": t.status,
                    "priority": t.priority,
                    "ticket_type": t.ticket_type,
                    "agent": t.agent,
                    "contact_id": t.contact_id,
                    "created_time": str(t.created_time) if t.created_time else None,
                    "resolved_time": str(t.resolved_time) if t.resolved_time else None,
                    "closed_time": str(t.closed_time) if t.closed_time else None,
                    "resolution_status": t.resolution_status,
                    "summary": t.summary,
                    "tags": t.tags
                } for t in tickets],
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
        finally:
            self.Session.remove()

    def get_freshdesk_stats(self):
        """Get aggregated stats from Freshdesk historical data."""
        session = self.get_session()
        try:
            total_tickets = session.query(FreshdeskTicket).count()
            total_contacts = session.query(FreshdeskContact).count()
            # Ticket type distribution
            type_dist = session.query(
                FreshdeskTicket.ticket_type, func.count(FreshdeskTicket.id)
            ).group_by(FreshdeskTicket.ticket_type).order_by(
                desc(func.count(FreshdeskTicket.id))
            ).limit(10).all()
            # Status distribution
            status_dist = session.query(
                FreshdeskTicket.status, func.count(FreshdeskTicket.id)
            ).group_by(FreshdeskTicket.status).all()
            # Priority distribution
            priority_dist = session.query(
                FreshdeskTicket.priority, func.count(FreshdeskTicket.id)
            ).group_by(FreshdeskTicket.priority).all()
            # Top agents
            top_agents = session.query(
                FreshdeskTicket.agent, func.count(FreshdeskTicket.id)
            ).group_by(FreshdeskTicket.agent).order_by(
                desc(func.count(FreshdeskTicket.id))
            ).limit(10).all()
            # Top companies
            top_companies = session.query(
                FreshdeskContact.company_name, func.count(FreshdeskContact.id)
            ).filter(FreshdeskContact.company_name.isnot(None), FreshdeskContact.company_name != "").group_by(
                FreshdeskContact.company_name
            ).order_by(desc(func.count(FreshdeskContact.id))).limit(10).all()

            return {
                "total_tickets": total_tickets,
                "total_contacts": total_contacts,
                "ticket_types": [{"type": t[0] or "Unknown", "count": t[1]} for t in type_dist],
                "statuses": [{"status": s[0] or "Unknown", "count": s[1]} for s in status_dist],
                "priorities": [{"priority": p[0] or "Unknown", "count": p[1]} for p in priority_dist],
                "top_agents": [{"agent": a[0] or "Unassigned", "count": a[1]} for a in top_agents],
                "top_companies": [{"company": c[0], "count": c[1]} for c in top_companies]
            }
        finally:
            self.Session.remove()

    def link_freshdesk_contact_to_user(self, freshdesk_id: str, user_id: str):
        """Link a Freshdesk contact to an internal portal User."""
        session = self.get_session()
        try:
            contact = session.query(FreshdeskContact).filter_by(freshdesk_id=freshdesk_id).first()
            if not contact:
                return False
            contact.internal_user_id = user_id
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error linking freshdesk contact: {e}")
            return False
        finally:
            self.Session.remove()

    def get_freshdesk_history_for_user(self, user_id: str):
        """Get Freshdesk ticket history for a linked internal user."""
        session = self.get_session()
        try:
            # Find linked FreshdeskContact
            contact = session.query(FreshdeskContact).filter_by(internal_user_id=user_id).first()
            if not contact:
                return None
            # Get tickets
            tickets = session.query(FreshdeskTicket).filter_by(
                contact_id=contact.freshdesk_id
            ).order_by(desc(FreshdeskTicket.created_time)).limit(20).all()
            return {
                "contact": {
                    "freshdesk_id": contact.freshdesk_id,
                    "full_name": contact.full_name,
                    "company_name": contact.company_name,
                    "total_tickets": contact.total_tickets
                },
                "tickets": [{
                    "ticket_id": t.ticket_id,
                    "subject": t.subject,
                    "status": t.status,
                    "priority": t.priority,
                    "ticket_type": t.ticket_type,
                    "created_time": str(t.created_time) if t.created_time else None,
                    "resolved_time": str(t.resolved_time) if t.resolved_time else None
                } for t in tickets]
            }
        finally:
            self.Session.remove()

    # ============ WhatsApp Messages ============

    def save_whatsapp_message(self, phone_number: str, direction: str, content: str,
                              message_type: str = "text", bird_message_id: str = None,
                              ticket_id: int = None, status: str = None):
        """Save a WhatsApp message (inbound or outbound) to the database."""
        session = self.get_session()
        try:
            msg = WhatsAppMessage(
                bird_message_id=bird_message_id,
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
                subq = subq.filter(WhatsAppMessage.phone_number.ilike(f'%{search}%'))

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
                    'bird_message_id': m.bird_message_id,
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
            total_messages = session.query(sqla_func.count(WhatsAppMessage.id)).scalar() or 0
            total_inbound = session.query(sqla_func.count(WhatsAppMessage.id)).filter_by(direction='inbound').scalar() or 0
            total_outbound = session.query(sqla_func.count(WhatsAppMessage.id)).filter_by(direction='outbound').scalar() or 0
            unique_contacts = session.query(sqla_func.count(sqla_func.distinct(WhatsAppMessage.phone_number))).scalar() or 0
            return {
                'total_messages': total_messages,
                'total_inbound': total_inbound,
                'total_outbound': total_outbound,
                'unique_contacts': unique_contacts
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

try:
    db_manager = DatabaseManager()
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to initialize DatabaseManager: {e}. App will start but DB features will be unavailable.")
    db_manager = None
