import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns

SOURCE_TEXT = "text"
SOURCE_HTML = "html"
SOURCE_NER = "ner"

LEVEL_REQUIRED = "required"
LEVEL_PREFERRED = "preferred"

NHAN_COMPANY       = "COMPANY"
NHAN_POSITION      = "POSITION"
NHAN_LOCATION      = "LOCATION"
NHAN_SALARY        = "SALARY"
NHAN_EXPERIENCE    = "EXPERIENCE"
NHAN_DEGREE        = "DEGREE"
NHAN_CERTIFICATE   = "CERTIFICATE"
NHAN_SKILL         = "SKILL"
NHAN_SKILL_GROUP   = "SKILL_GROUP"
NHAN_DEADLINE      = "DEADLINE"
NHAN_BENEFIT       = "BENEFIT"

_DIR = Path(__file__).resolve().parent / "Kho_tri_thuc"


def _load_json(path: Path, required: bool = True) -> dict:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Không tìm thấy file knowledge: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_canonical_to_alias(data: dict, include_canonical: bool = True) -> dict:
    out = {}
    for canonical, aliases in (data or {}).items():
        if include_canonical and canonical:
            out[str(canonical).strip().lower()] = canonical
        for alias in aliases or []:
            if isinstance(alias, str) and alias.strip():
                out[alias.strip().lower()] = canonical
    return out


def _invert_group_to_skill(data: dict) -> dict:
    out = {}
    for group, skills in (data or {}).items():
        for skill in skills or []:
            if isinstance(skill, str) and skill.strip():
                key = skill.strip().lower()
                if key not in out:
                    out[key] = group
    return out


def _merge_alias_into_kb(kb: dict, alias_map: dict) -> dict:
    merged = dict(kb)
    for alias, canonical in alias_map.items():
        cl = canonical.lower()
        if cl in kb and alias not in merged:
            merged[alias] = kb[cl]
    return merged


def _filter_alias_by_canonicals(alias_map: dict, canonicals: set) -> dict:
    canon_lower = {c.lower() for c in canonicals}
    out = {}
    for alias, canonical in alias_map.items():
        if canonical.lower() in canon_lower:
            out[alias] = canonical
    return out


ALIAS_MAC_DINH = _flatten_canonical_to_alias(
    _load_json(_DIR / "alias_knowledge.json")
)

TU_DIEN_DIA_DIEM_MAC_DINH = _flatten_canonical_to_alias(
    _load_json(_DIR / "location_knowledge.json")
)

_skill_raw = _load_json(_DIR / "skill_knowledge.json")
KB_SKILL_TO_GROUP_MAC_DINH = _invert_group_to_skill(_skill_raw)

SKILL_CANONICALS = {
    s.strip()
    for skills in _skill_raw.values()
    for s in skills or []
    if isinstance(s, str) and s.strip()
}
GROUP_CANONICALS = set(_skill_raw.keys())

TU_DIEN_SKILL_MAC_DINH = {s.lower(): s for s in SKILL_CANONICALS}
TU_DIEN_SKILL_MAC_DINH.update(
    _filter_alias_by_canonicals(ALIAS_MAC_DINH, SKILL_CANONICALS)
)

TU_DIEN_GROUP_MAC_DINH = {g.lower(): g for g in GROUP_CANONICALS}
TU_DIEN_GROUP_MAC_DINH.update(
    _filter_alias_by_canonicals(ALIAS_MAC_DINH, GROUP_CANONICALS)
)

_certi_raw = _load_json(_DIR / "certi_knowledge.json")
CHUNG_CHI_KB   = {}
CERTI_CANONICAL = {}

for _type, _certs in _certi_raw.items():
    for _c in _certs or []:
        if isinstance(_c, str) and _c.strip():
            _canon = _c.strip()
            _key   = _canon.lower()
            CHUNG_CHI_KB[_key]    = _type
            CERTI_CANONICAL[_key] = _canon

for _alias, _canon in ALIAS_MAC_DINH.items():
    _cl = _canon.lower()
    if _cl in CHUNG_CHI_KB and _alias not in CHUNG_CHI_KB:
        CHUNG_CHI_KB[_alias]    = CHUNG_CHI_KB[_cl]
        CERTI_CANONICAL[_alias] = CERTI_CANONICAL[_cl]

_degree_raw = _load_json(_DIR / "degree_knowledge.json")
BANG_CAP_MAP = _merge_alias_into_kb(
    _flatten_canonical_to_alias(_degree_raw.get("level", {})),
    ALIAS_MAC_DINH,
)

TU_DIEN_BENEFIT_MAC_DINH = _merge_alias_into_kb(
    _flatten_canonical_to_alias(_load_json(_DIR / "benefit_knowledge.json")),
    ALIAS_MAC_DINH,
)

_section_raw = _load_json(_DIR / "Section_knowledge.json")
SECTION_HEADERS: Dict[str, str] = {}
for _sec, _aliases in _section_raw.items():
    for _a in _aliases or []:
        if isinstance(_a, str) and _a.strip():
            SECTION_HEADERS[_a.strip().lower()] = _sec

TEN_GROUP_OTHER = "Other"

def tao_template_rong(job_id) -> dict:
    return {
        "task_id": job_id,
        "company": {"raw": None, "name": None, "source": None},
        "position": {"raw": None, "title": None, "source": None},
        "locations": [],
        "salary": {"raw": None, "type": None, "min": None, "max": None,
                   "currency": None, "period": None},
        "experience": [],
        "degree": [],
        "certificates": [],
        "skill_groups": [],
        "deadline": {"raw": None, "type": None, "date": None, "source": None},
        "benefits": [],
    }


def tao_location(raw=None, city=None, address=None, source=None) -> dict:
    return {"raw": raw, "city": city, "address": address, "source": source}


def tao_experience(raw=None, min_years=None, max_years=None, domains=None,
                   level=None, related_ok=False) -> dict:
    return {"raw": raw, "min_years": min_years, "max_years": max_years,
            "domains": domains or [], "level": level, "related_ok": related_ok}


def tao_degree(degree_raw=None, degree_level=None, majors=None,
               related_ok=False, level=None) -> dict:
    return {"degree_raw": degree_raw, "degree_level": degree_level,
            "majors": majors or [], "related_ok": related_ok, "level": level}


def tao_certificate(type_=None, detail=None, level=None, related_ok=False) -> dict:
    return {"type": type_, "detail": detail or [],
            "level": level, "related_ok": related_ok}


def tao_skill(name=None, raw=None, level=None, source=SOURCE_NER) -> dict:
    return {"name": name, "raw": raw, "level": level, "source": source}


