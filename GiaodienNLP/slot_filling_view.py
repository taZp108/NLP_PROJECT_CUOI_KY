from collections.abc import Mapping

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SlotFillingView(QWidget):

    SECTIONS = (
        ("company", "Công ty"),
        ("position", "Vị trí"),
        ("locations", "Địa điểm"),
        ("salary", "Mức lương"),
        ("experience", "Kinh nghiệm"),
        ("degree", "Bằng cấp"),
        ("certificates", "Chứng chỉ"),
        ("skill_groups", "Nhóm kỹ năng"),
        ("deadline", "Hạn ứng tuyển"),
        ("benefits", "Quyền lợi"),
    )

    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = {}
        self.setObjectName("slotFillingView")
        self.setStyleSheet("""
            QWidget#slotFillingView { background: #f5f7fb; color: #243247; }
            QScrollArea { border: 0; background: transparent; }
            QGroupBox {
                background: #ffffff; border: 1px solid #e2e8f0;
                border-radius: 10px; margin-top: 12px; padding: 14px 12px 12px;
                font-size: 14px; font-weight: 600; color: #344767;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLabel { background: transparent; }
            QLabel[fieldLabel="true"] { color: #718096; font-size: 12px; }
            QLabel[fieldValue="true"] { color: #243247; font-size: 13px; }
            QLabel#emptyState { color: #718096; font-size: 14px; padding: 18px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(10)
        self.scroll_area.setWidget(self.content)
        root.addWidget(self.scroll_area)
        self.set_data(data)

    def set_data(self, data):
        """Replace the displayed result. Non-mapping input is treated as empty."""
        self._data = data if isinstance(data, Mapping) else {}
        self._clear_content()

        task_id = self._data.get("task_id")
        if self._has_value(task_id):
            header = QLabel("Task ID: {}".format(self._format(task_id)))
            header.setStyleSheet(
                "font-size: 16px; font-weight: 700; color: #1e3a5f; padding: 2px 2px 4px;"
            )
            header.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.content_layout.addWidget(header)

        rendered = 0
        for key, title in self.SECTIONS:
            value = self._data.get(key)
            if not self._has_value(value):
                continue
            card = self._build_section(title, key, value)
            if card is not None:
                self.content_layout.addWidget(card)
                rendered += 1

        if not rendered:
            empty = QLabel("Chưa có dữ liệu slot filling để hiển thị.")
            empty.setObjectName("emptyState")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self.content_layout.addWidget(empty)
        self.content_layout.addStretch(1)

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_section(self, title, key, value):
        box = QGroupBox(title, self.content)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(7)

        if isinstance(value, Mapping):
            fields = self._mapping_fields(key, value)
            if not fields:
                return None
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(8)
            for row, (label, field_value) in enumerate(fields):
                grid.addWidget(self._label(label, "fieldLabel"), row, 0, Qt.AlignTop)
                grid.addWidget(self._label(self._format(field_value), "fieldValue"), row, 1)
            grid.setColumnStretch(1, 1)
            layout.addLayout(grid)
        elif isinstance(value, (list, tuple)):
            items = [item for item in value if self._has_value(item)]
            if not items:
                return None
            for index, item in enumerate(items, 1):
                item_frame = QFrame(box)
                item_frame.setStyleSheet(
                    "QFrame { background: #f8fafc; border: 1px solid #edf1f6; border-radius: 7px; }"
                )
                item_layout = QVBoxLayout(item_frame)
                item_layout.setContentsMargins(10, 8, 10, 8)
                item_layout.setSpacing(5)
                if len(items) > 1:
                    index_label = QLabel("Mục {}".format(index))
                    index_label.setStyleSheet("color: #526581; font-weight: 600; border: 0;")
                    item_layout.addWidget(index_label)
                if isinstance(item, Mapping):
                    for label, field_value in self._mapping_fields(key, item):
                        row = QGridLayout()
                        row.setColumnStretch(1, 1)
                        row.addWidget(self._label(label, "fieldLabel"), 0, 0, Qt.AlignTop)
                        row.addWidget(self._label(self._format(field_value), "fieldValue"), 0, 1)
                        item_layout.addLayout(row)
                else:
                    item_layout.addWidget(self._label(self._format(item), "fieldValue"))
                layout.addWidget(item_frame)
        else:
            layout.addWidget(self._label(self._format(value), "fieldValue"))
        return box

    def _mapping_fields(self, section, data):
        """Return ordered human-readable fields, expanding nested list data."""
        labels = {
            "raw": "Nội dung gốc", "name": "Tên", "source": "Nguồn",
            "title": "Chức danh", "city": "Thành phố", "address": "Địa chỉ",
            "type": "Loại", "min": "Lương tối thiểu", "max": "Lương tối đa",
            "currency": "Tiền tệ", "period": "Chu kỳ", "min_years": "Số năm tối thiểu",
            "max_years": "Số năm tối đa", "domains": "Lĩnh vực", "level": "Mức độ",
            "related_ok": "Chấp nhận lĩnh vực liên quan", "degree_raw": "Bằng cấp gốc",
            "degree_level": "Trình độ", "majors": "Chuyên ngành", "category": "Nhóm",
            "date": "Ngày", "skills": "Kỹ năng", "grade": "Điểm", "detail": "Chi tiết",
        }
        preferred = {
            "company": ("raw", "name", "source"),
            "position": ("raw", "title", "source"),
            "locations": ("raw", "city", "address", "source"),
            "salary": ("raw", "type", "min", "max", "currency", "period"),
            "experience": ("raw", "min_years", "max_years", "domains", "level", "related_ok"),
            "degree": ("degree_raw", "degree_level", "majors", "related_ok", "level"),
            "certificates": ("type", "detail", "level", "related_ok"),
            "skill_groups": ("name", "level", "source", "related_ok", "skills"),
            "deadline": ("raw", "type", "date", "source"),
            "benefits": ("raw", "category"),
        }.get(section, tuple(data.keys()))

        result = []
        for key in preferred:
            if key not in data or not self._has_value(data[key]):
                continue
            value = data[key]
            if key == "skills" and isinstance(value, (list, tuple)):
                value = [self._skill_summary(skill) for skill in value]
            elif key == "detail" and isinstance(value, (list, tuple)):
                value = [self._certificate_summary(detail) for detail in value]
            result.append((labels.get(key, key.replace("_", " ").title()), value))
        # Preserve any useful schema extensions instead of silently hiding them.
        for key, value in data.items():
            if key not in preferred and self._has_value(value):
                result.append((labels.get(key, key.replace("_", " ").title()), value))
        return result

    @staticmethod
    def _skill_summary(skill):
        if not isinstance(skill, Mapping):
            return skill
        name = skill.get("name") or skill.get("raw")
        extras = [skill.get(key) for key in ("level", "source") if skill.get(key)]
        return "{}{}".format(name or "", " ({})".format(", ".join(map(str, extras))) if extras else "")

    @staticmethod
    def _certificate_summary(detail):
        if not isinstance(detail, Mapping):
            return detail
        name = detail.get("name") or "Chứng chỉ"
        grade = detail.get("grade")
        return "{}{}".format(name, " — {}".format(grade) if grade is not None else "")

    @staticmethod
    def _has_value(value):
        return value is not None and value != "" and value != [] and value != {}

    @classmethod
    def _format(cls, value):
        if isinstance(value, bool):
            return "Có" if value else "Không"
        if isinstance(value, Mapping):
            return ", ".join(
                "{}: {}".format(key.replace("_", " "), cls._format(item))
                for key, item in value.items() if cls._has_value(item)
            ) or "—"
        if isinstance(value, (list, tuple, set)):
            return ", ".join(cls._format(item) for item in value if cls._has_value(item)) or "—"
        return str(value)

    @staticmethod
    def _label(text, property_name):
        label = QLabel(text)
        label.setProperty(property_name, "true")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    sample = {
        "task_id": "demo-001",
        "company": {"raw": "Công ty ABC", "name": "ABC", "source": "ner"},
        "position": {"raw": "Backend Developer", "title": "Backend Developer", "source": "ner"},
        "locations": [{"raw": "Quận 1, TP.HCM", "city": "TP.HCM", "address": "Quận 1", "source": "ner"}],
        "salary": {"raw": "20-30 triệu", "type": "range", "min": 20000000, "max": 30000000, "currency": "VND", "period": "month"},
        "skill_groups": [{"name": "BACKEND", "level": "required", "source": "ner", "related_ok": False,
                          "skills": [{"name": "Node.js", "raw": "NodeJS", "level": "required", "source": "ner"}]}],
    }
    app = QApplication(sys.argv)
    window = SlotFillingView(sample)
    window.resize(620, 720)
    window.setWindowTitle("Slot Filling Result")
    window.show()
    sys.exit(app.exec_())
