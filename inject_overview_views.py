import re

with open('templates/admin.html', 'r', encoding='utf-8') as f:
    text = f.read()

overview_chat = """
        <!-- Overview Chat Perf -->
        <section id="overview_chat-view" class="p-10 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold tracking-tight mb-2">Live Chat Performance</h2>
            <p class="text-gray-500 mb-8">Metrics and key drivers around live chat resolution.</p>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Avg Response Time</span><i class="fas fa-bolt text-cyan-500 w-8 h-8 flex items-center justify-center bg-cyan-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">45s</div>
                    <div class="text-xs text-emerald-500 mt-2 font-semibold"><i class="fas fa-arrow-down mr-1"></i>12% vs last week</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Resolution Rate</span><i class="fas fa-check-circle text-emerald-500 w-8 h-8 flex items-center justify-center bg-emerald-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">92%</div>
                    <div class="text-xs text-emerald-500 mt-2 font-semibold"><i class="fas fa-arrow-up mr-1"></i>3% vs last week</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Active Conversations</span><i class="fas fa-comments text-blue-500 w-8 h-8 flex items-center justify-center bg-blue-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">24</div>
                    <div class="text-xs text-gray-400 mt-2 font-semibold">Current ongoing</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">CSAT Score</span><i class="fas fa-star text-amber-500 w-8 h-8 flex items-center justify-center bg-amber-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">4.8</div>
                    <div class="text-xs text-gray-400 mt-2 font-semibold">Based on 142 ratings</div>
                </div>
            </div>
            
            <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50">
                <h3 class="font-bold text-gray-800 mb-8 flex items-center gap-2 text-sm tracking-wide">
                    <div class="w-8 h-8 bg-cyan-50 rounded-lg flex items-center justify-center">
                        <i class="fas fa-chart-area text-cyan-600"></i>
                    </div>
                    Live Chat Hourly Volume
                </h3>
                <div class="w-full h-48 bg-gray-50 rounded-xl flex items-center justify-center border border-dashed border-gray-200">
                    <p class="text-gray-400 font-semibold text-sm">Hourly metrics visualization will load here</p>
                </div>
            </div>
        </section>
"""

overview_whatsapp = """
        <!-- Overview WhatsApp Perf -->
        <section id="overview_whatsapp-view" class="p-10 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold tracking-tight mb-2">WhatsApp Performance</h2>
            <p class="text-gray-500 mb-8">Insights extracted directly from standard and automated WhatsApp exchanges.</p>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Total Messages</span><i class="fab fa-whatsapp text-green-500 w-8 h-8 flex items-center justify-center bg-green-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">1,245</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">AI Automated</span><i class="fas fa-robot text-purple-500 w-8 h-8 flex items-center justify-center bg-purple-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">48%</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Templates Used</span><i class="fas fa-file-alt text-blue-500 w-8 h-8 flex items-center justify-center bg-blue-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">324</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Drop-off Rate</span><i class="fas fa-door-open text-red-500 w-8 h-8 flex items-center justify-center bg-red-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">4.2%</div>
                </div>
            </div>
            
            <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50">
                <h3 class="font-bold text-gray-800 mb-8 flex items-center gap-2 text-sm tracking-wide">
                    <div class="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
                        <i class="fas fa-chart-line text-green-600"></i>
                    </div>
                    WhatsApp Engagement Trends
                </h3>
                <div class="w-full h-48 bg-gray-50 rounded-xl flex items-center justify-center border border-dashed border-gray-200">
                    <p class="text-gray-400 font-semibold text-sm">Engagement chart will be rendered here</p>
                </div>
            </div>
        </section>
"""

overview_email = """
        <!-- Overview Email Perf -->
        <section id="overview_email-view" class="p-10 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold tracking-tight mb-2">Email Inbox Performance</h2>
            <p class="text-gray-500 mb-8">Metrics for asynchronous ticketing and deeper support flows.</p>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Unread Emails</span><i class="fas fa-envelope text-indigo-500 w-8 h-8 flex items-center justify-center bg-indigo-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">12</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Time to First Reply</span><i class="fas fa-stopwatch text-amber-500 w-8 h-8 flex items-center justify-center bg-amber-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">4h 12m</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Avg Resolution</span><i class="fas fa-calendar-check text-emerald-500 w-8 h-8 flex items-center justify-center bg-emerald-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">1.2d</div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <div class="flex items-center justify-between mb-4"><span class="text-sm font-bold text-gray-500 uppercase tracking-wider">Escalations</span><i class="fas fa-arrow-trend-up text-red-500 w-8 h-8 flex items-center justify-center bg-red-50 rounded-lg"></i></div>
                    <div class="text-3xl font-extrabold text-gray-800">8</div>
                </div>
            </div>
            
            <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50">
                <h3 class="font-bold text-gray-800 mb-8 flex items-center gap-2 text-sm tracking-wide">
                    <div class="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center">
                        <i class="fas fa-inbox text-indigo-600"></i>
                    </div>
                    Email Ticket Volume History
                </h3>
                <div class="w-full h-48 bg-gray-50 rounded-xl flex items-center justify-center border border-dashed border-gray-200">
                    <p class="text-gray-400 font-semibold text-sm">Volume bar chart rendering region</p>
                </div>
            </div>
        </section>
"""