def tao_skill_group(name=None, level=None, source=None, related_ok=False,
                    skills=None) -> dict:
    return {"name": name, "level": level, "source": source,
            "related_ok": related_ok, "skills": skills or []}


def tao_benefit(raw=None, category=None) -> dict:
    return {"raw": raw, "category": category}


def _parse_so(s: str) -> float:
    s = s.strip()
    if re.match(r"^\d{1,3}([.,]\d{3})+$", s):
        return float(re.sub(r"[.,]", "", s))
    if re.match(r"^\d+[.,]\d+$", s):
        return float(s.replace(",", "."))
    return float(s)


def _int_if_whole(x):
    if x is None:
        return None
    return int(x) if float(x) == int(x) else x

def chuan_hoa_ten_group(raw: str, tu_dien: dict = None) -> str:
    if not raw:
        return raw
    d = {**TU_DIEN_GROUP_MAC_DINH, **(tu_dien or {})}
    return d.get(raw.strip().lower(), raw.strip())

def chuan_hoa_luong(raw: str) -> dict:
    result = {"type": None, "min": None, "max": None,
              "currency": None, "period": "month"}
    if not raw:
        return result
    s = raw.lower().strip()

    has_number = bool(re.search(r"\d", s))
    competitive_kw = (
        "cạnh tranh", "competitive", "hấp dẫn", "attractive",
        "thỏa thuận", "thương lượng", "negotiable", "theo năng lực",
    )
    if not has_number:
        if any(k in s for k in competitive_kw):
            result["type"] = "negotiable"
            result["currency"] = "VND"
        return result

    if any(k in s for k in ("usd", "$", "đô la", "dollar", "us$", "u$")):
        currency = "USD"
    elif any(k in s for k in ("eur", "€", "euro")):
        currency = "EUR"
    elif any(k in s for k in ("jpy", "¥", "yên nhật")):
        currency = "JPY"
    else:
        currency = "VND"
    result["currency"] = currency

    if re.search(r"[/\\]\s*năm|per\s+year|yearly|\bannual\b|hàng năm", s):
        result["period"] = "year"
    elif re.search(r"[/\\]\s*tuần|per\s+week|weekly|hàng tuần", s):
        result["period"] = "week"
    elif re.search(r"[/\\]\s*ngày|per\s+day|daily|hàng ngày", s):
        result["period"] = "day"
    elif re.search(r"[/\\]\s*giờ|per\s+hour|hourly|hàng giờ", s):
        result["period"] = "hour"

    mult = 1
    if re.search(
        r"\d\s*(triệu|trieu|million|mil|tr|m)\b|(triệu|trieu|million)\b", s
    ):
        mult = 1_000_000
    elif re.search(r"\d\s*(tỷ|ty|billion|bil)\b|(tỷ|billion)\b", s):
        mult = 1_000_000_000
    elif re.search(r"\d\s*(nghìn|ngàn|thousand|k)\b", s):
        mult = 1_000

    num_pattern = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
    nums = []
    for ns in re.findall(num_pattern, s):
        try:
            nums.append(_parse_so(ns))
        except ValueError:
            continue
    if not nums:
        if any(k in s for k in competitive_kw):
            result["type"] = "negotiable"
        return result

    def _apply(num: float) -> int:
        if mult > 1:
            return int(round(num * mult))
        if currency == "VND" and 0 < num < 1000:
            return int(round(num * 1_000_000))
        return int(round(num))

    if len(nums) >= 2:
        mn, mx = _apply(nums[0]), _apply(nums[1])
        if mn > mx:
            mn, mx = mx, mn
        result["type"] = "range"
        result["min"], result["max"] = mn, mx
        return result

    v = _apply(nums[0])
    if any(k in s for k in ("tối thiểu", "ít nhất", "trở lên", "min", "+")):
        result["type"] = "from"
        result["min"] = v
    elif any(k in s for k in ("từ", "from", "trên")):
        result["type"] = "from"
        result["min"] = v
    elif any(k in s for k in (
        "up to", "lên đến", "đến", "tối đa", "max",
        "dưới", "không quá", "≤", "<=",
    )):
        result["type"] = "up_to"
        result["max"] = v
    else:
        result["type"] = "exact"
        result["min"] = result["max"] = v

    return result


def chuan_hoa_kinh_nghiem(raw: str) -> dict:
    result = {"min_years": None, "max_years": None}
    if not raw:
        return result
    s = raw.lower()

    m = re.search(r"(\d+)\s*năm\s*(?:và\s*)?(\d+)\s*tháng", s)
    if m:
        v = int(m.group(1)) + int(m.group(2)) / 12
        v = round(v, 2)
        result["min_years"] = result["max_years"] = v
        return result

    m = re.search(r"(\d+)\s*năm\s*rưỡi", s)
    if m:
        v = int(m.group(1)) + 0.5
        result["min_years"] = result["max_years"] = v
        return result

    has_year  = ("năm" in s) or ("year" in s)
    has_month = ("tháng" in s) or ("month" in s)

    raw_nums = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?", s)
    nums = []
    for n in raw_nums:
        try:
            nums.append(_parse_so(n))
        except ValueError:
            pass

    if not nums:
        return result

    if has_month and not has_year:
        nums = [n / 12 for n in nums]

    if len(nums) >= 2:
        result["min_years"] = _int_if_whole(nums[0])
        result["max_years"] = _int_if_whole(nums[1])
        return result

    min_kw = ("ít nhất", "tối thiểu", "trở lên", "trên", "hơn", "từ",
              "min", "+", "≥", ">=", ">")
    max_kw = ("tối đa", "không quá", "dưới", "nhỏ hơn", "up to", "max",
              "≤", "<=", "<")

    v = _int_if_whole(nums[0])
    if any(k in s for k in min_kw):
        result["min_years"] = v
    elif any(k in s for k in max_kw):
        result["max_years"] = v
    else:
        result["min_years"] = result["max_years"] = v

    return result


def _build_location_lookup(tu_dien: dict = None):
    base = {**TU_DIEN_DIA_DIEM_MAC_DINH, **(tu_dien or {})}
    compact, word = {}, {}
    for k, v in base.items():
        k_low = k.lower().strip()
        k_compact = re.sub(r"[\s.]+", "", k_low)
        compact[k_compact] = v
        word[k_low] = v
    return compact, word

