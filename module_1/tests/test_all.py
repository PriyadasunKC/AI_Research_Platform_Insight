"""
tests/test_all.py
==================
Complete test suite for Insight Module 1.

Run from project root:
    python tests/test_all.py
"""

import os
import sys
import json
import unittest

# ── Path setup ────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ─────────────────────────────────────────────────────────────────────────
# Test essays
# ─────────────────────────────────────────────────────────────────────────

POOR_ESSAY = """රජු ගියා. රජු ආවා. රජු ගෙදර ගියා. රජු ගියා. රජු ආවා."""

AVERAGE_ESSAY = """
ශ්‍රී ලංකාවේ ඉතිහාසය පිළිබඳ මෙම රචනාව ඉදිරිපත් කරනු ලැබේ.

මහින්ද හිමි ලංකාවට පැමිණිය. නමුත් රජතුමා ඒ ගැන නොදැන සිටියේය.
මහාවිහාරය ඉදිකෙරිණ.

අවසාන වශයෙන් ශ්‍රී ලංකාවේ ඉතිහාසය ගොඩ නැගිණ.
"""

GOOD_ESSAY = """
ශ්‍රී ලංකාවේ ඉතිහාසය පිළිබඳ මෙම රචනාව ඉදිරිපත් කරනු ලැබේ.
බෞද්ධ ධර්මය ව්‍යාප්ත කිරීම ශ්‍රී ලංකා ඉතිහාසයේ ප්‍රධාන සිදුවීමක් බව සිතිය හැකිය.

මහින්ද හිමිගේ ලංකා ගමනය ක්‍රි.පූ. 247 දී සිදු විය.
එබැවින් දේවානම්පියතිස්ස රජතුමා බෞද්ධ ධර්මය වැළඳ ගත්තේය.
නමුත් රාජකීය සහාය නොමැතිව ඒ කළ නොහැකිව තිබිණ.

ඉන් පසු මහාවිහාරය ඉදිකෙරිණ.
ශ්‍රී ලංකාවේ සංස්කෘතික ශිෂ්ටාචාරය ගොඩ නැගිණ.
එසේම රාජකීය අනුග්‍රහය නිසා ධර්මය ශ්‍රී ලාංකීය සමාජය තුළ ශක්තිමත් විය.

අවසාන වශයෙන් මෙලෙස ශ්‍රී ලංකාවේ ඉතිහාසය ගොඩ නැගිණ.
ඉහත සාකච්ඡා කළ කරුණු රටේ සංස්කෘතික හෙළිදරව්ව සනාථ කරයි.
"""

EMPTY_ESSAY  = "   "
NO_SINHALA   = "This is a completely English essay with no Sinhala content at all."


