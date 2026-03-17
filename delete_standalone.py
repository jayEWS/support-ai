with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
old_text = r"customers: { icon: 'fa-users', label: 'Customers', onClick: \"switchTab('customers')\" }," + "\n" + r"                knowledge: { icon: 'fa-brain', label: 'Knowledge Base', onClick: \"switchTab('knowledge')\" },"

new_text = r"customers: { icon: 'fa-users', label: 'Customers', onClick: \"switchTab('customers')\" },"

if old_text in text:
    print('Found old_text')
    text = text.replace(old_text, new_text)

# Also remove 'knowledge' from the default menuOrder array
# e.g.: let menuOrder = ['overview', 'chat', 'team', 'tickets', 'customers', 'knowledge', 'operations', 'settings'];
menu_order_match = re.search(r'let menuOrder = \[[^\]]+\];', text)
if menu_order_match:
    mo = menu_order_match.group(0)
    mo_new = mo.replace(", 'knowledge'", "").replace("'knowledge', ", "")
    text = text.replace(mo, mo_new)
    print(f"Updated menuOrder: {mo_new}")

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Standalone menu item deleted')
