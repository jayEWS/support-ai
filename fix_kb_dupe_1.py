import re
with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("'customers', 'knowledge', 'operations'", "'customers', 'operations'")

# Now remove it from menuDefs
res = re.sub(r'\s+knowledge:\s*\{\s*icon:\s*\'fa-brain\',\s*label:\s*\'Knowledge Base\',\s*onClick:\s*\"switchTab\(\'knowledge\'\)\"\s*\},', '', text)

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(res)
print("Complete")