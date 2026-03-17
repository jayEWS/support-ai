import re

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

def replace_section(section_id, replacement):
    global html
    old_sec = re.search(r'<section id=["\']' + section_id + r'-view["\'].*?</section>', html, re.DOTALL)
    if old_sec:
        html = html.replace(old_sec.group(0), replacement)
        print(f'Replaced {section_id}')
    else:
        print(f'Not found {section_id}')

usermst_html = '''<section id="usermst-view" class="p-8 overflow-y-auto flex-1 hidden">
            <div class="flex items-center justify-between mb-8">
                <h2 class="text-2xl font-bold tracking-tight">User Master</h2>
                <button class="px-4 py-2 bg-blue-600 text-white rounded-xl font-bold text-xs shadow-sm hover:bg-blue-700 transition flex items-center gap-2">
                    <i class="fas fa-user-plus"></i> Add User
                </button>
            </div>
            
            <div class="bg-white rounded-3xl border shadow-sm overflow-hidden mb-8">
                <div class="p-6 border-b border-gray-100 bg-gray-50/50 flex place-content-between items-center">
                    <h3 class="font-bold text-gray-800 text-xs tracking-wide flex items-center gap-2">
                        <i class="fas fa-users text-blue-500"></i> Manage System Agents
                    </h3>
                    <div class="relative">
                        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
                        <input type="text" placeholder="Search users..." class="py-2 pl-8 pr-4 bg-white border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 w-64">
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase">Agent</th>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase">Email</th>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase">Roles / Groups</th>
                                <th class="px-6 py-4 text-right text-[11px] font-bold text-gray-500 tracking-wider uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="usermst-list" class="divide-y divide-gray-50 bg-white"></tbody>
                    </table>
                </div>
            </div>
        </section>'''

groupperms_html = '''<section id="groupperms-view" class="p-8 overflow-y-auto flex-1 hidden">
            <div class="flex items-center justify-between mb-8">
                <h2 class="text-2xl font-bold tracking-tight">Group Privileges</h2>
                <button class="px-4 py-2 bg-blue-600 text-white rounded-xl font-bold text-xs shadow-sm hover:bg-blue-700 transition flex items-center gap-2">
                    <i class="fas fa-plus"></i> New Group
                </button>
            </div>
            
            <div class="bg-white rounded-3xl border shadow-sm p-8">
                <div class="mb-6 flex items-center gap-2">
                    <h3 class="font-bold text-gray-800 text-xs tracking-wide flex items-center gap-2">
                        <i class="fas fa-users-cog text-purple-500"></i> Role & Group Allocations
                    </h3>
                </div>
                <div id="roles-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"></div>
            </div>
        </section>'''

privsetup_html = '''<section id="privsetup-view" class="p-8 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold mb-8 tracking-tight">Privilege Setup</h2>
            
            <div class="bg-white rounded-3xl border shadow-sm p-8">
                <div class="mb-6 flex items-center gap-2 border-b pb-4">
                    <h3 class="font-bold text-gray-800 text-xs tracking-wide flex items-center gap-2">
                        <i class="fas fa-key text-amber-500"></i> System Access Rights Configuration
                    </h3>
                </div>
                <div class="space-y-8" id="perms-category-list"></div>
            </div>
        </section>'''

audit_html = '''<section id="audit-view" class="p-8 overflow-y-auto flex-1 hidden">
            <div class="flex items-center justify-between mb-8">
                <h2 class="text-2xl font-bold tracking-tight">Audit Logs</h2>
                <div class="flex gap-3">
                    <button class="px-4 py-2 bg-white border border-gray-200 text-gray-600 rounded-xl font-bold text-xs shadow-sm hover:bg-gray-50 transition flex items-center gap-2">
                        <i class="fas fa-filter"></i> Filter
                    </button>
                    <button class="px-4 py-2 bg-white border border-gray-200 text-gray-600 rounded-xl font-bold text-xs shadow-sm hover:bg-gray-50 transition flex items-center gap-2">
                        <i class="fas fa-download"></i> Export
                    </button>
                </div>
            </div>
            
            <div class="bg-white rounded-3xl border shadow-sm overflow-hidden mb-8">
                <div class="p-6 border-b border-gray-100 bg-gray-50/50">
                    <h3 class="font-bold text-gray-800 text-xs tracking-wide flex items-center gap-2">
                        <i class="fas fa-shield-alt text-red-500"></i> System Activity Trail
                    </h3>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase w-48">Time</th>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase w-48">Agent</th>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-gray-500 tracking-wider uppercase">Action</th>
                            </tr>
                        </thead>
                        <tbody id="audit-list" class="divide-y divide-gray-50 bg-white text-sm"></tbody>
                    </table>
                </div>
            </div>
        </section>'''

replace_section('usermst', usermst_html)
replace_section('groupperms', groupperms_html)
replace_section('privsetup', privsetup_html)
replace_section('audit', audit_html)

# Also fix headers for macros and kb quickly if they are too big/old layout
html = html.replace('text-3xl font-extrabold mb-8 text-gray-900', 'text-2xl font-bold mb-8')
html = html.replace('text-3xl font-extrabold text-gray-900', 'text-2xl font-bold')

# one more variation might be present
html = html.replace('text-3xl font-extrabold', 'text-2xl font-bold')

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Done!')
