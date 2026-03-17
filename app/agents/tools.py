"""
AI Support Engineer Agent — Tool Definitions
==============================================
LangChain-compatible tools that the AI agent can use for investigation.
Each tool is a callable that returns structured data for the agent's reasoning.

Tools:
    - database_query_tool    — Query DB tables (read-only)
    - log_search_tool        — Search recent health check and incident logs
    - integration_status_tool — Check status of external integrations
    - knowledge_base_search  — Search the RAG knowledge base
    - digital_twin_tool      — Get store digital twin state
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from app.core.logging import logger


async def database_query_tool(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Query database tables for diagnostic information (READ-ONLY).
    
    Allowed tables: pos_devices, pos_transactions, outlets, vouchers,
                    ops_health_checks, ops_incidents, ops_device_states

    Args:
        table: Table name to query
        filters: Optional column=value filters
        limit: Max rows to return (capped at 50)
    """
    from app.core.database import db_manager
    from sqlalchemy import inspect

    ALLOWED_TABLES = {
        "pos_devices", "pos_transactions", "outlets", "vouchers",
        "memberships", "inventory_items", "ops_health_checks",
        "ops_incidents", "ops_device_states", "ops_store_twins",
    }

    if table not in ALLOWED_TABLES:
        return {"error": f"Table '{table}' is not in the allowed list. Allowed: {sorted(ALLOWED_TABLES)}"}

    limit = min(limit, 50)

    if not db_manager:
        return {"error": "Database not available"}

    session = db_manager.get_session()
    try:
        from sqlalchemy import text, MetaData

        # Build safe query
        where_clauses = []
        params = {}

        if filters:
            for i, (col, val) in enumerate(filters.items()):
                # Basic SQL injection prevention — only allow alphanumeric column names
                if not col.replace("_", "").isalnum():
                    continue
                param_name = f"p{i}"
                where_clauses.append(f'"{col}" = :{param_name}')
                params[param_name] = val

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = text(f'SELECT * FROM "{table}"{where_sql} LIMIT :lim')
        params["lim"] = limit

        result = session.execute(query, params)
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                if isinstance(val, datetime):
                    val = val.isoformat()
                row_dict[col] = val
            rows.append(row_dict)

        return {
            "table": table,
            "row_count": len(rows),
            "columns": columns,
            "data": rows,
        }
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}
    finally:
        db_manager.Session.remove()


async def log_search_tool(
    search_type: str = "health_checks",
    target: Optional[str] = None,
    status: Optional[str] = None,
    minutes_ago: int = 60,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search recent health check logs and incidents.

    Args:
        search_type: "health_checks" or "incidents"
        target: Filter by target name (optional)
        status: Filter by status (optional)
        minutes_ago: How far back to look (default 60)
        limit: Max results (capped at 50)
    """
    from app.core.database import db_manager

    if not db_manager:
        return {"error": "Database not available"}

    limit = min(limit, 50)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

    session = db_manager.get_session()
    try:
        if search_type == "health_checks":
            from app.models.ops_models import HealthCheck

            query = session.query(HealthCheck).filter(HealthCheck.checked_at >= cutoff)
            if target:
                query = query.filter(HealthCheck.target == target)
            if status:
                query = query.filter(HealthCheck.status == status)

            results = query.order_by(HealthCheck.checked_at.desc()).limit(limit).all()

            return {
                "search_type": "health_checks",
                "count": len(results),
                "data": [
                    {
                        "id": r.id,
                        "target": r.target,
                        "target_type": r.target_type,
                        "status": r.status,
                        "latency_ms": r.latency_ms,
                        "details": json.loads(r.details) if r.details else None,
                        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
                    }
                    for r in results
                ],
            }

        elif search_type == "incidents":
            from app.models.ops_models import Incident

            query = session.query(Incident).filter(Incident.created_at >= cutoff)
            if status:
                query = query.filter(Incident.status == status)

            results = query.order_by(Incident.created_at.desc()).limit(limit).all()

            return {
                "search_type": "incidents",
                "count": len(results),
                "data": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "severity": r.severity,
                        "status": r.status,
                        "category": r.category,
                        "root_cause": r.root_cause,
                        "recommended_fix": r.recommended_fix,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in results
                ],
            }

        else:
            return {"error": f"Unknown search_type: {search_type}. Use 'health_checks' or 'incidents'"}

    except Exception as e:
        return {"error": f"Log search failed: {str(e)}"}
    finally:
        db_manager.Session.remove()


async def integration_status_tool(
    integration_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check the status of system integrations (Groq, Neon DB, Qdrant, etc.)

    Args:
        integration_name: Specific integration to check (optional, checks all if None)
    """
    from app.monitoring.health_checks import (
        check_database, check_vector_store, check_llm_service, check_api_latency
    )

    checks = {
        "database": check_database,
        "vector_store": check_vector_store,
        "llm": check_llm_service,
        "api": check_api_latency,
    }

    if integration_name and integration_name in checks:
        result = await checks[integration_name]()
        return {
            "integration": integration_name,
            "status": result.status.value,
            "latency_ms": result.latency_ms,
            "details": result.details,
        }

    # Check all
    results = {}
    for name, check_fn in checks.items():
        try:
            result = await check_fn()
            results[name] = {
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "details": result.details,
            }
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}

    return {"integrations": results}


