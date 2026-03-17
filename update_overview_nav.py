import re
with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Update menuDefs
old_menu_def = "overview: { icon: 'fa-chart-pie', label: 'Overview', onClick: \"switchTab('overview')\" }"
new_menu_def = "overview: { icon: 'fa-chart-pie', label: 'Overview', isDropdown: true, id: 'overview' }"
if old_menu_def in text:
    text = text.replace(old_menu_def, new_menu_def)
    print("Replaced menu_def")

# Update renderSubContent
new_sub = """if (id === 'overview') return `
                <a href="#" onclick="switchTab('overview')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-chart-line text-blue-400'></i> Performance Center</span></a>
                <a href="#" onclick="switchTab('overview_chat')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-comments text-cyan-400'></i> Live Chat Perf</span></a>
                <a href="#" onclick="switchTab('overview_whatsapp')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fab fa-whatsapp text-green-500'></i> WhatsApp Perf</span></a>
                <a href="#" onclick="switchTab('overview_email')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-envelope text-indigo-400'></i> Email Perf</span></a>
                <a href="#" onclick="switchTab('overview_team')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-users text-amber-500'></i> Team Perf</span></a>
                <a href="#" onclick="switchTab('overview_category')" class="flex justify-between items-center px-4 py-1.5 text-[11px] text-gray-500 hover:text-blue-600 hover:bg-gray-50/50 transition-all rounded-lg font-medium"><span class='flex items-center gap-2'><i class='fas fa-tags text-purple-400'></i> Case Categories</span></a>`;
            if (id === 'chat') return `"""

if "if (id === 'chat') return `" in text:
    text = text.replace("if (id === 'chat') return `", new_sub)
    print("Replaced renderSubContent")

# Update arrays 
old_valid_tabs = "'overview', 'inbox', "
new_valid_tabs = "'overview', 'overview_chat', 'overview_whatsapp', 'overview_email', 'overview_team', 'overview_category', 'inbox', "
if old_valid_tabs in text:
    text = text.replace(old_valid_tabs, new_valid_tabs)
    print("Replaced valid_tabs / forEach")

old_submenuMap = "inbox: 'chat'"
new_submenuMap = "overview: 'overview', overview_chat: 'overview', overview_whatsapp: 'overview', overview_email: 'overview', overview_team: 'overview', overview_category: 'overview', inbox: 'chat'"
if old_submenuMap in text:
    text = text.replace(old_submenuMap, new_submenuMap)
    print("Replaced submenuMap")

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated overview navigation arrays!')
