"""Spatial Chinese OCR matching, independent of any named book or project."""
from collections import Counter
import difflib, math, unicodedata
PT_MM=72/25.4
PUNCTUATION_EQUIVALENTS=str.maketrans({',':'，','.':'。','!':'！','?':'？',':':'：',';':'；',chr(8220):chr(34),chr(8221):chr(34),chr(8216):chr(39),chr(8217):chr(39)})

def content(text):
    """Keep Han characters and digits; never convert traditional to simplified."""
    result = []
    for char in text:
        code = ord(char)
        if 0x3400 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0x20000 <= code <= 0x323AF:
            result.append(char)
        elif char.isdigit():
            result.append(unicodedata.normalize("NFKC", char))
    return "".join(result)


def punctuation(text):
    return "".join(char for char in text if unicodedata.category(char).startswith("P"))


def differences(expected, observed):
    wanted, found = Counter(expected), Counter(observed)
    return {"missing": dict(sorted((wanted-found).items())), "extras": dict(sorted((found-wanted).items()))}


def best_substring(expected, observed):
    """Semi-global edit alignment: expected against its best observed substring.

    Whole OCR boxes may contain two sentences, so surrounding recognized text
    is retained globally but does not count against an individual sentence.
    """
    if not expected:
        return {"distance": 0, "start": 0, "end": 0, "text": ""}
    if expected in observed:
        start = observed.index(expected)
        return {"distance": 0, "start": start, "end": start+len(expected), "text": expected}
    table = [list(range(1)) + [0]*len(observed)]
    for i, char in enumerate(expected, 1):
        row = [i]
        for j, other in enumerate(observed, 1):
            row.append(min(table[i-1][j]+1, row[j-1]+1, table[i-1][j-1]+(char != other)))
        table.append(row)
    end = min(range(len(observed)+1), key=lambda j: (table[-1][j], abs(j-len(expected))))
    i, j = len(expected), end
    while i:
        if j and table[i][j] == table[i-1][j-1]+(expected[i-1] != observed[j-1]):
            i, j = i-1, j-1
        elif table[i][j] == table[i-1][j]+1:
            i -= 1
        else:
            j -= 1
    return {"distance": table[-1][end], "start": j, "end": end, "text": observed[j:end]}


def box_join_cost(a, b):
    """Plausible left-to-right or top-to-bottom neighbor, in native pixels."""
    ax0, ay0, ax1, ay1 = a["bbox_px"]
    bx0, by0, bx1, by1 = b["bbox_px"]
    height = max(ay1-ay0, by1-by0, 1.)
    vertical_centers = abs((ay0+ay1-by0-by1)/2)
    if bx0 >= ax1-.25*height and vertical_centers <= .65*height:
        gap = max(0., bx0-ax1)
        if gap <= 5*height:
            return gap/height+vertical_centers/height
    overlap = max(0., min(ax1, bx1)-max(ax0, bx0))
    width = max(1., min(ax1-ax0, bx1-bx0))
    if by0 >= ay0+.4*height and by0-ay1 <= 3.5*height and (overlap/width >= .2 or abs(ax0-bx0) <= height):
        return max(0., by0-ay1)/height+abs(ax0-bx0)/(height*3)+1
    return None


def candidate_paths(blocks, max_chars):
    """Bounded spatial paths; no page-wide text/column ordering assumption."""
    usable = [b for b in blocks if b["content"]]
    by_id = {b["id"]: b for b in usable}
    neighbors = {}
    for a in usable:
        candidates = [(box_join_cost(a, b), b["id"]) for b in usable if a is not b]
        neighbors[a["id"]] = [identifier for cost, identifier in sorted((cost, identifier) for cost, identifier in candidates
                                                                     if cost is not None)[:5]]
    paths = {}
    for start in usable:
        frontier = [(start["id"],)]
        for _ in range(min(12, max_chars)):
            if not frontier:
                break
            following = []
            for identifiers in frontier:
                text = "".join(by_id[identifier]["content"] for identifier in identifiers)
                paths[identifiers] = {"ids": list(identifiers), "text": text,
                                      "raw_text": "".join(by_id[i]["text"] for i in identifiers),
                                      "confidence_min": min(by_id[i]["confidence"] for i in identifiers)}
                if len(text) < max_chars+16:
                    following.extend(identifiers+(identifier,) for identifier in neighbors[identifiers[-1]] if identifier not in identifiers)
            frontier = following[:60]
    return list(paths.values())


