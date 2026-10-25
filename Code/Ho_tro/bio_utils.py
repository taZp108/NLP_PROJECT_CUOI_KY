from Ho_tro.Normalize import chuan_hoa_2, chuan_hoa_1
import html, re, unicodedata
from collections import defaultdict 
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix


# Thêm tập bio vào một task đã có span và tokenized (dùng lên dữ liệu training)
def bien_span_thanh_bio(task: list) -> list:
    bio = []

    span_index_hien_tai = 0
    max_span_index = len(task["spans"]) - 1

    if(max_span_index < 0):
        bio = [["O" for x in dong] for dong in task["tokenized"]]
        task["bio"] = bio
        return

    
    spans = task["spans"]
    lan_dau = True

    for dong in task["tokenized"]:
        bio_dong = []

        for token in dong:
            if token[1] > spans[span_index_hien_tai][1]:
                span_index_hien_tai = min(span_index_hien_tai + 1, max_span_index)

            if token[1] >= spans[span_index_hien_tai][0] and token[2] <= spans[span_index_hien_tai][1]:
                if lan_dau:
                    bio_dong.append(f"B-{spans[span_index_hien_tai][2]}")
                    lan_dau = False
                else:
                    bio_dong.append(f"I-{spans[span_index_hien_tai][2]}")
            else:
                bio_dong.append("O")
                lan_dau = True

        bio.append(bio_dong)

    task["bio"] = bio

    return task


# Thêm tập span vào một task đã có bio và tokenized (dùng với kết quả pred của mô hình)
def bien_bio_thanh_span(task: dict) -> dict:
    out = []
    bio_s = task["bio"]
    tokenized = task["tokenized"]
    text_cua_task = task["text"]

    for bio_dong, token_dong in zip(bio_s, tokenized):
        len_bio_dong = len(bio_dong)
        i = 0

        while i < len_bio_dong:
            if bio_dong[i][0] == "B":
                j = i + 1

                while j < len_bio_dong:
                    if bio_dong[j][0] in {"B", "O"}:
                        break
                    j += 1

                # bắt đầu lấy span khi đã có start i và end j
                start = token_dong[i][1]
                end = token_dong[j - 1][2]
                label = bio_dong[i][2:]
                text = text_cua_task[start:end]

                out.append((start, end, label, text))

            i += 1

    task["spans"] = out

    return task


# Xử lý overlap, coi nested là overlap, giữ lại span dài, nếu có danh sách ưu tiên thì lấy theo danh sách, gộp lại 2 span overlap nếu như nó cùng nhãn
def xu_ly_overlap(task: dict, danh_sach_uu_tien: dict = None) -> dict:
    spans = task["spans"]

    if(len(spans)) < 2:
        return

    
    span_chong_cheo = spans[0]
    index_chong_cheo = 0

    for span in spans[1:]:
        if span[0] < span_chong_cheo[1]:
            if span_chong_cheo[2] == span[2]:
                del spans[index_chong_cheo + 1]
                del spans[index_chong_cheo]

                text = (
                    span_chong_cheo[3][0:span[0] - span_chong_cheo[0]]
                    + span[3][0:]
                )

                if span_chong_cheo[1] > span[1]:
                    text += span_chong_cheo[3][span[1] - span_chong_cheo[1]:]

                max_end = max(span[1], span_chong_cheo[1])

                spans.insert(
                    index_chong_cheo,
                    (
                        span_chong_cheo[0],
                        max_end,
                        span_chong_cheo[2],
                        text
                    )
                )

            elif not danh_sach_uu_tien:
                chieu_dai_span_hien_tai = span[1] - span[0]
                chieu_dai_span_chong_cheo = span_chong_cheo[1] - span_chong_cheo[0]

                if chieu_dai_span_chong_cheo > chieu_dai_span_hien_tai:
                    del spans[index_chong_cheo + 1]
                else:
                    span_chong_cheo = span
                    del spans[index_chong_cheo]

            else:
                do_uu_tien_nhan_chong_cheo = danh_sach_uu_tien.get(
                    span_chong_cheo[2], 0
                )

                do_uu_tien_nhan_hien_tai = danh_sach_uu_tien.get(
                    span[2], 0
                )

                if do_uu_tien_nhan_chong_cheo >= do_uu_tien_nhan_hien_tai:
                    del spans[index_chong_cheo + 1]
                else:
                    del spans[index_chong_cheo]

        else:
            span_chong_cheo = span
            index_chong_cheo += 1

    return task

