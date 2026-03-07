
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# JS Function v7.0 - Precision Parsing for Minimalist Layout
js_replacement = r"""        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. Initial Cleanup
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/\* \* \* \*/g, '')
                .trim();

            // 2. Structural Isolation (Force newlines where needed)
            const keywordList = ['Prerequisites', 'Instructions', 'Steps to', 'Troubleshooting', 'Note', 'Summary', 'Post-Closing', 'Reconciliation', 'Warning', 'How to', 'Conclusion'];
            keywordList.forEach(k => {
                const re = new RegExp('([^\\n])\\s*(\\**' + k + ':?\\**)', 'gi');
                cleaned = cleaned.replace(re, '$1\n\n$2');
            });
            cleaned = cleaned.replace(/([.!?])\s*(\d+\.\s+)/g, '$1\n\n$2');
            cleaned = cleaned.replace(/([.!?])\s+([-•*])\s+(?!\*)/g, '$1\n\n$2');

            // 3. NUCLEAR REMOVAL OF FORMATTING MARKERS
            cleaned = cleaned.replace(/\*/g, '');

            const lines = cleaned.split('\n');
            let html = '';
            
            lines.forEach(line => {
                let trimmed = line.trim();
                if (!trimmed) {
                    html += '<div style="height: 0.6rem;"></div>';
                    return;
                }

                // Escape and Highlight
                let safeText = trimmed
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>')
                    .replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                // BLOCK DETECTION
                // Numbered Step (1. Something)
                if (/^\d+\./.test(trimmed)) {
                    html += `<span class="kb-step-title">${safeText}</span>`;
                }
                // Bullet Point (- Something)
                else if (/^[-•]/.test(trimmed)) {
                    let content = safeText.replace(/^[-•]\s*/, '');
                    html += `<div class="kb-bullet">${content}</div>`;
                }
                // Header (Must end in colon AND be short, or be a specific section title)
                else if ((trimmed.endsWith(':') && trimmed.length < 60) || 
                         /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|Summary|Post-Closing|Reconciliation|How to.*):?$/i.test(trimmed)) {
                    html += `<span class="kb-title">${safeText}</span>`;
                }
                // Standard Paragraph
                else {
                    html += `<p class="kb-para">${safeText}</p>`;
                }
            });

            return html;
        }"""

js_start = "function formatKbAnswer(text) {"
js_end = "function copyKbAnswer(btn) {"
sj_idx = text.find(js_start)
ej_idx = text.find(js_end)
if sj_idx != -1 and ej_idx != -1:
    text = text[:sj_idx] + js_replacement + "\n\n        " + text[ej_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("KB Overhaul v7.0 applied (Precision Parsing).")
