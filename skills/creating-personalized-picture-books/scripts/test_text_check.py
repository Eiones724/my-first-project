import unittest
from text_algorithms import compare, content
from text_check import expected_digest, safety_estimate


def box(identifier,text,x=0):
    return {'id':identifier,'text':text,'content':content(text),'confidence':.99,'bbox_px':[x,0,x+40,20]}


class TextTests(unittest.TestCase):
    def test_word_order_is_not_just_counts(self):
        self.assertFalse(compare([{'text':'小手接住'}],[box(1,'手小接住')])['ocr_content_match'])
    def test_punctuation_is_a_review_not_confirmed_typo(self):
        result=compare([{'text':'你好，朋友！'}],[box(1,'你好朋友')])
        self.assertTrue(result['ocr_content_match']);self.assertTrue(result['requires_visual_review'])
    def test_neighbor_boxes_may_form_one_sentence(self):
        self.assertTrue(compare([{'text':'小手接住'}],[box(1,'小手'),box(2,'接住',45)])['ocr_content_match'])
    def test_unexpected_han_cannot_pass(self):
        self.assertFalse(compare([{'text':'朋友'}],[box(1,'朋友友')])['ocr_content_match'])
    def test_review_must_bind_current_copy(self):
        self.assertNotEqual(expected_digest(['生日快乐。']),expected_digest(['生日快乐！']))
    def test_crossing_center_is_a_gutter_risk(self):
        result=safety_estimate([998,400,1002,440],[2000,1000],'spread',{'trim_mm':230,'bleed_mm':3,'safe_mm':14})
        self.assertTrue(result['crosses_gutter']);self.assertTrue(result['requires_visual_review'])
    def test_blank_expected_text_needs_no_ocr_dependency(self):
        import tempfile,json,sys,io,builtins
        from pathlib import Path
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from text_check import main
        real_import=builtins.__import__
        def guard(name,*args,**kwargs):
            if name.startswith('rapidocr'):raise AssertionError('OCR dependency imported before expected text check')
            return real_import(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'assets').mkdir();(p/'assets/front.png').write_bytes(b'fixture')
            (p/'book.json').write_text(json.dumps({'artwork':[{'id':'front','kind':'single','file':'assets/front.png','expected_text':[]}]}),'utf-8')
            with patch.object(sys,'argv',['text_check.py','--project',directory]),patch('builtins.__import__',side_effect=guard),redirect_stdout(io.StringIO()):
                self.assertEqual(main(),2)
            self.assertEqual(json.loads((p/'qa/ocr.json').read_text('utf-8'))['images'][0]['status'],'missing_expected_text')


if __name__=='__main__':unittest.main()
