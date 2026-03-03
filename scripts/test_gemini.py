"""
Phase 1 PoC: Test Gemini LLM Integration
Run: python scripts/test_gemini.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

def test_gemini_direct():
    """Test Gemini API directly via google-generativeai"""
    print("=" * 60)
    print("TEST 1: Direct Gemini API call")
    print("=" * 60)
    
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not api_key:
        print("❌ GOOGLE_GEMINI_API_KEY not set in .env")
        print("   Get your free key at: https://aistudio.google.com/")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content("Jawab dalam 1 kalimat: Apa itu POS (Point of Sale)?")
        
        print(f"✅ Model: gemini-2.0-flash")
        print(f"✅ Response: {response.text[:200]}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_gemini_langchain():
    """Test Gemini via LangChain (same as what the app uses)"""
    print("\n" + "=" * 60)
    print("TEST 2: Gemini via LangChain")
    print("=" * 60)
    
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not api_key:
        print("❌ GOOGLE_GEMINI_API_KEY not set")
        return False
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.2,
            convert_system_message_to_human=True,
        )
        
        response = llm.invoke("Jawab dalam Bahasa Indonesia formal: Bagaimana cara closing shift di mesin kasir POS?")
        print(f"✅ LangChain + Gemini working!")
        print(f"✅ Response: {response.content[:300]}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_gemini_rag_simulation():
    """Simulate RAG query with context (like the real app)"""
    print("\n" + "=" * 60)
    print("TEST 3: RAG Simulation with Gemini")
    print("=" * 60)
    
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not api_key:
        print("❌ GOOGLE_GEMINI_API_KEY not set")
        return False
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.1,
            convert_system_message_to_human=True,
        )
        
        # Simulated knowledge context (like FAISS would return)
        context = """
        --- SOURCE: closing_v5.txt | UPLOADED: 2026-01-15 ---
        Cara Closing Shift V5:
        1. Buka menu Shift Management
        2. Klik tombol "Close Shift" 
        3. Hitung uang di cash drawer
        4. Input jumlah uang fisik
        5. Sistem akan menampilkan selisih
        6. Klik "Confirm Close"
        7. Print laporan shift
        
        --- SOURCE: PO_web_order.txt | UPLOADED: 2026-02-10 ---
        Purchase Order (PO) Web Order:
        1. Login ke dashboard admin
        2. Buka menu Purchase Order
        3. Pilih supplier
        4. Tambahkan item yang ingin di-order
        5. Review dan submit PO
        """
        
        prompt = f"""Anda adalah spesialis dukungan teknis dari Edgeworks.

Konteks Dokumen:
{context}

Pertanyaan: Bagaimana cara closing shift?

Jawab dalam Bahasa Indonesia formal berdasarkan konteks di atas:"""
        
        response = llm.invoke(prompt)
        print(f"✅ RAG simulation working!")
        print(f"✅ Answer:\n{response.content[:500]}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_provider_fallback():
    """Test the provider fallback chain: gemini → groq → openai"""
    print("\n" + "=" * 60)
    print("TEST 4: Provider Fallback Chain")
    print("=" * 60)
    
    providers_available = []
    
    # Check Gemini
    gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if gemini_key:
        providers_available.append("✅ Gemini: API key found")
    else:
        providers_available.append("⚠️  Gemini: No API key (will skip)")
    
    # Check Groq
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        providers_available.append("✅ Groq: API key found")
    else:
        providers_available.append("⚠️  Groq: No API key")
    
    # Check OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        providers_available.append("✅ OpenAI: API key found")
    else:
        providers_available.append("⚠️  OpenAI: No API key")
    
    current_provider = os.getenv("LLM_PROVIDER", "groq")
    
    for p in providers_available:
        print(f"   {p}")
    print(f"\n   Current LLM_PROVIDER={current_provider}")
    print(f"   Fallback chain: gemini → groq → openai")
    return True


if __name__ == "__main__":
    print("🚀 Gemini Integration Test Suite")
    print(f"   Project: Support Portal AI")
    print(f"   Phase: 1 - LLM Migration\n")
    
    results = []
    results.append(("Provider Check", test_provider_fallback()))
    results.append(("Direct Gemini", test_gemini_direct()))
    results.append(("LangChain Gemini", test_gemini_langchain()))
    results.append(("RAG Simulation", test_gemini_rag_simulation()))
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {name}")
    
    all_pass = all(r[1] for r in results)
    print(f"\n{'🎉 All tests passed!' if all_pass else '⚠️  Some tests failed. Check API key.'}")