# Check xem một bio của một task nó có lỗi gì hem
def check_bio(task: dict) -> dict:
    bio_s = task["bio"]
    tokenized = task["tokenized"]

    labels = {
        "COMPANY",
        "POSITION",
        "LOCATION",
        "SALARY",
        "EXPERIENCE",
        "DEGREE",
        "SKILL",
        "SKILL_GROUP",
        "CERTIFICATE",
        "DEADLINE",
        "BENEFIT"
    }


    for bio_dong, token_dong in zip(bio_s, tokenized):
        if len(bio_dong) != len(token_dong):
            return False

        da_co_B = False

        for i, bio in enumerate(bio_dong):
            if bio[0] == "O":
                da_co_B = False

            elif bio[0] == "I":
                if (
                    i == 0
                    or bio[2:] not in labels
                    or not da_co_B
                    or bio_dong[i - 1][0] == "O"
                    or bio[2:] != bio_dong[i - 1][2:]
                ):
                    return False

            elif bio[0] == "B":
                if bio[2:] not in labels:
                    return False

                da_co_B = True

            else:
                return False

    return True




# check hàm chuẩn hóa 2 có làm lệch offset hay không
def check_spans(text_after: str, spans: list) -> list:
    errors = []
    for span in spans:
        expected = chuan_hoa_2(span[3])
        gold = text_after[span[0]:span[1]]
        if gold != expected:
            errors.append(
                {
                    "start": span[0],
                    "end": span[1],
                    "text_after": gold,
                    "text_span": expected,
                    "nhan": span[2]
                }
            )
    return errors


# check xem có bị lệch offset dẫn đến lệch span hay không
def check_du_lieu_gan_nhan(tasks: list, old_normalize) -> dict:
    report = {"khong_NFC": [], "span_lech": []}
    for t in tasks:
        tid = t["task_id"]
        text = t["text"]
        if not unicodedata.is_normalized("NFC", text):
            report["khong_NFC"].append(tid);
        errs = check_spans(t["text_da_chuan_hoa_2"], t["spans"])
        if errs:
            report["span_lech"].append((tid, errs))
    return report


def danh_gia_tong_hop(tasks: list) -> dict:
    """
    Đánh giá mô hình trên toàn bộ danh sách tasks (Micro-average, Strict-match).
    Trả về Precision, Recall, F1 tổng hợp của tất cả các loại thực thể.
    """
    tp = 0 # True Positive: Đoán đúng hoàn toàn
    fp = 0 # False Positive: Đoán bừa (đoán ra nhưng sai ranh giới/loại)
    fn = 0 # False Negative: Bỏ sót (có trong gold nhưng không đoán ra)

    for task in tasks:
        # Lấy danh sách span gold và span predict
        gold_spans = task.get("spans", [])
        pred_spans = task.get("spans_predict", [])

        # Chỉ lấy 3 thông tin quan trọng nhất để so sánh strict-match: (start, end, label)
        # Dùng set() để tự động loại bỏ trùng lặp nếu có và tối ưu phép giao/hợp
        set_gold = set((s[0], s[1], s[2]) for s in gold_spans)
        set_pred = set((s[0], s[1], s[2]) for s in pred_spans)

        # Tính toán TP, FP, FN cho từng task
        tp += len(set_gold & set_pred) # Giao của 2 tập (Đoán đúng)
        fp += len(set_pred - set_gold) # Predict có mà Gold không có (Đoán bừa)
        fn += len(set_gold - set_pred) # Gold có mà Predict không có (Bỏ sót)

    # Tính P, R, F1 tổng (Micro)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn
    }


def _lay_tap_thuc_the(bio_dong: list) -> set:

    thuc_the = set()
    loai, bat_dau = None, None
    
    # Thêm "O" vào cuối để tự động đóng thực thể đang mở nếu nó kéo dài đến hết câu
    for i, tag in enumerate(list(bio_dong) + ["O"]):
        if tag == "O":
            nhan_moi, la_B = None, False
        else:
            tien_to, nhan_moi = tag.split("-", 1)
            la_B = tien_to == "B"

        # Nếu đang mở 1 thực thể mà gặp nhãn khác loại, hoặc gặp B- mới -> Đóng thực thể cũ lại
        if loai is not None and (nhan_moi != loai or la_B):
            thuc_the.add((loai, bat_dau, i - 1))
            loai = None
            
        # Nếu có nhãn mới và chưa mở thực thể nào -> Bắt đầu mở thực thể mới
        if nhan_moi is not None and loai is None:
            loai, bat_dau = nhan_moi, i

    return thuc_the