async def knowledge_base_search(
    query: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Search the RAG knowledge base for troubleshooting information.

    Args:
        query: Natural language search query
        top_k: Number of results to return
    """
    try:
        from app.services.qdrant_store import get_qdrant_store
        from app.services.rag_service import RAGService

        # Initialize embeddings
        rag = RAGService()
        if not rag.embeddings:
            return {"error": "Embeddings not initialized"}

        store = get_qdrant_store()
        if not store:
            return {"error": "Vector store not available"}

        # Perform similarity search
        docs = store.similarity_search_with_score(query, k=top_k)

        results = []
        for doc, score in docs:
            results.append({
                "content": doc.page_content[:500],  # Truncate for agent context
                "source": doc.metadata.get("source", "unknown"),
                "relevance_score": round(float(score), 4),
            })

        return {
            "query": query,
            "results_count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"error": f"Knowledge base search failed: {str(e)}"}


async def digital_twin_tool(
    outlet_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get the digital twin state for a store or all stores.

    Args:
        outlet_id: Specific outlet ID (optional, returns all if None)
    """
    try:
        from app.digital_twin.twin_manager import TwinManager
        tm = TwinManager()

        if outlet_id is not None:
            twin = await tm.get_store_twin(outlet_id)
            if twin:
                return {"outlet_id": outlet_id, "twin": twin}
            else:
                return {"error": f"No twin found for outlet {outlet_id}"}
        else:
            twins = await tm.get_all_twins()
            return {
                "total_stores": len(twins),
                "stores": twins,
            }
    except Exception as e:
        return {"error": f"Digital twin query failed: {str(e)}"}


# Tool registry for the agent
TOOL_REGISTRY = {
    "database_query": {
        "function": database_query_tool,
        "description": (
            "Query database tables for diagnostic info. "
            "Allowed tables: pos_devices, pos_transactions, outlets, vouchers, "
            "ops_health_checks, ops_incidents, ops_device_states, ops_store_twins"
        ),
    },
    "log_search": {
        "function": log_search_tool,
        "description": "Search recent health check logs and incidents by target, status, and time range",
    },
    "integration_status": {
        "function": integration_status_tool,
        "description": "Check the live status of system integrations (database, vector store, LLM, API)",
    },
    "knowledge_base_search": {
        "function": knowledge_base_search,
        "description": "Search the RAG knowledge base for troubleshooting guides and historical incident resolutions",
    },
    "digital_twin": {
        "function": digital_twin_tool,
        "description": "Get the digital twin state for a store showing device health, transaction activity, and overall status",
    },
}
