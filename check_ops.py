with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, l in enumerate(lines):
    if "id === 'operations'" in l:
        for x in range(i, i+10):
            print(lines[x].strip()[:200])
        break
