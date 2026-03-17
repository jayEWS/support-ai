"""
AI Support Engineer Agent
==========================
A LangChain-powered agent that performs step-by-step investigation of incidents.
Uses the tool registry to gather evidence, analyze root causes, and recommend fixes.

This agent does NOT use LangChain's agent executor (which requires OpenAI function calling).
Instead, it implements a structured investigation pipeline using the LLM for reasoning
and calling tools programmatically based on the incident type.

Investigation Flow:
    1. Classify incident category
    2. Gather relevant data (tools)
    3. Search knowledge base for similar issues
    4. Check digital twin state
    5. Synthesize root cause analysis
    6. Recommend fix and automation action
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.core.logging import logger
from app.core.config import settings
from app.monitoring.anomaly_detector import Anomaly
from app.agents.tools import (
    database_query_tool,
    log_search_tool,
    integration_status_tool,
    knowledge_base_search,
    digital_twin_tool,
)


# Investigation prompts per category
INVESTIGATION_PROMPTS = {
    "database": (
        "A database issue has been detected.\n\n"
        "Evidence:\n{evidence}\n\n"
        "Recent health checks:\n{health_logs}\n\n"
        "Integration status:\n{integration_status}\n\n"
        "Analyze this incident and provide:\n"
        "1. Root Cause: What is the most likely cause?\n"
        "2. Evidence: What data supports this conclusion?\n"
        "3. Recommended Fix: Step-by-step resolution\n"
        "4. Automation Action: Can this be auto-fixed? If yes, which action? "
        "(allowed: retry_integration, retry_api_call, flush_cache, reconnect_device)\n"
        "5. Confidence: How confident are you (0.0-1.0)?\n\n"
        "Return ONLY a JSON object with keys: root_cause, evidence_summary, recommended_fix, automation_action (or null), confidence"
    ),
    "pos_health": (
        "A POS device health issue has been detected.\n\n"
        "Incident: {title}\n"
        "Evidence:\n{evidence}\n\n"
        "Device data:\n{device_data}\n\n"
        "Store twin state:\n{twin_state}\n\n"
        "Knowledge base matches:\n{kb_results}\n\n"
        "Analyze this POS incident and provide:\n"
        "1. Root Cause: What is causing the POS issue?\n"
        "2. Evidence: Supporting data\n"
        "3. Recommended Fix: Step-by-step resolution for the support team\n"
        "4. Automation Action: Can this be auto-fixed? "
        "(allowed: restart_pos_service, reconnect_device, retry_integration)\n"
        "5. Confidence: 0.0-1.0\n\n"
        "Return ONLY a JSON object with keys: root_cause, evidence_summary, recommended_fix, automation_action (or null), confidence"
    ),
    "integration": (
        "An integration issue has been detected.\n\n"
        "Incident: {title}\n"
        "Evidence:\n{evidence}\n\n"
        "Integration status:\n{integration_status}\n\n"
        "Knowledge base:\n{kb_results}\n\n"
        "Analyze this integration issue and provide:\n"
        "1. Root Cause\n2. Evidence\n3. Recommended Fix\n"
        "4. Automation Action (allowed: retry_integration, retry_api_call, flush_cache)\n"
        "5. Confidence: 0.0-1.0\n\n"
        "Return ONLY a JSON object with keys: root_cause, evidence_summary, recommended_fix, automation_action (or null), confidence"
    ),
    "api": (
        "An API performance issue has been detected.\n\n"
        "Evidence:\n{evidence}\n\n"
        "Health checks:\n{health_logs}\n\n"
        "Analyze and provide root_cause, evidence_summary, recommended_fix, "
        "automation_action (allowed: retry_api_call, flush_cache, or null), confidence.\n\n"
        "Return ONLY a JSON object."
    ),
    "default": (
        "A system issue has been detected.\n\n"
        "Incident: {title}\n"
        "Description: {description}\n"
        "Severity: {severity}\n"
        "Evidence:\n{evidence}\n\n"
        "Health checks:\n{health_logs}\n\n"
        "Integration status:\n{integration_status}\n\n"
        "Knowledge base:\n{kb_results}\n\n"
        "Analyze this incident and provide:\n"
        "1. Root Cause\n2. Evidence\n3. Recommended Fix\n"
        "4. Automation Action (or null if manual fix needed)\n"
        "5. Confidence: 0.0-1.0\n\n"
        "Return ONLY a JSON object with keys: root_cause, evidence_summary, recommended_fix, automation_action (or null), confidence"
    ),
}


class SupportEngineerAgent:
    """
    AI Support Engineer that investigates incidents using a structured pipeline.
    Uses Groq LLM for reasoning and tool functions for data gathering.
    """

    def __init__(self):
        self.llm = self._init_llm()

    def _init_llm(self):
        """Initialize the LLM for the agent."""
        try:
            from langchain_groq import ChatGroq
            api_key = settings.GROQ_API_KEY
            if api_key:
                return ChatGroq(
                    model=settings.MODEL_NAME,
                    api_key=api_key,
                    temperature=0.1,
                )
        except Exception as e:
            logger.warning(f"[SupportAgent] LLM init failed: {e}")
        return None

    async def investigate_incident(
        self, incident_id: int, anomaly: Anomaly
    ) -> Optional[Dict[str, Any]]:
        """
        Perform a structured investigation of an incident.

        Args:
            incident_id: The incident record ID
            anomaly: The detected anomaly data

        Returns:
            Dict with root_cause, recommended_fix, automation_action, confidence, investigation_log
        """
        if not self.llm:
            logger.warning("[SupportAgent] No LLM available, skipping investigation")
            return None

        investigation_log: List[str] = []
        investigation_log.append(f"[{datetime.now(timezone.utc).isoformat()}] Starting investigation for incident #{incident_id}")
        investigation_log.append(f"Category: {anomaly.category}, Severity: {anomaly.severity}")
        investigation_log.append(f"Title: {anomaly.title}")

        # Step 1: Gather evidence using tools
        context = await self._gather_evidence(anomaly, investigation_log)

        # Step 2: Build investigation prompt
        prompt = self._build_prompt(anomaly, context)
        investigation_log.append(f"[{datetime.now(timezone.utc).isoformat()}] Sending analysis to LLM")

        # Step 3: Get AI analysis
        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(prompt),
                timeout=30.0,
            )

            content = response.content.strip()

            # Clean markdown wrapping if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:].strip()
                # Handle closing ```
                if "```" in content:
                    content = content[:content.rindex("```")]

            result = json.loads(content)
            investigation_log.append(f"[{datetime.now(timezone.utc).isoformat()}] AI analysis complete")
            investigation_log.append(f"Root cause: {result.get('root_cause', 'Unknown')}")
            investigation_log.append(f"Confidence: {result.get('confidence', 0)}")

            return {
                "root_cause": result.get("root_cause", "Unable to determine"),
                "evidence_summary": result.get("evidence_summary", ""),
                "recommended_fix": result.get("recommended_fix", "Manual investigation required"),
                "automation_action": result.get("automation_action"),
                "confidence": float(result.get("confidence", 0.5)),
                "investigation_log": investigation_log,
            }

        except asyncio.TimeoutError:
            investigation_log.append("LLM analysis timed out after 30s")
            logger.error(f"[SupportAgent] LLM timeout for incident #{incident_id}")
            return {
                "root_cause": "Analysis timed out",
                "recommended_fix": "Manual investigation required — LLM response timeout",
                "automation_action": None,
                "confidence": 0.0,
                "investigation_log": investigation_log,
            }

        except json.JSONDecodeError as e:
            investigation_log.append(f"Failed to parse LLM response: {e}")
            logger.error(f"[SupportAgent] JSON parse error: {e}")
            return {
                "root_cause": "LLM returned non-JSON response",
                "recommended_fix": "Manual investigation required",
                "automation_action": None,
                "confidence": 0.0,
                "investigation_log": investigation_log,
            }

        except Exception as e:
            investigation_log.append(f"Analysis error: {str(e)}")
            logger.error(f"[SupportAgent] Investigation error: {e}")
            return None

    async def _gather_evidence(
        self, anomaly: Anomaly, log: List[str]
    ) -> Dict[str, Any]:
        """Gather evidence from multiple tools concurrently."""
        context: Dict[str, Any] = {}

        # Always gather health checks and integration status
        tasks = {
            "health_logs": log_search_tool(
                search_type="health_checks",
                target=anomaly.evidence.get("target") if anomaly.evidence else None,
                minutes_ago=30,
                limit=10,
            ),
            "integration_status": integration_status_tool(),
        }

        # Category-specific evidence gathering
        if anomaly.category == "pos_health" and anomaly.device_id:
            tasks["device_data"] = database_query_tool(
                table="pos_devices",
                filters={"DeviceID": anomaly.device_id},
            )
            if anomaly.outlet_id:
                tasks["twin_state"] = digital_twin_tool(outlet_id=anomaly.outlet_id)

        elif anomaly.category == "database":
            tasks["recent_incidents"] = log_search_tool(
                search_type="incidents",
                status="detected",
                minutes_ago=120,
                limit=5,
            )

        # Always search knowledge base
        kb_query = f"{anomaly.category} {anomaly.title}"
        tasks["kb_results"] = knowledge_base_search(query=kb_query, top_k=3)

        # Execute all tasks concurrently
        log.append(f"[{datetime.now(timezone.utc).isoformat()}] Gathering evidence ({len(tasks)} tools)")

        results = await asyncio.gather(
            *[tasks[k] for k in tasks],
            return_exceptions=True,
        )

        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                context[key] = {"error": str(result)}
                log.append(f"  Tool '{key}' failed: {result}")
            else:
                context[key] = result
                count = result.get("count", result.get("results_count", result.get("row_count", "?")))
                log.append(f"  Tool '{key}': {count} results")

        return context

    def _build_prompt(self, anomaly: Anomaly, context: Dict[str, Any]) -> str:
        """Build the investigation prompt for the LLM."""
        category = anomaly.category
        template = INVESTIGATION_PROMPTS.get(category, INVESTIGATION_PROMPTS["default"])

        # Build template variables
        variables = {
            "title": anomaly.title,
            "description": anomaly.description,
            "severity": anomaly.severity,
            "evidence": json.dumps(anomaly.evidence, indent=2, default=str) if anomaly.evidence else "No raw evidence",
            "health_logs": json.dumps(context.get("health_logs", {}), indent=2, default=str)[:2000],
            "integration_status": json.dumps(context.get("integration_status", {}), indent=2, default=str)[:1500],
            "device_data": json.dumps(context.get("device_data", {}), indent=2, default=str)[:1500],
            "twin_state": json.dumps(context.get("twin_state", {}), indent=2, default=str)[:2000],
            "kb_results": json.dumps(context.get("kb_results", {}), indent=2, default=str)[:2000],
        }

        # Only format with keys that exist in the template
        try:
            prompt = template.format(**variables)
        except KeyError:
            # Fallback: use default template
            prompt = INVESTIGATION_PROMPTS["default"].format(**variables)

        return prompt

    async def ask(self, question: str) -> Dict[str, Any]:
        """
        Ask the AI Support Engineer a question (for interactive use via API).

        Args:
            question: Natural language question about the system

        Returns:
            Dict with answer, tools_used, and data gathered
        """
        if not self.llm:
            return {"answer": "AI agent is not available — no LLM configured", "tools_used": []}

        tools_used = []
        context_parts = []

        # Detect what tools to use based on question keywords
        q_lower = question.lower()

        if any(w in q_lower for w in ["device", "pos", "printer", "kds", "terminal", "scanner"]):
            result = await database_query_tool(table="pos_devices", limit=10)
            tools_used.append("database_query:pos_devices")
            context_parts.append(f"POS Devices: {json.dumps(result, default=str)[:1500]}")

        if any(w in q_lower for w in ["health", "status", "check", "system"]):
            result = await integration_status_tool()
            tools_used.append("integration_status")
            context_parts.append(f"Integration Status: {json.dumps(result, default=str)[:1500]}")

        if any(w in q_lower for w in ["store", "outlet", "twin", "overall"]):
            result = await digital_twin_tool()
            tools_used.append("digital_twin")
            context_parts.append(f"Store Twins: {json.dumps(result, default=str)[:2000]}")

        if any(w in q_lower for w in ["incident", "anomaly", "error", "issue", "problem"]):
            result = await log_search_tool(search_type="incidents", minutes_ago=120, limit=10)
            tools_used.append("log_search:incidents")
            context_parts.append(f"Recent Incidents: {json.dumps(result, default=str)[:1500]}")

        if any(w in q_lower for w in ["how to", "fix", "resolve", "troubleshoot", "guide"]):
            result = await knowledge_base_search(query=question, top_k=3)
            tools_used.append("knowledge_base_search")
            context_parts.append(f"Knowledge Base: {json.dumps(result, default=str)[:2000]}")

        # If no specific tools triggered, use integration status as baseline
        if not context_parts:
            result = await integration_status_tool()
            tools_used.append("integration_status")
            context_parts.append(f"Integration Status: {json.dumps(result, default=str)[:1500]}")

        context_text = "\n\n".join(context_parts)

        prompt = (
            "You are an AI Support Engineer for a Retail POS ecosystem.\n"
            "Use the following system data to answer the question.\n\n"
            f"System Data:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Provide a clear, actionable answer. If you detect any issues, "
            "suggest specific remediation steps."
        )

        try:
            response = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=30.0)
            return {
                "answer": response.content,
                "tools_used": tools_used,
                "data_gathered": len(context_parts),
            }
        except Exception as e:
            return {
                "answer": f"Agent analysis failed: {str(e)}",
                "tools_used": tools_used,
                "data_gathered": len(context_parts),
            }
