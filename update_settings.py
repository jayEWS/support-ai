import os
import re

html_path = 'templates/admin.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update renderSubContent('settings')
def repl(m):
    return m.group(0).replace("switchTab('settings', 'admin')", "switchTab('settings_admin')")\
                     .replace("switchTab('settings', 'support')", "switchTab('settings_support')")\
                     .replace("switchTab('settings', 'system_admin')", "switchTab('settings_system_admin')")

new_html = re.sub(r"<a href=[\"']#[\"'] onclick=[\"']switchTab\('settings', '(?:admin|support|system_admin)'\).*?</span></a>",
                  lambda m: m.group(0).replace("'settings', '", "'settings_"), html)

# 2. Update switchTab array
old_array = "['overview', 'inbox', 'team', 'tickets', 'whatsapp', 'macros', 'knowledge', 'customers', 'settings', 'audit', 'usermst', 'groupperms', 'privsetup', 'livechat', 'ops_health', 'ops_incidents', 'ops_twins', 'ops_automation', 'ops_agent']"
new_array = "['overview', 'inbox', 'team', 'tickets', 'whatsapp', 'macros', 'knowledge', 'customers', 'settings', 'settings_admin', 'settings_support', 'settings_system_admin', 'audit', 'usermst', 'groupperms', 'privsetup', 'livechat', 'ops_health', 'ops_incidents', 'ops_twins', 'ops_automation', 'ops_agent']"

new_html = new_html.replace(old_array, new_array)

# 3. Insert new sections after settings-view
settings_end = '''                                <span id="ticket-notify-status" class="text-xs text-gray-400"></span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>'''

