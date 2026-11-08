"""Small Streamlit dashboard. Run: streamlit run app.py"""
import json
import hashlib
import csv
import io
import os
import tempfile
from pathlib import Path

import streamlit as st
from parser import load_episodes, stamp
from finder import discover
from run import CSV_FIELDS
from review_utils import separate_reviewed

st.set_page_config(page_title='Promo Picker - Kuku assignment', page_icon='🎬', layout='wide')
st.title('🎬 Promo Picker')
st.caption('Student prototype | Finds 20-60 second promo suggestions from timestamped screenplay files')
st.info('This works offline using simple scoring rules. For stronger story judgment, you can optionally enable a Gemini review. Final clips still need an editor to check them.')

with st.sidebar:
    st.header('Settings')
    result_count = st.slider('How many promos?', 5, 30, 20, 5)
    use_ai = st.checkbox('Also use Gemini to review top picks', value=False)
    key = st.text_input('Gemini API key (optional)', type='password') if use_ai else ''
    review_count = st.selectbox('Promos to review with Gemini', [1, 5, 15, 20], index=0) if use_ai else 0
    st.caption('Your key is not saved by the app. It is sent directly to the Gemini API only when you enable this option.')
    st.caption('Input: episode script ZIP, TXT, or folder of episode files. Output: timestamps from the original script.')

uploaded = st.file_uploader('Upload a screenplay ZIP or TXT file', type=['zip', 'txt'])
if uploaded is None:
    st.write('Upload the provided screenplay ZIP, or try any similarly formatted script. The sample screenplay files are **not** included in the public repository.')
    st.stop()

upload_id = hashlib.sha256(uploaded.getvalue()).hexdigest()
if st.session_state.get('upload_id') != upload_id:
    st.session_state['upload_id'] = upload_id
    st.session_state.pop('ai_results', None)
    st.session_state.pop('ai_errors', None)

# If settings change, don't show results from a previous Gemini run.
review_signature = (upload_id, result_count, review_count,
                    hashlib.sha256(key.encode('utf-8')).hexdigest() if key else None)
if st.session_state.get('review_signature') != review_signature:
    st.session_state['review_signature'] = review_signature
    st.session_state.pop('ai_results', None)
    st.session_state.pop('ai_errors', None)

suffix = Path(uploaded.name).suffix.lower()
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / f'input{suffix}'
    path.write_bytes(uploaded.getvalue())
    try:
        episodes = load_episodes(path)
        all_candidates, ranked = discover(episodes, max_per_episode=6, show_top=result_count)
    except Exception as exc:
        st.error(f'Could not read this screenplay: {exc}')
        st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric('Episodes read', len(episodes))
col2.metric('Script events', sum(len(ep.events) for ep in episodes))
col3.metric('Candidates kept', len(all_candidates))
col4.metric('Promos shown', len(ranked))

if use_ai:
    if not key and not os.getenv('GEMINI_API_KEY'):
        st.warning('No Gemini API key entered. Showing offline results.')
    elif st.button('Review top promos with Gemini', type='primary'):
        from ai_rerank import rerank_candidates
        with st.spinner('Reviewing selected clips (this sends excerpts to Gemini)...'):
            updated, errors = rerank_candidates(ranked, episodes, api_key=key,
                                                limit=min(len(ranked), review_count))
        st.session_state['ai_results'] = updated
        st.session_state['ai_errors'] = errors

# Show the status on every rerun, not just during the button click.
showing = st.session_state.get('ai_results') if use_ai else None
errors = st.session_state.get('ai_errors', []) if use_ai else []
if showing:
    successful = sum('ai_score' in item for item in showing)
    if successful:
        st.success(f'Gemini successfully reviewed {successful} promo(s). '
                   'Updated scores are displayed below.')
    if errors:
        st.warning(f'{len(errors)} Gemini call(s) failed. Those clips keep offline scores.')
        with st.expander('Show Gemini API errors', expanded=True):
            for err in errors[:3]:
                st.error(f"Episode {err['episode']}: {err['error']}")

    # Compare Gemini-reviewed clips only with other Gemini-reviewed clips.
    # Keep the offline-only clips separate rather than mixing score scales.
    reviewed_picks, pending_picks = separate_reviewed(ranked, showing)
    ranked = reviewed_picks + pending_picks
