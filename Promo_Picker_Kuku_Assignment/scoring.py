"""Small explainable *heuristic baseline*, not a trained AI model.

These weights are our own design assumptions. An optional LLM judge can re-rank
candidates if the user has an API key (see ai_rerank.py).
"""
import re

# Simple keyword lists: easy to read and extend when reviewing real failures.
SHOCK = {'betray', 'traitor', 'secret', 'poison', 'dead', 'murder', 'kill', 'blood',
         'duke', 'marry', 'husband', 'wife', 'pregnant', 'arrest', 'guilty', 'not anymore',
         'never', 'liar', 'father', 'mother', 'sister', 'shame', 'destroy', 'torture',
         'prison', 'death', 'alive', 'lost', 'revenge', 'who', 'why', 'truth', 'confess'}
DANGER = {'blood', 'knife', 'poison', 'death', 'die', 'dead', 'kill', 'murder', 'gun',
          'arrest', 'guard', 'threat', 'scream', 'gasp', 'slap', 'punch', 'attack',
          'collapsed', 'betray', 'execution', 'trial', 'treason', 'escape'}
CLUES = {'who', 'why', 'what', 'how', 'where', 'which', 'secret', 'truth', 'wait', 'but',
         'unless', 'if', 'because', 'actually', 'real', 'not', 'name', 'is', 'was',
         'someone', 'revealed', 'know', 'tell', 'prove', 'lied', 'traitor'}
RESOLUTION = {'forgive', 'together forever', 'finally safe', 'it is over', 'i love you',
              'we won', 'thank you', 'happily', 'everything is fine'}
EMOTION = {'cry', 'tear', 'trembl', 'furious', 'heart', 'fear', 'love', 'hate', 'sobb',
           'shocked', 'betray', 'plead', 'desperate', 'angry', 'gasp', 'devastat',
           'embrace', 'kiss', 'cruel', 'panic', 'threat', 'beg', 'terrified'}


def tokens(s):
    return set(re.findall(r"[a-z]+", s.lower()))


def number_of_keywords(text, lexicon):
    t = text.lower()
    ws = tokens(t)
    return sum(1 for term in lexicon if (term in t if ' ' in term else term in ws or any(w.startswith(term) and len(term) >= 4 for w in ws)))


def hook_value(e):
    t = e.text.lower().strip('"\' ')
    score = 0.0
    score += min(0.55, 0.12 * number_of_keywords(t, SHOCK))
    score += min(0.25, 0.12 * number_of_keywords(t, DANGER))
    if e.category == 'DIALOGUE':
        score += 0.15
        if '?' in t or '!' in t: score += 0.12
        if any(t.startswith(x) for x in ('"you', '"i ', '"who', '"why', '"what', '"stop', '"no ', '"don\'t', '"tell', '"how')): score += 0.08
    if e.category == 'ACTION' and number_of_keywords(t, DANGER) > 0: score += 0.15
    if e.category == 'CAMERA': score -= 0.2
    if len(t) < 9: score -= 0.05
    return max(0.0, min(1.0, score))


def cliff_value(e):
    t = e.text.lower()
    v = 0.10
    if e.category == 'DIALOGUE':
        v += .18
        if '?' in t: v += .38
        if '...' in t or t.endswith('—"') or t.endswith('-"'): v += .18
        v += min(.3, .1 * number_of_keywords(t, CLUES))
        if any(x in t for x in RESOLUTION): v -= .26
    elif e.category == 'ACTION':
        v += min(.42, .11 * number_of_keywords(t, DANGER))
        if 'revea' in t or 'sudden' in t or 'horror' in t: v += .12
    else:
        v += min(.15, .08 * number_of_keywords(t, DANGER))
    return max(.0, min(1., v))


def emotional_value(events):
    text = ' '.join(x.text for x in events if x.category in ('DIALOGUE', 'ACTION'))
    return min(1., .15 + number_of_keywords(text, EMOTION) * .13)


def clarity_value(events):
    dialogue = [e for e in events if e.category == 'DIALOGUE']
    speakers = {e.speaker for e in dialogue}
    # Proxy, not a claim that a stranger can actually understand the clip.
    v = .2 + min(.28, len(dialogue) * .04) + min(.25, len(speakers) * .09)
    speech = ' '.join(e.text.lower() for e in dialogue)
    if any(word in speech for word in ('husband', 'wife', 'mother', 'sister', 'father', 'marry', 'wedding', 'duke', 'prison', 'death', 'poison', 'murder', 'traitor', 'judge', 'arrest')):
        v += .14
    if len(dialogue) < 3: v -= .18
    return max(0., min(1., v))


def score_candidate(events, start, end):
    included = [e for e in events if e.end > start and e.start < end]
    intro = [e for e in included if e.start < start + 3.0 and e.category in ('DIALOGUE', 'ACTION')]
    endings = [e for e in included if e.end >= end - 2.5 and e.end <= end + .05 and e.category in ('DIALOGUE', 'ACTION')]
    h_event = max(intro, key=hook_value) if intro else None
    c_event = max(endings, key=cliff_value) if endings else None
    hook = hook_value(h_event) if h_event else 0.0
    cliff = cliff_value(c_event) if c_event else .0
    clarity = clarity_value(included)
    emotion = emotional_value(included)
    # Penalties for the editor: empty openings, abrupt cutting through speech,
    # weak endings, and repeating generic emotional speeches.
    penalties = 0.
    if not h_event: penalties += .18
    if not c_event: penalties += .15
    if hook < .22: penalties += .06
    if cliff < .28: penalties += .08
    if end - start < 27: penalties += .02
    score = max(0, min(1, .30*hook + .30*cliff + .25*clarity + .15*emotion - penalties))
    return {
        'score': round(score*100, 1),
        'hook_score': round(hook*100, 1),
        'cliffhanger_score': round(cliff*100, 1),
        'clarity_score': round(clarity*100, 1),
        'emotion_score': round(emotion*100, 1),
        'hook': (h_event.text if h_event else 'No clear hook in the opening 3 seconds.'),
        'cliffhanger': (c_event.text if c_event else 'No clear unresolved line near the end.'),
        'hook_event_type': (h_event.category if h_event else None),
        'cliffhanger_event_type': (c_event.category if c_event else None),
        'hook_event_start': (h_event.start if h_event else None),
        'cliffhanger_event_end': (c_event.end if c_event else None),
        'dialogue_count': len([e for e in included if e.category == 'DIALOGUE']),
        'speaker_count': len({e.speaker for e in included if e.category == 'DIALOGUE'}),
        'reason': (
            'Starts with ' + ('a conflict or revelation' if h_event else 'a slower moment') +
            ' and ends ' + ('on an unanswered question' if c_event and '?' in c_event.text else 'at a tense beat') +
            f' after an exchange involving {len({e.speaker for e in included if e.category == "DIALOGUE"})} speaker(s).' +
            ' Editor should confirm that it makes sense without earlier episodes.'
        ),
        'warnings': [x for ok,x in [
            (hook < .30, 'Hook may not stop a viewer in the first 3 seconds.'),
            (cliff < .40, 'Ending may feel resolved or not suspenseful.'),
            (clarity < .50, 'Story may need context from earlier scenes.'),
        ] if ok],
    }
