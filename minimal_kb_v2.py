
import os

filepath = r"d:\Project\support-portal-edgeworks\templates\index.html"

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update CSS
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
            margin: 1.25rem 0 0.4rem 0;
            display: block;
        }

        .kb-answer .kb-step-title {
            font-weight: 700;
            color: var(--text-primary);
            margin: 1.2rem 0 0.3rem 0;
            display: block;
        }

        .kb-answer .kb-para {
            margin: 0.5rem 0;
        }

        .kb-answer .kb-bullet {
            margin: 0.35rem 0;
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
            color: var(--text-primary);
            font-weight: 700;
        }
    </style>"""

css_start = "/* ═══════════ KB ANSWER FORMATTING ═══════════ */"
css_end = "</style>"
s_idx = text.find(css_start)
e_idx = text.find(css_end, s_idx)
if s_idx != -1 and e_idx != -1:
    text = text[:s_idx] + css_replacement + text[e_idx + len(css_end):]

# 2. Update JS Function
js_replacement = r"""        function formatKbAnswer(text) {
            if (!text) return '';

            // 1. CLEANUP: Strip AI markers and UNWANTED ASTERISKS
            let cleaned = text
                .replace(/Source\s*\d+/gi, '')
                .replace(/Source\s*:\s*[^\n\r]*/gi, '')
                .replace(/^\s*\*?\*?Sources?:?\*?\*?\s*.*$/gim, '')
                .replace(/[\w_-]+\.(txt|pdf|docx|md|csv)/gi, '')
                .replace(/\(\s*[,\s]*\s*\)/g, '')
                .replace(/\[\s*[,\s]*\s*\]/g, '')
                .replace(/\*/g, '') // STRIP ALL ASTERISKS as requested
                .replace(/^#+\s+/gm, '') // STRIP HASH MARKERS
                .trim();

            const lines = cleaned.split('\n');
            let html = '';
            
            lines.forEach(line => {
                let trimmed = line.trim();
                if (!trimmed) {
                    html += '<div style="height: 0.6rem;"></div>';
                    return;
                }

                // Escape HTML
                let safeText = trimmed
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');

                // Highlight Clues in quotes
                safeText = safeText.replace(/("|&quot;)(.*?)("|&quot;)/g, '<span class="kb-clue">$1$2$3</span>');
                safeText = safeText.replace(/(')(.*?)(')/g, '<span class="kb-clue">$1$2$3</span>');

                // Detect Step Headers (1. Access...)
                if (/^\d+\./.test(trimmed)) {
                    html += `<span class="kb-step-title">${safeText}</span>`;
                }
                // Detect Bullets (- or •)
                else if (/^[-•]/.test(trimmed)) {
                    let content = safeText.replace(/^[-•]\s*/, '');
                    html += `<div class="kb-bullet">${content}</div>`;
                }
                // Detect Section Titles
                else if (trimmed.endsWith(':') || 
                         /^(Prerequisites|Instructions|Step-by-step|Steps to|Troubleshooting|Note|Summary|Post-Closing|Reconciliation|How to)/i.test(trimmed)) {
                    html += `<span class="kb-title">${safeText}</span>`;
                }
                // Regular Paragraph
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

print("KB Overhaul v5.1 applied via string slicing.")
