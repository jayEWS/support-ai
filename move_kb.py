import re

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove 'Knowledge Base' from settings
text = re.sub(r'<a href="#" onclick="switchTab\(\'knowledge\'\)".*?</span></a>\s+', '', text)

# Add 'Self Learning and Help' to operations
ops_old = r"""<a href="#" onclick="switchTab('ops_agent')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-user-astronaut text-indigo-500'></i> AI Engineer</span></a>"""
ops_new = ops_old + r"""
                <a href="#" onclick="switchTab('knowledge')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-brain text-purple-500'></i> Self Learning & Help</span></a>"""
if ops_old in text:
    text = text.replace(ops_old, ops_new)
else:
    print("WARNING: ops_old not found!")

# rename section h2
text = text.replace('<h2 class="text-2xl font-bold tracking-tight">Knowledge Base</h2>', '<h2 class="text-2xl font-bold tracking-tight">Self Learning & Help</h2>')
text = text.replace('<h2 class="text-2xl font-bold mb-8 tracking-tight">Knowledge Base</h2>', '<h2 class="text-2xl font-bold tracking-tight mb-8">Self Learning & Help</h2>')

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Done')