# Đồ án cuối kỳ môn Xử lý Ngôn ngữ Tự nhiên (NLP)
## Hệ thống Trích xuất Thông tin Tuyển dụng (Job Posting Information Extraction)

## Giới thiệu
Đây là đồ án cuối kỳ môn Xử lý Ngôn ngữ Tự nhiên (NLP). Dự án tập trung vào bài toán **Trích xuất thông tin từ các tin tuyển dụng (Information Extraction)**. Hệ thống kết hợp bài toán Nhận dạng Thực thể Định danh (NER) và Điền khuyết thông tin (Slot Filling) để bóc tách các thông tin quan trọng như: Tên công ty, Vị trí, Kỹ năng, Bằng cấp, Mức lương, Quyền lợi... từ đó điền vào một template tiêu chuẩn.

Dự án sử dụng mô hình **CRF** làm mô hình chính để đưa vào ứng dụng thực tế. Bên cạnh đó, mô hình **HMM** cũng được huấn luyện để làm cơ sở so sánh và đánh giá hiệu năng giữa hai phương pháp.

## Các tính năng chính
- **Trích xuất thực thể:** Nhận diện các thực thể trong tin tuyển dụng dựa trên mô hình CRF và hệ thống từ điển.
- **Slot Filling:** Điền các thực thể đã trích xuất vào biểu mẫu chuẩn hóa.
- **Giao diện đồ họa:** Ứng dụng desktop viết bằng PyQt5, cho phép người dùng:
  - Nhập văn bản trực tiếp, tải lên file PDF, hoặc nhập URL của tin tuyển dụng.
  - Hiển thị kết quả trích xuất với các thực thể được **tô màu** trực quan.
  - Hiển thị template thông tin đã được điền tự động.
  - Hỗ trợ bộ lọc và **xuất kết quả ra file JSON**.
- **Đánh giá mô hình:** Đánh giá chéo, so sánh hiệu năng CRF và HMM. Đánh giá độ đồng thuận (Cohen's Kappa) giữa 3 người gán nhãn.

## Cấu trúc thư mục
```text
Project_cuoi_ki/
│
├── Code/                           # Chứa toàn bộ mã nguồn xử lý
│   ├── Ho_tro/                     # Các module hỗ trợ (utils)
│   │   ├── bio_utils.py            # Xử lý định dạng BIO
│   │   ├── Normalize.py            # Chuẩn hóa văn bản
│   │   ├── Pipeline_of_project.py  # Pipeline chạy toàn bộ luồng dự án
│   │   ├── task_utils.py           # Tiện ích xử lý task
│   │   └── tokenize_task.py        # Tách từ (Word segmentation)
│   │
│   ├── Kho_tri_thuc/               # Từ điển & Cơ sở tri thức (Knowledge Base)
│   │   ├── *.json                  # Từ điển thực thể (skill, company, degree, benefit...)
│   │   └── *.txt                   # Domain, company, position knowledge
│   │
│   └── kiem_dinh_danh_gia/         # Đánh giá mô hình
│       └── Đánh_giá_độ_đồng_thuận.ipynb # Notebook tính Cohen's Kappa
│
├── Data/                           # Dữ liệu dự án
│   ├── Đánh giá độ đồng thuận/     # Dữ liệu gán nhãn của 3 người để tính Kappa
│   ├── Dữ liệu Huấn Luyện/         # Dữ liệu train/test
│   ├── Phân tích bắt buộc/         # Dữ liệu mẫu cho phần phân tích lỗi (Error Analysis)
│   ├── raw_data/                   # Dữ liệu thô (crawl được)
│   ├── task_thu_1.txt              # File text mẫu để test ứng dụng
│   └── task_thu_2.txt              # File text mẫu để test ứng dụng
│
├── Model/                          # Quản lý và huấn luyện mô hình
│   ├── trained_model/              # Nơi lưu trữ mô hình sau khi train
│   │   ├── crf_model.npz           # Mô hình CRF (Dùng cho App)
│   │   ├── hmm_model.pkl           # Mô hình HMM (Dùng để so sánh)
│   │   ├── bieu_do_train.png       # Biểu đồ huấn luyện
│   │   └── lich_su_train.json      # Lịch sử train
│   ├── feature_extractor.py        # Module trích xuất đặc trưng cho CRF
│   ├── Model_CRF.py                # Script huấn luyện/đánh giá CRF
│   ├── Model_HMM.py                # Script huấn luyện/đánh giá HMM
│   ├── slot_filling.py             # Logic điền template từ thực thể đã trích xuất
│   ├── train_model.ipynb           # Notebook huấn luyện
│   └── test_va_danh_gia.ipynb      # Notebook test và so sánh mô hình
│
├── GiaodienNLP/                    # Giao diện ứng dụng (PyQt5)
│   ├── sample_tasks/               # Task mẫu
│   ├── filter_panel.py             # Module bộ lọc
│   ├── run_app.py                  # FILE CHẠY CHÍNH CỦA ỨNG DỤNG
│   ├── slot_filling_view.py        # View hiển thị template
│   └── ui_main_window.py           # Code UI
│
└── README.md                       # Tài liệu hướng dẫn (File này)