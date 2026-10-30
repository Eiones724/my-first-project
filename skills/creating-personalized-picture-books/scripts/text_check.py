"""OCR image lettering against book.json; differences require visual review.

Run: python text_check.py --project BOOK_DIR [--image ARTWORK_ID]
Requires rapidocr_onnxruntime in addition to requirements.txt.
Never edits artwork, expected text, or an existing human review.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from text_algorithms import compare, content


def expected_digest(lines):
    return hashlib.sha256(json.dumps(lines,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def safety_estimate(bbox,pixels,kind,book):
    trim=book['trim_mm'];bleed=book['bleed_mm'];safe=book['safe_mm']
    width=(trim+2*bleed)*(2 if kind=='spread' else 1)
    offset=2*bleed if kind=='spread' else bleed
    x0,y0,x1,y1=bbox
    x0=x0*width/pixels[0]-offset;x1=x1*width/pixels[0]-offset
    y0=y0*(trim+2*bleed)/pixels[1]-bleed;y1=y1*(trim+2*bleed)/pixels[1]-bleed
    crosses=kind=='spread' and x0<trim<x1
    half=trim if kind=='spread' and (x0+x1)/2>=trim else 0
    margins=[x0-half,y0,half+trim-x1,trim-y1]
    return {'trim_bbox_mm':[round(v,3) for v in (x0,y0,x1,y1)],
            'minimum_edge_mm':round(min(margins),3),'crosses_gutter':crosses,
            'requires_visual_review':crosses or min(margins)<safe,
            'precision':'OCR boxes only; verify true text and disregard documented texture false positives'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--image',help='One artwork id; omitted means all artwork')
    args=parser.parse_args()
    root=args.project.resolve()
    config=json.loads((root/'book.json').read_text('utf-8-sig'))
    items=[a for a in config['artwork'] if not args.image or a['id']==args.image]
    if not items:parser.error('No artwork matches --image')
    engine=None
    reports=[]
    for item in items:
        path=(root/item['file']).resolve()
        if not path.is_relative_to(root):raise ValueError('Keep artwork inside project directory')
        expected=item.get('expected_text',[])
        if not isinstance(expected,list) or any(not isinstance(line,str) for line in expected):
            raise ValueError('expected_text must be a list of authored strings')
        row={'id':item['id'],'file':item['file'],'expected_text':expected,
             'expected_text_sha256':expected_digest(expected)}
        if not path.is_file():
            reports.append({**row,'status':'missing_image','ocr_content_match':False,'requires_visual_review':True});continue
        data=path.read_bytes();row['image_sha256']=hashlib.sha256(data).hexdigest()
        if not expected or not any(line.strip() for line in expected):
            reports.append({**row,'status':'missing_expected_text','ocr_content_match':False,'requires_visual_review':True});continue
        if engine is None:
            from rapidocr_onnxruntime import RapidOCR
            engine=RapidOCR(text_score=0.,intra_op_num_threads=2,inter_op_num_threads=1)
        result,_=engine(data,text_score=0.)
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as im:pixels=list(im.size)
        blocks=[]
        for i,(quad,text,confidence) in enumerate(result or [],1):
            xs,ys=zip(*quad)
            bbox=[float(min(xs)),float(min(ys)),float(max(xs)),float(max(ys))]
            blocks.append({'id':i,'text':str(text),'content':content(str(text)),
                           'confidence':float(confidence),'quad_px':[[float(x),float(y)] for x,y in quad],
                           'bbox_px':bbox,'safety_estimate':safety_estimate(bbox,pixels,item['kind'],config)})
        segments=[{'id':str(i),'role':'authored','text':line} for i,line in enumerate(expected,1) if line.strip()]
        comparison=compare(segments,blocks)
        unchanged=hashlib.sha256(path.read_bytes()).hexdigest()==row['image_sha256']
        review=comparison['requires_visual_review'] or not unchanged or any(b['safety_estimate']['requires_visual_review'] for b in blocks)
        reports.append({**row,'status':'requires_visual_review' if review else 'ocr_text_match',
                        'ocr_content_match':comparison['ocr_content_match'],'requires_visual_review':review,
                        'source_changed_during_check':not unchanged,'recognized_blocks':blocks,'comparison':comparison})
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'mode':'single' if args.image else 'all',
            'images_checked':len(reports),'all_expected_images_checked':len(items)==len(config['artwork']),
            'ocr_pass':all(r['ocr_content_match'] and not r['requires_visual_review'] for r in reports),
            'font_embedding_assessed':False,'exact_font_sizes_assessed':False,
            'interpretation':'OCR mismatches are review candidates, not confirmed errors. No production approval.',
            'images':reports}
    out=root/'qa';out.mkdir(exist_ok=True)
    filename='ocr.json' if not args.image else 'ocr_'+args.image+'.json'
    (out/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:report[k] for k in ['images_checked','all_expected_images_checked','ocr_pass']}))
    return 0 if report['ocr_pass'] else 2


if __name__=='__main__':raise SystemExit(main())
