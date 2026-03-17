import re
with open('templates/admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'<section id="overview-view".*?</section>', html, re.DOTALL)
if m:
    print('Overview length:', len(m.group(0)))
    print(m.group(0)[:1500])
else:
    print('Overview not found')
