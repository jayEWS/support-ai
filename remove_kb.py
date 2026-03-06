import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove sidebar link for KB
content = re.sub(r'<a href="/kb" onclick="event\.preventDefault\(\); showKnowledgeBase\(\)".*?Knowledge Base\s*</a>', '', content, flags=re.DOTALL)

# Remove the kb-view section
content = re.sub(r'<!-- ═══════ KNOWLEDGE BASE VIEW ═══════ -->.*?</main>\n', '', content, flags=re.DOTALL)

# Remove the quick chip for KB
content = re.sub(r'<span class="quick-chip">📖 Knowledge Base</span>\s*', '', content)

# Remove JS functions: showKnowledgeBase, kbQuickAsk, copyKbAnswer, formatKbAnswer, and event listener for kb-search-form
js_pattern = r'/\*\s*══════════ KNOWLEDGE BASE \(Internal Self-Service\) ══════════\s*\*/.*?(?=/\*\s*── History ──\s*\*/|/\*\s*── Audio/Screen Recording ──\s*\*/|/\*\s*── WebRTC Video Calling ──\s*\*/)'
content = re.sub(js_pattern, '', content, flags=re.DOTALL)

# Remove references to kb-view from nav functions
content = re.sub(r"document\.getElementById\('kb-view'\)\.classList\.remove\('hidden'\);\n\s*", '', content)
content = re.sub(r"document\.getElementById\('kb-view'\)\.classList\.add\('hidden'\);\n\s*", '', content)
content = re.sub(r"document\.getElementById\('nav-kb'\).classList.remove\('active'\);\s*", '', content)
content = re.sub(r"document\.getElementById\('nav-kb'\).classList.add\('active'\);\s*", '', content)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed KB from index.html")
