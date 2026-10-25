from . import bio_utils as bu
from . import Normalize as N
from . import task_utils as tu
from . import tokenize_task as tt

TAGSET = {
    "COMPANY", "POSITION", "LOCATION", "SALARY", "EXPERIENCE", "DEGREE",
    "CERTIFICATE", "SKILL", "SKILL_GROUP", "DEADLINE", "BENEFIT",
}
SPLITS = ("train", "dev", "test")


def tao_text_chuan_hoa_2(task: dict) -> dict:
    text = N.chuan_hoa_2(task["text"])
    task.setdefault("text_da_chuan_hoa_2", text)
    return task

def tao_bio_thanh_span_cho_tasks(tasks: list) -> list:
    for t in tasks:
        bu.bien_bio_thanh_span(t)
    return tasks

def tao_text_chuan_hoa_2_cho_tasks(tasks: list) -> list:
    for t in tasks:
        tao_text_chuan_hoa_2(t)
    return tasks

def xu_ly_overlap_cho_tasks(tasks: list) -> list:
    for t in tasks:
        bu.xu_ly_overlap(t)
    return tasks

def tokenized_cho_tasks(tasks: list) -> list:
    for t in tasks:
        tt.tokenize_task(t)

    return tasks

def bien_span_thanh_bio_cho_tasks(tasks: list) -> list:
    for t in tasks:
        bu.bien_span_thanh_bio(t)

    return tasks

def tinh_diem_cohhens_kappa(tasks1: list, tasks2: list) -> float:
    Po: float = 0
    Pe: float = 0

    trung_nhau: int = 0
    tong_bio: int = 0

    so_luong_nhan_cua_task1 = dict()
    so_luong_nhan_cua_task2 = dict()

    nhan_cua_task1 = set()
    nhan_cua_task2 = set()

    for task1, task2 in zip(tasks1, tasks2):
        bio1 = task1["bio"]
        bio2 = task2["bio"]
        for i in range(len(bio1)):
            bio1_dong = bio1[i]
            bio2_dong = bio2[i]

            tong_bio += len(bio1_dong)

            for j in range(len(bio1_dong)):

                # Phục vụ cho P0
                if bio1_dong[j] == bio2_dong[j]:
                    trung_nhau += 1


                # Phục vụ cho Pe

                nhan_cua_task1.add(bio1_dong[j])

                so_luong_nhan_cua_task1[bio1_dong[j]] = so_luong_nhan_cua_task1.get(bio1_dong[j], 0) + 1



                nhan_cua_task2.add(bio2_dong[j])

                so_luong_nhan_cua_task2[bio2_dong[j]] = so_luong_nhan_cua_task2.get(bio2_dong[j], 0) + 1


    Po = trung_nhau/tong_bio

    nhan_trung_nhau = nhan_cua_task1 & nhan_cua_task2

    for nhan in nhan_trung_nhau:
        Pe += (so_luong_nhan_cua_task1[nhan]/tong_bio)*(so_luong_nhan_cua_task2[nhan]/tong_bio)

    if Pe == 1:
        raise ValueError("Cohen's Kappa không xác định khi Pe = 1")
    
    score = (Po-Pe)/(1-Pe)

    return score



def danh_gia_do_dong_thuan_cua_tasks_trung_nhau(tasks_trung_nhau: dict) -> dict:
    keys = list(tasks_trung_nhau.keys())
    out = dict()
    for i in range(len(keys)):
        outi = dict()
        for j in range(len(keys)):
            if i == j:
                continue

            score = tinh_diem_cohhens_kappa(tasks1= tasks_trung_nhau[keys[i]], tasks2= tasks_trung_nhau[keys[j]])
            outi[keys[j]] = f"Độ đồng thuận giữa {keys[i]} và {keys[j]} là: {score}"

        out[keys[i]] = outi

    return out






def pipeline_cho_danh_gia_do_dong_thuan(dict_of_json_path: dict) -> dict:
    #{"thanh": path}


    #{"thanh": tasks}
    taskss = dict.fromkeys(dict_of_json_path.keys())
    for key, val in dict_of_json_path.items():
        taskss[key] = tu.load_json(val)

    #{"thanh": tasks_trung}
    task_id_trung = tu.lay_task_id_trung_nhau_tu_taskss(taskss)
    tasks_trung = tu.lay_task_trung(task_id_trung, taskss)


    #("thanh": tasks_da_xu_ly)
    for key, val in tasks_trung.items():
        tao_text_chuan_hoa_2_cho_tasks(val)
        xu_ly_overlap_cho_tasks(val)
        tokenized_cho_tasks(val)
        bien_span_thanh_bio_cho_tasks(val)

    out = danh_gia_do_dong_thuan_cua_tasks_trung_nhau(tasks_trung)

    return out
    

def pipeline_chuan_bi_data_training(json_paths: list) -> tuple:

    report = {
        "tong_task_doc_duoc": 0,
        "tong_task_hop_le": 0,
        "task_loi": [],
        "so_task_theo_split": {
            "train": 0,
            "dev": 0,
            "test": 0
        }
    }

    # 1. Đọc và gộp dữ liệu từ các file JSON
    tasks_goc = []

    for path in json_paths:
        try:
            tasks_goc.extend(tu.load_json(path))
        except Exception as e:
            report["task_loi"].append({
                "file": str(path),
                "loi": str(e)
            })

    report["tong_task_doc_duoc"] = len(tasks_goc)


    # 3. Xử lý từng task
    tasks_hop_le = []

    for task in tasks_goc:
        tid = task.get("task_id", "?")

        try:
            # Kiểm tra dữ liệu đầu vào
            if task.get("split") not in SPLITS:
                raise ValueError(
                    f"Split không hợp lệ: {task.get('split')}"
                )

            if not task.get("text", "").strip():
                raise ValueError("Văn bản rỗng")

            # Chuẩn hóa văn bản
            tao_text_chuan_hoa_2(task)

            
            # Xử lý span chồng chéo
            bu.xu_ly_overlap(task)

            

            # Tokenize theo dòng
            tt.tokenize_task(task)

            # Chuyển span thành BIO
            bu.bien_span_thanh_bio(task)

            # Kiểm tra BIO
            if not bu.check_bio(task):
                raise ValueError("BIO không hợp lệ")

            # Task hợp lệ
            tasks_hop_le.append(task)
            report["so_task_theo_split"][task["split"]] += 1

        except Exception as e:
            report["task_loi"].append({
                "task_id": tid,
                "loi": str(e)
            })

    report["tong_task_hop_le"] = len(tasks_hop_le)

    return tasks_hop_le, report


def tao_task_tu_text(text: str, task_id: str) -> dict:
    # Offset token/span cần tính trên cùng một chuỗi; giữ bản gốc riêng để tham chiếu.
    text_da_chuan_hoa = N.chuan_hoa_2(N.chuan_hoa_1(text))
    task = {
        "task_id": task_id,
        "text_goc": text,
        "text": text_da_chuan_hoa,
        "spans": [] 
    }

    task["text_da_chuan_hoa_2"] = text_da_chuan_hoa

    # 3. Tokenize văn bản
    tt.tokenize_task(task)

    return task
