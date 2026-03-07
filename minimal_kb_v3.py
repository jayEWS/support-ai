
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# JS Function v6.0 - Aggressive Newline Injection
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

            // 2. FORCE NEWLINES (Structural Isolation)
            // Keywords that should start a new section
            const sections = ['Prerequisites', 'Instructions', 'Steps to', 'Step-by-step', 'Troubleshooting', 'Note', 'Summary', 'Post-Closing', 'Reconciliation', 'Warning', 'Tip', 'How to', 'Conclusion'];
            sections.forEach(s => {
                const re = new RegExp('([^\\n])\\s*(\\**' + s + ':?\\**)', 'gi');
                cleaned = cleaned.replace(re, '$1\n\n$2');
            });

            // Force new line for Numbered Items (e.g., 1. 2.) if clumped
            cleaned = cleaned.replace(/([.!?])\s*(\d+\.\s+)/g, '$1\n\n$2');
            
            // Force new line for Bullet Items if clumped
            cleaned = cleaned.replace(/([.!?])\s+([-•*])\s+(?!\*)/g, '$1\n\n$2');

            // 3. NUCLEAR STAR REMOVAL
            // Strip ALL asterisks globally after we've used them for isolation
            cleaned = cleaned.replace(/\*/g, '');

            const lines = cleaned.split('\n');
            let html = '';
            
            lines.forEach(line => {
                let trimmed = line.trim();
                if (!trimmed) {
                    html += '<div style="height: 0.6rem;"></div>';
                    return;
                }

                // Clean the line leading artifacts again just in case
                let cleanLine = trimmed.replace(/^#+\s*/, '').trim();

                // Escape and Highlight
                let safeText = cleanLine
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>')
                    .replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                // Determine Block Type
                if (/^\d+\./.test(cleanLine)) {
                    html += `<span class="kb-step-title">${safeText}</span>`;
                }
                else if (/^[-•]/.test(cleanLine)) {
                    let content = safeText.replace(/^[-•]\s*/, '');
                    html += `<div class="kb-bullet">${content}</div>`;
                }
                else if (cleanLine.endsWith(':') || 
                         /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|Summary|Post-Closing|Reconciliation|How to)/i.test(cleanLine)) {
                    html += `<span class="kb-title">${safeText}</span>`;
                }
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

print("KB Overhaul v6.0 applied (Aggressive Newlines).")
