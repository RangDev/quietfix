import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps'))
import dashboard


class DashboardAnalysis(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, 0, 30, tzinfo=timezone.utc)
        self.sample = {'sample_id': 'new', 'timestamp': '2026-11-20T12:00:25Z'}

    def result(self, status='normal', sid='old', stamp='2026-11-20T12:00:20Z'):
        return {'collector_id': 'g', 'machine_id': 'm', 'sample_id': sid,
                'timestamp': stamp, 'status': status}

    def test_first_analysis_is_pending_not_normal(self):
        view = dashboard.analysis_view(self.sample, [], self.now)
        self.assertIsNone(view['analysis'])
        self.assertEqual(view['state'], 'waiting_for_analysis')
        self.assertTrue(view['analysis_pending'])
        self.assertFalse(view['analysis_delayed'])

    def test_previous_normal_and_abnormal_survive_new_measurement(self):
        for status in ('normal', 'abnormal', 'unassessed'):
            with self.subTest(status=status):
                view = dashboard.analysis_view(self.sample, [self.result(status)], self.now)
                self.assertEqual(view['analysis']['status'], status)
                self.assertEqual(view['state'], 'ready')
                self.assertTrue(view['analysis_pending'])

    def test_new_result_changes_status_even_when_telemetry_is_ahead(self):
        for status in ('normal', 'abnormal'):
            rows = [self.result(status, 'later', '2026-11-20T12:00:24Z'),
                    self.result('abnormal' if status == 'normal' else 'normal')]
            view = dashboard.analysis_view(self.sample, rows, self.now)
            self.assertEqual(view['analysis']['status'], status)
            self.assertEqual(view['analysis']['sample_id'], 'later')

    def test_matching_result_clears_pending(self):
        view = dashboard.analysis_view(self.sample, [self.result(sid='new')], self.now)
        self.assertFalse(view['analysis_pending'])

    def test_stale_result_remains_visible_and_is_flagged(self):
        row = self.result('abnormal', stamp='2026-11-20T11:59:30Z')
        with patch.object(dashboard.c, 'ANALYSIS_STALE_SECONDS', 60):
            view = dashboard.analysis_view(self.sample, [row], self.now)
        self.assertTrue(view['analysis_delayed'])
        self.assertEqual(view['analysis_age_seconds'], 60)
        self.assertEqual(view['analysis']['status'], 'abnormal')

    def test_initial_delay_and_invalid_time(self):
        for stamp in ('2026-11-20T11:58:00Z', 'invalid'):
            view = dashboard.analysis_view({**self.sample, 'timestamp': stamp}, [], self.now)
            self.assertTrue(view['analysis_delayed'])
            self.assertIsNone(view['analysis'])

    def test_future_analysis_does_not_label_older_measurement(self):
        view = dashboard.analysis_view(self.sample,
            [self.result(stamp='2026-11-20T12:01:00Z')], self.now)
        self.assertIsNone(view['analysis'])

    def test_snapshot_keeps_collectors_separate_and_ignores_result_order(self):
        client = Mock()
        client.records.return_value = [self.result('abnormal'),
            {**self.result('normal', 'new'), 'collector_id': 'other'}]
        machine = {'collector_id': 'g', 'machine_id': 'm', 'machine_name': 'M',
                   'sensors': [], 'path': 'archive/g/m'}
        with patch.object(dashboard, 'Client', return_value=client), \
             patch.object(dashboard, 'discover_machines', return_value=[machine]), \
             patch.object(dashboard, 'latest_group', return_value={('g', 'm'): self.sample}), \
             patch.object(dashboard.c, 'FLEX_ENABLED', False):
            view = dashboard.snapshot()['machines'][0]
        self.assertEqual(view['analysis']['status'], 'abnormal')
        self.assertEqual(view['analysis']['collector_id'], 'g')
        self.assertEqual(view['telemetry']['sample_id'], 'new')

    def test_continuous_new_samples_do_not_hide_missing_first_result(self):
        cache = dashboard.DashboardCache()
        def snapshot():
            return {'machines': [{'collector_id': 'g', 'machine_id': 'm',
                    'telemetry': dict(self.sample), 'analysis': None,
                    'analysis_delayed': False}], '_results': []}
        with patch.object(dashboard, 'snapshot', side_effect=snapshot), \
             patch.object(dashboard, 'monotonic', side_effect=[100, 161]), \
             patch.object(dashboard.c, 'ANALYSIS_STALE_SECONDS', 60):
            cache.refresh()
            self.assertFalse(cache.read()[1]['machines'][0]['analysis_delayed'])
            cache.refresh()
            self.assertTrue(cache.read()[1]['machines'][0]['analysis_delayed'])
