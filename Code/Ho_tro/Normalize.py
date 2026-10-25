import html, re, unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


HTML_COMMENT      = re.compile(r"<!--.*?-->", re.S)                       # <!-- ghi chú -->

HTML_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)  # cả thẻ lẫn nội dung bên trong

HTML_BLOCK_TAG    = re.compile(r"</?(?:br|p|div|li|ul|ol|tr|h[1-6]|table|section|article)\b[^>]*>", re.I)  # thẻ xuống dòng

HTML_TAG          = re.compile(r"</?[a-zA-Z][^<>]*>")                     # thẻ HTML thật còn lại

def chuan_hoa_1(text):

    """Chuẩn hóa 1: bỏ HTML, NFC, bỏ ký tự lạ, gộp khoảng trắng."""

    text = str(text)

    text = HTML_COMMENT.sub(" ", text)                # bỏ chú thích HTML

    text = HTML_SCRIPT_STYLE.sub(" ", text)           # bỏ script/style kèm nội dung

    text = HTML_BLOCK_TAG.sub("\n", text)             # thẻ khối -> xuống dòng

    text = HTML_TAG.sub(" ", text)                    # thẻ còn lại -> khoảng trắng

    text = html.unescape(text)                        # &   ... (làm SAU khi bỏ thẻ)

    text = unicodedata.normalize("NFC", text)         # chuẩn Unicode tiếng Việt

    text = text.translate(ZERO_WIDTH)                 # bỏ ký tự zero-width

    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)               # gộp khoảng trắng

    text = "\n".join(line.strip() for line in text.split("\n"))

    text = re.sub(r"\n{3,}", "\n\n", text)            # tối đa 1 dòng trống

    return text.strip()

import unicodedata

DASHES = ["\u2013", "\u2014", "\u2212", "\u2011"] # – — − ‑ -> "-"
BULLETS = ["\u2022", "\u25CF", "\u25AA", "\u2023", "\uF0B7"] # • ● ▪ ‣ (PDF) -> "-"
SPACES = ["\u00A0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004",
"\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200A",
"\u202F", "\u205F", "\u3000"] # các khoảng trắng Unicode -> " "
def build_char_map():
    m = {}
    for ch in DASHES + BULLETS: m[ord(ch)] = "-"
    for ch in "\u2018\u2019": m[ord(ch)] = "'" # ‘ ’
    for ch in "\u201C\u201D": m[ord(ch)] = '"' # “ ”
    m[ord("\u2026")] = "." # …
    for ch in SPACES: m[ord(ch)] = " "
    m[ord("\u30FB")] = "/" # ・
    for c in range(0xFF01, 0xFF5F):                    # full-width -> ASCII: （ ） ： ＜ ＞ － ～
        m[c] = chr(c - 0xFEE0)
    for ch in "✓✔■□○◦❖➢➡§※·⸻":                        # bullet / ký hiệu trang trí -> "-"
        m[ord(ch)] = "-"
    for ch in "\u00AD\u200E\u200F":                    # soft hyphen, LRM, RLM -> dấu cách (không xóa để giữ 1-1)
        m[ord(ch)] = " "
    for c in range(0x1D400, 0x1D800):                  # chữ in đậm/nghiêng kiểu Unicode -> chữ thường
        n = unicodedata.normalize("NFKC", chr(c))
        if len(n) == 1:
            m[c] = n
    assert all(len(v) == 1 for v in m.values()), "Có quy tắc đổi không phải 1-1"
    return m

CHAR_MAP = build_char_map()

def chuan_hoa_2(text: str) -> str:
    return text.translate(CHAR_MAP)