import unittest
from review_utils import separate_reviewed


class TestMixedScores(unittest.TestCase):
    def test_reviewed_and_offline_not_mixed(self):
        baseline = [
            {'episode': 1, 'start_seconds': 0, 'end_seconds': 30, 'score': 80, 'baseline_rank': 1},
            {'episode': 2, 'start_seconds': 0, 'end_seconds': 30, 'score': 70, 'baseline_rank': 2},
            {'episode': 3, 'start_seconds': 0, 'end_seconds': 30, 'score': 60, 'baseline_rank': 3},
        ]
        reviewed_input = [{**baseline[0], 'ai_score': 35, 'final_score': 50},
                          {**baseline[1], 'ai_score': 75, 'final_score': 73}]
        reviewed, pending = separate_reviewed(baseline, reviewed_input)
        self.assertEqual([r['episode'] for r in reviewed], [2, 1])
        self.assertEqual([r['episode'] for r in pending], [3])
        self.assertEqual(pending[0]['review_group'], 'offline_only')
        self.assertEqual(reviewed[0]['rank_within_group'], 1)

    def test_no_review_keeps_all_offline(self):
        baseline = [{'episode': 1, 'start_seconds': 0, 'end_seconds': 30,
                     'score': 60, 'baseline_rank': 1}]
        reviewed, pending = separate_reviewed(baseline, [])
        self.assertFalse(reviewed)
        self.assertEqual(len(pending), 1)

if __name__ == '__main__':
    unittest.main()
