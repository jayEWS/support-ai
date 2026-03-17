import re
with open('templates/admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'<section id="overview-view".*?</section>', html, re.DOTALL)
if m:
    with open('overview_dump.html', 'w', encoding='utf-8') as out:
        out.write(m.group(0))
    print('Dumped to overview_dump.html')
