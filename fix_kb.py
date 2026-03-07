
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'function formatKbAnswer(text) {' in line:
        start_idx = i
    if start_idx != -1 and i > start_idx and 'function copyKbAnswer(btn) {' in line:
        end_idx = i - 1
        break

if start_idx != -1 and end_idx != -1:
    new_func = """        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. CLEANUP (Keep newlines, just strip artifacts)
            let cleaned = text
                .replace(/Source\\s*\\d+/gi, '')
                .replace(/Source\\s*:\\s*[^\\n\\r]*/gi, '')
                .replace(/^\\s*\\*?\\*?Sources?:?\\*?\\*?\\s*.*$/gim, '')
                .replace(/[\\w_-]+\\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\\(\\s*[,\\s]*\\s*\\)/g, '')
                .replace(/\\[\\s*[,\\s]*\\s*\\]/g, '')
                .replace(/,\\s*,/g, ',')
                .replace(/,\\s*$/gm, '');

            // 2. SMART PRE-PROCESS: Only insert newlines if they are missing
            cleaned = cleaned.replace(/([.!?:)])\\s+(\\*?\\*?(?:Prerequisites|Instructions|Step-by-step|Post-Closing|Troubleshooting):?\\*?\\*?)/gi, '$1\\n$2');
            cleaned = cleaned.replace(/([.!?:)])\\s+(\\d+\\.\\s+)/g, '$1\\n$2');
            cleaned = cleaned.replace(/([.!?:)])\\s+([-•*])\\s+(?!\\*)/g, '$1\\n$2');

            // 3. Line-by-Line Parsing
            const rawLines = cleaned.split('\\n');
            let html = '';
            let inList = false;

            for (let i = 0; i < rawLines.length; i++) {
                let rawLine = rawLines[i].trim();
                if (!rawLine) {
                    if (inList) { html += '</ul>'; inList = false; }
                    html += '<div class="h-2"></div>';
                    continue;
                }

                let line = rawLine.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

                let numMatch = line.match(/^(\\d+)\\.\\s*(.*)/);
                if (numMatch) {
                    if (inList) { html += '</ul>'; inList = false; }
                    let content = numMatch[2].replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="text-brand-600">$1</strong>');
                    html += `<div class="kb-numbered"><span class="kb-num">${numMatch[1]}.</span> ${content}</div>`;
                    continue;
                }

                let bulletMatch = line.match(/^([-•*])\\s+(?!\\*)(.*)/);
                if (bulletMatch) {
                    if (!inList) { html += '<ul class="kb-bullets">'; inList = true; }
                    let content = bulletMatch[2].replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="text-brand-600">$1</strong>');
                    html += `<li>${content}</li>`;
                    continue;
                }

                let headerMatch = line.match(/^(\\*\\*|###)?\\s*(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|What is|Conclusion):?\\s*(\\*\\*|:)?$/i);
                const isShortBold = line.startsWith('**') && (line.endsWith('**') || line.endsWith('**:')) && line.length < 60;
                
                if (headerMatch || isShortBold) {
                    if (inList) { html += '</ul>'; inList = false; }
                    let headerText = line.replace(/^(#{1,3}\\s*|\\*\\*)/, '').replace(/(\\*\\*|:)$/, '').trim();
                    html += `<h4 class="kb-header">${headerText}</h4>`;
                    continue;
                }

                if (inList) { html += '</ul>'; inList = false; }
                let finalLine = line.replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="text-brand-600">$1</strong>');
                html += `<p class="kb-para">${finalLine}</p>`;
            }

            if (inList) html += '</ul>';
            return html;
        }

"""
    lines[start_idx:end_idx+1] = [new_func]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Function replaced successfully.")
else:
    print(f"Indices not found: start={start_idx}, end={end_idx}")
