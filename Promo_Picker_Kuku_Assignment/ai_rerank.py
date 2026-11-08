"""Optional Gemini judge. No API call or charge unless explicitly enabled.

The baseline works offline; this step gives us narrative judgment (with limited
context) that simple keywords cannot provide. It NEVER generates timestamps.
"""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DEFAULT_MODEL = 'gemini-3.5-flash-lite'


def _call_gemini(prompt, key, model):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'temperature': .2}
    }
    req = Request(url, data=json.dumps(payload).encode('utf-8'), headers={
        'x-goog-api-key': key, 'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=45) as response:
        data = json.load(response)
    txt = ''.join(part.get('text', '') for part in data['candidates'][0]['content']['parts'])
    return json.loads(txt)


def rerank_candidates(candidates, episodes, *, api_key=None, model=DEFAULT_MODEL, limit=15):
    """Only score top N offline picks; keep original cuts if LLM disagrees.

    Returns (ranked list, errors). Caller should keep the unmodified baseline
    in a separate file for reproducible comparison.
    """
    key = api_key or os.getenv('GEMINI_API_KEY', '')
    if not key:
        raise ValueError('GEMINI_API_KEY is missing. Offline mode needs no key.')
    epmap = {e.number: e for e in episodes}
    updated = []
    errors = []
    for item in candidates[:limit]:
        ep = epmap[item['episode']]
        inside = [e for e in ep.events if e.end > item['start_seconds'] and e.start < item['end_seconds'] and e.category in ('DIALOGUE','ACTION')]
        lines = '\n'.join(f"{e.start:.2f}-{e.end:.2f} {e.speaker or e.category}: {e.text[:280]}" for e in inside[:55])
        prompt = f'''You are helping a student prototype a short-drama promo picker.
Assess ONLY this continuous {item['duration_seconds']}-second clip from Episode {ep.number}.
An Instagram viewer has never seen the show. A promo needs a hook in the FIRST
3 seconds, enough context for a stranger, and an unresolved cliffhanger at the END.
Score hook, cliffhanger, standalone_clarity, and emotional_impact from 0 to 10.
Don't reward the line that comes much later as the opening hook. Don't pretend
an already-resolved plot is a cliffhanger. Be critical. Do not invent events.
Return JSON exactly: {{"hook":integer,"cliffhanger":integer,
"standalone_clarity":integer,"emotional_impact":integer,
"why":string,"weakness":string}}.
Episode premise (for your own reference only; the viewer has not read this):
{ep.logline[:500]}
Clip excerpt in chronological order (timestamps in seconds):
{lines}'''
        try:
            judgement = _call_gemini(prompt, key, model)
            vals = [max(0, min(10, int(judgement[k]))) for k in
                    ('hook','cliffhanger','standalone_clarity','emotional_impact')]
            llm_score = round(3*vals[0] + 3*vals[1] + 2.5*vals[2] + 1.5*vals[3], 1)
            revised = dict(item)
            revised.update({'method': f'gemini_review:{model}', 'ai_score': llm_score,
                            'ai_reason': str(judgement.get('why',''))[:250],
                            'ai_weakness': str(judgement.get('weakness',''))[:250],
                            'ai_breakdown': dict(zip(('hook','cliffhanger','standalone_clarity','emotional_impact'), vals))})
            # Mix human-readable baseline and model judgment rather than blindly overwriting.
            revised['final_score'] = round(.35*item['score'] + .65*llm_score, 1)
            updated.append(revised)
        except (HTTPError, URLError, KeyError, ValueError, TypeError, IndexError) as ex:
            errors.append({'episode': item['episode'], 'start': item['segments'][0]['start'], 'error': str(ex)[:170]})
            revised = dict(item)
            revised['final_score'] = item['score']
            revised['method'] = 'offline_rules (LLM failed)'
            updated.append(revised)
    updated.sort(key=lambda x: (-x['final_score'], x['episode']))
    for i, cand in enumerate(updated, 1):
        cand['rank'] = i
    return updated, errors