def _tra_city(segment: str, compact: dict, word: dict) -> Optional[str]:
    if not segment:
        return None
    s = segment.lower().strip()

    s_compact = re.sub(r"[\s.]+", "", s)
    if s_compact in compact:
        return compact[s_compact]

    s_norm = re.sub(r"\s+", " ", s).strip()
    best_key, best_val = None, None
    for k, v in word.items():
        if len(k) < 4:
            continue
        if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", s_norm):
            if best_key is None or len(k) > len(best_key):
                best_key, best_val = k, v
    return best_val

def chuan_hoa_dia_diem(raw: str, tu_dien: dict = None) -> dict:
    if not raw:
        return {"city": None, "address": None}

    compact, word = _build_location_lookup(tu_dien)
    city = None

    if ":" in raw:
        head = raw.split(":", 1)[0]
        city = _tra_city(head, compact, word)

    if city is None:
        parts = [p.strip() for p in re.split(r"[,;|]", raw) if p.strip()]
        for p in reversed(parts):
            c = _tra_city(p, compact, word)
            if c:
                city = c
                break

    if city is None:
        city = _tra_city(raw, compact, word)

    return {"city": city, "address": raw.strip()}


def _valid_date(y: int, mo: int, d: int) -> bool:
    if not (1 <= mo <= 12):
        return False
    if not (1 <= d <= 31):
        return False
    leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= days[mo - 1]


def _format_date(y: int, mo: int, d: int) -> Optional[str]:
    if not _valid_date(y, mo, d):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _parse_date_numeric(s: str) -> Optional[str]:
    m = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        res = _format_date(y, mo, d)
        if res:
            return res

    m = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        res = _format_date(y, b, a)
        if res:
            return res
        res = _format_date(y, a, b)
        if res:
            return res
    return None


def _parse_date_text(s: str) -> Optional[str]:
    m = re.search(
        r"(?:ngày\s*)?(\d{1,2})\s*tháng\s*(\d{1,2})(?:\s*năm\s*(\d{2,4}))?",
        s,
    )
    if not m:
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    y_str = m.group(3)
    if y_str is None:
        return None
    y = int(y_str)
    if y < 100:
        y += 2000
    return _format_date(y, mo, d)

def chuan_hoa_deadline(raw: str) -> dict:
    result = {"type": None, "date": None}
    if not raw:
        return result
    s = raw.lower().strip()

    date = _parse_date_numeric(s) or _parse_date_text(s)
    if date:
        result["type"] = "date"
        result["date"] = date
        return result

    if any(k in s for k in ("asap", "càng sớm càng tốt",
                            "ngay lập tức", "sớm nhất có thể", "sớm nhất")):
        result["type"] = "asap"
        return result
    if any(k in s for k in ("khi tuyển đủ", "until filled",
                            "liên tục", "thường xuyên", "ongoing")):
        result["type"] = "until_filled"
        return result

    return result


def chuan_hoa_bang_cap(raw: str, tu_dien: dict = None) -> Optional[str]:
    if not raw:
        return None
    s = raw.lower().strip()
    d = {**BANG_CAP_MAP, **(tu_dien or {})}

    if s in d:
        return d[s]

    for k in sorted(d.keys(), key=len, reverse=True):
        if len(k) <= 3:
            if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", s):
                return d[k]
        elif k in s:
            return d[k]
    return None


def chuan_hoa_chung_chi(raw: str, tu_dien: dict = None) -> dict:
    result = {"type": None, "name": None, "grade": None}
    if not raw:
        return result
    s = raw.strip()
    s_lower = s.lower()
    kb = {**CHUNG_CHI_KB, **(tu_dien or {})}

    matched_key = None
    m_match = None
    for k in sorted(kb.keys(), key=len, reverse=True):
        pat = r"(?:^|\b)" + re.escape(k) + r"\b"
        m = re.search(pat, s_lower)
        if m:
            matched_key = k
            m_match = m
            break

    if matched_key:
        result["type"] = kb[matched_key]

        start = m_match.start()
        if start > 0 and not s[start - 1].isalnum():
            start = m_match.start()

        key_start = s_lower.find(matched_key, start)
        key_end   = key_start + len(matched_key)
        name_core = s[key_start:key_end]
        result["name"] = CERTI_CANONICAL.get(
            matched_key,
            name_core.upper() if len(matched_key) <= 5 else name_core,
        )

        rest = s[key_end:].strip(" :,.-")
        if rest:
            m_grade = re.match(r"^(N\d|\d+(?:\.\d+)?)\b", rest, re.IGNORECASE)
            if m_grade:
                result["grade"] = m_grade.group(1)
                tail = rest[m_grade.end():].strip(" :,.-")
                if tail:
                    result["name"] = result["name"] + " " + tail
            else:
                result["name"] = result["name"] + " " + rest
        return result

    m_grade = re.search(r"(?:level\s*)?(N\d|\d+(?:\.\d+)?)\s*$",
                        s, re.IGNORECASE)
    if m_grade and m_grade.start() > 0:
        result["grade"] = m_grade.group(1)
        result["name"]  = s[:m_grade.start()].strip(" :,.-")
    else:
        result["name"] = s
    return result

def phan_loai_benefit(raw: str, tu_dien: dict = None) -> Optional[str]:
    if not raw:
        return None
    d = {**TU_DIEN_BENEFIT_MAC_DINH, **(tu_dien or {})}
    s = raw.lower()
    for k in sorted(d.keys(), key=len, reverse=True):
        if k in s:
            return d[k]
    return "other"


def chuan_hoa_ten_skill(raw: str, tu_dien: dict = None) -> str:
    if not raw:
        return raw
    d = {**TU_DIEN_SKILL_MAC_DINH, **(tu_dien or {})}
    return d.get(raw.strip().lower(), raw.strip())


PREFERRED_SIGNALS = (
    "ưu tiên", "được ưu tiên", "sẽ được ưu tiên", "ưu tiên hàng đầu",
    "là một lợi thế", "sẽ là lợi thế", "là lợi thế", "lợi thế",
    "lợi thế cạnh tranh", "điểm cộng", "điểm cộng lớn", "điểm cộng nếu",
    "mong muốn", "mong muốn có", "nên có", "có thì tốt", "có càng tốt",
    "khuyến khích", "được khuyến khích",
    "được đánh giá cao", "rất được đánh giá cao",
    "không bắt buộc", "không bắt buộc nhưng", "tùy chọn",
    "không yêu cầu bắt buộc",
    "nice to have", "good to have",
    "preferred", "preferably", "preferred but not required",
    "is a plus", "a plus", "would be a plus", "will be a plus",
    "is an advantage", "an advantage", "advantageous",
    "added advantage", "added bonus", "plus point", "plus points",
    "bonus if", "bonus points", "plus if",
    "desirable", "highly desirable", "desired",
    "is an asset", "an asset", "asset",
    "highly regarded", "would be advantageous",
    "optional", "not required", "not mandatory", "non-mandatory",
    "is beneficial", "beneficial", "is a benefit",
)

