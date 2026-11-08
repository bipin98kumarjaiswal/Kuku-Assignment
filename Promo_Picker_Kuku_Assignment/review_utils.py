"""Keep LLM-reviewed and offline-only clips separate when displaying results.

Gemini-adjusted scores and offline scores have different calibration, so they
should not compete in a single ranked list unless all clips were reviewed.
"""


def separate_reviewed(baseline, review_results):
    lookup = {(x['episode'], x['start_seconds'], x['end_seconds']): x
              for x in review_results}
    reviewed, pending = [], []
    for candidate in baseline:
        key = (candidate['episode'], candidate['start_seconds'], candidate['end_seconds'])
        item = lookup.get(key, candidate)
        if 'ai_score' in item:
            reviewed.append(dict(item))
        else:
            pending.append(dict(item))

    reviewed.sort(key=lambda p: (-p['final_score'], p['baseline_rank']))
    pending.sort(key=lambda p: (-p['score'], p['baseline_rank']))

    for group, name in ((reviewed, 'gemini_reviewed'), (pending, 'offline_only')):
        for index, p in enumerate(group, 1):
            p['review_group'] = name
            p['rank_within_group'] = index
            p['rank'] = index  # rank only within this score group
    return reviewed, pending
