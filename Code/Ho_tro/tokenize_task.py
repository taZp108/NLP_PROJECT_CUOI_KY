

import re


_AN = r"[^\W_]"        # Chữ hoặc số, không gồm "_"
_LETTER = r"[^\W\d_]"  # Chỉ chữ


# 10 từ ghép có dấu "-" được giữ nguyên thành một token
_TU_GHEP_GACH_NGANG = (
    r"(?<![^\W_])(?:"
    r"wi-fi|back-end|front-end|full-stack|full-time|part-time|"
    r"machine-learning|deep-learning|end-to-end|real-time"
    r")(?![^\W_])"
)


# Các dạng có dấu "/" được giữ nguyên
_TU_GHEP_GACH_CHEO = (
    r"(?<![^\W_])(?:S/W|H/W|N/A)(?![^\W_])"
)


# Token dạng số-chữ-số như 1-on-1
_SO_CHU_SO = rf"\d+-{_LETTER}+-\d+"


# Token lõi:
# - .NET, ASP.NET, Node.js, TP.HCM
# - R&D, O'Reilly
# - 3-5, 15-20tr, 3-month, 2-year
# - 30/10/2026, 24/7, 8:45, 15,5tr
# - C++, C#, 7+, 10%, $1000
_LOI = (
    rf"(?:(?<!{_AN})\.(?={_LETTER}))?"
    r"(?:\$(?=\d))?"
    rf"{_AN}+"
    rf"(?:(?:[.&]|'(?!s(?!{_AN}))|"
    rf"(?<=\d)-(?={_AN})|"
    rf"(?<=\d)[,:/](?=\d)){_AN}+)*"
    r"[+#%$]*"
)


_TOKEN = re.compile(
    "|".join([
        # URL
        r'''(?:https?://|www\.)\S*[^\s.,;:!?)\]'"]''',

        # Email
        rf"{_AN}[\w.+-]*@{_AN}[\w-]*(?:\.{_AN}[\w-]*)+",

        # Các trường hợp được giữ nguyên
        _TU_GHEP_GACH_NGANG,
        _SO_CHU_SO,

        # Bachelor's -> Bachelor, 's
        rf"'s(?!{_AN})",

        # ... hoặc nhiều dấu chấm liên tiếp
        r"\.{2,}",

        # Token lõi
        _LOI,

        # Ký tự lẻ, dấu câu, emoji
        r"\S(?:\ufe0f)?",
    ]),
    re.IGNORECASE,
)


def tokenize_task(task: dict, text_key: str = "text_da_chuan_hoa_2", max_tokens_dong: int = 300,kiem_tra: bool = False,) -> dict:
 
    text = task[text_key]
    tid = task.get("task_id", "?")

    # chuan_hoa_2 phải đổi ký tự 1-1 để offset spans không bị lệch
    if "text" in task and len(task["text"]) != len(text):
        raise ValueError(
            f"[{tid}] len(text)={len(task['text'])} khác "
            f"len({text_key})={len(text)}: "
            "chuan_hoa_2 đã làm thay đổi độ dài, offset spans sẽ sai"
        )

    tokenized = []
    canh_bao = []
    vi_tri = 0

    for so_dong, dong in enumerate(text.split("\n")):
        dau_dong = vi_tri
        vi_tri += len(dong) + 1

        if not dong.strip():
            continue

        matches = list(_TOKEN.finditer(dong))
        tokens = [
            (m.group(), dau_dong + m.start(), dau_dong + m.end())
            for m in matches
        ]

        if kiem_tra:
            da_phu = [False] * len(dong)
            cuoi_truoc = 0

            for m in matches:
                start, end = m.start(), m.end()

                if start < cuoi_truoc:
                    raise ValueError(
                        f"[{tid}] Token bị chồng lấn tại dòng {so_dong}"
                    )

                if dong[start:end] != m.group():
                    raise ValueError(
                        f"[{tid}] Token không khớp văn bản tại dòng {so_dong}"
                    )

                for i in range(start, end):
                    da_phu[i] = True

                cuoi_truoc = end

            for i, ky_tu in enumerate(dong):
                if not ky_tu.isspace() and not da_phu[i]:
                    raise ValueError(
                        f"[{tid}] Bỏ sót ký tự {ky_tu!r} "
                        f"tại offset {dau_dong + i}"
                    )

        tokenized.append(tokens)

        if len(tokens) > max_tokens_dong:
            canh_bao.append(
                f"[{tid}] dòng {so_dong} có {len(tokens)} token"
            )

    task["tokenized"] = tokenized

    if canh_bao:
        task["canh_bao_tokenize"] = canh_bao
    else:
        task.pop("canh_bao_tokenize", None)

    return task