PREFERRED_SECTIONS = {
    "benefits",
    "introduction",
    "objectives",
    "general",
}

REQUIRED_SECTIONS = {
    "requirements",
    "responsibilities",
    "skills",
    "experience",
    "degree",
    "certificates",
}

RELATED_SIGNALS = (
    "hoặc ngành liên quan", "ngành liên quan",
    "hoặc lĩnh vực liên quan", "lĩnh vực liên quan",
    "hoặc chuyên ngành liên quan", "chuyên ngành liên quan",
    "hoặc ngành tương tự", "ngành tương tự",
    "hoặc lĩnh vực tương tự", "lĩnh vực tương tự",
    "hoặc chuyên ngành tương tự",
    "hoặc các ngành tương tự", "các ngành tương tự",
    "tương đương", "hoặc tương đương", "hoặc lĩnh vực tương đương",
    "hoặc tương tự", "hoặc các lĩnh vực tương tự",
    "liên quan", "có liên quan",
    "or related field", "or related fields", "related field", "related fields",
    "or related discipline", "related discipline",
    "or related area", "related area",
    "or related", "related",
    "or equivalent", "equivalent", "or equivalent experience",
    "or equivalent qualification", "equivalent qualification",
    "or similar", "or similar field", "or similar fields",
    "or closely related", "closely related",
    "or comparable", "comparable",
    "or allied field", "allied field",
)

RELATED_SPAN_PATTERN = re.compile(
    r"^(?:related|liên\s+quan|or\s+related|ngành\s+liên\s+quan"
    r"|tương\s+đương|equivalent|or\s+equivalent)"
    r"(?:\s+.*)?$",
    re.IGNORECASE,
)


def _la_span_related(text: str) -> bool:
    if not text:
        return False
    return bool(RELATED_SPAN_PATTERN.match(text.strip()))

def _tach_nhieu_chung_chi(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"\s*(?:[,;]|\bvà\b|\band\b|\bhoặc\b|\bor\b|&)\s*", text)
    return [p.strip() for p in parts if p.strip()]

def xac_dinh_related_ok(span: dict) -> bool:
    text      = (span.get("line_text") or "").lower()
    span_text = (span.get("text") or "").lower()
    combined  = text + " " + span_text
    return any(s in combined for s in RELATED_SIGNALS)


def xac_dinh_level(span: dict) -> str:
    text    = (span.get("line_text") or "").lower()
    section = (span.get("section") or "").lower()

    if any(s in text for s in PREFERRED_SIGNALS):
        return LEVEL_PREFERRED
    if section in PREFERRED_SECTIONS:
        return LEVEL_PREFERRED
    if section in REQUIRED_SECTIONS:
        return LEVEL_REQUIRED
    return LEVEL_REQUIRED


def gan_skill_vao_nhom(spans: list, tu_dien_skill: dict = None) -> list:
    groups: List[dict] = []
    current_group = None
    current_line = None

    def _close():
        nonlocal current_group, current_line
        if current_group is not None:
            groups.append(current_group)
            current_group = None
            current_line = None

    def _add_orphan(skill):
        if groups and groups[-1]["name"] is None:
            groups[-1]["skills"].append(skill)
        else:
            g = tao_skill_group(name=None, source=SOURCE_NER)
            g["skills"].append(skill)
            groups.append(g)

    for span in spans:
        label = span["label"]
        li = span.get("line_idx")

        if label == NHAN_SKILL_GROUP:
            _close()
            current_group = tao_skill_group(
                name=chuan_hoa_ten_skill(span["text"], tu_dien_skill),
                source=SOURCE_NER,
                level=xac_dinh_level(span),
                related_ok=xac_dinh_related_ok(span),
            )
            current_line = li
        elif label == NHAN_SKILL:
            skill = tao_skill(
                name=chuan_hoa_ten_skill(span["text"], tu_dien_skill),
                raw=span["text"],
                level=xac_dinh_level(span),
                source=SOURCE_NER,
            )
            if current_group is not None and li == current_line:
                current_group["skills"].append(skill)
            else:
                _close()
                _add_orphan(skill)

    _close()
    return groups


