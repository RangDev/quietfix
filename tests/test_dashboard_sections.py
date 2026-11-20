import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
from dashboard import section_settings
class DashboardSections(unittest.TestCase):
    def test_default_grouping_and_unassigned(self):
        sections,mapping=section_settings()
        self.assertEqual(mapping[('collector-01','machine-01')]['section_id'],'a')
        self.assertEqual(mapping[('collector-01','machine-04')]['section_id'],'a')
        self.assertEqual(len(mapping),8)
        self.assertEqual(mapping[('collector-01','machine-08')]['section_id'],'b')
        self.assertEqual(sections[-1]['id'],'unassigned')
    def test_same_machine_id_in_two_collectors_is_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'sections.json';file.write_text(json.dumps({'sections':[{'id':'a','name':'A','machines':[{'collector_id':'one','machine_id':'m'}]},{'id':'b','name':'B','machines':[{'collector_id':'two','machine_id':'m'}]}]}))
            with patch.dict(os.environ,{'QF_DASHBOARD_SECTIONS':str(file)}):
                _,mapping=section_settings();self.assertEqual(len(mapping),2)
    def test_duplicate_assignments_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'sections.json';file.write_text(json.dumps({'sections':[{'id':'a','name':'A','machines':[{'collector_id':'one','machine_id':'m'}]*2}]}))
            with patch.dict(os.environ,{'QF_DASHBOARD_SECTIONS':str(file)}):
                with self.assertRaises(ValueError):section_settings()