else:
    reviewed_picks, pending_picks = [], []

st.subheader('Ranked promo suggestions')
st.caption('Scores measure SCRIPT-based promise, not real social-media performance.')
if reviewed_picks:
    st.info(f'{len(reviewed_picks)} clips were reviewed by Gemini and are ranked among themselves. '
            f'{len(pending_picks)} are offline-only and shown AFTER the reviewed group. '
            'Their scores use a different scale and are not directly comparable.')

for i, item in enumerate(ranked, 1):
    if reviewed_picks and i == 1:
        st.markdown('### Gemini-reviewed clips')
    if reviewed_picks and i == len(reviewed_picks) + 1:
        st.markdown('### Not reviewed by Gemini - offline candidates')
        st.caption('These clips were not reviewed by Gemini; their scores should not be compared to adjusted scores.')
    group_label = ('Gemini' if item.get('review_group') == 'gemini_reviewed'
                   else 'Offline')
    group_rank = item.get('rank_within_group', i)
    s = item['segments'][0]
    rating = item.get('final_score', item['score'])
    with st.expander(f"{group_label} #{group_rank}  |  Episode {item['episode']}  |  {s['start']} to {s['end']}  |  {rating}/100", expanded=(i==1)):
        a, b, c, d = st.columns(4)
        if 'ai_score' in item:
            st.caption(f"Gemini reviewed | Offline: {item['score']}/100 | "
                       f"AI: {item['ai_score']}/100 | Final: {item['final_score']}/100")
        a.metric('Clip length', f"{item['duration_seconds']:.1f}s")
        b.metric('Hook', f"{item['hook_score']:.0f}/100")
        c.metric('Cliffhanger', f"{item['cliffhanger_score']:.0f}/100")
        d.metric('Clarity', f"{item['clarity_score']:.0f}/100")
        st.markdown('**Opening hook**')
        st.write(item['hook'])
        st.markdown('**Ending / possible cliffhanger**')
        st.write(item['cliffhanger'])
        st.markdown('**Why it was selected**')
        st.write(item.get('ai_reason', item['reason']))
        if item.get('ai_weakness'):
            st.warning('AI concern: ' + item['ai_weakness'])
        for warning in item.get('warnings', []):
            st.warning(warning)
        ep = next(e for e in episodes if e.number == item['episode'])
        if st.checkbox('Show dialogue / actions from this clip', key=f'clip_{i}'):
            rows = [{'start': stamp(e.start), 'end': stamp(e.end), 'speaker': e.speaker or e.category,
                     'text': e.text} for e in ep.events if e.category in ('DIALOGUE','ACTION') and e.end>item['start_seconds'] and e.start<item['end_seconds']]
            st.dataframe(rows, hide_index=True, use_container_width=True)

st.subheader('Export')
st.download_button('Download ranked promos (JSON)', json.dumps(ranked, indent=2, ensure_ascii=False),
                   file_name='ranked_promos.json', mime='application/json')
# Keep the Gemini score and explanation in the CSV too (if AI was used).
with io.StringIO() as csv_buffer:
    columns = list(CSV_FIELDS) + ['review_group', 'rank_within_group', 'final_score', 'ai_score', 'ai_reason', 'ai_weakness']
    writer = csv.DictWriter(csv_buffer, fieldnames=columns)
    writer.writeheader()
    for i, item in enumerate(ranked, 1):
        row = {name: item.get(name, '') for name in columns}
        row.update(rank=item.get('rank', i), start=item['segments'][0]['start'],
                   end=item['segments'][0]['end'],
                   warnings='; '.join(item.get('warnings', [])))
        writer.writerow(row)
    csv_bytes = csv_buffer.getvalue().encode('utf-8-sig')
st.download_button('Download ranked promos (CSV)', csv_bytes, file_name='ranked_promos.csv', mime='text/csv')
st.caption('Limits: no video analysed, and Gemini reviews still need human judgement. The tool outputs continuous clips only, not multi-episode edits.')