def match_sentences(segments, blocks):
    candidates = candidate_paths(blocks, max((len(content(s["text"])) for s in segments), default=1))
    matches = []
    for segment in segments:
        wanted = content(segment["text"])
        best = None
        for candidate in candidates:
            alignment = best_substring(wanted, candidate["text"])
            rank = (alignment["distance"], len(candidate["ids"]), -candidate["confidence_min"],
                    len(candidate["text"])-len(alignment["text"]))
            if best is None or rank < best[0]:
                best = (rank, candidate, alignment)
        candidate = best[1] if best else {"ids": [], "raw_text": "", "confidence_min": None}
        alignment = best[2] if best else {"distance": len(wanted), "text": "", "start": 0, "end": 0}
        observed = alignment["text"]
        edits = [{"operation": tag, "expected": wanted[i:j], "ocr": observed[k:l]}
                 for tag, i, j, k, l in difflib.SequenceMatcher(None, wanted, observed, autojunk=False).get_opcodes() if tag != "equal"]
        matches.append({**segment, "expected_content": wanted, "best_ocr_content": observed,
                        "source_block_ids": candidate["ids"], "source_raw_text": candidate["raw_text"],
                        "minimum_source_confidence": candidate["confidence_min"], "edit_distance": alignment["distance"],
                        "content_match": bool(wanted) and alignment["distance"] == 0,
                        "requires_visual_review": not wanted or alignment["distance"] != 0,
                        "character_differences": differences(wanted, observed), "edit_operations": edits})
    return matches


def font_height_estimate(quad, image_size, placement):
    width, height = image_size
    sx, sy = placement[0]*PT_MM/width, placement[1]*PT_MM/height
    sides = [(quad[2][0]-quad[1][0], quad[2][1]-quad[1][1]),
             (quad[3][0]-quad[0][0], quad[3][1]-quad[0][1])]
    native_height = sum(math.hypot(x, y) for x, y in sides)/2
    placed_height = sum(math.hypot(x*sx, y*sy) for x, y in sides)/2
    return {"native_detected_line_height_px": round(native_height, 3),
            "detected_line_height_at_placement_pt": round(placed_height, 3),
            "estimated_font_size_pt_range": [round(placed_height*.8, 2), round(placed_height*1.6, 2)],
            "precision": "heuristic_only_not_an_exact_font_size",
            "assumption": "OCR line box may include padding; point-size range is 0.8..1.6 times detected line height"}


def compare(segments, blocks, confidence_threshold=.85):
    wanted = "\n".join(segment["text"] for segment in segments)
    observed = "\n".join(block["text"] for block in blocks)
    counts = differences(content(wanted), content(observed))
    sentences = match_sentences(segments, blocks)
    raw_punctuation = differences(punctuation(wanted), punctuation(observed))
    normalized_punctuation = differences(punctuation(wanted).translate(PUNCTUATION_EQUIVALENTS),
                                         punctuation(observed).translate(PUNCTUATION_EQUIVALENTS))
    low_confidence = [block["id"] for block in blocks if block["confidence"] < confidence_threshold]
    unexpected = [{"block_id": block["id"], "text": "".join(char for char in block["text"]
                  if not char.isspace() and not content(char) and not unicodedata.category(char).startswith("P"))}
                  for block in blocks]
    unexpected = [entry for entry in unexpected if entry["text"]]
    content_match = bool(blocks) and not counts["missing"] and not counts["extras"] and all(s["content_match"] for s in sentences)
    punctuation_review = bool(normalized_punctuation["missing"] or normalized_punctuation["extras"])
    review = not content_match or punctuation_review or bool(low_confidence or unexpected)
    return {"ocr_content_match": content_match, "requires_visual_review": review,
            "interpretation": "OCR differences are candidates for visual review, not confirmed mistakes in the image",
            "content_character_frequency": {"expected_count": len(content(wanted)), "ocr_count": len(content(observed)), **counts},
            "sentence_matches": sentences,
            "punctuation_comparison": {"raw": raw_punctuation, "typographic_variants_normalized": normalized_punctuation,
                                       "requires_visual_review": punctuation_review, "affects_han_digit_content_match": False},
            "space_comparison": {"expected_whitespace_count": sum(c.isspace() for c in wanted),
                                 "ocr_whitespace_count": sum(c.isspace() for c in observed), "affects_han_digit_content_match": False},
            "low_confidence_block_ids": low_confidence, "confidence_review_threshold": confidence_threshold,
            "unmodeled_ocr_characters": unexpected}


