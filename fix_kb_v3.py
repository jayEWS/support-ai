
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

            // 1. Initial Sanitization
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/,\s*,/g, ',')
                .replace(/\* \* \* \*/g, '') 
                .replace(/,\s*$/gm, '');

            // 2. Structural Isolation (Ensuring everything starts on a new line)
            // Inject double newlines before major sections
            const sectionKeywords = [
                'Prerequisites', 'Instructions', 'Step-by-step', 'Steps to', 
                'Troubleshooting', 'Note', 'What is', 'Conclusion', 'Summary', 
                'Post-Closing', 'Reconciliation', 'Warning', 'Tip', 'How to'
            ];
            const sectionRegex = new RegExp('([^\\n])\\s*(\\*?\\*?(?:' + sectionKeywords.join('|') + '):?\\*?\\*?)', 'gi');
            cleaned = cleaned.replace(sectionRegex, '$1\n\n$2');
            
            // Isolate list items
            cleaned = cleaned.replace(/([^\\n])\s+(\d+\.\s+)/g, '$1\n\n$2');
            cleaned = cleaned.replace(/([^\\n])\s+([-•*])\s+(?!\*)/g, '$1\n\n$2');

            // 3. Line-by-Line Parsing
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

                // Clean the line of potential formatting stars just for detection
                const pureLine = line.replace(/^\*+\s*/, '').replace(/\*+$/, '').replace(/^\d+\.\s*/, '').trim();
                
                const isCommonTitle = /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|What is|Conclusion|Summary|Post-Closing|Reconciliation|How to.*|Instructions for.*):?$/i.test(pureLine);
                const isShortBold = line.startsWith('**') && line.length < 80 && (line.endsWith('**') || line.endsWith('**:'));
                
                if (match = line.match(/^(\d+)\.\s*(.*)/)) {
                    type = 'numbered';
                } else if (match = line.match(/^([-•*])\s+(?!\*)(.*)/)) {
                    type = 'bullet';
                } else if (isCommonTitle || isShortBold || line.startsWith('###')) {
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

            // 4. RENDERING & CLEANUP
            let html = '';
            let inList = false;

            blocks.forEach(block => {
                let raw = block.content;
                
                // MANDATORY: Remove all * and ### characters used for formatting
                // We keep * only if it's trapped between letters (e.g. math or wildcard, unlikely here)
                // But generally, for AI answers, stars are formatting.
                let content = raw
                    .replace(/^###\s*/, '')
                    .replace(/\*\*/g, '') // remove double stars
                    .replace(/(^|[^\w])\*([^\w]|$)/g, '$1$2') // remove single stars not in words
                    .trim();

                let text = content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                // RED HIGHLIGHTING for "Quotes" (Clues)
                text = text.replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>');
                text = text.replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                if (block.type === 'header') {
                    if (inList) { html += '</ul>'; inList = false; }
                    html += `<h4 class="kb-header">${text.replace(/:$/, '')}</h4>`;
                } else if (block.type === 'numbered') {
                    if (inList) { html += '</ul>'; inList = false; }
                    let num = block.match[1];
                    let rem = text.replace(/^\d+\.\s*/, '');
                    html += `<div class="kb-numbered"><span class="kb-num">${num}.</span><div class="kb-item-content">${rem}</div></div>`;
                } else if (block.type === 'bullet') {
                    if (!inList) { html += '<ul class="kb-bullets">'; inList = true; }
                    let rem = text.replace(/^([-•*])\s+/, '');
                    html += `<li>${rem}</li>`;
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
    print("KB Formatting Engine v3.0 applied (Aggressive Marker Removal).")
else:
    print(f"Markers not found. start={start_pos}, end={end_pos}")
