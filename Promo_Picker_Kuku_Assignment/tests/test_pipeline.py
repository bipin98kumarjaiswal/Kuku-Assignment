"""Run with: python -m unittest discover -s tests -v"""
import io
import unittest
import zipfile
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import parse_script, load_episodes, seconds, stamp
from finder import discover

SAMPLE = '''EPISODE NUMBER: Episode 1
EPISODE LOGLINE: Some conflict
SCENE 01
Scene start: 00:00.00
Scene end: 01:03.00
**MARY (Terrified):**
Start: (00:01.00) | End: (00:04.00)
"You murdered my sister!"
**JOHN (Angry):**
Start: (00:05.00) | End: (00:09.00)
"That is a lie."
**ACTION:**
Start: (00:19.00) | End: (00:22.00)
She slaps him.
**MARY (Demanding):**
Start: (00:30.00) | End: (00:33.00)
"Then who did it?"
**JOHN (Whispering):**
Start: (00:45.00) | End: (00:49.00)
"The real murderer is..."
**ACTION:**
Start: (00:50.00) | End: (00:51.00)
A scream interrupts him.
--- SCRIPT END ---
'''

class TestPipeline(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(stamp(seconds('02:17.50')), '02:17.50')
        self.assertEqual(seconds('00:08.30'), 8.3)

    def test_parse(self):
        e = parse_script(SAMPLE)
        self.assertEqual(e.number, 1)
        self.assertEqual(len(e.events), 6)
        self.assertEqual(e.duration, 63.)
        self.assertEqual(e.events[0].speaker, 'MARY')

    def test_rank_valid_times(self):
        ep = parse_script(SAMPLE)
        all_candidates, ranked = discover([ep])
        self.assertTrue(all_candidates)
        for p in all_candidates:
            self.assertGreaterEqual(p['duration_seconds'], 20)
            self.assertLessEqual(p['duration_seconds'], 60)
            self.assertGreaterEqual(p['start_seconds'], 0)
            self.assertLessEqual(p['end_seconds'], ep.duration)
            self.assertEqual(p['segments'][0]['start'], stamp(p['start_seconds']))

    def test_zip_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'scripts.zip'
            with zipfile.ZipFile(path, 'w') as zipout:
                zipout.writestr('folder/episode-001.txt', SAMPLE)
            loaded = load_episodes(path)
            self.assertEqual(len(loaded), 1)

if __name__ == '__main__':
    unittest.main()

class TestOptionalAI(unittest.TestCase):
    def test_optional_judge_preserves_timestamps(self):
        from unittest.mock import patch
        from ai_rerank import rerank_candidates, DEFAULT_MODEL
        ep = parse_script(SAMPLE)
        _, ranked = discover([ep])
        mocked = {'hook':7,'cliffhanger':8,'standalone_clarity':6,'emotional_impact':7,
                  'why':'There is a question','weakness':'Needs context'}
        with patch('ai_rerank._call_gemini', return_value=mocked):
            out,errors = rerank_candidates(ranked, [ep], api_key='demo-only', limit=1)
        self.assertFalse(errors)
        self.assertEqual(out[0]['segments'], ranked[0]['segments'])
        self.assertEqual(out[0]['method'], f'gemini_review:{DEFAULT_MODEL}')
        self.assertIn('ai_score', out[0])
