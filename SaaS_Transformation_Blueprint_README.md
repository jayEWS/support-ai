# 🚀 Support Portal -- SaaS Transformation Blueprint

## Overview

This document outlines the technical transformation plan to evolve the
current internal AI-powered support portal into a scalable, multi-tenant
SaaS platform.

The goal is to transition from:

> Internal Enterprise Tool\
> to\
> AI-Native Multi-Industry SaaS Infrastructure

------------------------------------------------------------------------

# 🧱 Current State Assessment

## ✅ Strengths (Keep & Strengthen)

-   Hybrid RAG (BM25 + Vector + RRF)
-   SLA engine with auto-assignment
-   Ticket lifecycle state machine
-   Multi-language onboarding
-   PII masking & jailbreak detection
-   WhatsApp (Meta Cloud API) integration
-   Audit logging
-   Role-based access control (RBAC)

These form a strong enterprise-grade foundation.

------------------------------------------------------------------------

## ⚠️ Structural Issues (Must Fix)

### 1. No Multi-Tenant Architecture

-   All tables share single schema
-   No tenant isolation
-   Not SaaS-ready

### 2. Monolithic DatabaseManager (1,600+ lines)

-   High coupling
-   Hard to scale development
-   Risky to modify

### 3. Frontend Technical Debt

-   3,500+ lines SPA (vanilla JS)
-   Hard to maintain
-   Not scalable for SaaS expansion

------------------------------------------------------------------------

# ❌ Components to Remove (Phase 1 Cleanup)

-   Bird WhatsApp legacy adapters (if fully migrated to Meta Cloud API)
-   Asana integration (optional -- not core)
-   Freshdesk viewer module (convert to migration-only tool)

Reduce complexity before scaling.

------------------------------------------------------------------------

# 🏗 Target SaaS Architecture

## Core Principle

Every operational table must include:

    tenant_id (NOT NULL)

All queries must be tenant-scoped.

------------------------------------------------------------------------

## Core SaaS Tables

### Tenant

-   id
-   name
-   industry
-   plan_id
-   status
-   created_at

### Plan

-   id
-   name
-   price_monthly
-   max_agents
-   max_ai_messages
-   max_tickets
-   features_json

### TenantUser

-   id
-   tenant_id
-   email
-   role
-   status

------------------------------------------------------------------------

## Operational Tables (All Tenant-Scoped)

-   Customer
-   Ticket
-   Message
-   KnowledgeCollection
-   AIInteractionLog
-   UsageTracking

------------------------------------------------------------------------

# 🧠 AI Observability Blueprint

To become AI-native SaaS, add:

## Metrics to Track

-   AI confidence score
-   Escalation rate
-   Hallucination detection flag
-   Re-answer rate
-   Average latency
-   Token usage per interaction
-   Cost per response

## Required Table

### AIInteractionLog

-   tenant_id
-   ticket_id
-   tokens_used
-   confidence_score
-   escalation_flag
-   latency_ms
-   created_at

This enables AI quality monitoring and billing readiness.

------------------------------------------------------------------------

# 💰 Monetization Architecture

## Pricing Model (Suggested)

### Starter -- \$99/month

-   3 agents
-   1,500 AI messages

### Growth -- \$299/month

-   10 agents
-   10,000 AI messages
-   SLA engine
-   WhatsApp integration

### Enterprise -- \$999+/month

-   Unlimited agents
-   Advanced AI observability
-   Dedicated support

## Required Billing Tables

-   Subscription
-   UsageTracking
-   Invoice (placeholder)
-   Payment (placeholder)

------------------------------------------------------------------------

# 🛠 Refactor Roadmap

## Phase 1 -- Stabilize (0--2 Months)

-   Add tenant_id to all tables
-   Split DatabaseManager into repositories
-   Remove unused integrations
-   Add usage tracking middleware

## Phase 2 -- SaaS Foundation (2--4 Months)

-   Tenant onboarding flow
-   Plan enforcement middleware
-   Feature flag system
-   AIInteractionLog implementation

## Phase 3 -- AI-Native Upgrade (4--6 Months)

-   Confidence scoring engine
-   Escalation prediction
-   SLA breach prediction
-   AI dashboard panel

## Phase 4 -- Productization (6+ Months)

-   Stripe integration
-   Self-serve signup
-   Tenant admin panel
-   Industry template packs

------------------------------------------------------------------------

# 🚨 Development Rules Going Forward

Before adding any new feature, ask:

1.  Is this tenant-isolated?
2.  Is this configurable per tenant?
3.  Is this usage-trackable for billing?
4.  Does this increase AI quality or reduce operational load?

If not, reconsider building it.

------------------------------------------------------------------------

# 🎯 Final Strategic Direction

Do NOT position as:

    "AI Helpdesk SaaS"

Position as:

    AI Operations Support Infrastructure

For: - Retail - F&B - Omnichannel - Integration - ERP - Dev Teams

Build once. Configure per industry.

------------------------------------------------------------------------

Generated as SaaS Transformation Blueprint.
