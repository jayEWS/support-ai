# AI-Powered Support Portal (Advanced v2.1)

A production-grade support ticketing and real-time chat system with RAG (Retrieval-Augmented Generation) and advanced multi-agent routing.

## 🚀 Key Features (Milestone 4 Complete)

-   **Real-time WebSocket Chat**: Modern chat interface with typing indicators, read receipts, and avatars.
-   **AI Support Agent**: Automated responses powered by GPT-4o and your custom Knowledge Base.
-   **Advanced Routing**: Least-busy routing logic and overflow queueing for human agents.
-   **SLA Management**: Dynamic ticket priorities and due dates calculated by AI.
-   **Agent Dashboard**: Full-featured admin panel with live queue monitoring, macros (canned responses), and CSAT analytics.
-   **Omnichannel Ready**: Support for WhatsApp integration via Bird (MessageBird).

## 🛠 Tech Stack

-   **Backend**: FastAPI, Python 3.10+, SQLite
-   **AI/LLM**: OpenAI (GPT-4o), LangChain, FAISS (Vector DB)
-   **Real-time**: WebSockets
-   **Frontend**: Tailwind CSS, Vanilla JS

## 📋 Project Status

| Milestone | Feature | Status |
| :--- | :--- | :--- |
| **1** | RAG Engine & Basic API | ✅ Complete |
| **2** | WebSocket Foundation | ✅ Complete |
| **3** | Routing & SLA Logic | ✅ Complete |
| **4** | Agent Dashboard & Macros | ✅ Complete |
| **5** | Hardening & CSAT | ✅ Complete |

## ⚙️ Installation

1.  Clone the repository.
2.  Install dependencies: `pip install -r requirements.txt`
3.  Set up your `.env` file (see `.env.example`).
4.  Run the application: `python main.py`

## 🔐 Security

The portal uses an `X-API-Key` for administrative actions. In production, ensure `SUPPORT_PORTAL_ADMIN_KEY` is set in your environment variables.
