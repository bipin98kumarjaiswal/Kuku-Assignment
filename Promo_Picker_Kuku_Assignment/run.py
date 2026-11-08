"""Command line version. Example: python run.py --input scripts.zip --out outputs"""
import argparse
import csv
import json
from pathlib import Path
from parser import load_episodes
from finder import discover

CSV_FIELDS = ('rank', 'episode', 'start', 'end', 'duration_seconds', 'score',
              'hook_score', 'cliffhanger_score', 'clarity_score', 'emotion_score',
              'hook', 'cliffhanger', 'reason', 'warnings', 'method')


def export_csv(items, filepath):
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for i, row in enumerate(items, 1):
            writer.writerow({**{k: row.get(k, '') for k in CSV_FIELDS},
                             'rank': i,
                             'start': row['segments'][0]['start'],
                             'end': row['segments'][0]['end'],
                             'warnings': '; '.join(row.get('warnings', []))})


def run(input_path, output_folder='outputs', use_ai=False, ai_limit=15, api_key=None):
    out = Path(output_folder)
    out.mkdir(parents=True, exist_ok=True)
    episodes = load_episodes(input_path)
    all_candidates, ranked = discover(episodes)
    manifest = {
        'source_episode_count': len(episodes),
        'episode_numbers': [e.number for e in episodes],
        'total_script_seconds': round(sum(e.duration for e in episodes), 2),
        'events_parsed': sum(len(e.events) for e in episodes),
        'dialogue_events': sum(sum(ev.category == 'DIALOGUE' for ev in e.events) for e in episodes),
        'episodes_with_candidates': len({p['episode'] for p in all_candidates}),
        'candidates_kept': len(all_candidates),
        'ranked_count': len(ranked),
        'mode': 'offline_rules',
        'note': 'All timestamps derived from input screenplay files. Scores are heuristic estimates, not measured ad performance.'
    }
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (out/'all_candidates.json').write_text(json.dumps(all_candidates, indent=2, ensure_ascii=False), encoding='utf-8')
    (out/'ranked_promos.json').write_text(json.dumps(ranked, indent=2, ensure_ascii=False), encoding='utf-8')
    export_csv(ranked, out/'ranked_promos.csv')
    errors=[]
    if use_ai:
        from ai_rerank import rerank_candidates
        ai_ranked, errors = rerank_candidates(ranked, episodes, api_key=api_key, limit=ai_limit)
        (out/'ai_ranked_promos.json').write_text(json.dumps(ai_ranked, indent=2, ensure_ascii=False), encoding='utf-8')
        (out/'ai_errors.json').write_text(json.dumps(errors, indent=2), encoding='utf-8')
        export_csv(ai_ranked, out/'ai_ranked_promos.csv')
    return manifest, all_candidates, ranked, errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find promo suggestions from screenplay txt/zip/folder')
    parser.add_argument('--input', required=True, help='ZIP, directory of TXT, or individual TXT')
    parser.add_argument('--out', default='outputs')
    parser.add_argument('--use-ai', action='store_true', help='Optional API-based reranking (requires GEMINI_API_KEY)')
    parser.add_argument('--ai-limit', type=int, default=15)
    args = parser.parse_args()
    result, candidates, promos, errors = run(args.input, args.out, args.use_ai, args.ai_limit)
    print(json.dumps(result, indent=2))
    print('Top 5 recommendations:')
    for p in promos[:5]:
        s = p['segments'][0]
        print(f"  #{p['rank']} episode {p['episode']:02d} {s['start']}-{s['end']} | {p['score']} / 100")
    if errors: print(f'AI errors: {len(errors)} (details in ai_errors.json)')
