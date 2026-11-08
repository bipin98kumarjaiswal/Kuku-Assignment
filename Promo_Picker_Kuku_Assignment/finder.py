"""Generate, validate, de-duplicate and rank real timestamped promo candidates."""
from collections import defaultdict
from parser import stamp
from scoring import hook_value, cliff_value, score_candidate

MIN_LENGTH = 20.0
MAX_LENGTH = 60.0


def overlap_ratio(a, b):
    if a['episode'] != b['episode']: return 0.0
    common = max(0., min(a['end_seconds'], b['end_seconds']) - max(a['start_seconds'], b['start_seconds']))
    union = max(a['end_seconds'], b['end_seconds']) - min(a['start_seconds'], b['start_seconds'])
    return common / union if union else 0


def find_candidates(episode, max_candidates=8):
    events = episode.events
    useful = [e for e in events if e.category in ('DIALOGUE', 'ACTION')]
    beginnings = sorted(useful, key=hook_value, reverse=True)
    # Use a mix of strong hooks and early story beats. Evaluate at most 35 starts
    # per episode to keep the baseline fast even with large input packs.
    starts = sorted(set(round(e.start, 2) for e in beginnings[:35]))
    possible_ends = sorted(set(round(e.end, 2) for e in useful))
    # Prefer cut points at the END of a line or action. No cut mid-dialogue.
    generated = []
    seen = set()
    for start in starts:
        options = [t for t in possible_ends if MIN_LENGTH <= t-start <= MAX_LENGTH]
        if not options:
            continue
        # Include a broad set of candidate endings, because a clean cliffhanger
        # is not necessarily 30/45/60 seconds after the hook.
        for end in options:
            key = (start, end)
            if key in seen: continue
            seen.add(key)
            metrics = score_candidate(events, start, end)
            if metrics['dialogue_count'] < 2:
                continue
            item = {
                'episode': episode.number,
                'segments': [{'episode': episode.number, 'start': stamp(start), 'end': stamp(end)}],
                'start_seconds': start,
                'end_seconds': end,
                'duration_seconds': round(end-start, 2),
                'method': 'offline_rules',
                **metrics,
            }
            generated.append(item)
    generated.sort(key=lambda x: (-x['score'], -x['hook_score'], -x['cliffhanger_score'], x['start_seconds']))
    picked = []
    for item in generated:
        if any(overlap_ratio(item, prev) > .55 or (abs(item['start_seconds'] - prev['start_seconds']) < 3 and overlap_ratio(item, prev) > .20) or (abs(item['end_seconds'] - prev['end_seconds']) < 3 and overlap_ratio(item, prev) > .35) for prev in picked):
            continue
        picked.append(item)
        if len(picked) >= max_candidates:
            break
    return picked


def discover(episodes, max_per_episode=6, show_top=20):
    all_candidates = []
    for ep in episodes:
        all_candidates.extend(find_candidates(ep, max_per_episode))
    all_candidates.sort(key=lambda x: (-x['score'], x['episode'], x['start_seconds']))
    for i, cand in enumerate(all_candidates, 1):
        cand['baseline_rank'] = i
    # Keep high-ranked global promos without letting a single episode dominate.
    selected = []
    per_episode = defaultdict(int)
    for candidate in all_candidates:
        if per_episode[candidate['episode']] >= 2:
            continue
        selected.append(dict(candidate))
        per_episode[candidate['episode']] += 1
        if len(selected) >= show_top: break
    for i, cand in enumerate(selected, 1):
        cand['rank'] = i
    return all_candidates, selected
