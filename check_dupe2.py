with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, l in enumerate(lines):
    if "function renderSidebar()" in l:
        print("\n--- renderSidebar ---")
        for x in range(i, i+60):
            line = lines[x].strip()
            if 'knowledge' in line.lower() or 'Knowledge' in line:
                print(f"FOUND (Line {i+x}):", line[:200])
        break
