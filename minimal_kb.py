
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update CSS to be more "Minimal" as requested
css_replacement = """        /* ═══════════ KB ANSWER FORMATTING ═══════════ */
        .kb-answer {
            font-size: 0.95rem;
            line-height: 1.6;
            color: var(--text-primary);
            font-family: inherit;
        }

        .kb-answer .kb-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 1.2rem 0 0.4rem 0;
            display: block;
        }

        .kb-answer .kb-step-title {
            font-weight: 700;
            color: var(--text-primary);
            margin: 1rem 0 0.2rem 0;
            display: block;
        }

        .kb-answer .kb-para {
            margin: 0.4rem 0;
        }

        .kb-answer .kb-bullet {
            margin: 0.3rem 0;
            padding-left: 1.2rem;
            position: relative;
        }

        .kb-answer .kb-bullet::before {
            content: "-";
            position: absolute;
            left: 0.2rem;
            font-weight: 700;
        }

        .kb-clue {
            color: #ff3b3b; /* Red as requested */
            font-weight: 700;
        }

        .text-brand-600 {
            color: var(--text-primary); /* No special color for bold, just keep it clean */
            font-weight: 700;
        }
    </style>"""

# Find the CSS block
css_start_marker = "/* ═══════════ KB ANSWER FORMATTING ═══════════ */"
css_end_marker = "</style>"
# We need to be careful with the markers

# 2. Update JS Function
js_replacement = r"""        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. NUCLEAR CLEANUP: Remove ALL asterisks and hash markers as requested
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/\*/g, '') // STRIP ALL ASTERISKS
                .replace(/^#+\s+/gm, '') // STRIP HASH HEADERS
                .trim();

            const lines = cleaned.split('\n');
            let html = '';
            
            lines.forEach(line => {
                let trimmed = line.trim();
                if (!trimmed) {
                    html += '<div style="height: 0.8rem;"></div>';
                    return;
                }

                // Detect Clues in quotes and wrap in red
                let processedText = trimmed
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>')
                    .replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                // Detect Numbered Steps (e.g., 1. Access...)
                if (/^\d+\./.test(trimmed)) {
                    html += `<span class="kb-step-title">${processedText}</span>`;
                }
                // Detect Dash Bullets
                else if (/^[-•]/.test(trimmed)) {
                    let content = processedText.replace(/^[-•]\s*/, '');
                    html += `<div class="kb-bullet">${content}</div>`;
                }
                // Detect Possible Section Titles (ends with colon or is short)
                else if (trimmed.endsWith(':') || 
                         /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|Summary|Post-Closing|Reconciliation|How to)/i.test(trimmed)) {
                    html += `<span class="kb-title">${processedText}</span>`;
                }
                // Regular Paragraph
                else {
                    html += `<p class="kb-para">${processedText}</p>`;
                }
            });

            return html;
        }"""

# Apply Replacements
# For CSS
import re
text = re.sub(re.escape(css_start_marker) + r".*?" + re.escape(css_end_marker), css_replacement, text, flags=re.DOTALL)

# For JS
js_start_marker = "function formatKbAnswer(text) {"
js_end_marker = "function copyKbAnswer(btn) {"
text = re.sub(re.escape(js_start_marker) + r".*?" + re.escape(js_end_marker), js_replacement + "\n\n        " + js_end_marker, text, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("KB Overhaul v5.0 applied (Minimalist & Zero-Star).")