class SlotFiller:

    def __init__(self, tu_dien_dia_diem: dict = None,
                 tu_dien_skill: dict = None,
                 tu_dien_benefit: dict = None,
                 tu_dien_bang_cap: dict = None,
                 tu_dien_chung_chi: dict = None,
                 tu_dien_group: dict = None,
                 kb_skill_to_group: dict = None):
        self.tu_dien_dia_diem   = tu_dien_dia_diem or {}
        self.tu_dien_skill      = tu_dien_skill or {}
        self.tu_dien_benefit    = tu_dien_benefit or {}
        self.tu_dien_bang_cap   = tu_dien_bang_cap or {}
        self.tu_dien_chung_chi  = tu_dien_chung_chi or {}
        self.tu_dien_group      = tu_dien_group or {}
        self.kb_skill_to_group  = kb_skill_to_group or {}

    def dien(self, task: dict) -> dict:
        job_id = task.get("task_id") or task.get("job_id")
        template = tao_template_rong(job_id)

        spans = self._lam_giau_span(task)
        spans_theo_nhan = self._nhom_span_theo_nhan(spans)

        self._dien_company(template, spans_theo_nhan)
        self._dien_position(template, spans_theo_nhan)
        self._dien_locations(template, spans_theo_nhan)
        self._dien_salary(template, spans_theo_nhan)
        self._dien_experience(template, spans_theo_nhan)
        self._dien_degree(template, spans_theo_nhan)
        self._dien_certificates(template, spans_theo_nhan)
        self._dien_skill_groups(template, spans_theo_nhan, task.get("text", ""))
        self._dien_deadline(template, spans_theo_nhan)
        self._dien_benefits(template, spans_theo_nhan)
        return template

    def _lam_giau_span(self, task: dict) -> List[dict]:
        text      = task.get("text", "")
        tokenized = task.get("tokenized", []) or []
        bio       = task.get("bio", []) or []
        n = min(len(tokenized), len(bio))

        line_bounds = []
        for i in range(n):
            line = tokenized[i]
            line_bounds.append((line[0][1], line[-1][2]) if line else (None, None))

        line_section = self._xac_dinh_section_theo_dong(tokenized[:n], bio[:n])

        def tim_dong(start, end):
            for i, (ls, le) in enumerate(line_bounds):
                if ls is not None and ls <= start and end <= le:
                    return i
            for i, (ls, le) in enumerate(line_bounds):
                if ls is not None and not (end <= ls or start >= le):
                    return i
            return -1

        spans = []
        for item in task.get("spans", []):
            start, end, label, span_text = item
            li = tim_dong(start, end)
            if 0 <= li < len(line_bounds) and line_bounds[li][0] is not None:
                ls, le    = line_bounds[li]
                line_text = text[ls:le]
                section   = line_section[li] if li < len(line_section) else None
            else:
                line_text, section = "", None
            spans.append({
                "start": start, "end": end, "label": label, "text": span_text,
                "line_idx": li, "line_text": line_text, "section": section,
            })
        return spans

    def _xac_dinh_section_theo_dong(self, tokenized, bio):
        sections, current = [], None
        for line, line_bio in zip(tokenized, bio):
            line_str = " ".join(t[0] for t in line).strip().lower()
            for hdr, sec in SECTION_HEADERS.items():
                if hdr in line_str and len(line_str) < 40:
                    current = sec
                    break
            if current is None:
                counts = {}
                for tag in line_bio:
                    if tag == "O":
                        continue
                    base = tag.split("-", 1)[-1]
                    counts[base] = counts.get(base, 0) + 1
                if counts:
                    current = max(counts, key=counts.get)
            sections.append(current)
        return sections

    def _nhom_span_theo_nhan(self, spans: List[dict]) -> Dict[str, List[dict]]:
        out: Dict[str, List[dict]] = {}
        for span in spans:
            out.setdefault(span["label"], []).append(span)
        return out

    def _chon_mot_span(self, spans: list):
        return spans[0] if spans else None

    def _ensure_group(self, groups: Dict[str, dict], name: str,
                      level=None, related=False, source=None) -> dict:
        if name not in groups:
            groups[name] = tao_skill_group(
                name=name, level=level, source=source,
                related_ok=bool(related),
            )
        else:
            g = groups[name]
            if level == LEVEL_REQUIRED:
                g["level"] = LEVEL_REQUIRED
            elif g["level"] is None and level is not None:
                g["level"] = level
            if related:
                g["related_ok"] = True
            if g["source"] is None and source is not None:
                g["source"] = source
        return groups[name]

    def _add_skill_to_group(self, groups, skill_index, group_name,
                            skill_name, raw, level, source):
        key = skill_name.lower()
        if key in skill_index:
            old_group_name, entry = skill_index[key]
            if level == LEVEL_REQUIRED and entry["level"] != LEVEL_REQUIRED:
                entry["level"] = LEVEL_REQUIRED
                if old_group_name in groups:
                    groups[old_group_name]["level"] = LEVEL_REQUIRED
            return

        new_skill = tao_skill(name=skill_name, raw=raw,
                              level=level, source=source)
        groups[group_name]["skills"].append(new_skill)
        skill_index[key] = (group_name, new_skill)

    def _kb_tra_group(self, skill_name: str) -> Optional[str]:
        kb = {**KB_SKILL_TO_GROUP_MAC_DINH, **self.kb_skill_to_group}
        key = skill_name.strip().lower()
        for k, v in kb.items():
            if k.lower() == key:
                return v
        return None

    def _tim_group_cho_skill(self, skill_span, group_spans_sorted, task_text):
        skill_line  = skill_span.get("line_idx")
        skill_start = skill_span["start"]
        if skill_line is None:
            return None
        best = None
        for gs in group_spans_sorted:
            if gs.get("line_idx") != skill_line:
                continue
            if gs["start"] >= skill_start:
                continue
            gap = task_text[gs["end"]:skill_start]
            if "." in gap:
                continue
            if best is None or gs["start"] > best["start"]:
                best = gs
        if best is None:
            return None
        return chuan_hoa_ten_group(best["text"], self.tu_dien_group)

    def _tim_skill_trong_text(self, text: str,
                              exclude_canonicals=None) -> List[str]:
        if not text:
            return []
        exclude = {c.lower() for c in (exclude_canonicals or [])}
        text_lower = text.lower()
        kb = {**TU_DIEN_SKILL_MAC_DINH, **self.tu_dien_skill}
        found: Dict[str, str] = {}
        for alias, canonical in kb.items():
            cl = canonical.lower()
            if cl in exclude or cl in found:
                continue
            pat = r"(?<!\w)" + re.escape(alias.lower()) + r"(?!\w)"
            if re.search(pat, text_lower):
                found[cl] = canonical
        return list(found.values())

    def _tim_group_trong_text(self, text: str,
                              exclude_canonicals=None) -> List[str]:
        if not text:
            return []
        exclude = {c.lower() for c in (exclude_canonicals or [])}
        text_lower = text.lower()
        kb = {**TU_DIEN_GROUP_MAC_DINH, **self.tu_dien_group}
        found: Dict[str, str] = {}
        for alias, canonical in kb.items():
            cl = canonical.lower()
            if cl in exclude or cl in found:
                continue
            pat = r"(?<!\w)" + re.escape(alias.lower()) + r"(?!\w)"
            if re.search(pat, text_lower):
                found[cl] = canonical
        return list(found.values())

    def _dien_company(self, template, spans_theo_nhan):
        span = self._chon_mot_span(spans_theo_nhan.get(NHAN_COMPANY, []))
        if span:
            template["company"] = {
                "raw": span["text"], "name": span["text"], "source": SOURCE_NER,
            }

    def _dien_position(self, template, spans_theo_nhan):
        span = self._chon_mot_span(spans_theo_nhan.get(NHAN_POSITION, []))
        if span:
            template["position"] = {
                "raw": span["text"], "title": span["text"], "source": SOURCE_NER,
            }

    def _dien_locations(self, template, spans_theo_nhan):
        spans = spans_theo_nhan.get(NHAN_LOCATION, [])
        if not spans:
            return

        by_line = {}
        city_spans = []
        
        for span in spans:
            norm = chuan_hoa_dia_diem(span["text"], self.tu_dien_dia_diem)
            li = span.get("line_idx", -1)
            
            norm_span = {
                "raw": span["text"],
                "city": norm["city"],
                "address": norm["address"],
                "start": span["start"],
                "line_idx": li
            }
            
            if li not in by_line:
                by_line[li] = []
            by_line[li].append(norm_span)
            
            if norm["city"]:
                city_spans.append(norm_span)

        line_locs = []
        for li, line_spans in by_line.items():
            line_spans.sort(key=lambda x: x["start"])
            combined_raw = ", ".join(s["raw"] for s in line_spans)
            
            city = None
            for s in line_spans:
                if s["city"]:
                    city = s["city"]
                    break
            
            if not city:
                norm_combined = chuan_hoa_dia_diem(combined_raw, self.tu_dien_dia_diem)
                city = norm_combined["city"]

            line_locs.append({
                "raw": combined_raw,
                "city": city,
                "address": combined_raw,
                "line_idx": li,
                "start": line_spans[0]["start"],
            })

        all_cities = set(cs["city"] for cs in city_spans)
        
        for loc in line_locs:
            if not loc["city"]:
                if len(all_cities) == 1:
                    loc["city"] = list(all_cities)[0]
                elif len(all_cities) > 1:
                    best_city = None
                    min_dist = float('inf')
                    for cs in city_spans:
                        dist = abs(cs["start"] - loc["start"])
                        if dist < min_dist:
                            min_dist = dist
                            best_city = cs["city"]
                    loc["city"] = best_city

        merged_by_city = {}
        no_city_locs = []
        
        for loc in line_locs:
            city = loc["city"]
            if city:
                if city in merged_by_city:
                    merged_by_city[city]["raw"] += " | " + loc["raw"]
                    merged_by_city[city]["address"] += " | " + loc["address"]
                else:
                    merged_by_city[city] = loc
            else:
                exists = False
                for n_loc in no_city_locs:
                    if n_loc["raw"] == loc["raw"]:
                        exists = True
                        break
                if not exists:
                    no_city_locs.append(loc)

        for loc in no_city_locs:
            template["locations"].append(tao_location(
                raw=loc["raw"], city=loc["city"], address=loc["address"], source=SOURCE_NER
            ))
        for city, loc in merged_by_city.items():
            template["locations"].append(tao_location(
                raw=loc["raw"], city=loc["city"], address=loc["address"], source=SOURCE_NER
            ))

    def _dien_salary(self, template, spans_theo_nhan):
        spans = spans_theo_nhan.get(NHAN_SALARY, [])
        if not spans:
            return

        best_norm, best_span = None, None
        for span in spans:
            norm = chuan_hoa_luong(span["text"])
            if best_norm is None or (
                best_norm["type"] == "negotiable"
                and norm["type"] not in (None, "negotiable")
            ):
                best_norm, best_span = norm, span
            if best_norm["type"] in ("range", "from", "up_to", "exact"):
                break

        template["salary"] = {
            "raw":      best_span["text"],
            "type":     best_norm["type"],
            "min":      best_norm["min"],
            "max":      best_norm["max"],
            "currency": best_norm["currency"],
            "period":   best_norm["period"],
        }

    def _dien_experience(self, template, spans_theo_nhan):
        spans = spans_theo_nhan.get(NHAN_EXPERIENCE, [])
        if not spans:
            return

        by_line: Dict = {}
        for span in spans:
            by_line.setdefault(span.get("line_idx"), []).append(span)

        for li, group in by_line.items():
            anchor = group[0]

            min_years = max_years = None
            has_years = False
            domains: List[str] = []
            raw_parts: List[str] = []
            is_preferred = False
            related_ok = False

            for span in group:
                text = span["text"]
                raw_parts.append(text)

                if re.search(r"\d", text):
                    norm = chuan_hoa_kinh_nghiem(text)
                    if norm["min_years"] is not None:
                        has_years = True
                        min_years = (norm["min_years"] if min_years is None
                                     else min(min_years, norm["min_years"]))
                    if norm["max_years"] is not None:
                        has_years = True
                        max_years = (norm["max_years"] if max_years is None
                                     else max(max_years, norm["max_years"]))
                elif _la_span_related(text):
                    related_ok = True
                else:
                    domains.append(text.strip())

                if xac_dinh_level(span) == LEVEL_PREFERRED:
                    is_preferred = True
                if xac_dinh_related_ok(span):
                    related_ok = True

            if is_preferred:
                level = LEVEL_PREFERRED
            elif has_years:
                level = LEVEL_REQUIRED
            else:
                sec = (anchor.get("section") or "").lower()
                level = LEVEL_REQUIRED if sec in REQUIRED_SECTIONS else LEVEL_PREFERRED

            template["experience"].append(tao_experience(
                raw=" ".join(raw_parts).strip() or anchor["text"],
                min_years=min_years,
                max_years=max_years,
                domains=domains,
                level=level,
                related_ok=related_ok,
            ))
    
    def _dien_degree(self, template, spans_theo_nhan):
        spans = spans_theo_nhan.get(NHAN_DEGREE, [])
        if not spans:
            return

        by_line: Dict = {}
        for span in spans:
            by_line.setdefault(span.get("line_idx"), []).append(span)

        for li, group in by_line.items():
            levels: List = []
            majors: List[str] = []
            related_ok = False
            is_preferred = False

            for span in group:
                text = span["text"]

                if _la_span_related(text):
                    related_ok = True
                    continue

                lvl = chuan_hoa_bang_cap(text, self.tu_dien_bang_cap)
                if lvl is not None:
                    levels.append((span, lvl))
                else:
                    majors.append(text.strip())

                if xac_dinh_level(span) == LEVEL_PREFERRED:
                    is_preferred = True
                if xac_dinh_related_ok(span):
                    related_ok = True

            level_req = LEVEL_PREFERRED if is_preferred else LEVEL_REQUIRED

            if levels:
                for span, lvl in levels:
                    template["degree"].append(tao_degree(
                        degree_raw=span["text"],
                        degree_level=lvl,
                        majors=list(majors),
                        related_ok=related_ok,
                        level=level_req,
                    ))
            elif majors:
                template["degree"].append(tao_degree(
                    degree_raw=None,
                    degree_level=None,
                    majors=majors,
                    related_ok=related_ok,
                    level=level_req,
                ))

    def _dien_certificates(self, template, spans_theo_nhan):
        spans = spans_theo_nhan.get(NHAN_CERTIFICATE, [])
        if not spans:
            return

        groups: Dict = {}

        for span in spans:
            text = span["text"]
            parts = _tach_nhieu_chung_chi(text) or [text]

            certs_in_span = []
            for sub in parts:
                if _la_span_related(sub):
                    continue
                certs_in_span.append(
                    chuan_hoa_chung_chi(sub, self.tu_dien_chung_chi)
                )

            span_level   = xac_dinh_level(span)
            span_related = xac_dinh_related_ok(span) or _la_span_related(text)

            for norm in certs_in_span:
                t = norm["type"]
                g = groups.setdefault(t, {
                    "detail": [],
                    "has_required": False,
                    "related_ok": False,
                })
                g["detail"].append({
                    "name":  norm["name"],
                    "grade": norm["grade"],
                })
                if span_level == LEVEL_REQUIRED:
                    g["has_required"] = True
                if span_related:
                    g["related_ok"] = True

        for t, g in groups.items():
            template["certificates"].append(tao_certificate(
                type_=t,
                detail=g["detail"],
                level=LEVEL_REQUIRED if g["has_required"] else LEVEL_PREFERRED,
                related_ok=g["related_ok"],
            ))

    def _dien_deadline(self, template, spans_theo_nhan):
        span = self._chon_mot_span(spans_theo_nhan.get(NHAN_DEADLINE, []))
        if not span:
            return
        norm = chuan_hoa_deadline(span["text"])
        template["deadline"] = {
            "raw": span["text"], "type": norm["type"],
            "date": norm["date"], "source": SOURCE_NER,
        }

    def _dien_benefits(self, template, spans_theo_nhan):
        for span in spans_theo_nhan.get(NHAN_BENEFIT, []):
            template["benefits"].append(tao_benefit(
                raw=span["text"],
                category=phan_loai_benefit(span["text"], self.tu_dien_benefit),
            ))

    def _dien_skill_groups(self, template, spans_theo_nhan, task_text=""):
        skill_spans   = spans_theo_nhan.get(NHAN_SKILL, [])
        group_spans   = spans_theo_nhan.get(NHAN_SKILL_GROUP, [])
        position_span = self._chon_mot_span(
            spans_theo_nhan.get(NHAN_POSITION, []))

        groups: Dict[str, dict] = {}
        skill_index: Dict[str, Tuple[str, dict]] = {}

        group_spans_sorted = sorted(group_spans, key=lambda x: x["start"])
        for gs in group_spans_sorted:
            name = chuan_hoa_ten_group(gs["text"], self.tu_dien_group)
            if name in groups:
                continue
            groups[name] = tao_skill_group(
                name=name,
                level=xac_dinh_level(gs),
                source=SOURCE_NER,
                related_ok=xac_dinh_related_ok(gs),
            )

        if position_span:
            existing_group_names = list(groups.keys())
            for name in self._tim_group_trong_text(
                position_span["text"], exclude_canonicals=existing_group_names,
            ):
                self._ensure_group(
                    groups, name, level=LEVEL_REQUIRED, source="kb",
                )

        for sk in sorted(skill_spans, key=lambda x: x["start"]):
            skill_name = chuan_hoa_ten_skill(sk["text"], self.tu_dien_skill)
            sk_level   = xac_dinh_level(sk)
            sk_related = xac_dinh_related_ok(sk)

            target = self._tim_group_cho_skill(sk, group_spans_sorted, task_text)
            target_source = SOURCE_NER

            if target is None:
                target = self._kb_tra_group(skill_name)
                target_source = "kb"

            if target is None:
                target = TEN_GROUP_OTHER
                target_source = SOURCE_NER

            self._ensure_group(
                groups, target,
                level=sk_level, related=sk_related, source=target_source,
            )
            self._add_skill_to_group(
                groups, skill_index, target, skill_name,
                raw=sk["text"], level=sk_level, source=SOURCE_NER,
            )

        if position_span:
            existing_skill_names = [s["name"]
                                    for g in groups.values()
                                    for s in g["skills"]]
            for canon in self._tim_skill_trong_text(
                position_span["text"], exclude_canonicals=existing_skill_names,
            ):
                target = self._kb_tra_group(canon) or TEN_GROUP_OTHER
                target_source = "kb" if target != TEN_GROUP_OTHER else SOURCE_NER
                self._ensure_group(
                    groups, target,
                    level=LEVEL_REQUIRED, source=target_source,
                )
                self._add_skill_to_group(
                    groups, skill_index, target, canon,
                    raw=None, level=LEVEL_REQUIRED, source="kb",
                )

        template["skill_groups"] = list(groups.values())


