
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = "function formatKbAnswer(text) {"
end_marker = "function copyKbAnswer(btn) {"

start_pos = text.find(start_marker)
end_pos = text.find(end_marker)

if start_pos != -1 and end_pos != -1:
    new_func = r"""        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. CLEANUP (Keep newlines, just strip artifacts)
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/,\s*,/g, ',')
                .replace(/,\s*$/gm, '');

            // 2. STRUCTURAL ISOLATION: Inject double newlines before major sections
            // Ensure bullets have a space: "*Something" -> "* Something"
            cleaned = cleaned.replace(/^([-•*])([A-Za-z])/gm, '$1 $2');

            const sections = [
                'Prerequisites', 'Instructions', 'Step-by-step', 'Steps to', 
                'Troubleshooting', 'Note', 'What is', 'Conclusion', 'Summary', 
                'Post-Closing', 'Reconciliation', 'Warning', 'Tip', 'How to', 'Instructions for'
            ];
            const sectionRegex = new RegExp('([^\\n])\\s*(\\*?\\*?(?:' + sections.join('|') + '):?\\*?\\*?)', 'gi');
            cleaned = cleaned.replace(sectionRegex, '$1\n\n$2');
            
            // Isolate numbered and bullet items
            cleaned = cleaned.replace(/([^\\n])\\s*(\d+\.\s+)/g, '$1\n\n$2');
            cleaned = cleaned.replace(/([^\\n])\\s+([-•*])\\s+(?!\*)/g, '$1\n\n$2');

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

                // Detect Type
                let type = 'para';
                let match = null;

                const isCommonTitle = /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|What is|Conclusion|Summary|Post-Closing|Reconciliation|How to.*):?$/i.test(line.replace(/\*\*/g, ''));
                const isMarkdownHeader = line.match(/^###\s+/) || line.match(/^\*\*.*?\*\*:?$/) || (line.startsWith('**') && line.length < 80 && (line.endsWith('**') || line.endsWith('**:')));

                if (match = line.match(/^(\d+)\.\s*(.*)/)) {
                    type = 'numbered';
                } else if (match = line.match(/^([-•*])\s+(?!\*)(.*)/)) {
                    type = 'bullet';
                } else if (isMarkdownHeader || isCommonTitle) {
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
                let raw = block.content;
                let text = raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                // HIGHLIGHTING
                // 1. Clues (Quoted text in red color)
                text = text.replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>');
                text = text.replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');
                
                // 2. Bold (Brand blue)
                text = text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-brand-600">$1</strong>');

                if (block.type === 'header') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let headerText = text.replace(/^(#{1,3}\s*|\*\*)/, '').replace(/(\*\*|:)$/, '').trim();
                    html += `<h4 class="kb-header">${headerText}</h4>`;
                } else if (block.type === 'numbered') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let num = block.match[1];
                    let content = text.replace(/^\d+\.\s*/, '');
                    html += `<div class="kb-numbered"><span class="kb-num">${num}.</span><div class="kb-item-content">${content}</div></div>`;
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
    
    new_content = text[:start_pos] + new_func + "\n\n        " + text[end_pos:]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("KB Final Overhaul applied.")
else:
    print(f"Markers not found. start={start_pos}, end={end_pos}")