new_sections = '''

        <!-- Admin Settings -->
        <section id="settings_admin-view" class="p-8 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold mb-8 tracking-tight">Admin Settings</h2>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- Company Profile -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-building text-blue-600"></i> Company Profile
                        </h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Company Name</label>
                                <input type="text" value="Edgeworks Solutions" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                            </div>
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Support Portal Title</label>
                                <input type="text" value="Edgeworks Support AI" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                            </div>
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Timezone</label>
                                <select class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                                    <option>Asia/Singapore (+08:00)</option>
                                    <option>Asia/Jakarta (+07:00)</option>
                                    <option>UTC (00:00)</option>
                                </select>
                            </div>
                            <div class="pt-2">
                                <button class="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-bold text-xs tracking-wide hover:bg-blue-700 transition shadow-sm">
                                    <i class="fas fa-save mr-1"></i> Save Profile
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Support Hours -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-clock text-amber-500"></i> Support Hours
                        </h3>
                        <div class="space-y-4">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-sm font-bold text-gray-700">24/7 Support</p>
                                    <p class="text-xs text-gray-400">Agents are always online</p>
                                </div>
                                <input type="checkbox" class="w-10 h-5 rounded-full bg-gray-300 appearance-none cursor-pointer relative checked:bg-blue-600 checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:w-4 after:h-4 after:rounded-full after:transition-all">
                            </div>
                            <div class="grid grid-cols-2 gap-4 pt-2">
                                <div>
                                    <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Start Time</label>
                                    <input type="time" value="09:00" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none" />
                                </div>
                                <div>
                                    <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">End Time</label>
                                    <input type="time" value="18:00" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none" />
                                </div>
                            </div>
                            <div class="pt-2">
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Offline Message</label>
                                <textarea rows="2" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none resize-none">Our team is currently offline. We will reply as soon as we're back!</textarea>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Support Settings -->
        <section id="settings_support-view" class="p-8 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold mb-8 tracking-tight">Support Settings</h2>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- Ticket Configuration -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-ticket-alt text-green-600"></i> Ticket Configuration
                        </h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Default SLA (Hours)</label>
                                <input type="number" value="24" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none" />
                            </div>
                            <div class="flex items-center justify-between pt-2">
                                <div>
                                    <p class="text-sm font-bold text-gray-700">Auto-Assign Tickets</p>
                                    <p class="text-xs text-gray-400">Round-robin assignment to active agents</p>
                                </div>
                                <input type="checkbox" checked class="w-10 h-5 rounded-full bg-blue-600 appearance-none cursor-pointer relative checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:w-4 after:h-4 after:rounded-full after:transition-all">
                            </div>
                            <div class="flex items-center justify-between pt-2">
                                <div>
                                    <p class="text-sm font-bold text-gray-700">Auto-Close Tickets</p>
                                    <p class="text-xs text-gray-400">Close resolved tickets after 3 days</p>
                                </div>
                                <input type="checkbox" checked class="w-10 h-5 rounded-full bg-blue-600 appearance-none cursor-pointer relative checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:w-4 after:h-4 after:rounded-full after:transition-all">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Customer Satisfaction (CSAT) -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-star text-yellow-500"></i> CSAT Feedback
                        </h3>
                        <div class="space-y-4">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-sm font-bold text-gray-700">Request CSAT Score</p>
                                    <p class="text-xs text-gray-400">Ask for rating when ticket is resolved</p>
                                </div>
                                <input type="checkbox" checked class="w-10 h-5 rounded-full bg-blue-600 appearance-none cursor-pointer relative checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:w-4 after:h-4 after:rounded-full after:transition-all">
                            </div>
                            <div class="pt-2">
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">CSAT Email Template</label>
                                <textarea rows="3" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none resize-none">We'd love to hear your feedback on our support! Please rate your experience...</textarea>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- System Admin Settings -->
        <section id="settings_system_admin-view" class="p-8 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold mb-8 tracking-tight">System Admin</h2>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- Database Status -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-database text-indigo-600"></i> Database Storage
                        </h3>
                        <div class="space-y-4">
                            <div class="bg-gray-50 p-4 rounded-xl flex items-center justify-between">
                                <div>
                                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider">PostgreSQL Status</p>
                                    <p class="text-sm font-bold text-emerald-600 flex items-center gap-1"><i class="fas fa-circle text-[8px]"></i> Online</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider">Size</p>
                                    <p class="text-sm font-bold text-gray-800">482 MB</p>
                                </div>
                            </div>
                            <div class="bg-gray-50 p-4 rounded-xl flex items-center justify-between">
                                <div>
                                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider">Vector DB (Qdrant)</p>
                                    <p class="text-sm font-bold text-emerald-600 flex items-center gap-1"><i class="fas fa-circle text-[8px]"></i> Online</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider">Vectors</p>
                                    <p class="text-sm font-bold text-gray-800">12,450</p>
                                </div>
                            </div>
                            <div class="pt-2 flex gap-3">
                                <button class="px-4 py-2 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded-xl font-bold text-xs hover:bg-indigo-100 transition">
                                    <i class="fas fa-download mr-1"></i> Trigger Backup
                                </button>
                                <button class="px-4 py-2 bg-gray-50 text-gray-600 border border-gray-200 rounded-xl font-bold text-xs hover:bg-gray-100 transition">
                                    <i class="fas fa-broom mr-1"></i> Clear Cache
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- API & Integrations -->
                <div class="bg-white p-8 rounded-3xl border shadow-sm space-y-6">
                    <div>
                        <h3 class="font-bold text-gray-800 mb-4 flex items-center gap-2 text-xs tracking-wide">
                            <i class="fas fa-plug text-blue-500"></i> API Integrations
                        </h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Support Portal Webhook URL</label>
                                <div class="flex">
                                    <input type="text" readonly value="https://api.edgeworks.com.sg/webhook" class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-l-xl text-sm text-gray-500 focus:outline-none" />
                                    <button class="px-4 py-3 bg-gray-100 border border-l-0 border-gray-200 rounded-r-xl text-gray-600 hover:bg-gray-200"><i class="fas fa-copy"></i></button>
                                </div>
                            </div>
                            <div>
                                <label class="block text-[11px] font-bold text-gray-500 tracking-wide mb-2">Groq LLM Usage</label>
                                <div class="w-full bg-gray-100 rounded-full h-2 mb-1">
                                    <div class="bg-blue-500 h-2 rounded-full" style="width: 45%"></div>
                                </div>
                                <p class="text-xs text-gray-400">45% of monthly quota</p>
                            </div>
                            <div class="pt-2">
                                <button class="px-4 py-2 bg-slate-900 text-white rounded-xl font-bold text-xs shadow-sm hover:bg-slate-800 transition">
                                    <i class="fas fa-key mr-1"></i> Manage API Keys
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>'''

if settings_end in new_html:
    new_html = new_html.replace(settings_end, settings_end + new_sections)
else:
    print('Failed to find settings end matching!')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_html)

print('Success')
