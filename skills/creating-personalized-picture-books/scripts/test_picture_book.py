"""Engineering fixtures only: generated geometry, colours and ASCII folios."""
import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas

sys.dont_write_bytecode = True


class PictureBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('picture_book.py')
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location('picture_book', path)
        cls.pb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pb)

    def setUp(self):
        self.assertTrue(hasattr(self, 'pb'), 'Reusable picture_book.py is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'book'

    def project_with_art(self, high=False):
        self.pb.init_project(self.project, 4)
        book = json.loads((self.project / 'book.json').read_text('utf-8'))
        for i, art in enumerate(book['artwork']):
            side = 2800 if high else 400
            size = (side * 2, side) if art['kind'] == 'spread' else (side, side)
            im = Image.new('RGB', size, (25 + i * 35, 80, 120))
            ImageDraw.Draw(im).rectangle((0, 0, size[0] // 3, size[1]), fill=(220, 160, 40))
            im.save(self.project / art['file'])
        return book

    def write_book(self, book):
        (self.project / 'book.json').write_text(json.dumps(book), 'utf-8')

    def write_reviews(self, book, wordless=True):
        reviews = []
        for art in book['artwork']:
            expected = json.dumps(art['expected_text'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            row = dict(id=art['id'], image_sha256=hashlib.sha256((self.project/art['file']).read_bytes()).hexdigest(), expected_text_sha256=hashlib.sha256(expected).hexdigest(), visual_review_completed=True, confirmed_text_error=False)
            if wordless and not any(s.strip() for s in art['expected_text']):
                row['wordless'] = True
            reviews.append(row)
        (self.project/'qa/text_review.json').write_text(json.dumps(dict(reviews=reviews)), 'utf-8')
        return reviews

    def test_init_defaults_and_refuses_overwrite(self):
        self.pb.init_project(self.project)
        book = json.loads((self.project / 'book.json').read_text('utf-8'))
        self.assertEqual(book['interior_pages'], 24)
        self.assertEqual(len(book['artwork']), 15)
        self.assertEqual([a['id'] for a in book['artwork'][:3]], ['front', 'P01', 'spread_01'])
        self.assertEqual(book['artwork'][-2]['id'], 'P24')
        before = (self.project / 'book.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.pb.init_project(self.project)
        self.assertEqual((self.project / 'book.json').read_bytes(), before)

    def test_rejects_odd_page_count_and_negative_bleed(self):
        with self.assertRaises(ValueError):
            self.pb.init_project(self.project, 5)
        book = self.project_with_art()
        book['bleed_mm'] = -1
        self.write_book(book)
        with self.assertRaises(ValueError):
            self.pb.export_project(self.project)

    def test_real_four_page_export_sequence_boxes_and_font(self):
        self.project_with_art()
        self.pb.export_project(self.project)
        for name, count in [('print.pdf', 6), ('interior_print.pdf', 4), ('covers_print.pdf', 2), ('preview.pdf', 5)]:
            with fitz.open(self.project / name) as pdf:
                self.assertEqual(len(pdf), count)
        pdf = PdfReader(self.project / 'print.pdf')
        self.assertEqual([p.extract_text().strip() for p in pdf.pages], ['', '1', '2', '3', '4', ''])
        mm = 72 / 25.4
        for p in pdf.pages:
            self.assertAlmostEqual(float(p.mediabox.width), 236 * mm, places=3)
            self.assertAlmostEqual(float(p.trimbox.left), 3 * mm, places=3)
            self.assertAlmostEqual(float(p.trimbox.width), 230 * mm, places=3)
            self.assertEqual(list(p.bleedbox), list(p.mediabox))
        with fitz.open(self.project / 'print.pdf') as rendered:
            left = rendered[2].get_pixmap(matrix=fitz.Matrix(.2, .2))
            right = rendered[3].get_pixmap(matrix=fitz.Matrix(.2, .2))
            self.assertGreater(left.pixel(20, 20)[0], right.pixel(20, 20)[0])
        report = self.pb.check_project(self.project)
        self.assertTrue(report['technical_consistent'], report)
        self.assertFalse(report['print_ready'])
        self.assertTrue(report['page_numbers_embedded'])
        manifest = json.loads((self.project / 'qa/export_manifest.json').read_text())
        self.assertEqual(manifest['sources']['spread_01']['pixels'], [800, 400])
        self.assertEqual(manifest['outputs']['print.pdf']['pages'][2]['artwork_id'], 'spread_01')

    def test_full_transform_ppi_does_not_increase_when_clipped(self):
        book = self.project_with_art()
        art = next(a for a in book['artwork'] if a['kind'] == 'spread')
        Image.new('RGB', (3000, 1500), 'orange').save(self.project / art['file'])
        self.pb.export_project(self.project)
        report = self.pb.check_project(self.project)
        info = report['pdfs']['print.pdf']['pages'][2]['images'][0]
        self.assertAlmostEqual(info['ppi'][0], 3000 / (472 / 25.4), places=2)
        self.assertLess(info['ppi'][0], 300)
        self.assertFalse(report['print_ready'])

    def test_current_sources_and_outputs_invalidate_old_qa(self):
        book = self.project_with_art()
        self.pb.export_project(self.project)
        self.pb.check_project(self.project)
        Image.new('RGB', (400, 400), 'white').save(self.project / book['artwork'][0]['file'])
        report = self.pb.check_project(self.project)
        self.assertFalse(report['technical_consistent'])
        self.assertTrue(any('source' in e.lower() for e in report['technical_errors']))
        self.pb.export_project(self.project)
        self.assertTrue(self.pb.check_project(self.project)['technical_consistent'])
        (self.project / 'print.pdf').unlink()
        report = self.pb.check_project(self.project)
        self.assertFalse(report['technical_consistent'])
        self.assertFalse(report['print_ready'])
        self.assertTrue(any('print.pdf' in e for e in report['technical_errors']))

    def test_confirmed_high_resolution_can_pass_and_modified_pdf_cannot(self):
        book = self.project_with_art(high=True)
        book.update(printer_profile_confirmed=True, color_profile='Printer-approved RGB', binding='Printer-approved binding', in_image_text_reviewed=True)
        self.write_book(book)
        self.pb.export_project(self.project)
        report = self.pb.check_project(self.project)
        self.assertTrue(report['technical_consistent'], report)
        self.assertFalse(report['print_ready'], 'A global review flag cannot approve individual images')
        self.assertTrue(any('text_review' in e for e in report['production_blockers']))
        self.write_reviews(book)
        report = self.pb.check_project(self.project)
        self.assertTrue(report['print_ready'], report)
        with (self.project / 'covers_print.pdf').open('ab') as f:
            f.write(b'\n% modified\n')
        self.assertFalse(self.pb.check_project(self.project)['technical_consistent'])

    def test_expected_text_change_invalidates_review_even_when_image_is_unchanged(self):
        book = self.project_with_art()
        book['in_image_text_reviewed'] = True
        self.write_reviews(book)
        before = hashlib.sha256((self.project/book['artwork'][0]['file']).read_bytes()).hexdigest()
        book['artwork'][0]['expected_text'] = ['Engineering fixture']
        self.write_book(book)
        self.pb.export_project(self.project)
        report = self.pb.check_project(self.project)
        self.assertEqual(before, hashlib.sha256((self.project/book['artwork'][0]['file']).read_bytes()).hexdigest())
        self.assertTrue(report['technical_consistent'], report)
        self.assertFalse(report['print_ready'])
        self.assertTrue(any('front' in e and 'expected_text' in e for e in report['production_blockers']), report)

    def test_wordless_review_requires_explicit_per_image_declaration(self):
        book = self.project_with_art()
        book['in_image_text_reviewed'] = True
        self.write_book(book)
        self.write_reviews(book, wordless=False)
        self.pb.export_project(self.project)
        report = self.pb.check_project(self.project)
        self.assertTrue(any('wordless' in e for e in report['production_blockers']), report)

    def test_spread_trim_is_one_continuous_native_pixel_interval(self):
        book = self.project_with_art()
        art = next(a for a in book['artwork'] if a['kind'] == 'spread')
        im = Image.new('RGB', (944, 472))
        draw = ImageDraw.Draw(im)
        for x in range(im.width):
            draw.line((x, 0, x, 471), fill=(x % 251, (x // 251) * 60, 190))
        im.save(self.project/art['file'])
        self.pb.export_project(self.project)
        intervals, pixels = [], []
        with fitz.open(self.project/'print.pdf') as pdf:
            for page_index in (2, 3):
                page = pdf[page_index]
                info = page.get_image_info()[0]
                matrix = fitz.Matrix(info['transform'])
                inverse = ~matrix
                start = fitz.Point(3*self.pb.MM, 3*self.pb.MM) * inverse
                end = fitz.Point(233*self.pb.MM, 3*self.pb.MM) * inverse
                intervals.append((start.x*im.width, end.x*im.width))
                pix = page.get_pixmap(matrix=fitz.Matrix(50.8/72, 50.8/72), colorspace=fitz.csRGB, alpha=False)
                pixels.extend(pix.pixel(x, 200) for x in range(6, 466))
        self.assertAlmostEqual(intervals[0][0], 12, places=3)
        self.assertAlmostEqual(intervals[0][1], intervals[1][0], places=3)
        self.assertAlmostEqual(intervals[1][1], 932, places=3)
        self.assertEqual(pixels, [im.getpixel((x, 200)) for x in range(12, 932)])

    def test_render_comparison_uses_common_origin_grid_and_detects_shift(self):
        self.project.mkdir()
        for name, dx in [('a.pdf', 0), ('b.pdf', 0), ('shift.pdf', 2)]:
            c = canvas.Canvas(str(self.project / name), pagesize=(200, 200))
            c.setFillColorRGB(.2, .3, .8)
            c.rect(32 + dx, 45, 80, 90, fill=1, stroke=0)
            c.save()
        with fitz.open(self.project / 'a.pdf') as a, fitz.open(self.project / 'b.pdf') as b, fitz.open(self.project / 'shift.pdf') as shifted:
            same = self.pb.compare_renders(a[0], b[0], clip=(21.3, 28.7, 160.8, 172.2), dpi=101)
            changed = self.pb.compare_renders(a[0], shifted[0], clip=(21.3, 28.7, 160.8, 172.2), dpi=101)
        self.assertEqual(same['changed_pixels'], 0)
        self.assertGreater(changed['changed_pixels'], 0)

    def test_render_comparison_counts_even_one_channel_one_level_change(self):
        self.project.mkdir()
        for name, blue in [('a.pdf', 0), ('b.pdf', 1/255)]:
            c = canvas.Canvas(str(self.project / name), pagesize=(20, 20))
            c.setFillColorRGB(0, 0, blue)
            c.rect(0, 0, 20, 20, fill=1, stroke=0)
            c.save()
        with fitz.open(self.project / 'a.pdf') as a, fitz.open(self.project / 'b.pdf') as b:
            self.assertEqual(self.pb.compare_renders(a[0], b[0], dpi=72)['changed_pixels'], 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
