import sys
import os

sys.path.append(os.path.abspath(".."))


import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

from slot_filling import SlotFiller
from Model_CRF import CRF
from feature_extractor import FeatureExtractor
from Ho_tro import bio_utils as bu
from Ho_tro import task_utils as tu

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
        
        # 1. LOCATION
        for loc in filled.get("locations", []):
            raw_val = loc.get("raw")
            sf = str(raw_val).strip().lower() if raw_val else ""
            cf = loc.get("city") or sf 
            if sf:
                self.stats["Location"]["sf"][sf] += 1
                self.stats["Location"]["cf"][cf] += 1

        # 2. SALARY
        sal = filled.get("salary", {})
        raw_val = sal.get("raw")
        if raw_val:
            sf = str(raw_val).strip().lower()
            cf = f"{sal.get('type')}|{sal.get('min')}|{sal.get('max')}|{sal.get('currency')}|{sal.get('period')}"
            self.stats["Salary"]["sf"][sf] += 1
            self.stats["Salary"]["cf"][cf] += 1

        # 3. SKILL
        for group in filled.get("skill_groups", []):
            for sk in group.get("skills", []):
                raw_val = sk.get("raw") or sk.get("name")
                sf = str(raw_val).strip().lower() if raw_val else ""
                cf = sk.get("name", "Unknown")
                if sf and cf:
                    self.stats["Skill"]["sf"][sf] += 1
                    self.stats["Skill"]["cf"][cf] += 1

        # 4. CERTIFICATE
        for cert in filled.get("certificates", []):
            for detail in cert.get("detail", []):
                raw_val = detail.get("name")
                sf = str(raw_val).strip().lower() if raw_val else ""
                cf = f"{detail.get('name')}|{detail.get('grade')}" 
                if sf:
                    self.stats["Certificate"]["sf"][sf] += 1
                    self.stats["Certificate"]["cf"][cf] += 1

        # 5. DEGREE
        for deg in filled.get("degree", []):
            raw_val = deg.get("degree_raw")
            sf = str(raw_val).strip().lower() if raw_val else ""
            # Xử lý an toàn cho majors (đề phòng majors bị None)
            majors_list = deg.get('majors') or []
            cf = f"{deg.get('degree_level')}|{','.join(majors_list)}"
            if sf:
                self.stats["Degree"]["sf"][sf] += 1
                self.stats["Degree"]["cf"][cf] += 1
                
        # 6. EXPERIENCE
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
                "Số Surface Forms (SF)": sf_count,
                "Số Canonical Forms (CF)": cf_count,
                "Độ đa dạng (SF/CF)": round(diversity_ratio, 2),
                "Tỉ lệ Long-tail": f"{round(long_tail_ratio * 100, 1)}%"
            })
            
        df = pd.DataFrame(results)
        return df.sort_values(by="Độ đa dạng (SF/CF)", ascending=False).reset_index(drop=True)


def run_evaluation_pipeline(test_file_path, model_path):
    print(f"1. Đang load dữ liệu test từ: {test_file_path}")
    test_tasks = tu.load_json(test_file_path)

    print(f"2. Đang load mô hình CRF từ: {model_path}")
    crf_model = CRF.nap_mo_hinh(model_path)

    print("3. Đang chuẩn bị features và dự đoán...")
    X_test, _ = tu.lay_dong(test_tasks, split="test")
    Y_pred = crf_model.predict(X_test)

    print("4. Đang chạy Slot Filling và phân tích độ đa dạng...")
    filler = SlotFiller()
    analyzer = DiversityAnalyzer(filler)

    pred_idx = 0
    for task in test_tasks:
        if task.get("split") != "test":
            continue
            
        bio_pred_task = []
        for _ in task["tokenized"]:
            bio_pred_task.append(Y_pred[pred_idx])
            pred_idx += 1
            
        task["bio"] = bio_pred_task
        
        bu.bien_bio_thanh_span(task)
        
        analyzer.process_task(task)

    print("5. Đang tổng hợp kết quả...")
    df_metrics = analyzer.get_metrics()
    
    print("\n" + "="*80)
    print("BẢNG THỐNG KÊ ĐỘ ĐA DẠNG SURFACE FORM / CANONICAL FORM")
    print("="*80)
    print(df_metrics.to_string(index=False))
    print("="*80 + "\n")

    plot_diversity_chart(df_metrics)
    
    return df_metrics


def plot_diversity_chart(df_metrics):
    plt.figure(figsize=(12, 7))
    
    df_melted = df_metrics.melt(
        id_vars="Nhãn", 
        value_vars=["Số Surface Forms (SF)", "Số Canonical Forms (CF)"],
        var_name="Loại", value_name="Số lượng"
    )

    # Vẽ
    ax = sns.barplot(
        data=df_melted, 
        x="Nhãn", 
        y="Số lượng", 
        hue="Loại", 
        palette=["#FF9999", "#66B2FF"] 
    )
    
    plt.title("So sánh số lượng Cách viết gốc (SF) và Dạng chuẩn (CF) theo từng nhãn", fontsize=14, pad=15)
    plt.xlabel("Nhãn Thực Thể", fontsize=12)
    plt.ylabel("Số lượng", fontsize=12)
    plt.xticks(rotation=45, fontsize=11)
    plt.legend(title="Loại Form", fontsize=11)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(f'{int(height)}', 
                        (p.get_x() + p.get_width() / 2., height), 
                        ha='center', va='center', 
                        xytext=(0, 5), 
                        textcoords='offset points',
                        fontsize=10)
            
    plt.tight_layout()
    plt.savefig("diversity_chart.png", dpi=300)
    print("Đã lưu biểu đồ tại: diversity_chart.png")
    plt.show()
