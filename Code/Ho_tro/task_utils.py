import json

import json
from pathlib import Path

def load_json(json_path: str) -> list:
    json_path = Path(__file__).parent / json_path

    with open(json_path, encoding="utf-8") as f:
        tasks = json.load(f)

    out = []

    for task in tasks:

        # Nếu không gán thì bỏ qua
        t = task.get("annotations", [])
        if not t:
            continue


        # Lấy đúng lần gán nhãn đầu tiên, nếu bị cancelled thì bỏ qua
        ann = t[0]
        if ann["was_cancelled"]:
            continue

        spans = []
        for s in ann["result"]:
            spans.append((
                s["value"]["start"],
                s["value"]["end"],
                s["value"]["labels"][0],
                s["value"]["text"]
            ))

        data = task["data"]

        out.append({
            "task_id": data["task_id"],
            "text": data["text"],
            "spans": spans,
            "split": data["split"]
        })

    return out

def lay_task_id_trung(tasks1: list, tasks2: list) -> set:
    tid_khac = set()
    tid_trung = set()
    for task in tasks1 + tasks2:
        rtid = task["task_id"]
        if rtid not in tid_khac:
            tid_khac.add(rtid)
            continue
        tid_trung.add(rtid)

    return tid_trung



def lay_task_trung(task_id_trung: set, taskss: dict) -> dict:
    out = {}

    for ten_tasks, tasks in taskss.items():
        task_trung = []
        for task in tasks:
            if task["task_id"] in task_id_trung:
                task_trung.append(task)

        out[ten_tasks] = task_trung

    return out


def lay_task_id_trung_nhau_tu_taskss(taskss: dict) -> set:
    out = set()
    keys = list(taskss.keys())

    if len(keys) < 2:
        return set()
    
    out =  lay_task_id_trung(taskss[keys[0]], taskss[keys[1]])

    for i in range(1, len(keys)-1):
        for j in range(i+1, len(keys)):
            temp = lay_task_id_trung(taskss[keys[i]], taskss[keys[j]])

            out = out & temp

    return out


# Nhận nhiều tasks để lấy theo split
def lay_dong(tasks, split):
    X, Y = [], []
    for t in tasks:
        if t["split"] != split:
            continue

        # Kiểm tra số dòng token với số dòng bio
        assert len(t["tokenized"]) == len(t["bio"]), \
            f"task {t['task_id']}: số dòng tokenized khác số dòng bio"

        
        for tokens, bio in zip(t["tokenized"], t["bio"]):
            assert len(tokens) == len(bio), \
                f"task {t['task_id']}: một dòng có số token khác số nhãn" # Kiểm tra số token với số bio trong 1 dòng
            
            if len(tokens) == 0:
                continue

            X.append(tokens)
            Y.append(bio)

    return X, Y


def build_task(task_id, lines):
    """lines = [(line_text, [(label, span_text), ...]), ...]"""
    text_parts, tokenized, bio_lines, spans = [], [], [], []
    offset = 0
    for line_text, label_texts in lines:
        toks, pos = [], 0
        for tok in line_text.split():
            i = line_text.index(tok, pos)
            toks.append((tok, i + offset, i + offset + len(tok)))
            pos = i + len(tok)
        bio_line = ["O"] * len(toks)
        cursor = 0
        for label, stext in label_texts:
            idx = line_text.find(stext, cursor)
            if idx < 0:
                raise ValueError(f"span {stext!r} không có trong dòng {line_text!r}")
            start, end = idx + offset, idx + offset + len(stext)
            spans.append((start, end, label, stext))
            b = False
            for i, (t, ts, te) in enumerate(toks):
                if ts < end and te > start:
                    bio_line[i] = f"B-{label}" if (ts >= start and not b) else f"I-{label}"
                    if ts >= start:
                        b = True
            cursor = idx + len(stext)
        text_parts.append(line_text)
        tokenized.append(toks)
        bio_lines.append(bio_line)
        offset += len(line_text) + 1
    return {
        "task_id": task_id,
        "text": "\n".join(text_parts),
        "tokenized": tokenized,
        "bio": bio_lines,
        "spans": sorted(spans),
    }

import json


def doc_du_lieu_mo(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tokenized = []      # list các dòng, mỗi dòng là list các token (text, start, end)
    bio = []            # list các dòng, mỗi dòng là list nhãn BIO
    errors = []

    for task in data:
        tokens = task["tokenized"]
        labels = task["bio"]
        task_id = task["task_id"]

        if len(tokens) != len(labels):
            errors.append(f"[{task_id}] Số dòng khác nhau: tokens={len(tokens)}, bio={len(labels)}")
            continue

        for i, (t, b) in enumerate(zip(tokens, labels)):
            if len(t) != len(b):
                errors.append(f"[{task_id}] Dòng {i+1}: tokens={len(t)}, bio={len(b)}")
                continue

            # JSON đọc ra token là list [text, start, end], đổi thành tuple (text, start, end)
            dong_token = [tuple(token) for token in t]

            if any(len(token) != 3 for token in dong_token):
                errors.append(f"[{task_id}] Dòng {i+1}: có token không đủ 3 phần tử (text, start, end)")
                continue

            tokenized.append(dong_token)
            bio.append(list(b))

    assert all(len(t) == len(b) for t, b in zip(tokenized, bio)), "vẫn còn dòng lệch"

    return tokenized, bio, errors