def danh_gia(Y_that: list, Y_doan: list) -> dict:
    tp = 0
    fp = 0
    fn = 0
    thong_ke = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    cac_loai_trong_gold = set()

    for yt, yp in zip(Y_that, Y_doan):
        tt = _lay_tap_thuc_the(yt)      
        td = _lay_tap_thuc_the(yp)

        tp += len(tt & td)
        fp += len(td - tt)
        fn += len(tt - td)

        for e in (tt & td):
            thong_ke[e[0]]["tp"] += 1
            cac_loai_trong_gold.add(e[0])
        for e in (td - tt):
            thong_ke[e[0]]["fp"] += 1
        for e in (tt - td):
            thong_ke[e[0]]["fn"] += 1
            cac_loai_trong_gold.add(e[0])

    def _tinh(d, p, g):
        P = d / p if p else 0.0
        R = d / g if g else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        return {"p": P, "r": R, "f1": F, "so_that": g}

    tung_nhan = {
        nhan: _tinh(v["tp"], v["tp"] + v["fp"], v["tp"] + v["fn"])
        for nhan, v in sorted(thong_ke.items())
    }

    micro = _tinh(tp, tp + fp, tp + fn)

    # Macro chỉ tính trên các nhãn CÓ trong Gold (tránh mô hình đoán bừa loại lạ)
    f1_cac_loai = [v["f1"] for nhan, v in tung_nhan.items()
                   if nhan in cac_loai_trong_gold]
    macro_f1 = sum(f1_cac_loai) / len(f1_cac_loai) if f1_cac_loai else 0.0

    return {"micro": micro, "macro_f1": macro_f1, "tung_nhan": tung_nhan}




def in_ket_qua(kq: dict) -> None:
    print(f"{'nhãn':<14}{'P':>8}{'R':>8}{'F1':>8}{'số thật':>10}")
    for nhan, v in kq["tung_nhan"].items():
        print(f"{nhan:<14}{v['p']:>8.3f}{v['r']:>8.3f}"
              f"{v['f1']:>8.3f}{v['so_that']:>10}")

    m = kq["micro"]
    print("-" * 48)
    print(f"{'micro':<14}{m['p']:>8.3f}{m['r']:>8.3f}"
          f"{m['f1']:>8.3f}{m['so_that']:>10}")
    print(f"{'macro F1':<14}{kq['macro_f1']:>24.3f}")


def ve_confusion_matrix_ner(Y_that: list, Y_doan: list):
    flat_that = []
    flat_doan = []
    
    # Làm phẳng dữ liệu
    for seq_that, seq_doan in zip(Y_that, Y_doan):
        min_len = min(len(seq_that), len(seq_doan))
        flat_that.extend(seq_that[:min_len])
        flat_doan.extend(seq_doan[:min_len])
    
    # Gộp B-, I- thành nhãn gốc
    def clean_tag(tag):
        if tag == "O":
            return "O"
        return tag.split("-")[-1]

    cleaned_that = [clean_tag(t) for t in flat_that]
    cleaned_doan = [clean_tag(t) for t in flat_doan]
    
    all_labels = sorted(list(set(cleaned_that + cleaned_doan) - {"O"}))
    labels = ["O"] + all_labels

    cm = confusion_matrix(cleaned_that, cleaned_doan, labels=labels)

    plt.figure(figsize=(12, 9))
    cm_log = np.log1p(cm) 
    
    sns.heatmap(cm_log, annot=cm, fmt='d', cmap='YlOrRd',
                xticklabels=labels, yticklabels=labels,
                cbar_kws={'label': 'Log(Số lượng)'})
    
    plt.title("Ma trận nhầm lẫn (Confusion Matrix) - Mức Token", fontsize=14, fontweight='bold')
    plt.xlabel("Nhãn Dự Đoán (Predict)")
    plt.ylabel("Nhãn Thực Tế (Gold)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()