def _so_sanh_scalar(g, p) -> bool:
    if g is None and p is None:
        return True
    if g is None or p is None:
        return False
    if isinstance(g, (int, float)) and isinstance(p, (int, float)):
        return float(g) == float(p)
    return g == p


def _chon_key_match(gold_list: list, pred_list: list,
                    match_by: str) -> Optional[str]:
    if match_by and match_by != "auto":
        return match_by if match_by != "index" else None
    combined = gold_list + pred_list
    if not combined:
        return None
    for field in ("name", "id", "raw"):
        if all(isinstance(it, dict) and field in it for it in combined):
            return field
    return None


def _get_field(item, field):
    if isinstance(item, dict) and field in item:
        return item[field]
    return None


def _walk(gold, pred, path, out_mismatch, out_match, match_by):
    if isinstance(gold, dict) and isinstance(pred, dict):
        all_keys = set(gold.keys()) | set(pred.keys())
        for k in sorted(all_keys, key=str):
            new_path = f"{path}.{k}" if path else str(k)
            if k not in gold:
                out_mismatch.append(
                    {"path": new_path, "gold": "<MISSING>", "pred": pred[k]}
                )
                continue
            if k not in pred:
                out_mismatch.append(
                    {"path": new_path, "gold": gold[k], "pred": "<MISSING>"}
                )
                continue
            _walk(gold[k], pred[k], new_path,
                  out_mismatch, out_match, match_by)
        return

    if isinstance(gold, list) and isinstance(pred, list):
        key_field = _chon_key_match(gold, pred, match_by)
        if key_field is not None:
            gold_by_key = {_get_field(it, key_field): it for it in gold}
            pred_by_key = {_get_field(it, key_field): it for it in pred}
            all_keys = set(gold_by_key.keys()) | set(pred_by_key.keys())
            for kv in sorted(all_keys, key=str):
                new_path = f"{path}[{key_field}={kv}]"
                if kv not in gold_by_key:
                    out_mismatch.append(
                        {"path": new_path,
                         "gold": "<MISSING>",
                         "pred": pred_by_key[kv]}
                    )
                    continue
                if kv not in pred_by_key:
                    out_mismatch.append(
                        {"path": new_path,
                         "gold": gold_by_key[kv],
                         "pred": "<MISSING>"}
                    )
                    continue
                _walk(gold_by_key[kv], pred_by_key[kv], new_path,
                      out_mismatch, out_match, match_by)
        else:
            n = max(len(gold), len(pred))
            for i in range(n):
                new_path = f"{path}[{i}]"
                if i >= len(gold):
                    out_mismatch.append(
                        {"path": new_path, "gold": "<MISSING>", "pred": pred[i]}
                    )
                    continue
                if i >= len(pred):
                    out_mismatch.append(
                        {"path": new_path, "gold": gold[i], "pred": "<MISSING>"}
                    )
                    continue
                _walk(gold[i], pred[i], new_path,
                      out_mismatch, out_match, match_by)
        return

    both_numeric = (
        isinstance(gold, (int, float)) and isinstance(pred, (int, float))
    )
    if type(gold) is not type(pred) and not both_numeric:
        out_mismatch.append({"path": path, "gold": gold, "pred": pred})
        return

    if _so_sanh_scalar(gold, pred):
        out_match.append({"path": path, "value": gold})
    else:
        out_mismatch.append({"path": path, "gold": gold, "pred": pred})


