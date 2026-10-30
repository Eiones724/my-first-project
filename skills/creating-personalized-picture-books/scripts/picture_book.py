"""Bind existing raster picture-and-text PNGs; this is not editable text authoring.

Coordinates in reports use the PDF's top-left origin; image PPI uses the full
image transform before clipping. Chinese inside artwork remains raster pixels.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path

import pymupdf as fitz
import reportlab
from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MM = 72 / 25.4
NAMES = ('print.pdf', 'interior_print.pdf', 'covers_print.pdf', 'preview.pdf')
RASTER_NOTE = 'In-image Chinese is raster pixels; no Chinese font embedding or word-level editability is claimed.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def expected_digest(lines):
    return hashlib.sha256(json.dumps(lines, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def text_review_blockers(project, book, sources):
    """Human reviews bind both the current image bytes and authored lettering."""
    try:
        rows = json.loads((project/'qa/text_review.json').read_text('utf-8-sig'))['reviews']
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows):
            raise ValueError('reviews must be an array of records with string ids')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f'text_review.json: current per-image visual review is missing or invalid ({exc})']
    blockers = []
    for art in book['artwork']:
        matches = [r for r in rows if r['id'] == art['id']]
        reasons = []
        if len(matches) != 1:
            reasons.append('requires exactly one current review')
        else:
            row = matches[0]
            if row.get('image_sha256') != sources[art['id']]['sha256']:
                reasons.append('image_sha256 changed or missing')
            if row.get('expected_text_sha256') != expected_digest(art['expected_text']):
                reasons.append('expected_text_sha256 changed or missing')
            if row.get('visual_review_completed') is not True:
                reasons.append('visual_review_completed must be true')
            if row.get('confirmed_text_error') is not False:
                reasons.append('confirmed_text_error must be false')
            if not any(s.strip() for s in art['expected_text']) and row.get('wordless') is not True:
                reasons.append('empty expected_text requires explicit wordless:true')
        if reasons:
            blockers.append(f'text_review.json {art["id"]}: ' + '; '.join(reasons))
    return blockers


def artwork_order(n):
    if type(n) is not int or n < 2 or n % 2:
        raise ValueError('interior_pages must be an even integer of at least 2')
    return [('front', 'single'), ('P01', 'single')] + [
        (f'spread_{i:02d}', 'spread') for i in range(1, n // 2)
    ] + [(f'P{n:02d}', 'single'), ('back', 'single')]


def validate(book):
    order = artwork_order(book['interior_pages'])
    for key in ('trim_mm', 'bleed_mm', 'safe_mm'):
        v = book[key]
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError(f'{key} must be a finite non-negative number')
    if book['trim_mm'] <= 0 or book['safe_mm'] >= book['trim_mm'] / 2:
        raise ValueError('trim_mm must be positive and safe_mm less than half trim_mm')
    if type(book['printer_profile_confirmed']) is not bool:
        raise ValueError('printer_profile_confirmed must be boolean')
    if [(a['id'], a['kind']) for a in book['artwork']] != order:
        raise ValueError('artwork must follow front, P01, continuous spreads, last page, back')
    for art in book['artwork']:
        p = Path(art['file'])
        if p.is_absolute() or '..' in p.parts or p.parts[0] != 'assets' or p.suffix.lower() != '.png':
            raise ValueError('artwork files must be project-local assets/*.png')
        if not isinstance(art['expected_text'], list) or not all(isinstance(s, str) for s in art['expected_text']):
            raise ValueError('expected_text must be an array of strings')


def init_project(project, interior_pages=24):
    project = Path(project)
    artwork_order(interior_pages)
    if (project / 'book.json').exists():
        raise FileExistsError('book.json already exists; init never overwrites it')
    template = Path(__file__).resolve().parent.parent / 'assets/book.template.json'
    book = json.loads(template.read_text('utf-8'))
    if interior_pages != book['interior_pages']:
        book['interior_pages'] = interior_pages
        book['artwork'] = [dict(id=i, kind=k, file=f'assets/{i}.png', expected_text=[]) for i, k in artwork_order(interior_pages)]
    validate(book)
    for folder in ('assets', 'qa', 'source'):
        (project / folder).mkdir(parents=True, exist_ok=True)
    with (project / 'book.json').open('x', encoding='utf-8') as f:
        f.write(json.dumps(book, ensure_ascii=False, indent=2) + '\n')
    return book


def load_book(project):
    book = json.loads((project / 'book.json').read_text('utf-8'))
    validate(book)
    return book


def source_info(project, book):
    result = {}
    for a in book['artwork']:
        path = (project / a['file']).resolve()
        if not path.is_relative_to((project / 'assets').resolve()):
            raise ValueError('source resolves outside project assets')
        with Image.open(path) as im:
            im.load()
            ratio = 2 if a['kind'] == 'spread' else 1
            if im.format != 'PNG' or abs(im.width / im.height / ratio - 1) > .01:
                raise ValueError(f'{a["id"]}: expected PNG with aspect ratio {ratio}:1')
            result[a['id']] = dict(file=a['file'], sha256=sha(path), pixels=list(im.size), mode=im.mode)
    return result


def page_sequence(book):
    n = book['interior_pages']
    pages = [('front', None, 0), ('P01', 1, 0)]
    for i in range(1, n // 2):
        pages.extend([(f'spread_{i:02d}', i * 2, 0), (f'spread_{i:02d}', i * 2 + 1, 1)])
    return pages + [(f'P{n:02d}', n, 0), ('back', None, 0)]


def specs(book):
    pages, t, b = page_sequence(book), book['trim_mm'], book['bleed_mm']
    size = t + b * 2
    def single(p):
        return dict(artwork_id=p[0], folios=[] if p[1] is None else [str(p[1])], media_mm=[0, 0, size, size], trim_mm=[b, b, b+t, b+t], bleed_mm=[0, 0, size, size])
    output = {'print.pdf': list(map(single, pages)), 'interior_print.pdf': list(map(single, pages[1:-1])), 'covers_print.pdf': list(map(single, [pages[0], pages[-1]]))}
    preview = []
    for j, a in enumerate(book['artwork']):
        width = t if j in (0, len(book['artwork'])-1) else 2*t
        folios = [str(p[1]) for p in pages if p[0] == a['id'] and p[1] is not None]
        preview.append(dict(artwork_id=a['id'], folios=folios, media_mm=[0, 0, width, t], trim_mm=[0, 0, width, t], bleed_mm=[0, 0, width, t]))
    output['preview.pdf'] = preview
    return output


def save_subset(reader, indexes, target, book):
    writer = PdfWriter()
    t, b = book['trim_mm'] * MM, book['bleed_mm'] * MM
    for i in indexes:
        page = writer.add_page(reader.pages[i])
        page.trimbox = RectangleObject([b, b, b+t, b+t])
        page.bleedbox = RectangleObject(list(page.mediabox))
    with target.open('wb') as f:
        writer.write(f)


def export_project(project):
    project = Path(project).resolve()
    book = load_book(project)
    sources, sequence = source_info(project, book), page_sequence(book)
    font = Path(reportlab.__file__).parent / 'fonts/Vera.ttf'
    pdfmetrics.registerFont(TTFont('PageNumber', str(font)))
    t, b, safe = (book[k] * MM for k in ('trim_mm', 'bleed_mm', 'safe_mm'))
    size, buffer = t + 2*b, io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(size, size), pageCompression=1)
    for art_id, number, side in sequence:
        spread = art_id.startswith('spread_')
        width = size * (2 if spread else 1)
        # The two trim regions meet at one source coordinate; gutter bleed overlaps.
        x = -b-side*t if spread else 0
        c.drawImage(str(project / sources[art_id]['file']), x, 0, width, size)
        if number is not None:
            c.setFont('PageNumber', 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(b + (t-safe if number % 2 else safe), b+safe, str(number))
        c.showPage()
    c.save()
    reader = PdfReader(buffer)
    for name, indexes in [('print.pdf', range(len(sequence))), ('interior_print.pdf', range(1, len(sequence)-1)), ('covers_print.pdf', [0, len(sequence)-1])]:
        save_subset(reader, indexes, project / name, book)
    with fitz.open(project / 'print.pdf') as src, fitz.open() as preview:
        for j, a in enumerate(book['artwork']):
            cover = j in (0, len(book['artwork'])-1)
            p = preview.new_page(width=t if cover else 2*t, height=t)
            indexes = [i for i, item in enumerate(sequence) if item[0] == a['id']]
            for half, i in enumerate(indexes):
                x = t if a['id'] == 'P01' else half*t
                p.show_pdf_page(fitz.Rect(x, 0, x+t, t), src, i, clip=fitz.Rect(b, b, b+t, b+t))
            p.set_trimbox(p.rect)
            p.set_bleedbox(p.rect)
        preview.save(project / 'preview.pdf', garbage=4, deflate=True)
    expected = specs(book)
    outputs = {}
    for name in NAMES:
        data = inspect_pdf(project / name)
        for page, spec in zip(data['pages'], expected[name]):
            page['artwork_id'] = spec['artwork_id']
        outputs[name] = dict(sha256=sha(project/name), **data)
    manifest = dict(schema_version=1, book_sha256=sha(project/'book.json'), sources=sources, outputs=outputs, raster_text_note=RASTER_NOTE, image_policy='Original PNG pixels embedded; physical enlargement covers bleed; no pixel upsampling.')
    write_json(project / 'qa/export_manifest.json', manifest)
    return manifest


def inspect_pdf(path):
    result = []
    with fitz.open(path) as pdf:
        reader = PdfReader(path)
        for i, page in enumerate(pdf):
            boxes = {k+'_mm': [round(float(x)/MM, 4) for x in getattr(reader.pages[i], k+'box')] for k in ('media', 'trim', 'bleed')}
            images = []
            for im in page.get_image_info(hashes=True, xrefs=True):
                a, b, c, d, e, f = im['transform']
                x, y = math.hypot(a, b), math.hypot(c, d)
                images.append(dict(pixels=[im['width'], im['height']], transform_pt=list(im['transform']), placement_mm=[round(v/MM, 4) for v in im['bbox']], ppi=[round(im['width']*72/x, 4) if x else 0, round(im['height']*72/y, 4) if y else 0], digest=im['digest'].hex()))
            spans = [s for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for s in line['spans'] if s['text'].strip()]
            fonts = page.get_fonts(full=True)
            embedded = all(abs(s['size']-10) < .05 and any(f[3].split('+')[-1] == s['font'].split('+')[-1] and bool(pdf.extract_font(f[0])[3]) for f in fonts) for s in spans)
            result.append(dict(**boxes, images=images, folios=[s['text'].strip() for s in spans], page_number_fonts_embedded=embedded))
    return dict(page_count=len(result), pages=result)


def compare_renders(left, right, clip=None, dpi=96):
    """Render full pages from one origin, then crop on one integer pixel grid."""
    if tuple(left.rect) != tuple(right.rect):
        raise ValueError('comparison requires matching page rectangles; never resize images')
    scale = dpi / 72
    ims = []
    for page in (left, right):
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        if clip is not None:
            r = fitz.Rect(clip) & page.rect
            if r.is_empty:
                raise ValueError('comparison clip is empty')
            im = im.crop((math.floor(r.x0*scale), math.floor(r.y0*scale), math.ceil(r.x1*scale), math.ceil(r.y1*scale)))
        ims.append(im)
    diff = ImageChops.difference(*ims)
    changed = sum(count for count, value in diff.getcolors(diff.width*diff.height) if any(value))
    return dict(pixels=list(diff.size), changed_pixels=changed, mean_absolute_difference=sum(ImageStat.Stat(diff).mean)/3)


def check_project(project):
    project = Path(project).resolve()
    errors, blockers, pdfs = [], [], {}
    report = dict(technical_consistent=False, print_ready=False, technical_errors=errors, production_blockers=blockers, pdfs=pdfs, page_numbers_embedded=False, per_image_text_reviewed=False, raster_text_note=RASTER_NOTE)
    try:
        book = load_book(project)
        sources = source_info(project, book)
        manifest = json.loads((project/'qa/export_manifest.json').read_text('utf-8'))
        if manifest.get('book_sha256') != sha(project/'book.json'):
            errors.append('book.json changed since export')
        if manifest.get('sources') != sources:
            errors.append('source hashes/pixels changed since export')
        if not book['printer_profile_confirmed']:
            blockers.append('Printer profile has not been confirmed')
        for key in ('color_profile', 'binding'):
            if not isinstance(book.get(key), str) or book[key].strip().lower() in ('', 'unknown', 'unconfirmed'):
                blockers.append(f'{key} is unknown')
        if book.get('in_image_text_reviewed') is not True:
            blockers.append('In-image text and safe-area placement require visual review')
        review_errors = text_review_blockers(project, book, sources)
        blockers.extend(review_errors)
        report['per_image_text_reviewed'] = not review_errors
        expected = specs(book)
        for name in NAMES:
            try:
                path = project/name
                data = inspect_pdf(path)
                pdfs[name] = data
                if len(data['pages']) != len(expected[name]):
                    errors.append(f'{name}: page count mismatch')
                for i, (p, spec) in enumerate(zip(data['pages'], expected[name])):
                    p['artwork_id'] = spec['artwork_id']
                    for key in ('media_mm', 'trim_mm', 'bleed_mm'):
                        if any(abs(x-y) > .02 for x, y in zip(p[key], spec[key])):
                            errors.append(f'{name} page {i+1}: {key} mismatch')
                    if p['folios'] != spec['folios'] or not p['page_number_fonts_embedded']:
                        errors.append(f'{name} page {i+1}: folio/font mismatch')
                    image_count = 2 if name == 'preview.pdf' and spec['artwork_id'].startswith('spread_') else 1
                    if len(p['images']) != image_count:
                        errors.append(f'{name} page {i+1}: image count mismatch')
                    if any(min(im['ppi']) < 300 for im in p['images']):
                        blockers.append(f'{name} page {i+1}: actual image PPI below 300')
                actual = dict(sha256=sha(path), **data)
                if manifest.get('outputs', {}).get(name) != actual:
                    errors.append(f'{name}: exported hash/measurements mismatch')
            except Exception as exc:
                errors.append(f'{name}: {exc}')
        if not errors:
            with fitz.open(project/'print.pdf') as full:
                for name, indexes in [('interior_print.pdf', range(1, len(full)-1)), ('covers_print.pdf', [0, len(full)-1])]:
                    with fitz.open(project/name) as part:
                        for j, i in enumerate(indexes):
                            if compare_renders(full[i], part[j])['changed_pixels']:
                                errors.append(f'{name} page {j+1}: rendered content differs')
        report['page_numbers_embedded'] = bool(pdfs) and len(pdfs) == 4 and all(p['page_number_fonts_embedded'] for d in pdfs.values() for p in d['pages'])
    except Exception as exc:
        errors.append(f'Current project cannot be verified: {exc}')
    report['technical_consistent'] = not errors
    report['print_ready'] = not errors and not blockers
    write_json(project/'qa/preflight.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'export', 'check'):
        p = sub.add_parser(name)
        p.add_argument('--project', type=Path, required=True)
        if name == 'init':
            p.add_argument('--interior-pages', type=int, default=24)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            init_project(args.project, args.interior_pages)
            print('Created book.json and assets/, source/, qa/. Supply raster PNG artwork before export.')
        elif args.command == 'export':
            export_project(args.project)
            print('Exported four PDFs and qa/export_manifest.json. Run check before production.')
        else:
            report = check_project(args.project)
            print(json.dumps({k: report[k] for k in ('technical_consistent', 'print_ready', 'technical_errors', 'production_blockers')}, ensure_ascii=False))
            return 0 if report['print_ready'] else 2
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
