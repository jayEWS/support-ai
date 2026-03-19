import re

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update menu_def
old_menu_def = "overview: { icon: 'fa-chart-pie', label: 'Overview', isDropdown: true, id: 'overview' }"
new_menu_def = "overview: { icon: 'fa-chart-pie', label: 'Overview', onClick: \"switchTab('overview')\" }"
text = text.replace(old_menu_def, new_menu_def)

# 2. Extract Subcontent Removal
start_idx = text.find("if (id === 'overview') return `")
if start_idx != -1:
    end_idx = text.find("`;", start_idx) + 2
    if end_idx > 1:
        text = text[:start_idx] + text[end_idx:]

# 3. Clean up tabs arrays
old_valid = "'overview', 'overview_chat', 'overview_whatsapp', 'overview_email', 'overview_team', 'overview_category', 'inbox'"
new_valid = "'overview', 'inbox'"
text = text.replace(old_valid, new_valid)

old_valid2 = "'overview', 'overview_chat', 'overview_whatsapp', 'overview_email', 'overview_team', 'overview_category', 'inbox', "
new_valid2 = "'overview', 'inbox', "
text = text.replace(old_valid2, new_valid2)

# Submenu map
old_submap = "overview: 'overview', overview_chat: 'overview', overview_whatsapp: 'overview', overview_email: 'overview', overview_team: 'overview', overview_category: 'overview', inbox: 'chat'"
new_submap = "inbox: 'chat'"
text = text.replace(old_submap, new_submap)

# Remove old fragmented sections
text = re.sub(r'<section id="overview_?[^"]*?-view".*?</section>', '', text, flags=re.DOTALL)
text = re.sub(r'<section id="overview-view".*?</section>', '', text, flags=re.DOTALL)

