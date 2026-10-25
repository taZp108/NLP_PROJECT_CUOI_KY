# Task mẫu cho giao diện

Đặt file `.json` chứa task đã gán nhãn và slot filling trong thư mục này:

`GiaodienNLP/sample_tasks/`

Ứng dụng tự đọc các file JSON trong thư mục khi khởi động. Hỗ trợ một task object,
một mảng task, hoặc object có khóa `tasks` chứa danh sách task. File Label Studio
export cũng được nhận nếu có `data.text` và `annotations[].result[]`.

## Dạng khuyến nghị

```json
[
  {
    "task_id": "job-001",
    "text": "Công ty ABC tuyển Backend Developer tại TP.HCM.",
    "spans": [
      [8, 11, "COMPANY", "ABC"],
      [18, 35, "POSITION", "Backend Developer"],
      [40, 46, "LOCATION", "TP.HCM"]
    ],
    "slot_filling": {
      "company": {"raw": "ABC", "name": "ABC", "source": "ner"},
      "position": {"raw": "Backend Developer", "title": "Backend Developer", "source": "ner"},
      "locations": [{"raw": "TP.HCM", "city": "TP.HCM", "source": "ner"}],
      "salary": {},
      "experience": [],
      "degree": [],
      "certificates": [],
      "skill_groups": [],
      "deadline": {},
      "benefits": []
    }
  }
]
```

`spans` dùng offset ký tự `[start, end)` tính trên đúng chuỗi `text` (tính từ 0).
Mỗi span có dạng `[start, end, LABEL, text_span]`; các nhãn có thể gồm COMPANY,
POSITION, LOCATION, SALARY, EXPERIENCE, DEGREE, CERTIFICATE, SKILL,
SKILL_GROUP, DEADLINE và BENEFIT. Text span phải trùng với đoạn tương ứng trong
`text` để được tô màu ở tab **View full**.

`slot_filling` là kết quả JSON từ pipeline; các trường nhận diện được sẽ hiện ở
tab **Brief**. Có thể bỏ các trường không có dữ liệu. Khi thêm/sửa file JSON,
đóng rồi mở lại ứng dụng để nạp lại task mẫu.
