import json
import re
from pathlib import Path


class FeatureExtractor:
    THU_TU_NHAN = [
        "COMPANY",
        "POSITION",
        "LOCATION",
        "SALARY",
        "EXPERIENCE",
        "DEGREE",
        "CERTIFICATE",
        "SKILL",
        "SKILL_GROUP",
        "DEADLINE",
        "BENEFIT"
    ]

    # 15 hình thái + 3 ngoặc + 5 gazetteer
    # + 1 feature cả dòng + 8 trigger + 5 liên quan
    # + 2 feature vùng ngành + 2 feature vùng chứng chỉ
    # + 12 feature giữ nguyên từ bản cũ = 51 feature
    TEN_FEATURE = [
        # 15 hình thái
        "is_upper",
        "is_title",
        "is_lower",
        "has_upper",
        "is_digit",
        "has_digit",
        "is_alpha",
        "has_digit_and_letter",
        "starts_with_digit",
        "ends_with_digit",
        "has_hyphen",
        "has_slash",
        "has_dot",
        "has_plus",
        "has_hash",
        # 3 ngoặc
        "is_inside_parentheses",
        "is_before_parenthesis_in_3_word",
        "is_parenthesis",
        # 5 gazetteer
        "is_in_skill_gaz",
        "is_in_group_skill_gaz",
        "is_in_certi_gaz",
        "is_in_degree_gaz",
        "is_in_domain_gaz",
        "is_in_exp_domain_gaz",
        # 1 feature cả dòng (duy nhất còn giữ)
        "is_in_location_block",
        "has_certificate_keyword_in_line",
        "has_experience_keyword_in_line",
        "has_degree_keyword_in_line",
        # 6 trigger theo cửa sổ (đúng thứ tự TRIGGER_LUAT)
        "trigger_company_sau",
        "trigger_position_sau", 
        "trigger_salary_sau",
        "trigger_experience_sau",
        "trigger_experience_truoc",
        "trigger_certificate_sau",
        "trigger_degree_sau",
        "trigger_deadline_sau",  # <-- THÊM DÒNG NÀY

        # 2 feature vùng ngành của DEGREE
        "trigger_degree_vung_nganh",
        "degree_dau_muc_trong_vung",
        # 2 feature vùng chứng chỉ của CERTIFICATE (MỚI)
        "trigger_certificate_vung",
        "certificate_dau_muc_trong_vung",

        "trigger_experience_vung",
        "experience_dau_muc_trong_vung",
        # 5 feature "liên quan"
        "la_tu_lien_quan",
        "lien_quan_ngu_canh_degree",
        "lien_quan_ngu_canh_experience",
        "lien_quan_ngu_canh_skill",
        "lien_quan_ngu_canh_certificate",
        # 12 feature giữ nguyên
        "la_khoang_so",
        "la_so_dinh_don_vi",
        "is_truoc_tu_don_vi",
        "is_tu_don_vi",
        "is_tien_to_pos",
        "is_hau_to_pos",
        "is_in_pos_gaz",
        "is_hau_to_company",
        
        "is_in_benefit_gaz",
        "truoc_la_dau_hai_cham",
        "sau_la_dau_hai_cham",
        "truoc_hoac_sau_la_phay_hoac_slash",
    ]

    TRIGGER_LUAT = [
        ("trigger_company_sau",    "COMPANY",     "sau", 2),
        ("trigger_position_sau",   "POSITION",    "sau", 3),
        ("trigger_salary_sau",       "SALARY",      "sau",   3),
        ("trigger_experience_sau",   "EXPERIENCE",  "sau",   2),
        ("trigger_experience_truoc", "EXPERIENCE",  "truoc", 2),
        ("trigger_certificate_sau",  "CERTIFICATE", "sau",   3),
        ("trigger_degree_sau",       "DEGREE",      "sau",   3),
        ("trigger_deadline_sau",     "DEADLINE",    "sau",   3), # <-- THÊM DÒNG NÀY
    ]

    SO_TOKEN_TOI_DA_VUNG = 25
    TU_PHAN_CACH = {",", "/", "hoặc", "và", "or", "and", "&"}
    
    NGANH_MAC_DINH = [
        "chuyên ngành", "khối ngành", "ngành",
        "major in", "majoring in", "degree in",
    ]
    KET_THUC_NGANH_MAC_DINH = [
        "có kinh nghiệm", "kinh nghiệm", "với", "ưu tiên", "yêu cầu",
        "ít nhất", "tối thiểu", "thành thạo",
        "with", "experience", "preferred", "required",
    ]

    CHUNG_CHI_MAC_DINH = [
        "chứng chỉ", "chứng nhận", "có chứng chỉ", "chứng chỉ quốc tế",
        "certificate", "certification"
    ]
    KET_THUC_CHUNG_CHI_MAC_DINH = [
        "có kinh nghiệm", "kinh nghiệm", "với", "ưu tiên", "yêu cầu",
        "ít nhất", "tối thiểu", "thành thạo",
        "with", "experience", "preferred", "required",
    ]

    NHAN_NGU_CANH = ("DEGREE", "EXPERIENCE", "SKILL", "CERTIFICATE")
    KHOANG_CACH_NGU_CANH = 6
    LIEN_QUAN_MAC_DINH = {
        "tu_lien_quan": [
            "liên quan", "tương tự", "tương đương",
            "related", "relevant", "similar", "equivalent",
        ],
        "ngu_canh": {
            "DEGREE": ["chuyên ngành", "ngành", "bằng cấp", "tốt nghiệp", "degree", "major"],
            "EXPERIENCE": ["kinh nghiệm", "experience", "năm", "year", "years", "yrs"],
            "SKILL": ["công nghệ", "kỹ năng", "technologies", "technology", "tools",
                      "framework", "frameworks", "languages", "ngôn ngữ", "skills"],
            "CERTIFICATE": ["chứng chỉ", "chứng nhận", "certificate", "certification",
                            "certifications"],
        },
    }

    RE_KHOANG_SO = re.compile(r"^\d+(?:[.,]\d+)?\s*[-–]\s*\d+(?:[.,]\d+)?$")
    RE_SO_DINH_DON_VI = re.compile(
        r"^\d[\d.,]*\s*"
        r"(?:tr|triệu|trieu|m|k|usd|vnd|vnđ|đ|d|%|"
        r"năm|nam|tháng|thang|ngày|ngay|"
        r"year|years|yrs|month|months|day|days)$",
        re.IGNORECASE,
    )
    RE_SO_PHAN_CACH = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")

    TU_DON_VI = {
        "triệu", "tr", "trieu", "m", "k", "usd", "vnd", "vnđ", "đ", "d",
        "năm", "nam", "tháng", "thang", "ngày", "ngay",
        "year", "years", "yrs", "month", "months", "day", "days",
    }

    def __init__(self, knowledge_dir="."):
        self.knowledge_dir = Path(knowledge_dir)
        self._location_block_countdown = 0

        alias_data = self.doc_json("alias_knowledge.json")
        skill_data = self.doc_json("skill_knowledge.json")
        certi_data = self.doc_json("certi_knowledge.json")
        domain_data = self.doc_txt("domain_knowledge.txt")
        trigger_data = self.doc_json("trigger_knowledge.json")
        degree_data = self.doc_json("degree_knowledge.json")
        benefit_data = self.doc_json_neu_co("benefit_knowledge.json")
        location_data = self.doc_json_neu_co("location_knowledge.json")

        position_data = self.doc_txt_neu_co("position_knowledge.txt")
        company_data = self.doc_txt_neu_co("company_knowledge.txt")

        self.bang_alias = self.tao_bang_alias(alias_data)

        self.skill_gaz = self.tao_tap_skill_gazetteer(skill_data)
        self.group_skill_gaz = self.tao_tap_group_skill_gazetteer(skill_data)
        self.certi_gaz = self.tao_tap_gazetteer(certi_data)
        self.domain_gaz = self.tao_tap_txt_gazetteer(domain_data)
        self.degree_gaz = self.tao_tap_gazetteer(degree_data)
        self.benefit_gaz = self.tao_tap_gazetteer(benefit_data)
        self.location_gaz = self.tao_tap_gazetteer(location_data) # <-- THÊM DÒNG NÀY

        self.pos_gaz = self.tao_tap_txt_gazetteer(position_data)
        self.company_gaz = self.tao_tap_txt_gazetteer(company_data)

        self.exp_domain_gaz = self.domain_gaz | self.pos_gaz 

        self.pos_gaz_1_token = {p for p in self.pos_gaz if " " not in p}
        self.company_gaz_1_token = {c for c in self.company_gaz if " " not in c}
        self.company_gaz_nhieu_token = [c for c in self.company_gaz if " " in c]

        self.do_dai_cum_toi_da = max(
            (
                len(cum.split())
                for gaz in (self.skill_gaz, self.group_skill_gaz, self.certi_gaz,
                            self.degree_gaz, self.domain_gaz,
                            self.pos_gaz, self.company_gaz, self.benefit_gaz, self.location_gaz)
                for cum in gaz
            ),
            default=1,
        )

        ten_trigger = [luat[0] for luat in self.TRIGGER_LUAT]
        vi_tri_dau = self.TEN_FEATURE.index(ten_trigger[0])
        assert self.TEN_FEATURE[vi_tri_dau:vi_tri_dau + len(ten_trigger)] == ten_trigger, \
            "TRIGGER_LUAT lệch thứ tự so với TEN_FEATURE"

        self.bang_trigger = {}
        for ten, khoa, huong, so_token in self.TRIGGER_LUAT:
            tap_cum = self.lay_nhom_cum(trigger_data, khoa, huong)
            self.bang_trigger[ten] = (
                tap_cum, self.do_dai_cum_dai_nhat(tap_cum), huong, so_token
            )

        # Cụm keyword cả dòng (chỉ còn LOCATION)
        self.location_cum = self.lay_nhom_cum(trigger_data, "LOCATION", "sau")

         # --- CỤM KEYWORD INLINE CHO CERTIFICATE, EXPERIENCE, DEGREE (MỚI) ---
        self.certi_inline_cum = self.chuan_hoa_tap_cum([
            "chứng chỉ", "chứng nhận", "certificate", "certification", "certified"
        ])
        
        self.exp_inline_cum = self.chuan_hoa_tap_cum([
            "kinh nghiệm", "trải nghiệm", "experience", "exp", "years of experience"
        ])
        
        self.degree_inline_cum = self.chuan_hoa_tap_cum([
            "bằng cấp", "tốt nghiệp", "trình độ", "chuyên ngành", "ngành", 
            "degree", "major", "education", "graduated"
        ])
        # ---------------------------------------------------------------------
        
        # THÊM DÒNG NÀY ĐỂ TÍNH ĐỘ DÀI MAX CỦA TỪ DẪN
        self.do_dai_loc_trigger = self.do_dai_cum_dai_nhat(self.location_cum)

        # Vùng ngành của DEGREE
        self.nganh_trigger = self.lay_nhom_cum(
            trigger_data, "DEGREE", "nganh", self.NGANH_MAC_DINH
        )
        self.do_dai_nganh_trigger = self.do_dai_cum_dai_nhat(self.nganh_trigger)
        self.nganh_ket_thuc = self.lay_nhom_cum(
            trigger_data, "DEGREE", "ket_thuc_nganh", self.KET_THUC_NGANH_MAC_DINH
        )
        self.do_dai_nganh_ket_thuc = self.do_dai_cum_dai_nhat(self.nganh_ket_thuc)

        # Vùng chứng chỉ của CERTIFICATE (MỚI)
        self.certi_trigger = self.lay_nhom_cum(
            trigger_data, "CERTIFICATE", "chung_chi", self.CHUNG_CHI_MAC_DINH
        )
        self.do_dai_certi_trigger = self.do_dai_cum_dai_nhat(self.certi_trigger)
        self.certi_ket_thuc = self.lay_nhom_cum(
            trigger_data, "CERTIFICATE", "ket_thuc_chung_chi", self.KET_THUC_CHUNG_CHI_MAC_DINH
        )
        self.do_dai_certi_ket_thuc = self.do_dai_cum_dai_nhat(self.certi_ket_thuc)

        cau_hinh_lq = trigger_data.get("LIEN_QUAN", {})
        self.tu_lien_quan = self.chuan_hoa_tap_cum(
            cau_hinh_lq.get("tu_lien_quan", self.LIEN_QUAN_MAC_DINH["tu_lien_quan"])
        )
        self.do_dai_lien_quan = self.do_dai_cum_dai_nhat(self.tu_lien_quan)

        ngu_canh_json = cau_hinh_lq.get("ngu_canh", {})
        self.cum_ngu_canh = {}
        for nhan in self.NHAN_NGU_CANH:
            tap_cum = self.chuan_hoa_tap_cum(
                ngu_canh_json.get(nhan, self.LIEN_QUAN_MAC_DINH["ngu_canh"][nhan])
            )
            self.cum_ngu_canh[nhan] = (tap_cum, self.do_dai_cum_dai_nhat(tap_cum))

        # Vùng kinh nghiệm của EXPERIENCE (MỚI)
        self.exp_trigger = self.lay_nhom_cum(
            trigger_data, "EXPERIENCE", "vung", 
            ["kinh nghiệm về", "kinh nghiệm trong", "kinh nghiệm với"]
        )
        self.do_dai_exp_trigger = self.do_dai_cum_dai_nhat(self.exp_trigger)
        self.exp_ket_thuc = self.lay_nhom_cum(
            trigger_data, "EXPERIENCE", "ket_thuc_vung", self.KET_THUC_NGANH_MAC_DINH
        )
        self.do_dai_exp_ket_thuc = self.do_dai_cum_dai_nhat(self.exp_ket_thuc)

    def doc_json(self, ten_file):
        duong_dan = self.knowledge_dir / ten_file
        with duong_dan.open("r", encoding="utf-8") as f:
            return json.load(f)

    def doc_txt(self, ten_file):
        duong_dan = self.knowledge_dir / ten_file
        with duong_dan.open("r", encoding="utf-8") as f:
            return [dong.strip() for dong in f if dong.strip()]

    def doc_txt_neu_co(self, ten_file):
        duong_dan = self.knowledge_dir / ten_file
        if not duong_dan.exists():
            return []
        return self.doc_txt(ten_file)

    def doc_json_neu_co(self, ten_file):
        duong_dan = self.knowledge_dir / ten_file
        if not duong_dan.exists():
            return {}
        return self.doc_json(ten_file)

    @staticmethod
    def chuan_hoa(text):
        return str(text).strip().casefold()

    @staticmethod
    def lay_chuoi(data):
        ket_qua = set()
        if isinstance(data, str):
            if data.strip():
                ket_qua.add(data.strip())
        elif isinstance(data, list):
            for item in data:
                ket_qua.update(FeatureExtractor.lay_chuoi(item))
        elif isinstance(data, dict):
            for value in data.values():
                ket_qua.update(FeatureExtractor.lay_chuoi(value))
        return ket_qua

    def tao_bang_alias(self, alias_data):
        bang_alias = {}
        for ten_chuan, aliases in alias_data.items():
            bang_alias[self.chuan_hoa(ten_chuan)] = self.chuan_hoa(ten_chuan)
            if not isinstance(aliases, list):
                continue
            for alias in aliases:
                alias = str(alias).strip()
                bang_alias[self.chuan_hoa(alias)] = ten_chuan
        return bang_alias

    def chuan_hoa_alias_mot_token(self, token):
        return self.bang_alias.get(self.chuan_hoa(token), token)

    def tao_tap_gazetteer(self, data):
        tap_gaz = set()
        for item in self.lay_chuoi(data):
            item_chuan = self.chuan_hoa(item)
            tap_gaz.add(item_chuan)
        return tap_gaz

    def tao_tap_skill_gazetteer(self, skill_data):
        tap_gaz = set()
        for danh_sach_skill in skill_data.values():
            if not isinstance(danh_sach_skill, list):
                continue
            for skill in danh_sach_skill:
                skill_chuan = self.chuan_hoa(skill)
                tap_gaz.add(skill_chuan)
        return tap_gaz

    def tao_tap_group_skill_gazetteer(self, skill_data):
        tap_gaz = set()
        for group_skill in skill_data.keys():
            if isinstance(group_skill, str):
                tap_gaz.add(self.chuan_hoa(group_skill))
        return tap_gaz

    def tao_tap_txt_gazetteer(self, data):
        tap_gaz = set()
        for item in data:
            item_chuan = self.chuan_hoa(item)
            tap_gaz.add(item_chuan)
        return tap_gaz

    def chuan_hoa_tap_cum(self, danh_sach_cum):
        return {
            " ".join(self.chuan_hoa(cum).split())
            for cum in danh_sach_cum
            if isinstance(cum, str) and cum.strip()
        }

    def lay_nhom_cum(self, trigger_data, khoa, nhom, mac_dinh=()):
        gia_tri = trigger_data.get(khoa)
        if isinstance(gia_tri, dict):
            gia_tri = gia_tri.get(nhom)
        elif nhom not in ("sau", "truoc"):
            gia_tri = None
        if gia_tri is None:
            gia_tri = mac_dinh
        return self.chuan_hoa_tap_cum(gia_tri)

    @staticmethod
    def do_dai_cum_dai_nhat(tap_cum):
        return max((len(cum.split()) for cum in tap_cum), default=1)

    @staticmethod
    def la_dau_het_cau(text):
        t = text.strip()
        return bool(t) and (t in {";", "!", "?"} or set(t) <= {"."})

    def tim_cum(self, tokens_casefold, tap_cum, do_dai_toi_da):
        ket_qua = []
        if not tap_cum:
            return ket_qua
        so_token = len(tokens_casefold)
        for i in range(so_token):
            for do_dai in range(1, min(do_dai_toi_da, so_token - i) + 1):
                if " ".join(tokens_casefold[i:i + do_dai]) in tap_cum:
                    ket_qua.append((i, i + do_dai))
        return ket_qua

    def co_cum_trong_dong(self, tokens_casefold, tap_cum):
        dong = " " + " ".join(tokens_casefold) + " "
        return any(f" {cum} " in dong for cum in tap_cum)

    def tao_feature_ngoac(self, tokens):
        so_token = len(tokens)
        ben_trong = [False] * so_token
        truoc_ngoac = [False] * so_token
        la_ngoac = [False] * so_token
        do_sau = 0
        for i, token in enumerate(tokens):
            text = token[0].strip()
            if text == "(":
                do_sau += 1
                la_ngoac[i] = True
            elif text == ")":
                la_ngoac[i] = True
                do_sau = max(0, do_sau - 1)
            else:
                ben_trong[i] = do_sau > 0
        for i, token in enumerate(tokens):
            if token[0].strip() != "(":
                continue
            da_dem = 0
            j = i - 1
            while j >= 0 and da_dem < 3:
                text = tokens[j][0].strip()
                if text not in {"(", ")"} and any(c.isalnum() for c in text):
                    truoc_ngoac[j] = True
                    da_dem += 1
                j -= 1
        return ben_trong, truoc_ngoac, la_ngoac

    def danh_dau_gazetteer(self, tokens_chuan, tap_gaz):
        so_token = len(tokens_chuan)
        ket_qua = [False] * so_token
        for i in range(so_token):
            for do_dai in range(min(self.do_dai_cum_toi_da, so_token - i), 0, -1):
                cum = " ".join(tokens_chuan[i:i + do_dai])
                if cum in tap_gaz:
                    for j in range(i, i + do_dai):
                        ket_qua[j] = True
                    break
        return ket_qua

    def danh_dau_cua_so(self, vi_tri_cum, huong, so_token, co_noi_dung, het_cau):
        n = len(co_noi_dung)
        ket_qua = [False] * n

        for bat_dau, ket_thuc in vi_tri_cum:
            if huong == "sau":
                j, buoc = ket_thuc, 1
            else:
                j, buoc = bat_dau - 1, -1

            da_dem = 0
            while 0 <= j < n and da_dem < so_token:
                if het_cau[j]:
                    break
                ket_qua[j] = True
                if co_noi_dung[j]:
                    da_dem += 1
                j += buoc

        return ket_qua

    def danh_dau_vung_nganh(self, tokens_casefold, co_noi_dung, het_cau):
        n = len(tokens_casefold)
        trong_vung = [False] * n
        dau_muc = [False] * n

        vi_tri_ket_thuc = {
            bat_dau for bat_dau, _ in self.tim_cum(
                tokens_casefold, self.nganh_ket_thuc, self.do_dai_nganh_ket_thuc
            )
        }

        for _, ket_thuc in self.tim_cum(
            tokens_casefold, self.nganh_trigger, self.do_dai_nganh_trigger
        ):
            j = ket_thuc
            da_dem = 0
            dau_moi = True
            while j < n and da_dem < self.SO_TOKEN_TOI_DA_VUNG:
                if het_cau[j] or j in vi_tri_ket_thuc:
                    break
                trong_vung[j] = True
                if tokens_casefold[j] in self.TU_PHAN_CACH:
                    dau_moi = True
                elif co_noi_dung[j]:
                    if dau_moi:
                        dau_muc[j] = True
                        dau_moi = False
                    da_dem += 1
                j += 1

        return trong_vung, dau_muc

    def danh_dau_vung_chung_chi(self, tokens_casefold, co_noi_dung, het_cau):
        n = len(tokens_casefold)
        trong_vung = [False] * n
        dau_muc = [False] * n

        vi_tri_ket_thuc = {
            bat_dau for bat_dau, _ in self.tim_cum(
                tokens_casefold, self.certi_ket_thuc, self.do_dai_certi_ket_thuc
            )
        }

        for _, ket_thuc in self.tim_cum(
            tokens_casefold, self.certi_trigger, self.do_dai_certi_trigger
        ):
            j = ket_thuc
            da_dem = 0
            dau_moi = True
            while j < n and da_dem < self.SO_TOKEN_TOI_DA_VUNG:
                if het_cau[j] or j in vi_tri_ket_thuc:
                    break
                trong_vung[j] = True
                if tokens_casefold[j] in self.TU_PHAN_CACH:
                    dau_moi = True
                elif co_noi_dung[j]:
                    if dau_moi:
                        dau_muc[j] = True
                        dau_moi = False
                    da_dem += 1
                j += 1

        return trong_vung, dau_muc

    def chon_ngu_canh(self, bat_dau, ket_thuc, cue, het_cau):
        n = len(het_cau)

        for nhan in self.NHAN_NGU_CANH:
            if any(cue[nhan][j] for j in range(bat_dau, ket_thuc)):
                return nhan

        trai_ok = phai_ok = True
        for khoang_cach in range(1, self.KHOANG_CACH_NGU_CANH + 1):
            ung_vien = []

            j = bat_dau - khoang_cach
            if trai_ok and j >= 0 and not het_cau[j]:
                ung_vien.append(j)
            else:
                trai_ok = False

            j = ket_thuc - 1 + khoang_cach
            if phai_ok and j < n and not het_cau[j]:
                ung_vien.append(j)
            else:
                phai_ok = False

            for nhan in self.NHAN_NGU_CANH:
                if any(cue[nhan][j] for j in ung_vien):
                    return nhan

            if not trai_ok and not phai_ok:
                break

        return None

    def tinh_feature_lien_quan(self, tokens_casefold, co_cue_gaz, trong_vung_nganh, het_cau):
        n = len(tokens_casefold)
        la_lien_quan = [False] * n
        ket_qua = {nhan: [False] * n for nhan in self.NHAN_NGU_CANH}

        cac_lan_xuat_hien = self.tim_cum(
            tokens_casefold, self.tu_lien_quan, self.do_dai_lien_quan
        )
        if not cac_lan_xuat_hien:
            return la_lien_quan, ket_qua

        for bat_dau, ket_thuc in cac_lan_xuat_hien:
            for j in range(bat_dau, ket_thuc):
                la_lien_quan[j] = True

        cue = {}
        for nhan in self.NHAN_NGU_CANH:
            mang = list(co_cue_gaz[nhan])
            tap_cum, do_dai = self.cum_ngu_canh[nhan]
            cac_cum = self.tim_cum(tokens_casefold, tap_cum, do_dai)
            if nhan == "DEGREE":
                cac_cum += self.tim_cum(
                    tokens_casefold, self.nganh_trigger, self.do_dai_nganh_trigger
                )
            for bat_dau, ket_thuc in cac_cum:
                for j in range(bat_dau, ket_thuc):
                    mang[j] = True
            cue[nhan] = mang

        for j in range(n):
            if trong_vung_nganh[j]:
                cue["DEGREE"][j] = True

        for bat_dau, ket_thuc in cac_lan_xuat_hien:
            nhan = self.chon_ngu_canh(bat_dau, ket_thuc, cue, het_cau)
            if nhan is None:
                continue
            for j in range(bat_dau, ket_thuc):
                ket_qua[nhan][j] = True

        return la_lien_quan, ket_qua

    def tinh_feature_regex_so(self, tokens):
        so_token = len(tokens)
        texts = [str(tok[0]).strip() for tok in tokens]
        chuan = [self.chuan_hoa(t) for t in texts]

        la_khoang = [bool(self.RE_KHOANG_SO.match(t)) for t in texts]
        la_so_dv = [
            bool(self.RE_SO_DINH_DON_VI.match(t)) or bool(self.RE_SO_PHAN_CACH.match(t))
            for t in texts
        ]
        is_tu_dv = [c in self.TU_DON_VI for c in chuan]
        is_truoc = [
            (i + 1 < so_token) and is_tu_dv[i + 1]
            for i in range(so_token)
        ]
        return la_khoang, la_so_dv, is_truoc, is_tu_dv

    def danh_dau_pos(self, tokens_chuan):
        so_token = len(tokens_chuan)
        tien_to = [False] * so_token
        hau_to = [False] * so_token

        for i, t in enumerate(tokens_chuan):
            if not t:
                continue
            for p in self.pos_gaz_1_token:
                if t == p:
                    continue
                if not tien_to[i] and t.startswith(p):
                    tien_to[i] = True
                if not hau_to[i] and t.endswith(p):
                    hau_to[i] = True
                if tien_to[i] and hau_to[i]:
                    break

        is_in = self.danh_dau_gazetteer(tokens_chuan, self.pos_gaz)
        return tien_to, hau_to, is_in

    def danh_dau_hau_to_company(self, tokens_chuan):
        so_token = len(tokens_chuan)
        ket_qua = [False] * so_token

        for i, t in enumerate(tokens_chuan):
            if not t:
                continue
            for c in self.company_gaz_1_token:
                if t != c and t.endswith(c):
                    ket_qua[i] = True
                    break
            if ket_qua[i]:
                continue
            for c in self.company_gaz_nhieu_token:
                so_tu = len(c.split())
                if i + 1 < so_tu:
                    continue
                cum = " ".join(tokens_chuan[i - so_tu + 1:i + 1])
                if cum != c and cum.endswith(c):
                    ket_qua[i] = True
                    break

        return ket_qua

    def tinh_feature_dau_cau(self, tokens):
        so_token = len(tokens)
        texts = [str(tok[0]).strip() for tok in tokens]

        truoc_hai_cham = [False] * so_token
        sau_hai_cham = [False] * so_token
        truoc_sau_phay = [False] * so_token

        for i in range(so_token):
            if i - 1 >= 0:
                if texts[i - 1] == ":":
                    truoc_hai_cham[i] = True
                if texts[i - 1] in {",", "/"}:
                    truoc_sau_phay[i] = True
            if i + 1 < so_token:
                if texts[i + 1] == ":":
                    sau_hai_cham[i] = True
                if texts[i + 1] in {",", "/"}:
                    truoc_sau_phay[i] = True

        return truoc_hai_cham, sau_hai_cham, truoc_sau_phay

    def trich_xuat_features(self, tokens):
        danh_sach_text = [str(token[0]) for token in tokens]

        ben_trong, truoc_ngoac, la_ngoac = self.tao_feature_ngoac(tokens)

        tokens_chuan = [
            self.chuan_hoa(self.chuan_hoa_alias_mot_token(text.strip()))
            for text in danh_sach_text
        ]

        tokens_casefold = [self.chuan_hoa(text) for text in danh_sach_text]
        co_noi_dung = [any(c.isalnum() for c in text) for text in danh_sach_text]
        het_cau = [self.la_dau_het_cau(text) for text in danh_sach_text]

        co_skill = self.danh_dau_gazetteer(tokens_chuan, self.skill_gaz)
        co_group = self.danh_dau_gazetteer(tokens_chuan, self.group_skill_gaz)
        co_certi = self.danh_dau_gazetteer(tokens_chuan, self.certi_gaz)
        co_degree = self.danh_dau_gazetteer(tokens_chuan, self.degree_gaz)
        co_domain = self.danh_dau_gazetteer(tokens_chuan, self.domain_gaz)
        co_exp_domain = self.danh_dau_gazetteer(tokens_chuan, self.exp_domain_gaz)


        vi_tri_loc = self.tim_cum(tokens_casefold, self.location_cum, self.do_dai_loc_trigger)
        
        if vi_tri_loc:
            _, ket_thuc_cuoi = vi_tri_loc[-1]
            
            so_token_sau = sum(1 for j in range(ket_thuc_cuoi, len(tokens_casefold)) if co_noi_dung[j])
            
            dong_co_location = True
            if so_token_sau == 0:
                self._location_block_countdown = 1 
            else:
                self._location_block_countdown = 0 
        else:
            if self._location_block_countdown > 0:
                dong_co_location = True
                self._location_block_countdown -= 1
            else:
                dong_co_location = False

        dong_co_certi = self.co_cum_trong_dong(tokens_casefold, self.certi_inline_cum)
        dong_co_exp = self.co_cum_trong_dong(tokens_casefold, self.exp_inline_cum)
        dong_co_degree = self.co_cum_trong_dong(tokens_casefold, self.degree_inline_cum)

        co_trigger = {}
        for ten, (tap_cum, do_dai, huong, so_token) in self.bang_trigger.items():
            vi_tri_cum = self.tim_cum(tokens_casefold, tap_cum, do_dai)
            co_trigger[ten] = self.danh_dau_cua_so(
                vi_tri_cum, huong, so_token, co_noi_dung, het_cau
            )

        # Vùng ngành của DEGREE
        trong_vung_nganh, dau_muc_nganh = self.danh_dau_vung_nganh(
            tokens_casefold, co_noi_dung, het_cau
        )
        
        # Vùng chứng chỉ của CERTIFICATE (MỚI)
        trong_vung_certi, dau_muc_certi = self.danh_dau_vung_chung_chi(
            tokens_casefold, co_noi_dung, het_cau
        )


        trong_vung_exp, dau_muc_exp = self.danh_dau_vung_kinh_nghiem(
            tokens_casefold, co_noi_dung, het_cau
        )


        co_cue_gaz = {
            "DEGREE": co_degree,
            "EXPERIENCE": [False] * len(tokens),
            "SKILL": [a or b for a, b in zip(co_skill, co_group)],
            "CERTIFICATE": co_certi,
        }
        la_lien_quan, lien_quan_ngu_canh = self.tinh_feature_lien_quan(
            tokens_casefold, co_cue_gaz, trong_vung_nganh, het_cau
        )

        la_khoang, la_so_dv, is_truoc_dv, is_tu_dv = self.tinh_feature_regex_so(tokens)
        tien_to_pos, hau_to_pos, is_in_pos = self.danh_dau_pos(tokens_chuan)
        is_hau_to_company = self.danh_dau_hau_to_company(tokens_chuan)
        co_benefit = self.danh_dau_gazetteer(tokens_chuan, self.benefit_gaz)
        truoc_hai_cham, sau_hai_cham, truoc_sau_phay = self.tinh_feature_dau_cau(tokens)


        ket_qua = []

        for i, text_goc in enumerate(danh_sach_text):
            text = text_goc.strip()
            co_chu = any(c.isalpha() for c in text)
            co_so = any(c.isdigit() for c in text)

            features = [
                text.isupper(),
                bool(text) and text[0].isupper(),
                text.islower(),
                any(c.isupper() for c in text),
                bool(text) and text.isdigit(),
                co_so,
                bool(text) and text.isalpha(),
                co_chu and co_so,
                bool(text) and text[0].isdigit(),
                bool(text) and text[-1].isdigit(),
                "-" in text,
                "/" in text,
                "." in text,
                "+" in text,
                "#" in text,
                ben_trong[i],
                truoc_ngoac[i],
                la_ngoac[i],
                co_skill[i],
                co_group[i],
                co_certi[i],
                co_degree[i],
                co_domain[i],
                co_exp_domain[i],
            ]

            features.append(dong_co_location)

            # 3 feature inline mới
            features.append(dong_co_certi)
            features.append(dong_co_exp)
            features.append(dong_co_degree)

            features.extend(co_trigger[luat[0]][i] for luat in self.TRIGGER_LUAT)

            # 2 feature vùng ngành
            features.append(trong_vung_nganh[i])
            features.append(dau_muc_nganh[i])
            
            # 2 feature vùng chứng chỉ
            features.append(trong_vung_certi[i])
            features.append(dau_muc_certi[i])

            # 2 feature vùng kinh nghiệm 
            features.append(trong_vung_exp[i])
            features.append(dau_muc_exp[i])

            features.append(la_lien_quan[i])
            features.extend(lien_quan_ngu_canh[nhan][i] for nhan in self.NHAN_NGU_CANH)

            features.extend([
                la_khoang[i],
                la_so_dv[i],
                is_truoc_dv[i],
                is_tu_dv[i],
                tien_to_pos[i],
                hau_to_pos[i],
                is_in_pos[i],
                is_hau_to_company[i],
                co_benefit[i],
                truoc_hai_cham[i],
                sau_hai_cham[i],
                truoc_sau_phay[i],
            ])

            assert len(features) == len(self.TEN_FEATURE)

            features = [idx for idx, gia_tri in enumerate(features) if gia_tri]
            ket_qua.append(features)

        return ket_qua

    def danh_dau_vung_kinh_nghiem(self, tokens_casefold, co_noi_dung, het_cau):
        n = len(tokens_casefold)
        trong_vung = [False] * n
        dau_muc = [False] * n

        vi_tri_ket_thuc = {
            bat_dau for bat_dau, _ in self.tim_cum(
                tokens_casefold, self.exp_ket_thuc, self.do_dai_exp_ket_thuc
            )
        }

        for _, ket_thuc in self.tim_cum(
            tokens_casefold, self.exp_trigger, self.do_dai_exp_trigger
        ):
            j = ket_thuc
            da_dem = 0
            dau_moi = True
            while j < n and da_dem < self.SO_TOKEN_TOI_DA_VUNG:
                if het_cau[j] or j in vi_tri_ket_thuc:
                    break
                trong_vung[j] = True
                if tokens_casefold[j] in self.TU_PHAN_CACH:
                    dau_moi = True
                elif co_noi_dung[j]:
                    if dau_moi:
                        dau_muc[j] = True
                        dau_moi = False
                    da_dem += 1
                j += 1

        return trong_vung, dau_muc