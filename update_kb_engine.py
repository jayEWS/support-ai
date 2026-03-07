
import os
import re

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

new_js_func = r"""        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. CLEANUP
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/,\s*,/g, ',')
                .replace(/,\s*$/gm, '');

            // 2. STRUCTURAL ISOLATION: Ensure headers and list items start on new lines
            // Aggressively split common sections
            cleaned = cleaned.replace(/([^\n])\s*(\*\*?(?:Prerequisites|Instructions for|Steps to|Troubleshooting|Note|What is|Conclusion|Summary|Post-Closing|Instructions):?\*\*?)/gi, '$1\n\n$2');
            
            // Fix clumping of numbered items
            cleaned = cleaned.replace(/([^\n])\s+(\d+\.\s*)/g, '$1\n\n$2');
            
            // Fix clumping of bullet points
            cleaned = cleaned.replace(/([^\n])\s+([-•*])\s+(?!\*)/g, '$1\n\n$2');

            // 3. BLOCK PARSING
            const rawLines = cleaned.split('\n');
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

                if (match = line.match(/^(\d+)\.\s*(.*)/)) {
                    type = 'numbered';
                } else if (match = line.match(/^([-•*])\s+(?!\*)(.*)/)) {
                    type = 'bullet';
                } else if (line.match(/^###\s+/) || line.match(/^\*\*.*?\*\*:?$/) || (line.startsWith('**') && line.length < 80 && (line.endsWith('**') || line.endsWith('**:')))) {
                    type = 'header';
                }

                if (type === 'para' && currentBlock && currentBlock.type === 'para') {
                    currentBlock.content += ' ' + line;
                } else if (type === 'para' && currentBlock && (currentBlock.type === 'numbered' || currentBlock.type === 'bullet')) {
                    // This allows multi-line list items
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
                
                // Highlight bold text (Brand Blue)
                text = text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-brand-600">$1</strong>');
                
                // Highlight Clues (Red Color for quoted text or common buttons)
                // Match text in "quotes" or 'quotes'
                text = text.replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>');
                text = text.replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                if (block.type === 'header') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let headerText = text.replace(/^(#{1,3}\s*|\*\*|<strong[^>]*>)/, '').replace(/(\*\*|<\/strong>|:)$/, '').trim();
                    html += `<h4 class="kb-header">${headerText}</h4>`;
                } else if (block.type === 'numbered') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let num = block.match[1];
                    let rem = text.replace(/^\d+\.\s*/, '');
                    html += `<div class="kb-numbered"><span class="kb-num">${num}.</span><div class="kb-item-content">${rem}</div></div>`;
                } else if (block.type === 'bullet') {
                    if (!inList) { html += '<ul class="kb-bullets">'; inList = true; }
                    let content = text.replace(/^([-•*])\s+/, '');
                    html += `<li>${content}</li>`;
                } else {
                    if (inList) { html += '</ul>'; inList = false; }
                    html += `<p class="kb-para">${text}</p>`;
                }
            });

            if (inList) html += '</ul>';
            return html;
        }"""

# Use marker-based replacement
start_marker = "function formatKbAnswer(text) {"
end_marker = "function copyKbAnswer(btn) {"

# Find the function body
pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
# Re-read to ensure we have the latest
with open(filepath, 'r', encoding='utf-8') as f:
    latest_content = f.read()

# Replace using re.sub with DOTALL
updated_content = re.sub(pattern, new_js_func + "\n\n        " + end_marker, latest_content, flags=re.DOTALL)

if updated_content != latest_content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print("KB JS Engine updated successfully.")
else:
    print("Failed to replace JS function. Markers might have changed.")
