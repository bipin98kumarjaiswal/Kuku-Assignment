# Promo Picker - Kuku AI Generalist Assignment (Problem 1)

This is my small project to help an editor pick promo moments from episode scripts. It looks for **20-60-second continuous clips**, ranks them, and shows the hook, possible cliffhanger, and exact timestamps.

I built it so **it works without any API key**. The offline score is a simple rule-based baseline, **not** a trained model. There is also an optional Gemini evaluation for people who want to use an LLM to re-check the results. The original baseline outputs are preserved, and a separate local Streamlit run reviewed 15 top candidates using Gemini.

## Run in 3 steps

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload the original Kuku screenplay ZIP. This repository **does not include** the scripts, because they are Kuku's confidential material.

To generate all raw outputs without Streamlit or internet:

```bash
python run.py --input "path/to/the-provided-scripts.zip" --out outputs
```

Optional: if you get a Gemini API key and want an AI review, run:

```bash
# Set GEMINI_API_KEY in your terminal environment first.
python run.py --input "path/to/the-provided-scripts.zip" --out outputs --use-ai
```

`ai_ranked_promos.json` contains the optional API-reviewed suggestions, while `ranked_promos.json` stays as the original offline baseline. Gemini may have usage limits or costs; check your provider dashboard. Never commit your API key.

## Files

- `parser.py`: reads all TXT files and extracts timestamps, dialogue, actions and scenes.
- `scoring.py`: simple keyword/rule-based scores for opening hook, suspense, clarity and emotion.
- `finder.py`: generates legal 20-60 second clips, checks the cuts, reduces duplicates and ranks them.
- `ai_rerank.py`: optional Gemini reviewer for shortlisted clips only (timestamps cannot change).
- `run.py`: repeatable command-line pipeline and CSV/JSON exports.
- `app.py`: small Streamlit interface for a non-technical editor.
- `tests/`: seven basic tests for parsing, timing, candidate generation and ZIP input.
- `outputs/`: unedited offline outputs from the full 50-episode pack and review notes in a separate file.

## Method in simple language

1. I read each timestamped script and make a list of what happens and when.
2. I treat dialogue and significant actions as possible starting and ending points.
3. I try lengths between 20 and 60 seconds, **cutting only at time-coded event boundaries**.
4. I calculate a score: hook 30%, cliffhanger 30%, clarity 25%, emotion 15%. These weights were my assumption, not a Kuku requirement.
5. I reduce overlaps and show the strongest candidates, with their actual start/end times and an explanation.
6. Optionally, Gemini sees the selected clip's dialogue/actions and critiques whether an unfamiliar viewer would understand it. The system never asks it to guess timestamps.

## Checking quality

The `outputs/manifest.json` confirms how much data was processed, and `outputs/manual_review.csv` records my spot-check notes. The raw baseline recommendations are kept unchanged even when a human disagrees with them. Running on another show uses the same parser and rules (but only if the scripts follow this timestamp format).

## Limits / things that went wrong

- Keyword rules sometimes mistake an emotional speech for an unresolved cliffhanger.
- A line that mentions someone's name may need context from earlier episodes.
- Some candidates contain the same underlying scene; the overlap filter helps, but does not solve all repetition.
- It only reads text, so it cannot judge acting, audio, camera pace, or real ad engagement.
- Current prototype finds **continuous clips only**, not montages combining multiple episodes.
- Gemini is optional: without a key there is no claim of LLM-based scoring. Gemini was successfully exercised on 15 candidates in the user's local Streamlit run; source-code tests use a mocked API call.

## Technical checks

```bash
python -m unittest discover -s tests -v
```

The code is intentionally short and divided into small files so I can explain it in an interview. It should also be easy to change `ai_rerank.py` to another model/provider later.

## Privacy

The input scripts are private to Kuku. Do not add the ZIP or extracted full scripts to a public repository or send them to an API service unless the assignment terms and your data-handling choices allow it. Publicly shared outputs can expose portions of the story too, so share the output folder only with the reviewers.

## Note about mixed Gemini/offline rankings

When Gemini reviews only some of the top clips, the adjusted scores are not directly comparable to unreviewed baseline scores. The Streamlit app displays Gemini-reviewed and offline-only clips in separate sections. The assignment raw outputs include both runs without changing the original files. The optional review needs an API key; do not commit or publish it.

## Public demo without Kuku files

The `demo_input/` folder contains one fictional sample episode written for this repository (not from Kuku).
To verify that the command line tool works without any private screenplay data:

```bash
python run.py --input demo_input --out outputs
```

The real assignment results for 50 episodes were created using Kuku's confidential input pack and are provided to the reviewers **separately**, not committed to this public repository.

## Before pushing to GitHub

Run `git status --short` and check that there is no `.venv/`, no API key, no original screenplay ZIP/TXT files, and no `outputs/` folder in the staged files.