overview_team = """
        <!-- Overview Team Perf -->
        <section id="overview_team-view" class="p-10 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold tracking-tight mb-2">Team & Agent Performance</h2>
            <p class="text-gray-500 mb-8">Agent-level analytics to assist in training and resource planning.</p>
            
            <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50 mb-8">
                <h3 class="font-bold text-gray-800 mb-6 flex items-center gap-2 text-sm tracking-wide">
                    <div class="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center">
                        <i class="fas fa-users text-amber-600"></i>
                    </div>
                    Agent Leaderboard & Scorecard
                </h3>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-gray-50/50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Agent</th>
                                <th class="px-6 py-3 text-center text-xs font-bold text-gray-500 uppercase tracking-wider">Tickets Resolved</th>
                                <th class="px-6 py-3 text-center text-xs font-bold text-gray-500 uppercase tracking-wider">Avg Handle Time</th>
                                <th class="px-6 py-3 text-center text-xs font-bold text-gray-500 uppercase tracking-wider">CSAT</th>
                                <th class="px-6 py-3 text-right text-xs font-bold text-gray-500 uppercase tracking-wider">Score</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-50 bg-white">
                            <!-- Placeholder -->
                            <tr><td class="px-6 py-4 text-sm font-medium">System AI</td><td class="px-6 py-4 text-sm text-center">452</td><td class="px-6 py-4 text-sm text-center">2m</td><td class="px-6 py-4 text-sm text-center text-amber-500"><i class="fas fa-star text-xs"></i> 4.9</td><td class="px-6 py-4 text-sm text-right text-emerald-500 font-bold">98</td></tr>
                            <tr><td class="px-6 py-4 text-sm font-medium">Jay</td><td class="px-6 py-4 text-sm text-center">124</td><td class="px-6 py-4 text-sm text-center">15m</td><td class="px-6 py-4 text-sm text-center text-amber-500"><i class="fas fa-star text-xs"></i> 4.8</td><td class="px-6 py-4 text-sm text-right text-emerald-500 font-bold">92</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
"""

overview_category = """
        <!-- Overview Category Perf -->
        <section id="overview_category-view" class="p-10 overflow-y-auto flex-1 hidden">
            <h2 class="text-2xl font-bold tracking-tight mb-2">Case Categories</h2>
            <p class="text-gray-500 mb-8">Determine volume metrics mapped against intent classification.</p>
            
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50">
                    <h3 class="font-bold text-gray-800 mb-6 flex items-center gap-2 text-sm tracking-wide">
                        <div class="w-8 h-8 bg-purple-50 rounded-lg flex items-center justify-center">
                            <i class="fas fa-tags text-purple-600"></i>
                        </div>
                        Top Intents
                    </h3>
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between mb-1"><span class="text-sm font-medium text-gray-600">Password Reset</span><span class="text-sm font-bold text-gray-800">45%</span></div>
                            <div class="w-full bg-gray-100 rounded-full h-2"><div class="bg-purple-500 h-2 rounded-full" style="width: 45%"></div></div>
                        </div>
                        <div>
                            <div class="flex justify-between mb-1"><span class="text-sm font-medium text-gray-600">Hardware Issues</span><span class="text-sm font-bold text-gray-800">28%</span></div>
                            <div class="w-full bg-gray-100 rounded-full h-2"><div class="bg-purple-400 h-2 rounded-full" style="width: 28%"></div></div>
                        </div>
                        <div>
                            <div class="flex justify-between mb-1"><span class="text-sm font-medium text-gray-600">Billing Inquiry</span><span class="text-sm font-bold text-gray-800">15%</span></div>
                            <div class="w-full bg-gray-100 rounded-full h-2"><div class="bg-purple-300 h-2 rounded-full" style="width: 15%"></div></div>
                        </div>
                        <div>
                            <div class="flex justify-between mb-1"><span class="text-sm font-medium text-gray-600">Other</span><span class="text-sm font-bold text-gray-800">12%</span></div>
                            <div class="w-full bg-gray-100 rounded-full h-2"><div class="bg-purple-200 h-2 rounded-full" style="width: 12%"></div></div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100/50">
                    <h3 class="font-bold text-gray-800 mb-6 flex items-center gap-2 text-sm tracking-wide">
                        <div class="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
                            <i class="fas fa-brain text-blue-600"></i>
                        </div>
                        AI Confidence per Category
                    </h3>
                    <div class="w-full h-48 bg-gray-50 rounded-xl flex items-center justify-center border border-dashed border-gray-200">
                        <p class="text-gray-400 font-semibold text-sm">Radar chart rendering region</p>
                    </div>
                </div>
            </div>
        </section>
"""

new_views = overview_chat + overview_whatsapp + overview_email + overview_team + overview_category

# Find the end of overview-view
m = re.search(r'<section id="overview-view".*?</section>', text, re.DOTALL)
if m:
    text = text.replace(m.group(0), m.group(0) + new_views)
    print("Injected new overview views")

with open('templates/admin.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Done')
