
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Replace formatKbAnswer function
new_func = """        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. CLEANUP: Strip source markers but preserve natural structure
            let cleaned = text
                .replace(/Source\\s*\\d+/gi, '')
                .replace(/Source\\s*:\\s*[^\\n\\r]*/gi, '')
                .replace(/^\\s*\\*?\\*?Sources?:?\\*?\\*?\\s*.*$/gim, '')
                .replace(/[\\w_-]+\\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\\(\\s*[,\\s]*\\s*\\)/g, '')
                .replace(/\\[\\s*[,\\s]*\\s*\\]/g, '')
                .replace(/,\\s*,/g, ',')
                .replace(/,\\s*$/gm, '');

            // 2. STRUCTURAL ISOLATION: Ensure headers and list items start on new lines
            cleaned = cleaned.replace(/([^\\n])\\s*(\\*?\\*?(?:Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|What is|Conclusion|Summary):?\\*?\\*?)/gi, '$1\\n\\n$2');
            cleaned = cleaned.replace(/([^\\n])\\s+(\\d+\\.\\s+)/g, '$1\\n\\n$2');
            cleaned = cleaned.replace(/([^\\n])\\s+([-•*])\\s+(?!\\*)/g, '$1\\n\\n$2');

            // 3. BLOCK PARSING
            const rawLines = cleaned.split('\\n');
            let blocks = [];
            let currentBlock = null;

            for (let i = 0; i < rawLines.length; i++) {
                let line = rawLines[i].trim();
                if (!line) {
                    currentBlock = null;
                    continue;
                }

                let type = 'para';
                let match = null;

                if (match = line.match(/^(\\d+)\\.\\s*(.*)/)) {
                    type = 'numbered';
                } else if (match = line.match(/^([-•*])\\s+(?!\\*)(.*)/)) {
                    type = 'bullet';
                } else if (line.match(/^###\\s+||^\\*\\*.*?\\*\\*:?$/) || (line.startsWith('**') && line.length < 60 && (line.endsWith('**') || line.endsWith('**:')))) {
                    type = 'header';
                }

                if (type === 'para' && currentBlock && currentBlock.type === 'para') {
                    currentBlock.content += ' ' + line;
                } else if (type === 'para' && currentBlock && (currentBlock.type === 'numbered' || currentBlock.type === 'bullet')) {
                    currentBlock.content += ' ' + line;
                } else {
                    currentBlock = { type, content: line, match: match };
                    blocks.push(currentBlock);
                }
            }

            // 4. RENDERING
            let html = '';
            let inList = false;

            blocks.forEach(block => {
                let text = block.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                text = text.replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="text-brand-600">$1</strong>');

                if (block.type === 'header') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let headerText = text.replace(/^(#{1,3}\\s*|\\*\\*)/, '').replace(/(\\*\\*|:)$/, '').trim();
                    html += `<h4 class="kb-header">${headerText}</h4>`;
                } else if (block.type === 'numbered') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let num = block.match[1];
                    let content = text.replace(/^\\d+\\.\\s*/, '');
                    html += `<div class="kb-numbered"><span class="kb-num">${num}.</span><div class="kb-item-content">${content}</div></div>`;
                } else if (block.type === 'bullet') {
                    if (!inList) { html += '<ul class="kb-bullets">'; inList = true; }
                    let content = text.replace(/^([-•*])\\s+/, '');
                    html += `<li>${content}</li>`;
                } else {
                    if (inList) { html += '</ul>'; inList = false; }
                    html += `<p class="kb-para">${text}</p>`;
                }
            });

            if (inList) html += '</ul>';
            return html;
        }"""

import re
text = re.sub(r'function formatKbAnswer\(text\) \{.*?\}\n\n\s+function copyKbAnswer', new_func + '\n\n        function copyKbAnswer', text, flags=re.DOTALL)

# 2. Update CSS
css_updates = """        .kb-answer .kb-numbered {
            margin: 0.6rem 0;
            padding-left: 0.1rem;
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
        }

        .kb-answer .kb-num {
            font-weight: 700;
            color: #2e6bff;
            min-width: 1.5rem;
            flex-shrink: 0;
            text-align: left;
        }

        .kb-answer .kb-item-content {
            flex: 1;
            line-height: 1.62;
        }"""

text = re.sub(r'\.kb-answer \.kb-numbered \{.*?\}\n\n\s+\.kb-answer \.kb-num \{.*?\}', css_updates, text, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
print("KB Formatting overhaul applied successfully.")
