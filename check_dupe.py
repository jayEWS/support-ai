with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for j, k in enumerate(["id === 'operations'", "id === 'settings'"]):
    for i, l in enumerate(lines):
        if k in l:
            print(f"\n--- {k} ---")
            for x in range(i, i+15):
                line = lines[x].strip()
                if 'knowledge' in line:
                    print("FOUND KNOWLEDGE:", line[:200])
            break