def tinh_accuracy(gold, pred, match_by: str = "auto") -> dict:
    out_mismatch = []
    out_match = []
    _walk(gold, pred, "", out_mismatch, out_match, match_by)

    total = len(out_mismatch) + len(out_match)
    matched = len(out_match)
    return {
        "total": total,
        "matched": matched,
        "accuracy": (matched / total) if total > 0 else 0.0,
        "exact_match": len(out_mismatch) == 0,
        "mismatches": out_mismatch,
    }


def tinh_accuracy_dataset(pairs: List[Tuple[Any, Any]],
                          match_by: str = "auto") -> dict:
    all_matched = 0
    all_total = 0
    n_exact = 0
    field_stats: Dict[str, dict] = {}

    for gold, pred in pairs:
        out_mismatch = []
        out_match = []
        _walk(gold, pred, "", out_mismatch, out_match, match_by)

        all_matched += len(out_match)
        all_total += len(out_match) + len(out_mismatch)
        if not out_mismatch:
            n_exact += 1

        for m in out_match:
            p = m["path"]
            fs = field_stats.setdefault(p, {"matched": 0, "total": 0})
            fs["matched"] += 1
            fs["total"] += 1
        for m in out_mismatch:
            p = m["path"]
            fs = field_stats.setdefault(p, {"matched": 0, "total": 0})
            fs["total"] += 1

    field_accuracy = {
        p: {
            "matched": fs["matched"],
            "total": fs["total"],
            "accuracy": (fs["matched"] / fs["total"]) if fs["total"] > 0 else 0.0,
        }
        for p, fs in field_stats.items()
    }

    n = len(pairs)
    return {
        "n_samples": n,
        "avg_accuracy": (all_matched / all_total) if all_total > 0 else 0.0,
        "exact_match_rate": (n_exact / n) if n > 0 else 0.0,
        "total_units": all_total,
        "matched_units": all_matched,
        "field_accuracy": field_accuracy,
    }


