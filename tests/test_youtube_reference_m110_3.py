from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creator_studio.youtube_reference import (
    YOUTUBE_REFERENCE_FILENAME,
    YouTubeReferenceService,
    build_reference_targets,
    parse_description_timestamps,
    parse_iso8601_duration,
)


class FakeTransport:
    def __init__(self):
        self.calls = []

    def get_json(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint.endswith('/search'):
            return {
                'items': [
                    {'id': {'videoId': 'vid1'}, 'snippet': {'title': 'Havana streets at night'}},
                    {'id': {'videoId': 'vid2'}, 'snippet': {'title': 'Cuba city life'}},
                ]
            }
        return {
            'items': [
                {
                    'id': 'vid1',
                    'snippet': {
                        'title': 'Havana streets at night',
                        'description': '0:00 Intro\n1:20 Old Havana streets\n2:10 Classic cars at night',
                        'channelTitle': 'Travel Test',
                        'publishedAt': '2026-01-01T00:00:00Z',
                    },
                    'contentDetails': {'duration': 'PT4M10S'},
                    'status': {'embeddable': True, 'license': 'youtube'},
                },
                {
                    'id': 'vid2',
                    'snippet': {
                        'title': 'Cuba city life',
                        'description': 'Walking around the city',
                        'channelTitle': 'City Test',
                        'publishedAt': '2026-01-02T00:00:00Z',
                    },
                    'contentDetails': {'duration': 'PT2M'},
                    'status': {'embeddable': True, 'license': 'creativeCommon'},
                },
            ]
        }


def write_inputs(root: Path):
    query = root / 'visual_query_plan.json'
    stock = root / 'stock_acquisition_manifest.json'
    query.write_text(json.dumps({
        'plans': [
            {
                'scene_id': 'scene_001', 'strategy': 'search',
                'primary_query': 'Old Havana streets',
                'queries': ['Old Havana streets', 'Havana classic cars'],
                'duration': 6.0,
            },
            {
                'scene_id': 'scene_002', 'strategy': 'search',
                'primary_query': 'Cuba family', 'queries': ['Cuba family'], 'duration': 5.0,
            },
            {
                'scene_id': 'scene_003', 'strategy': 'reuse_previous',
                'primary_query': '', 'queries': [], 'duration': 1.0,
            },
        ]
    }), encoding='utf-8')
    stock.write_text(json.dumps({
        'scenes': [
            {
                'scene_id': 'scene_001',
                'stock': {
                    'status': 'validated',
                    'selection': {'best_score': 0.72},
                    'selected_media': {'final_score': 0.72},
                },
            },
            {
                'scene_id': 'scene_002',
                'stock': {'status': 'search_again'},
            },
        ]
    }), encoding='utf-8')
    return query, stock


class YouTubeReferenceM1103Tests(unittest.TestCase):
    def test_iso_duration(self):
        self.assertEqual(parse_iso8601_duration('PT1H2M3S'), 3723.0)
        self.assertEqual(parse_iso8601_duration('PT4M10S'), 250.0)

    def test_description_timestamps(self):
        chapters = parse_description_timestamps('0:00 Intro\n1:20 Old Havana\n2:10 Cars')
        self.assertEqual(chapters[1], (80.0, 'Old Havana'))
        self.assertEqual(chapters[2], (130.0, 'Cars'))

    def test_targets_include_weak_and_unresolved_but_not_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            query, stock = write_inputs(Path(td))
            targets = build_reference_targets(query, stock, weak_stock_threshold=0.85)
            self.assertEqual([x.scene_id for x in targets], ['scene_001', 'scene_002'])
            self.assertEqual(targets[0].reason, 'weak_stock')
            self.assertEqual(targets[1].reason, 'unresolved_stock')

    def test_missing_key_does_not_call_network(self):
        import os
        from unittest.mock import patch

        # YouTubeReferenceService intentionally falls back to
        # YOUTUBE_API_KEY when api_key is empty. Force this test's
        # "missing key" precondition so it is independent of the
        # developer machine and of tests executed earlier.
        with patch.dict(
            os.environ,
            {"YOUTUBE_API_KEY": ""},
            clear=False,
        ):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                query, stock = write_inputs(root)
                transport = FakeTransport()
                report = YouTubeReferenceService(
                    run_dir=root,
                    query_plan_path=query,
                    stock_manifest_path=stock,
                    api_key='',
                    transport=transport,
                ).run()
                self.assertTrue(report.missing_api_key)
                self.assertEqual(report.target_count, 2)
                self.assertEqual(transport.calls, [])
                self.assertTrue((root / YOUTUBE_REFERENCE_FILENAME).is_file())

    def test_search_uses_embeddable_and_syndicated_filters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query, stock = write_inputs(root)
            transport = FakeTransport()
            YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key='secret-key',
                transport=transport,
            ).run()
            search_call = next(params for endpoint, params in transport.calls if endpoint.endswith('/search'))
            self.assertEqual(search_call['type'], 'video')
            self.assertEqual(search_call['videoEmbeddable'], 'true')
            self.assertEqual(search_call['videoSyndicated'], 'true')
            self.assertNotIn('videoLicense', search_call)

    def test_cc_only_adds_license_filter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query, stock = write_inputs(root)
            transport = FakeTransport()
            YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key='secret-key',
                creative_commons_only=True,
                transport=transport,
            ).run()
            search_call = next(params for endpoint, params in transport.calls if endpoint.endswith('/search'))
            self.assertEqual(search_call['videoLicense'], 'creativeCommon')

    def test_chapter_segment_is_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query, stock = write_inputs(root)
            report = YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key='secret-key',
                transport=FakeTransport(),
            ).run()
            self.assertGreater(report.chapter_segment_count, 0)
            payload = json.loads((root / YOUTUBE_REFERENCE_FILENAME).read_text(encoding='utf-8'))
            first = payload['scenes'][0]['best_candidate']
            self.assertEqual(first['video_id'], 'vid1')
            self.assertEqual(first['segment_start_seconds'], 80.0)
            self.assertEqual(first['segment_basis'], 'description_timestamp')

    def test_manifest_never_promotes_youtube_reference_to_render_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query, stock = write_inputs(root)
            YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key='secret-key',
                transport=FakeTransport(),
            ).run()
            raw = (root / YOUTUBE_REFERENCE_FILENAME).read_text(encoding='utf-8')
            payload = json.loads(raw)
            candidate = payload['scenes'][0]['best_candidate']
            self.assertTrue(candidate['preview_only'])
            self.assertFalse(candidate['render_eligible'])
            self.assertNotIn('secret-key', raw)
            self.assertNotIn('description', candidate)

    def test_no_targets_uses_zero_network_calls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            query = root / 'visual_query_plan.json'
            stock = root / 'stock_acquisition_manifest.json'
            query.write_text(json.dumps({'plans': [{
                'scene_id': 'scene_001', 'strategy': 'search',
                'primary_query': 'Havana', 'queries': ['Havana'], 'duration': 5,
            }]}), encoding='utf-8')
            stock.write_text(json.dumps({'scenes': [{
                'scene_id': 'scene_001',
                'stock': {'status': 'validated', 'selection': {'best_score': 0.91}},
            }]}), encoding='utf-8')
            transport = FakeTransport()
            report = YouTubeReferenceService(
                run_dir=root,
                query_plan_path=query,
                stock_manifest_path=stock,
                api_key='secret-key',
                transport=transport,
            ).run()
            self.assertEqual(report.target_count, 0)
            self.assertEqual(transport.calls, [])


if __name__ == '__main__':
    unittest.main()
