"""Mechanical checks only. These cannot prove a promo is engaging."""
import json
import sys
from pathlib import Path
from parser import load_episodes, seconds


def check(input_path, ranked_path):
    episodes = {e.number: e for e in load_episodes(input_path)}
    ranked = json.loads(Path(ranked_path).read_text(encoding='utf-8'))
    results = {'checked': len(ranked), 'passes': 0, 'failures': []}
    for rank, p in enumerate(ranked, 1):
        problems=[]
        segments=p['segments']
        length=0
        for seg in segments:
            ep=episodes.get(seg['episode'])
            if not ep:
                problems.append('Missing episode')
                continue
            start,end=seconds(seg['start']),seconds(seg['end'])
            length += end-start
            if not (0 <= start < end <= ep.duration+0.01): problems.append('Outside episode time')
            if not any(abs(e.start-start) < .011 for e in ep.events if e.category in ('DIALOGUE','ACTION')):
                problems.append('Not on event start boundary')
            if not any(abs(e.end-end) < .011 for e in ep.events if e.category in ('DIALOGUE','ACTION')):
                problems.append('Not on event end boundary')
        if not 20 <= length <= 60: problems.append('Clip duration outside 20-60 seconds')
        if problems:
            results['failures'].append({'rank': rank, 'episode': p.get('episode'), 'issues': problems})
        else:
            results['passes']+=1
    return results

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('Usage: python quality_check.py scripts.zip outputs/ranked_promos.json')
    print(json.dumps(check(sys.argv[1],sys.argv[2]), indent=2))