class DiversityAnalyzer:
    def __init__(self, slot_filler):
        self.slot_filler = slot_filler
        self.stats = {
            "Location": {"sf": Counter(), "cf": Counter()},
            "Salary":   {"sf": Counter(), "cf": Counter()},
            "Skill":    {"sf": Counter(), "cf": Counter()},
            "Certificate": {"sf": Counter(), "cf": Counter()},
            "Experience":  {"sf": Counter(), "cf": Counter()},
            "Degree":      {"sf": Counter(), "cf": Counter()}
        }

    def process_task(self, task):
        filled = self.slot_filler.dien(task)
        
        for loc in filled.get("locations", []):
            raw_val = loc.get("raw")
            sf = str(raw_val).strip().lower() if raw_val else ""
            cf = loc.get("city") or sf 
            if sf:
                self.stats["Location"]["sf"][sf] += 1
                self.stats["Location"]["cf"][cf] += 1

        sal = filled.get("salary", {})
        raw_val = sal.get("raw")
        if raw_val:
            sf = str(raw_val).strip().lower()
            cf = f"{sal.get('type')}|{sal.get('min')}|{sal.get('max')}|{sal.get('currency')}|{sal.get('period')}"
            self.stats["Salary"]["sf"][sf] += 1
            self.stats["Salary"]["cf"][cf] += 1

        for group in filled.get("skill_groups", []):
            for sk in group.get("skills", []):
                raw_val = sk.get("raw") or sk.get("name")
                sf = str(raw_val).strip().lower() if raw_val else ""
                cf = sk.get("name", "Unknown")
                if sf and cf:
                    self.stats["Skill"]["sf"][sf] += 1
                    self.stats["Skill"]["cf"][cf] += 1

        for cert in filled.get("certificates", []):
            for detail in cert.get("detail", []):
                raw_val = detail.get("name")
                sf = str(raw_val).strip().lower() if raw_val else ""
                cf = f"{detail.get('name')}|{detail.get('grade')}" 
                if sf:
                    self.stats["Certificate"]["sf"][sf] += 1
                    self.stats["Certificate"]["cf"][cf] += 1

        for deg in filled.get("degree", []):
            raw_val = deg.get("degree_raw")
            sf = str(raw_val).strip().lower() if raw_val else ""
            majors_list = deg.get('majors') or []
            cf = f"{deg.get('degree_level')}|{','.join(majors_list)}"
            if sf:
                self.stats["Degree"]["sf"][sf] += 1
                self.stats["Degree"]["cf"][cf] += 1
                
        for exp in filled.get("experience", []):
            raw_val = exp.get("raw")
            sf = str(raw_val).strip().lower() if raw_val else ""
            domains_list = exp.get('domains') or []
            cf = f"{exp.get('min_years')}|{exp.get('max_years')}|{','.join(domains_list)}"
            if sf:
                self.stats["Experience"]["sf"][sf] += 1
                self.stats["Experience"]["cf"][cf] += 1

    def get_metrics(self):
        results = []
        for label, data in self.stats.items():
            sf_count = len(data["sf"])
            cf_count = len(data["cf"])
            total_mentions = sum(data["sf"].values())
            
            diversity_ratio = sf_count / cf_count if cf_count > 0 else 0
            
            single_occurrence_sf = sum(1 for count in data["sf"].values() if count == 1)
            long_tail_ratio = single_occurrence_sf / sf_count if sf_count > 0 else 0

            results.append({
                "Nhãn": label,
                "Tổng số lần xuất hiện": total_mentions,
                "Số Surface Forms": sf_count,
                "Số Canonical Forms": cf_count,
                "Độ đa dạng (SF/CF)": round(diversity_ratio, 2),
                "Tỉ lệ Long-tail": f"{round(long_tail_ratio * 100, 1)}%"
            })
        return pd.DataFrame(results).sort_values(by="Số Surface Forms", ascending=False)