# ═════════════════════════════════════════════════════════════════════════════
# 1. Feature Extractor Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestFeatureExtractor(unittest.TestCase):

    def setUp(self):
        from features.feature_extractor import extract_features
        self.extract = extract_features

    def test_returns_dict(self):
        self.assertIsInstance(self.extract(AVERAGE_ESSAY), dict)

    def test_required_keys(self):
        result   = self.extract(AVERAGE_ESSAY)
        required = [
            'ttr', 'mattr', 'total_tokens', 'unique_tokens',
            'repetition_ratio', 'academic_density', 'informal_ratio',
            'discourse_type_count', 'discourse_markers',
            'para_count', 'sentence_count',
            'has_intro', 'has_thesis', 'has_conclusion',
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_total_tokens_positive(self):
        self.assertGreater(self.extract(GOOD_ESSAY)['total_tokens'], 0)

    def test_unique_lte_total(self):
        r = self.extract(GOOD_ESSAY)
        self.assertLessEqual(r['unique_tokens'], r['total_tokens'])

    def test_ttr_range(self):
        r = self.extract(GOOD_ESSAY)
        self.assertGreaterEqual(r['ttr'], 0.0)
        self.assertLessEqual   (r['ttr'], 1.0)

    def test_mattr_range(self):
        r = self.extract(GOOD_ESSAY)
        self.assertGreaterEqual(r['mattr'], 0.0)
        self.assertLessEqual   (r['mattr'], 1.0)

    def test_poor_lower_mattr(self):
        poor = self.extract(POOR_ESSAY)
        good = self.extract(GOOD_ESSAY)
        self.assertLessEqual(poor['mattr'], good['mattr'])

    def test_bool_flags(self):
        r = self.extract(GOOD_ESSAY)
        self.assertIsInstance(r['has_intro'],      bool)
        self.assertIsInstance(r['has_thesis'],     bool)
        self.assertIsInstance(r['has_conclusion'], bool)

    def test_good_has_conclusion(self):
        self.assertTrue(self.extract(GOOD_ESSAY)['has_conclusion'])

    def test_poor_no_conclusion(self):
        self.assertFalse(self.extract(POOR_ESSAY)['has_conclusion'])

    def test_empty_raises(self):
        from features.feature_extractor import extract_features
        with self.assertRaises(ValueError):
            extract_features(EMPTY_ESSAY)

    def test_no_sinhala_raises(self):
        from features.feature_extractor import extract_features
        with self.assertRaises(ValueError):
            extract_features(NO_SINHALA)

    def test_discourse_markers_is_dict(self):
        r = self.extract(GOOD_ESSAY)
        self.assertIsInstance(r['discourse_markers'], dict)

    def test_good_more_markers_than_poor(self):
        poor = self.extract(POOR_ESSAY)
        good = self.extract(GOOD_ESSAY)
        self.assertGreaterEqual(
            good['discourse_type_count'],
            poor['discourse_type_count']
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Coherence Scorer Tests (D2)
# ═════════════════════════════════════════════════════════════════════════════

class TestCoherenceScorer(unittest.TestCase):

    def setUp(self):
        from models.coherence_scorer import score_coherence
        self.score = score_coherence

    def test_returns_dict(self):
        self.assertIsInstance(self.score(AVERAGE_ESSAY), dict)

    def test_score_in_range(self):
        for essay in [POOR_ESSAY, AVERAGE_ESSAY, GOOD_ESSAY]:
            self.assertIn(self.score(essay)['score'], [1,2,3,4,5])

    def test_required_keys(self):
        r = self.score(GOOD_ESSAY)
        for k in ['score','max','dimension','found_markers',
                  'missing_types','type_count','hint_si','hint_en']:
            self.assertIn(k, r)

    def test_max_is_5(self):
        self.assertEqual(self.score(GOOD_ESSAY)['max'], 5)

    def test_poor_lower_than_good(self):
        self.assertLessEqual(
            self.score(POOR_ESSAY)['score'],
            self.score(GOOD_ESSAY)['score']
        )

    def test_no_markers_score_1(self):
        r = self.score("රජු ගෙදර. ඔහු ගියා. ඒ සිදු විය.")
        self.assertEqual(r['score'], 1)
        self.assertEqual(r['type_count'], 0)

    def test_hint_si_string(self):
        r = self.score(GOOD_ESSAY)
        self.assertIsInstance(r['hint_si'], str)
        self.assertGreater(len(r['hint_si']), 0)

    def test_found_markers_dict(self):
        self.assertIsInstance(self.score(GOOD_ESSAY)['found_markers'], dict)

    def test_missing_types_list(self):
        self.assertIsInstance(self.score(POOR_ESSAY)['missing_types'], list)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Vocabulary Scorer Tests (D3)
# ═════════════════════════════════════════════════════════════════════════════

class TestVocabularyScorer(unittest.TestCase):

    def setUp(self):
        from models.vocabulary_scorer import score_vocabulary
        self.score = score_vocabulary

    def test_returns_dict(self):
        self.assertIsInstance(self.score(AVERAGE_ESSAY), dict)

    def test_score_in_range(self):
        for essay in [POOR_ESSAY, AVERAGE_ESSAY, GOOD_ESSAY]:
            self.assertIn(self.score(essay)['score'], [1,2,3,4,5])

    def test_required_keys(self):
        r = self.score(GOOD_ESSAY)
        for k in ['score','max','dimension','mattr',
                  'academic_density','repetition_ratio',
                  'informal_count','hint_si','hint_en']:
            self.assertIn(k, r)

    def test_max_is_5(self):
        self.assertEqual(self.score(GOOD_ESSAY)['max'], 5)

    def test_poor_lower_than_good(self):
        self.assertLessEqual(
            self.score(POOR_ESSAY)['score'],
            self.score(GOOD_ESSAY)['score']
        )

    def test_mattr_float(self):
        r = self.score(GOOD_ESSAY)
        self.assertIsInstance(r['mattr'], float)
        self.assertGreaterEqual(r['mattr'], 0.0)
        self.assertLessEqual   (r['mattr'], 1.0)

    def test_highly_repetitive_low_score(self):
        repeated = "රජු ගියා. " * 30
        r = self.score(repeated)
        self.assertLessEqual(r['score'], 2)

    def test_hint_si_string(self):
        r = self.score(GOOD_ESSAY)
        self.assertIsInstance(r['hint_si'], str)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Structure Scorer Tests (D4)
# ═════════════════════════════════════════════════════════════════════════════

class TestStructureScorer(unittest.TestCase):

    def setUp(self):
        from models.structure_scorer import score_structure
        self.score = score_structure

    def test_returns_dict(self):
        self.assertIsInstance(self.score(AVERAGE_ESSAY), dict)

    def test_score_in_range(self):
        for essay in [POOR_ESSAY, AVERAGE_ESSAY, GOOD_ESSAY]:
            self.assertIn(self.score(essay)['score'], [1,2,3,4,5])

    def test_required_keys(self):
        r = self.score(GOOD_ESSAY)
        for k in ['score','max','dimension','para_count',
                  'has_intro','has_thesis','has_body',
                  'has_conclusion','missing','hint_si','hint_en']:
            self.assertIn(k, r)

    def test_max_is_5(self):
        self.assertEqual(self.score(GOOD_ESSAY)['max'], 5)

    def test_good_higher_than_poor(self):
        self.assertGreaterEqual(
            self.score(GOOD_ESSAY)['score'],
            self.score(POOR_ESSAY)['score']
        )

    def test_good_has_conclusion(self):
        self.assertTrue(self.score(GOOD_ESSAY)['has_conclusion'])

    def test_poor_no_conclusion(self):
        self.assertFalse(self.score(POOR_ESSAY)['has_conclusion'])

    def test_para_count_positive(self):
        self.assertGreater(self.score(GOOD_ESSAY)['para_count'], 0)

    def test_missing_is_list(self):
        self.assertIsInstance(self.score(POOR_ESSAY)['missing'], list)

    def test_has_body_bool(self):
        self.assertIsInstance(self.score(GOOD_ESSAY)['has_body'], bool)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Rule-Based Master Scorer Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestRuleBasedScorer(unittest.TestCase):

    def setUp(self):
        from models.rule_based_scorer import score_essay
        self.score = score_essay

    def test_returns_dict(self):
        self.assertIsInstance(self.score(GOOD_ESSAY), dict)

    def test_required_top_keys(self):
        r = self.score(GOOD_ESSAY)
        for k in ['scores','average_score','dimensions','model_type']:
            self.assertIn(k, r)

    def test_scores_key_has_d2_d3_d4(self):
        r = self.score(GOOD_ESSAY)
        for d in ['D2','D3','D4']:
            self.assertIn(d, r['scores'])

    def test_all_dimensions_present(self):
        r = self.score(GOOD_ESSAY)
        for dim in ['D1_historical_accuracy','D2_coherence',
                    'D3_vocabulary','D4_structure']:
            self.assertIn(dim, r['dimensions'])

    def test_d1_none_when_not_passed(self):
        r = self.score(GOOD_ESSAY)
        self.assertIsNone(r['scores'].get('D1'))

    def test_d1_set_when_passed(self):
        r = self.score(GOOD_ESSAY, d1_score=4)
        self.assertEqual(r['scores']['D1'], 4)

    def test_average_score_range(self):
        r = self.score(GOOD_ESSAY)
        self.assertGreaterEqual(r['average_score'], 1.0)
        self.assertLessEqual   (r['average_score'], 5.0)

    def test_good_better_average_than_poor(self):
        poor_avg = self.score(POOR_ESSAY)['average_score']
        good_avg = self.score(GOOD_ESSAY)['average_score']
        self.assertGreaterEqual(good_avg, poor_avg)

    def test_model_type_string(self):
        r = self.score(GOOD_ESSAY)
        self.assertIsInstance(r['model_type'], str)

    def test_empty_raises(self):
        from models.rule_based_scorer import score_essay
        with self.assertRaises(ValueError):
            score_essay(EMPTY_ESSAY)

    def test_d1_out_of_range_ignored(self):
        r = self.score(GOOD_ESSAY, d1_score=10)
        self.assertIsNone(r['scores']['D1'])

    def test_elapsed_sec_positive(self):
        r = self.score(AVERAGE_ESSAY)
        self.assertIn('elapsed_sec', r)
        self.assertGreaterEqual(r['elapsed_sec'], 0)   # 0.0 is valid on fast machines

    def test_notes_present(self):
        # notes field must exist for Module 3
        r = self.score(GOOD_ESSAY)
        self.assertIn('notes', r)
        for key in ['D2_note','D3_note','D4_note']:
            self.assertIn(key, r['notes'])

    def test_notes_have_required_fields(self):
        r = self.score(GOOD_ESSAY)
        for key in ['D2_note','D3_note','D4_note']:
            note = r['notes'][key]
            for field in ['score','what_wrong','how_to_improve','short_note_si']:
                self.assertIn(field, note, f"Missing {field} in {key}")


# ═════════════════════════════════════════════════════════════════════════════
# 6. Flask API Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestFlaskAPI(unittest.TestCase):

    def setUp(self):
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()

    def test_index_200(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_health_endpoint(self):
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertEqual(data['status'], 'ok')

    def test_score_good_essay_json(self):
        r = self.client.post(
            '/score',
            json={'essay': GOOD_ESSAY},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn('scores', data)
        self.assertIn('average_score', data)

    def test_score_with_d1(self):
        r = self.client.post(
            '/score',
            json={'essay': GOOD_ESSAY, 'd1_score': 4},
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertEqual(data['scores'].get('D1'), 4)

    def test_empty_essay_400(self):
        r = self.client.post('/score', json={'essay': ''})
        self.assertEqual(r.status_code, 400)

    def test_short_essay_400(self):
        r = self.client.post('/score', json={'essay': 'කෙටි'})
        self.assertEqual(r.status_code, 400)

    def test_response_has_scores(self):
        r    = self.client.post('/score', json={'essay': AVERAGE_ESSAY})
        data = json.loads(r.data)
        for dim in ['D2','D3','D4']:
            self.assertIn(dim, data['scores'])

    def test_response_has_hints(self):
        r    = self.client.post('/score', json={'essay': GOOD_ESSAY})
        data = json.loads(r.data)
        self.assertIn('hints', data)

    def test_response_has_notes_for_module3(self):
        r    = self.client.post('/score', json={'essay': GOOD_ESSAY})
        data = json.loads(r.data)
        self.assertIn('notes', data)

    def test_score_form_data(self):
        # Also test form-data submission (for file upload UI)
        r = self.client.post(
            '/score',
            data={'essay_text': GOOD_ESSAY},
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(r.status_code, 200)

    def test_model_type_in_response(self):
        r    = self.client.post('/score', json={'essay': GOOD_ESSAY})
        data = json.loads(r.data)
        self.assertIn('model_type', data)


# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 65)
    print("  Insight Module 1 - Test Suite")
    print("=" * 65)
    print()

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    test_classes = [
        TestFeatureExtractor,
        TestCoherenceScorer,
        TestVocabularyScorer,
        TestStructureScorer,
        TestRuleBasedScorer,
        TestFlaskAPI,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print("✅  All tests passed!")
    else:
        print(f"❌  {len(result.failures)} failure(s), {len(result.errors)} error(s)")
        sys.exit(1)