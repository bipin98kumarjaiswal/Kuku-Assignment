"""Make a read-only offline HTML preview from the ranked JSON file."""
import html
import json
from pathlib import Path

def main():
    base=Path(__file__).parent
    promos=json.loads((base/'outputs'/'ranked_promos.json').read_text('utf-8'))
    sections=[]
    for p in promos:
        esc=lambda s: html.escape(str(s))
        seg=p['segments'][0]
        warnings='; '.join(p.get('warnings',[])) or 'None flagged by rules'
        sections.append(f'''<details {'open' if p['rank']==1 else ''}>
          <summary>#{p['rank']} - Episode {p['episode']} - {seg['start']} to {seg['end']} - {p['score']}/100</summary>
          <div class="inner"><p><b>Duration:</b> {p['duration_seconds']} seconds</p>
          <p><b>Hook:</b> {esc(p['hook'])}</p><p><b>Cut on:</b> {esc(p['cliffhanger'])}</p>
          <p><b>Why:</b> {esc(p['reason'])}</p><p><b>Risks:</b> {esc(warnings)}</p>
          <small>Hook {p['hook_score']} | Cliffhanger {p['cliffhanger_score']} | Clarity {p['clarity_score']} | Emotion {p['emotion_score']}</small></div>
        </details>''')
    doc='''<!doctype html><html lang="en"><head><meta charset="UTF-8"><title>Promo Picker - Offline Results</title>
    <meta name="viewport" content="width=device-width,initial-scale=1"><style>
    body{font:16px/1.55 system-ui,Arial,sans-serif;max-width:880px;margin:36px auto;padding:0 20px;background:#f5f6f9;color:#19212d}
    h1{font-size:29px;margin-bottom:0} .sub{color:#586277;margin:4px 0 24px}
    details{border:1px solid #dee3ea;border-radius:10px;background:white;margin-bottom:11px;padding:14px 18px}
    summary{cursor:pointer;font-weight:650} .inner{border-top:1px solid #eee;margin-top:12px;padding-top:7px}
    .note{padding:13px 16px;background:#fff3d9;border-radius:9px;margin:22px 0} small{color:#586277}
    </style></head><body><h1>Promo Picker</h1><p class="sub">Offline example: 50 episodes reviewed by the parser</p>
    <div class="note">These are rule-based recommendations from screenplay text, not viewed video. Human approval required. The original scripts remain confidential.</div>
    ''' + '\n'.join(sections) + '</body></html>'
    (base/'results_preview.html').write_text(doc,encoding='utf-8')

if __name__ == '__main__': main()