# Insert new Mega Overview Section
mega_overview = """
<section id="overview-view" class="p-10 overflow-y-auto flex-1 hidden bg-slate-50 relative">
    <!-- Header -->
    <div class="mb-10 flex flex-col pt-8 sm:flex-row justify-between items-start sm:items-end gap-6 bg-white z-20 pb-6 border-b border-gray-100 shadow-[0_4px_20px_-15px_rgba(0,0,0,0.1)] -mt-10 -mx-10 px-10 pt-10 sticky top-0">
        <div>
            <h2 class="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                Performance Center
            </h2>
            <p class="text-slate-500 mt-2 text-sm max-w-2xl leading-relaxed">Unified Analytics across Live Chat, WhatsApp, Email, Team Performance & Case Categories.</p>
        </div>
        <div class="flex items-center gap-3 self-end">
            <span class="text-xs font-semibold uppercase tracking-wider text-slate-400 bg-slate-100 px-3 py-1 rounded-full"><i class="fas fa-satellite-dish mr-1 text-emerald-500 animate-pulse"></i> Live Sync</span>
            <button onclick="refreshDashboard()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-medium text-sm transition-all shadow-lg shadow-indigo-200 flex items-center gap-2 group">
                <i class="fas fa-sync-alt group-hover:rotate-180 transition-transform duration-500"></i> Refresh
            </button>
        </div>
    </div>

    <!-- MAIN GRID DASHBOARD -->
    <div class="space-y-8 max-w-full">
        <!-- TOP KPI STATS (Legacy ID overview-stats) -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6" id="overview-stats">
             <!-- Dynamically populated by updateOverviewStats JS -->
        </div>

        <!-- CHANNEL METRICS ROW -->
        <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest pt-4 pl-1 border-t border-slate-200/60 mt-8 mb-2"><i class="fas fa-layer-group mr-2"></i>Channel Performance Breakdown</h3>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Chat Card -->
            <div class="bg-white p-7 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
                <div class="flex items-center gap-4 mb-6 relative">
                    <div class="w-12 h-12 bg-cyan-50 rounded-xl flex items-center justify-center border border-cyan-100">
                        <i class="fas fa-comments text-cyan-500 text-lg"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-slate-800">Live Chat</h4>
                        <div class="text-xs text-slate-400 font-medium">Real-time Portal</div>
                    </div>
                </div>
                <div class="space-y-5">
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">Avg Response Time</span><span id="chat-resp" class="font-bold text-slate-800">32s</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-cyan-400 h-1.5 rounded-full w-[70%]"></div></div>
                    </div>
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">Resolution Rate</span><span id="chat-res" class="font-bold text-slate-800 text-emerald-600">92%</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-emerald-400 h-1.5 rounded-full w-[92%]"></div></div>
                    </div>
                </div>
            </div>

            <!-- WhatsApp Card -->
            <div class="bg-white p-7 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
                <div class="flex items-center gap-4 mb-6">
                    <div class="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center border border-emerald-100/50">
                        <i class="fab fa-whatsapp text-emerald-500 text-xl"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-slate-800">WhatsApp</h4>
                        <div class="text-xs text-slate-400 font-medium">+62 Meta API</div>
                    </div>
                </div>
                <div class="space-y-5">
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">Daily Messages</span><span id="wa-vol" class="font-bold text-slate-800">1,245</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-emerald-400 h-1.5 rounded-full w-[85%]"></div></div>
                    </div>
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">AI Managed</span><span id="wa-ai" class="font-bold text-slate-800 text-indigo-500">48%</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-indigo-400 h-1.5 rounded-full w-[48%]"></div></div>
                    </div>
                </div>
            </div>

            <!-- Email Card -->
            <div class="bg-white p-7 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
                <div class="flex items-center gap-4 mb-6">
                    <div class="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center border border-indigo-100">
                        <i class="fas fa-envelope text-indigo-500 text-lg"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-slate-800">Email Support</h4>
                        <div class="text-xs text-slate-400 font-medium">support@domain</div>
                    </div>
                </div>
                <div class="space-y-5">
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">Pending Backlog</span><span id="email-backlog" class="font-bold text-slate-800">14 Tickets</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-amber-400 h-1.5 rounded-full w-[30%]"></div></div>
                    </div>
                    <div>
                        <div class="flex justify-between items-end mb-1"><span class="text-xs font-semibold text-slate-500">Avg Time to Reply</span><span id="email-reply" class="font-bold text-slate-800">4h 12m</span></div>
                        <div class="w-full bg-slate-50 rounded-full h-1.5"><div class="bg-indigo-400 h-1.5 rounded-full w-[50%]"></div></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- BIG CHARTS ROW -->
        <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest pt-4 pl-1 border-t border-slate-200/60 mt-8 mb-2"><i class="fas fa-chart-area mr-2"></i>Trends & Categories</h3>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
                <h4 class="font-bold text-slate-700 mb-6 flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-indigo-500"></div> Total Volume Trend</h4>
                <div class="h-64 flex items-end justify-center px-4 w-full">
                    <canvas id="volumeChart" class="w-full"></canvas>
                </div>
            </div>
            
            <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
                <h4 class="font-bold text-slate-700 mb-6 flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-purple-500"></div> Case Categories Map</h4>
                
                <div class="space-y-6 mt-4 relative">
                     <!-- Category Bars -->
                     <div>
                         <div class="flex justify-between mb-2"><span class="text-sm font-semibold text-slate-600 truncate mr-2"><i class="fas fa-key text-purple-400 text-xs mr-2"></i>Password Reset</span><span class="text-sm font-bold text-slate-800">45%</span></div>
                         <div class="w-full bg-slate-100 rounded-full h-2"><div class="bg-purple-500 h-2 rounded-full" style="width: 45%"></div></div>
                     </div>
                     <div>
                         <div class="flex justify-between mb-2"><span class="text-sm font-semibold text-slate-600 truncate mr-2"><i class="fas fa-desktop text-purple-400 text-xs mr-2"></i>Hardware Issues</span><span class="text-sm font-bold text-slate-800">28%</span></div>
                         <div class="w-full bg-slate-100 rounded-full h-2"><div class="bg-purple-400 h-2 rounded-full" style="width: 28%"></div></div>
                     </div>
                     <div>
                         <div class="flex justify-between mb-2"><span class="text-sm font-semibold text-slate-600 truncate mr-2"><i class="fas fa-file-invoice-dollar text-purple-400 text-xs mr-2"></i>Billing Inquiry</span><span class="text-sm font-bold text-slate-800">15%</span></div>
                         <div class="w-full bg-slate-100 rounded-full h-2"><div class="bg-purple-300 h-2 rounded-full" style="width: 15%"></div></div>
                     </div>
                     <div>
                         <div class="flex justify-between mb-2"><span class="text-sm font-semibold text-slate-600"><i class="fas fa-question-circle text-purple-400 text-xs mr-2"></i>Other</span><span class="text-sm font-bold text-slate-800">12%</span></div>
                         <div class="w-full bg-slate-100 rounded-full h-2"><div class="bg-purple-200 h-2 rounded-full" style="width: 12%"></div></div>
                     </div>
                </div>
                <!-- Need original canvas element just in case scripts rely on it -->
                <canvas id="priorityChart" height="1" style="display:none;"></canvas>
            </div>
        </div>

        <!-- PEOPLE AND AI ROW -->
        <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest pt-4 pl-1 border-t border-slate-200/60 mt-8 mb-2"><i class="fas fa-users-cog mr-2"></i>Team & Intelligence</h3>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Team Performance Leaderboard -->
            <div class="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                <div class="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h4 class="font-bold text-slate-700 flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-amber-500"></div> Support Agents</h4>
                    <button class="text-xs font-semibold text-indigo-500 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-3 py-1 rounded-full transition-colors">View All</button>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-slate-100">
                        <thead class="bg-stone-50">
                            <tr>
                                <th class="px-6 py-4 text-left text-[11px] font-bold text-slate-400 uppercase tracking-wider">Agent</th>
                                <th class="px-6 py-4 text-center text-[11px] font-bold text-slate-400 uppercase tracking-wider">Tickets Closed</th>
                                <th class="px-6 py-4 text-right text-[11px] font-bold text-slate-400 uppercase tracking-wider">CSAT Rating</th>
                            </tr>
                        </thead>
                        <tbody id="agent-leaderboard" class="divide-y divide-slate-50 bg-white">
                            <!-- Injected dynamically, fallback below -->
                            <tr class="hover:bg-slate-50/50">
                                <td class="px-6 py-4 whitespace-nowrap"><div class="flex items-center"><div class="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-400 to-orange-500 text-white flex items-center justify-center font-bold text-xs mr-3 shadow-md">SM</div><div class="text-sm font-semibold text-slate-700">Sarah Mitchell</div></div></td>
                                <td class="px-6 py-4 text-center text-sm font-bold text-slate-600">42</td>
                                <td class="px-6 py-4 text-right"><span class="px-2.5 py-1 text-xs font-bold bg-emerald-100 text-emerald-700 rounded-full border border-emerald-200"><i class="fas fa-star text-amber-400 mr-1"></i>4.9</span></td>
                            </tr>
                            <tr class="hover:bg-slate-50/50">
                                <td class="px-6 py-4 whitespace-nowrap"><div class="flex items-center"><div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-400 to-indigo-500 text-white flex items-center justify-center font-bold text-xs mr-3 shadow-md">JD</div><div class="text-sm font-semibold text-slate-700">James Doe</div></div></td>
                                <td class="px-6 py-4 text-center text-sm font-bold text-slate-600">38</td>
                                <td class="px-6 py-4 text-right"><span class="px-2.5 py-1 text-xs font-bold bg-emerald-100 text-emerald-700 rounded-full border border-emerald-200"><i class="fas fa-star text-amber-400 mr-1"></i>4.7</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- AI Magic Analysis Box -->
            <div class="bg-slate-900 text-white p-8 rounded-2xl shadow-xl border border-slate-700 relative overflow-hidden flex flex-col justify-between group">
                <div class="absolute -top-24 -right-24 w-64 h-64 bg-indigo-600/20 rounded-full blur-3xl group-hover:bg-indigo-500/30 transition-colors duration-700"></div>
                <div class="absolute -bottom-12 -left-12 w-48 h-48 bg-purple-600/20 rounded-full blur-3xl group-hover:bg-purple-500/30 transition-colors duration-700"></div>
                
                <h4 class="font-bold text-white mb-6 flex items-center gap-3 relative z-10 text-lg tracking-wide border-b border-white/10 pb-4">
                    <div class="w-10 h-10 bg-indigo-500/30 backdrop-blur-md rounded-xl flex items-center justify-center shadow-inner border border-indigo-400/20">
                        <i class="fas fa-brain text-indigo-300"></i>
                    </div>
                    Copilot Insights
                </h4>
                
                <div id="ai-trends" class="text-sm text-indigo-100/90 leading-relaxed font-medium mt-2 mb-6 relative z-10 flex-1">
                    <div class="flex gap-3 mb-4"><i class="fas fa-bolt text-yellow-500 mt-1"></i><p>Noticeable spike in "Hardware Issues" between 10am-12pm. Consider re-allocating agent bandwidth for the afternoon shift.</p></div>
                    <div class="flex gap-3 mb-4"><i class="fas fa-check-circle text-emerald-400 mt-1"></i><p>Live chat resolution rate is up 4% today vs 7-day average. Excellent handling times recorded across the board.</p></div>
                </div>
                
                <div class="mt-auto relative z-10">
                    <button class="w-full bg-white/10 hover:bg-white/20 border border-white/20 text-white py-2.5 rounded-xl text-sm font-semibold transition-all">Generate Strategy Report</button>
                </div>
            </div>
        </div>
    </div>
</section>
"""

# Insert perfectly before chat view
if '<section id="chat-view"' in text:
    text = text.replace('<section id="chat-view"', mega_overview + '\n<section id="chat-view"')

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replaced successfully!")
