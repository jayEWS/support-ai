#!/usr/bin/env python
"""
Quick Setup Script for RAG Improvements
Installs all enhanced dependencies and configures system
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run command with status indicator"""
    print(f"\n📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed")
            return True
        else:
            print(f"⚠️  {description} had issues: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False

def setup_rag_improvements():
    """Setup all RAG improvements"""
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║   🚀 RAG IMPROVEMENTS SETUP                       ║
    ║   Hybrid Search | Observability | Deployment     ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    # Step 1: Install enhanced requirements
    print("\n[1/5] Installing enhanced requirements...")
    if run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Upgrading pip"
    ):
        run_command(
            f"{sys.executable} -m pip install -r requirements.txt",
            "Installing all dependencies"
        )
    
    # Step 2: Create .env.local if doesn't exist
    print("\n[2/5] Configuring environment...")
    env_file = Path(".env")
    env_advanced = Path(".env.advanced")
    
    if not env_file.exists():
        print("⚠️  .env not found - create one from .env.example")
    
    if env_advanced.exists():
        print(f"✅ Advanced config available: {env_advanced}")
    
    # Step 3: Verify installations
    print("\n[3/5] Verifying installations...")
    packages = [
        ("rank_bm25", "Hybrid search (BM25)"),
        ("chromadb", "Persistent vector store"),
        ("langfuse", "Observability & tracing"),
        ("slowapi", "Rate limiting"),
        ("langchain_groq", "Groq LLM provider"),
        ("ragas", "RAG evaluation"),
        ("deepeval", "Quality testing"),
        ("unstructured", "Document processing"),
    ]
    
    installed = []
    missing = []
    
    for package, name in packages:
        try:
            __import__(package)
            print(f"✅ {name} ({package})")
            installed.append(name)
        except ImportError:
            print(f"⚠️  {name} ({package}) - optional")
            missing.append(package)
    
    # Step 4: Setup directories
    print("\n[4/5] Creating directories...")
    dirs = ["data/uploads/chat", "data/db_storage", "data/knowledge", "logs"]
    for dir in dirs:
        Path(dir).mkdir(parents=True, exist_ok=True)
        print(f"✅ {dir}/")
    
    # Step 5: Test imports
    print("\n[5/5] Testing core functionality...")
    try:
        from app.services.rag_service import RAGService
        print("✅ RAG Service imports correctly")
    except Exception as e:
        print(f"⚠️  RAG Service import issue: {e}")
    
    try:
        from app.services.rag_evaluation import RAGEvaluator
        print("✅ RAG Evaluator imports correctly")
    except Exception as e:
        print(f"⚠️  RAG Evaluator import issue: {e}")
    
    # Summary
    print(f"""
    ╔═══════════════════════════════════════════════════╗
    ║   ✅ SETUP COMPLETE                              ║
    ╠═══════════════════════════════════════════════════╣
    ║ Installed: {len(installed)}/8 enhanced packages        ║
    ║ Missing:   {len(missing)}/8 (optional)                  ║
    ╚═══════════════════════════════════════════════════╝
    
    📋 Next Steps:
    
    1️⃣  Configure .env:
        - Set your LLM provider (openai/groq/ollama)
        - Add API keys
        - Enable hybrid search: RAG_HYBRID_SEARCH_ENABLED=true
    
    2️⃣  Optional - Setup Observability:
        - Langfuse: https://langfuse.com
        - Self-host on Render for free
    
    3️⃣  Optional - Switch LLM Provider:
        - Use Groq for free + 10x speed: https://console.groq.com
        - Use Ollama for completely local: https://ollama.ai
    
    4️⃣  Test RAG:
        - Run: python app/services/rag_evaluation.py
        - Verify hybrid search is working
    
    5️⃣  Deploy:
        - Docker: docker build -t support-portal .
        - Render: Push to GitHub + connect
        - Railway: Similar to Render
    
    📚 Documentation: See IMPROVEMENTS_GUIDE.md
    """)

if __name__ == "__main__":
    try:
        setup_rag_improvements()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {e}")
        sys.exit(1)
