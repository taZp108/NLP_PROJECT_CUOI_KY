import sys
import os
import html as html_lib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
import fitz

from PyQt5.QtWidgets import (QApplication, QMainWindow, QListView, QCompleter, 
                             QFileDialog, QMessageBox, QListWidgetItem, QWidget, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                             QLabel, QTreeWidget, QTreeWidgetItem, QSizePolicy,
                             QScrollArea, QFrame)
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QTextCharFormat, QColor, QTextCursor, QFont
from PyQt5.QtCore import Qt

# Thêm thư mục Code vào đường dẫn import để dùng các module của project.
CURRENT_DIR = Path(__file__).resolve().parent

# 2. Lùi ra 1 cấp để lấy thư mục gốc (Project_cuoi_ki)
PROJECT_ROOT = CURRENT_DIR.parent

# 3. Trỏ tới thư mục Code và Code/Model
CODE_DIR = PROJECT_ROOT / "Code"
MODEL_DIR = CODE_DIR / "Model" 
HO_TRO_DIR = MODEL_DIR / "Ho_tro"

MODEL_DIR_CRF = MODEL_DIR / "trained_model"

# 4. Thêm vào sys.path (nếu chưa có)
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))
if str(HO_TRO_DIR) not in sys.path:
    sys.path.insert(0, str(HO_TRO_DIR))

# ==========================================
# 5. Bây giờ bạn có thể import thoải mái
# ==========================================

# Import từ Code/Model
from Model_CRF import CRF
import feature_extractor as fe

# Import từ Code/Ho_tro
from Ho_tro import Pipeline_of_project as pipeline

# Import file slot_filling
import slot_filling 

# Import UI (Chỉ gọi 1 lần)
from ui_main_window import Ui_MainWindow
import resources_rc
from filter_panel import FilterPanel


def _walk_jobposting(value):
    """Yield JobPosting dictionaries from JSON-LD objects, arrays, or @graph."""
    if isinstance(value, list):
        for item in value:
            yield from _walk_jobposting(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if "JobPosting" in types:
            yield value
        for key, child in value.items():
            if key != "@context":
                yield from _walk_jobposting(child)


def _jsonld_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "value", "streetAddress", "addressLocality", "addressRegion"):
            candidate = _jsonld_text(value.get(key))
            if candidate:
                return candidate
    return ""


def _extract_jobposting_text(soup):
    """Return structured JobPosting content when the page publishes JSON-LD."""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        for job in _walk_jobposting(payload):
            description = job.get("description", "")
            description = BeautifulSoup(str(description), "html.parser").get_text(
                separator="\n", strip=True
            )
            fields = []

            title = _jsonld_text(job.get("title"))
            company = _jsonld_text(job.get("hiringOrganization"))
            if isinstance(job.get("hiringOrganization"), dict):
                company = _jsonld_text(job["hiringOrganization"].get("name"))

            locations = job.get("jobLocation", [])
            if not isinstance(locations, list):
                locations = [locations]
            location_values = []
            for location in locations:
                address = location.get("address", location) if isinstance(location, dict) else location
                value = _jsonld_text(address)
                if value and value not in location_values:
                    location_values.append(value)

            salary = _jsonld_text(job.get("baseSalary"))
            for label, value in (
                ("Vị trí tuyển dụng", title),
                ("Công ty", company),
                ("Địa điểm", ", ".join(location_values)),
                ("Mức lương", salary),
            ):
                if value:
                    fields.append(f"{label}: {value}")
            if description:
                fields.append(description)

            text = "\n\n".join(fields).strip()
            if description and text:
                return text
    return ""


def _extract_main_page_text(html_document):
    """Extract main page text; use Trafilatura when installed, with a BS4 fallback."""
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html_document,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if extracted and extracted.strip():
            return extracted.strip()
    except Exception:
        pass

    soup = BeautifulSoup(html_document, "html.parser")
    noise_pattern = re.compile(
        r"nav|footer|header|cookie|banner|related|recommend|sidebar|popup|modal|advert|\bads?\b",
        re.IGNORECASE,
    )
    for node in soup.select("script, style, noscript, svg, iframe, nav, footer, header, aside, form"):
        node.decompose()
    for node in soup.find_all(True):
        if node.parent is None:
            continue
        markers = " ".join((str(node.get("id") or ""), " ".join(node.get("class") or [])))
        if noise_pattern.search(markers):
            node.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    return main.get_text(separator="\n", strip=True)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return value
    return []


def _as_number(value):
    """Convert numeric JSON values safely; return None for null or malformed values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slot_filling_data(record):
    """Support both raw slot-filling objects and the app's job/task wrappers."""
    record = _as_dict(record)
    nested_task = _as_dict(record.get("task"))
    for candidate in (record, nested_task):
        slots = candidate.get("slot_filling")
        if isinstance(slots, dict):
            return slots
        if any(key in candidate for key in ("company", "position", "salary", "locations")):
            return candidate
    return {}


def filter_tasks(tasks: list, filters: dict) -> list:
    """Return tasks matching every populated filter, using slot-filling fields."""
    filters = _as_dict(filters)
    wanted_position = str(filters.get("position") or "").strip().casefold()
    wanted_company = str(filters.get("company") or "").strip().casefold()
    wanted_locations = {
        str(code).strip().upper()
        for code in _as_list(filters.get("locations"))
        if code is not None and str(code).strip()
    }
    wanted_benefits = {
        str(code).strip().casefold()
        for code in _as_list(filters.get("benefits"))
        if code is not None and str(code).strip()
    }

    filter_currency = str(filters.get("salary_currency") or "VND").upper()
    if filter_currency not in {"VND", "USD"}:
        filter_currency = "VND"
    filter_min_value = _as_number(filters.get("salary_min"))
    filter_max_value = _as_number(filters.get("salary_max"))
    has_salary_max = filter_max_value is not None
    filter_min_value = 0.0 if filter_min_value is None else filter_min_value
    # A missing upper bound means no upper limit; the real panel supplies one.
    filter_max_value = float("inf") if filter_max_value is None else filter_max_value
    salary_max_unlimited = bool(filters.get("salary_max_unlimited", False))
    # VND slider values are in millions; USD slider values are whole dollars.
    filter_min = filter_min_value * 1_000_000 if filter_currency == "VND" else filter_min_value
    if salary_max_unlimited:
        filter_max = float("inf")
    elif filter_currency == "VND":
        filter_max = filter_max_value * 1_000_000
    else:
        filter_max = filter_max_value
    salary_range_active = filter_min_value > 0 or (
        has_salary_max and filter_max_value > 0 and not salary_max_unlimited
    )
    include_negotiable = bool(filters.get("is_negotiable", False))

    matches = []
    for task in _as_list(tasks):
        slots = _slot_filling_data(task)
        position = _as_dict(slots.get("position"))
        company = _as_dict(slots.get("company"))

        title = str(position.get("title") or "")
        company_name = str(company.get("name") or "")
        if wanted_position and wanted_position not in title.casefold():
            continue
        if wanted_company and wanted_company not in company_name.casefold():
            continue

        if wanted_locations:
            task_locations = _as_list(slots.get("locations"))
            task_city_codes = {
                str(_as_dict(location).get("city") or "").strip().upper()
                for location in task_locations
            }
            if not wanted_locations.intersection(task_city_codes):
                continue

        salary = _as_dict(slots.get("salary"))
        if str(salary.get("type") or "").casefold() == "negotiable":
            if not include_negotiable:
                continue
        elif not salary:
            # No salary can only pass when the salary range is inactive.
            if salary_range_active:
                continue
        else:
            task_currency = str(salary.get("currency") or "VND").upper()
            if task_currency not in {"VND", "USD"}:
                task_currency = "VND"
            task_min = _as_number(salary.get("min"))
            task_max = _as_number(salary.get("max"))
            task_min = 0.0 if task_min is None else task_min
            task_max = 999_999_999.0 if task_max is None else task_max

            # Convert task salary bounds to the currency selected in the UI.
            if task_currency != filter_currency:
                if task_currency == "USD":
                    task_min *= 25_000
                    task_max *= 25_000
                else:
                    task_min /= 25_000
                    task_max /= 25_000

            if task_max < filter_min or task_min > filter_max:
                continue

        if wanted_benefits:
            task_benefits = {
                str(_as_dict(benefit).get("category") or "").strip().casefold()
                for benefit in _as_list(slots.get("benefits"))
            }
            # Benefits use AND semantics: every selected category must exist.
            if not wanted_benefits.issubset(task_benefits):
                continue

        matches.append(task)

    return matches


class MainWindow(QMainWindow):
    MAX_PDF_PAGES = 50
    MAX_INPUT_CHARACTERS = 100_000
    MAX_URL_BYTES = 5 * 1024 * 1024
    MIN_URL_TEXT_CHARACTERS = 80
    ENTITY_COLORS = {
        "COMPANY": "#F8B4C6",
        "POSITION": "#B8D8F8",
        "LOCATION": "#B9E4C9",
        "SALARY": "#FFE08A",
        "EXPERIENCE": "#D8C2F0",
        "DEGREE": "#AEE7E7",
        "CERTIFICATE": "#FFC99B",
        "SKILL": "#C8E6A0",
        "SKILL_GROUP": "#AFC8F5",
        "DEADLINE": "#F5B7A8",
        "BENEFIT": "#E6C6A8",
    }

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setup_brief_ui()
        self._install_filter_panel()
        
        self.all_jobs = [] 
        self.current_displayed_tasks = []
        self.processed_tasks = []
        self.filter_panel.applyRequested.connect(self.apply_filters)
        self.job_id_counter = 0 
        self.crf_model = None
        self.slot_filler = slot_filling.SlotFiller()
        
        self.loaded_paths = set()
        
        self.ui.comboBox.setView(QListView())
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        image_path_main = os.path.join(current_dir, "hello_kitty_4.png")
        
        if os.path.exists(image_path_main):
            pixmap_main = QPixmap(image_path_main)
            small_pixmap_main = pixmap_main.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            brush_main = QBrush(small_pixmap_main)
            
            palette_main = QPalette()
            palette_main.setBrush(QPalette.Window, brush_main)
            self.setPalette(palette_main)

        self.ui.comboBox.currentIndexChanged.connect(self.change_input_method)
        self.change_input_method()

        self.ui.radioBrief.toggled.connect(self.switch_view_mode)
        self.ui.radioFull.toggled.connect(self.switch_view_mode)
        
        self.ui.radioBrief.setChecked(True) 
        self.ui.stackedwidgetView.setCurrentWidget(self.ui.View_brief)

        skill_list = ["Python", "Java", "C++", "SQL", "ReactJS", "NodeJS", "Django"]
        location_list = ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Cần Thơ", "Hải Phòng"]
        salary_list = ["2000000-4000000", "11000000-20000000"]
        
        self.ui.filterPosition.setCompleter(QCompleter(skill_list, self))

        self.ui.btnUrl.clicked.connect(self.handle_fetch_url)
        self.ui.btnText.clicked.connect(self.handle_text_input)
        
        self.ui.btnChooseFile.clicked.connect(self.handle_choose_file)
        self.ui.btnDelete.clicked.connect(self.handle_delete_job) 
        self.filter_panel.exportRequested.connect(self.export_to_json)
        
        self.ui.btnReset.clicked.connect(self.reset_task_list)
        
        self.ui.listWidget.itemClicked.connect(self.handle_item_clicked)
        self.ui.listWidget.itemSelectionChanged.connect(self._refresh_job_item_styles)

        self.sample_tasks_dir = Path(__file__).resolve().parent / "sample_tasks"
        self._load_sample_tasks()

    def _install_filter_panel(self):
        """Replace only the old right-column filter/actions with FilterPanel."""
        right_layout = self.ui.verticalLayout_5
        while right_layout.count():
            item = right_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        # The old action area was nested in a layout rather than being a
        # direct item of verticalLayout_5, so dispose of that widget explicitly.
        old_action_area = getattr(self.ui, "widget_5", None)
        if old_action_area is not None:
            old_action_area.hide()
            old_action_area.deleteLater()

        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(0)
        # Reuse the mascot that was already shown in the old filter column;
        # FilterPanel keeps the original art and restores its portrait display size.
        self.filter_panel = FilterPanel(":/chikawa_work.jpg", self.ui.widget)
        right_layout.addWidget(self.filter_panel)

        # Keep controls accessible alongside the generated UI namespace.
        self.ui.filterPanel = self.filter_panel
        self.ui.filterPosition = self.filter_panel.filterPosition
        self.ui.filterCompany = self.filter_panel.filterCompany
        self.ui.filterLocationsDropdown = self.filter_panel.locationDropdown
        self.ui.salaryCurrency = self.filter_panel.salaryCurrency
        self.ui.salaryMinSlider = self.filter_panel.salaryMinSlider
        self.ui.salaryMaxSlider = self.filter_panel.salaryMaxSlider
        self.ui.filterBenefitsChecks = self.filter_panel.benefitChecks
        self.ui.btnApply = self.filter_panel.btnApply
        self.ui.btnExport = self.filter_panel.btnExport

    def change_input_method(self):
        index = self.ui.comboBox.currentIndex()
        if index == 0:
            self.ui.stackedWidget.setCurrentWidget(self.ui.stack_2_url)
        elif index == 1:
            self.ui.stackedWidget.setCurrentWidget(self.ui.stack_1_plaintext)
        elif index == 2:
            self.ui.stackedWidget.setCurrentWidget(self.ui.stack_3_pdf)

    def switch_view_mode(self):
        if self.ui.radioBrief.isChecked():
            self.ui.stackedwidgetView.setCurrentWidget(self.ui.View_brief)
        elif self.ui.radioFull.isChecked():
            self.ui.stackedwidgetView.setCurrentWidget(self.ui.View_full)
            current_item = self.ui.listWidget.currentItem()
            if current_item is not None:
                self.handle_item_clicked(current_item)

    def _show_task_text(self, task):
        """Render normalized task text and shade each predicted entity span."""
        text = task.get("text_da_chuan_hoa_2") or task.get("text") or ""
        editor = self.ui.viewbox_full
        editor.setPlainText(text)
        if not text:
            return

        # Explicitly clear any old character background before applying this
        # task's entity colors, so formatting cannot carry over between views.
        reset_cursor = QTextCursor(editor.document())
        reset_cursor.select(QTextCursor.Document)
        base_format = QTextCharFormat()
        base_format.setBackground(QColor("#FFFFFF"))
        base_format.setForeground(QColor("#333333"))
        reset_cursor.mergeCharFormat(base_format)

        cursor = QTextCursor(editor.document())
        raw_spans = task.get("spans", [])
        spans = [
            span for span in raw_spans
            if isinstance(span, (list, tuple)) and len(span) >= 4
            and isinstance(span[0], int) and isinstance(span[1], int)
        ] if isinstance(raw_spans, (list, tuple)) else []
        spans.sort(key=lambda span: (span[0], span[1]))
        for span in spans:
            start, end, label, span_text = span[:4]
            # Offsets are half-open [start, end), and must point into this exact
            # normalized text. Skip stale or malformed model output safely.
            if start < 0 or end <= start or end > len(text):
                continue
            if span_text and text[start:end] != span_text:
                continue
            color = self.ENTITY_COLORS.get(str(label))
            if color is None:
                continue
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(color))
            fmt.setToolTip(str(label))
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)

        # Do not leave a selection/caret highlight covering the rendered text.
        display_cursor = QTextCursor(editor.document())
        display_cursor.movePosition(QTextCursor.Start)
        editor.setTextCursor(display_cursor)

    def show_pink_message(self, title, text, icon=QMessageBox.Information):
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStyleSheet("""
            QMessageBox { background-color: #FFF0F5; }
            QLabel { color: black; font-size: 13px; font-weight: bold; }
            QPushButton {
                background-color: #FFB6C1; color: black; border: 1px solid #FF69B4;
                border-radius: 5px; padding: 5px 15px; font-weight: bold;
            }
            QPushButton:hover { background-color: #FF69B4; }
        """)
        msg.exec_()

    def add_job_to_system(self, html_content, source_name, source_path=None, task_data=None):
        if not html_content.strip():
            return

        normalized_path = None
        if source_path is not None:
            normalized_path = source_path.replace("\\", "/").lower()
            if normalized_path in self.loaded_paths:
                self.show_pink_message("Cảnh báo trùng lặp", 
                                       f"Đường dẫn này đã được tải trước đó:\n{source_path}", 
                                       QMessageBox.Warning)
                return
            else:
                self.loaded_paths.add(normalized_path)

        for job in self.all_jobs:
            if job['full_text'].strip() == html_content.strip():
                self.show_pink_message("Cảnh báo trùng lặp", 
                                       "Nội dung tin tuyển dụng này đã có trong hệ thống!", 
                                       QMessageBox.Warning)
                return

        entities = self._entities_from_task(task_data)

        self.job_id_counter += 1
        new_job = {
            "id": self.job_id_counter, "source": source_name, 
            "full_text": html_content, "entities": entities, "path": normalized_path,
            "task": task_data
        }
        self.all_jobs.append(new_job)
        self.current_displayed_tasks.append(new_job)
        if task_data is not None:
            self.processed_tasks.append(new_job)
        self.add_item_to_list_widget(new_job)
        return new_job

    @staticmethod
    def _sample_task_records(payload):
        """Accept a single task, a task list, or a Label Studio export."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("tasks", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
            return [payload]
        raise ValueError("JSON phải là một task object hoặc danh sách task.")

    @staticmethod
    def _normalize_sample_task(record, task_id):
        """Convert a prepared JSON/Label Studio task to the app's task shape."""
        if not isinstance(record, dict):
            raise ValueError("Mỗi task phải là một JSON object.")

        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        text = (
            record.get("text_da_chuan_hoa_2") or record.get("text")
            or data.get("text_da_chuan_hoa_2") or data.get("text") or ""
        )
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Task thiếu trường text hoặc text_da_chuan_hoa_2.")

        spans = record.get("spans") or data.get("spans") or []
        # Label Studio export: annotations[].result[].value has start/end/labels/text.
        if not spans:
            annotations = record.get("annotations") or []
            if annotations and isinstance(annotations[0], dict):
                spans = []
                for result in annotations[0].get("result", []):
                    value = result.get("value", {})
                    labels = value.get("labels") or []
                    if labels and "start" in value and "end" in value:
                        spans.append((value["start"], value["end"], labels[0], value.get("text", "")))

        normalized_spans = []
        for span in spans:
            if isinstance(span, dict):
                value = span.get("value")
                if isinstance(value, (list, tuple)) and len(value) >= 4:
                    start, end, label, span_text = value[:4]
                else:
                    start, end = span.get("start"), span.get("end")
                    label = span.get("label") or span.get("entity")
                    span_text = span.get("text", "")
            elif isinstance(span, (list, tuple)) and len(span) >= 4:
                start, end, label, span_text = span[:4]
            else:
                continue
            if isinstance(start, int) and isinstance(end, int) and label:
                span_text = str(span_text or "")
                # Some hand-added sample tasks have stale offsets. Re-anchor
                # those spans by their text instead of dropping all highlights.
                if span_text and (
                    start < 0 or end > len(text) or end <= start
                    or text[start:end] != span_text
                ):
                    matches = []
                    search_from = 0
                    while True:
                        match_at = text.find(span_text, search_from)
                        if match_at < 0:
                            break
                        matches.append(match_at)
                        search_from = match_at + 1
                    if matches:
                        start = min(matches, key=lambda position: abs(position - start))
                        end = start + len(span_text)
                normalized_spans.append((start, end, str(label), span_text))

        slots = record.get("slot_filling") or data.get("slot_filling")
        if not isinstance(slots, dict):
            # Also allow a slot-filling result at the root alongside text/spans.
            slot_keys = (
                "company", "position", "locations", "salary", "experience", "degree",
                "certificates", "skill_groups", "deadline", "benefits",
            )
            slots = {key: record[key] for key in slot_keys if key in record}

        result = dict(record)
        result.update({
            "task_id": record.get("task_id", record.get("id", task_id)),
            "text": text,
            "text_da_chuan_hoa_2": text,
            "spans": normalized_spans,
            "slot_filling": slots if isinstance(slots, dict) else {},
        })
        return result

    def _load_sample_tasks(self):
        """Load prepared JSON tasks from GiaodienNLP/sample_tasks on startup."""
        if not self.sample_tasks_dir.is_dir():
            return

        errors = []
        for json_path in sorted(self.sample_tasks_dir.glob("*.json")):
            try:
                with json_path.open("r", encoding="utf-8-sig") as source:
                    records = self._sample_task_records(json.load(source))
                for index, record in enumerate(records, 1):
                    task = self._normalize_sample_task(record, f"{json_path.stem}_{index}")
                    html_text = html_lib.escape(task["text"]).replace("\n", "<br>")
                    html_content = (
                        "<div style='font-family:Arial; font-size:14px; line-height:1.5;'>"
                        f"{html_text}</div>"
                    )
                    self.add_job_to_system(
                        html_content,
                        "Task mẫu · {}".format(json_path.name),
                        # A single JSON file may contain many distinct tasks;
                        # source_path deduplication is intended for imported files.
                        source_path=None,
                        task_data=task,
                    )
            except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
                errors.append("{}: {}".format(json_path.name, error))

        if errors:
            self.show_pink_message(
                "Một số task mẫu chưa tải được",
                "\n".join(errors),
                QMessageBox.Warning,
            )

    @staticmethod
    def _entities_from_task(task):
        """Tạo các trường hiển thị từ kết quả slot filling, không dùng dữ liệu mẫu."""
        slots = (task or {}).get("slot_filling", {})
        company = slots.get("company") or {}
        position = slots.get("position") or {}
        salary = slots.get("salary") or {}
        deadline = slots.get("deadline") or {}

        locations = [
            location.get("city") or location.get("raw") or location.get("address")
            for location in slots.get("locations", [])
        ]
        experiences = [item.get("raw") for item in slots.get("experience", [])]
        degrees = [
            item.get("degree_raw") or ", ".join(item.get("majors", []))
            for item in slots.get("degree", [])
        ]
        certificates = [
            detail.get("name")
            for certificate in slots.get("certificates", [])
            for detail in certificate.get("detail", [])
        ]
        skills = [
            skill.get("name")
            for group in slots.get("skill_groups", [])
            for skill in group.get("skills", [])
        ]

        return {
            "company": company.get("name") or company.get("raw") or "",
            "position": position.get("title") or position.get("raw") or "",
            "salary": salary.get("raw") or "",
            "degree": ", ".join(value for value in degrees if value),
            "certificate": ", ".join(value for value in certificates if value),
            "experience": ", ".join(value for value in experiences if value),
            "skill": ", ".join(value for value in skills if value),
            "benefit": ", ".join(
                item.get("raw", "") for item in slots.get("benefits", [])
            ),
            "location": ", ".join(value for value in locations if value),
            "deadline": deadline.get("raw") or deadline.get("date") or "",
        }

    def add_item_to_list_widget(self, job):
        item = QListWidgetItem(self.ui.listWidget)
        widget = QWidget()
        
        style_normal = "QWidget { background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #FFF9FB, stop:1 #FFE4E1); border-radius: 12px; border: 2px solid #FFD1DC; }"
        style_selected = "QWidget { background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #FFF0F5, stop:1 #FFB6C1); border-radius: 12px; border: 2px solid #FF1493; }"
        
        widget.setStyleSheet(style_normal) 
        widget.setProperty("normalStyle", style_normal)
        widget.setProperty("selectedStyle", style_selected)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10) 
        layout.setSpacing(5)
        
        entities = job['entities']
        title_text = (
            entities.get('company')
            or entities.get('position')
            or f"Tin tuyển dụng #{job['id']}"
        )
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #333333; background: transparent; border: none;")
        
        sub_text = f"📍 {entities.get('location', '')}  |  💰 {entities.get('salary', '')}"
        lbl_sub = QLabel(sub_text)
        lbl_sub.setStyleSheet("font-size: 13px; color: #666666; background: transparent; border: none;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)
        widget.setFixedHeight(70) 
        item.setSizeHint(widget.sizeHint())
        
        self.ui.listWidget.addItem(item)
        self.ui.listWidget.setItemWidget(item, widget)
        item.setData(Qt.UserRole, job['id'])

    def _refresh_job_item_styles(self):
        """Refresh visible card styles without callbacks bound to deleted items."""
        for row in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(row)
            widget = self.ui.listWidget.itemWidget(item)
            if widget is None:
                continue
            style_property = "selectedStyle" if item.isSelected() else "normalStyle"
            style = widget.property(style_property)
            if style:
                widget.setStyleSheet(style)

    def handle_choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file", "", "Tất cả file (*.txt *.pdf);;Text (*.txt);;PDF (*.pdf)")
        if file_path:
            display_path = file_path.replace("/", "\\")
            self.ui.lineFile.setText(display_path) 
            
            if file_path.lower().endswith('.txt'):
                try:
                    with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                    html_content = f"<pre style='font-family:Arial; font-size:14px;'>{content}</pre>"
                    self.ui.viewbox_full.setHtml(html_content) 
                    self.add_job_to_system(html_content, "File TXT", source_path=file_path)
                except Exception as e: self.show_pink_message("Lỗi", str(e), QMessageBox.Warning)
            
            elif file_path.lower().endswith('.pdf'):
                try:
                    with fitz.open(file_path) as doc:
                        if doc.needs_pass:
                            raise ValueError("PDF được mã hóa hoặc cần mật khẩu.")
                        if len(doc) > self.MAX_PDF_PAGES:
                            raise ValueError(
                                f"PDF có {len(doc)} trang; giới hạn hiện tại là "
                                f"{self.MAX_PDF_PAGES} trang."
                            )
                        text = "\n\n".join(
                            page.get_text("text", sort=True).strip()
                            for page in doc
                        ).strip()

                    if not text:
                        raise ValueError(
                            "Không trích xuất được văn bản. File có thể là PDF scan; "
                            "ứng dụng hiện chưa hỗ trợ OCR."
                        )
                    if len(text) > self.MAX_INPUT_CHARACTERS:
                        raise ValueError(
                            f"Văn bản PDF vượt giới hạn "
                            f"{self.MAX_INPUT_CHARACTERS:,} ký tự."
                        )

                    task = self.process_text(
                        text,
                        task_id=f"pdf_{self.job_id_counter + 1}",
                    )
                    escaped_text = html_lib.escape(text).replace("\n", "<br>")
                    html_content = (
                        "<div style='font-family:Arial; font-size:14px; line-height:1.5;'>"
                        f"{escaped_text}</div>"
                    )
                    self._show_task_text(task)
                    added_job = self.add_job_to_system(
                        html_content,
                        "File PDF",
                        source_path=file_path,
                        task_data=task,
                    )
                    if added_job is not None:
                        self.show_pink_message(
                            "Trích xuất thành công",
                            "Đã xử lý PDF và thêm tin tuyển dụng vào danh sách.",
                        )
                except Exception as e: self.show_pink_message("Lỗi", str(e), QMessageBox.Warning)

    def handle_fetch_url(self):
        url = self.ui.lineUrl.toPlainText().strip() 
        if not url:
            self.show_pink_message("Cảnh báo", "Vui lòng nhập URL!", QMessageBox.Warning)
            return
        try:
            parsed_url = urlsplit(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                raise ValueError("URL phải bắt đầu bằng http:// hoặc https://.")

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            chunks = []
            total_bytes = 0
            with requests.get(
                url, headers=headers, timeout=(5, 20), stream=True, allow_redirects=True
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if content_type and not any(
                    kind in content_type for kind in ("text/html", "application/xhtml+xml")
                ):
                    raise ValueError(f"URL không trả về trang HTML ({content_type}).")

                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.MAX_URL_BYTES:
                    raise ValueError("Trang HTML vượt giới hạn tải 5 MB.")

                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > self.MAX_URL_BYTES:
                        raise ValueError("Trang HTML vượt giới hạn tải 5 MB.")
                    chunks.append(chunk)

            html_document = b"".join(chunks)
            soup = BeautifulSoup(html_document, "html.parser")
            text = _extract_jobposting_text(soup) or _extract_main_page_text(str(soup))
            text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            if len(text) < self.MIN_URL_TEXT_CHARACTERS:
                raise ValueError(
                    "Không trích xuất đủ nội dung từ trang này. Có thể đây không phải "
                    "trang chi tiết tuyển dụng hoặc nội dung được tải bằng JavaScript."
                )

            task = self.process_text(
                text,
                task_id=f"url_{self.job_id_counter + 1}",
            )
            escaped_text = html_lib.escape(text).replace("\n", "<br>")
            html_content = (
                "<div style='font-family:Arial; font-size:14px; line-height:1.5;'>"
                f"{escaped_text}</div>"
            )
            self._show_task_text(task)
            added_job = self.add_job_to_system(
                html_content,
                "URL",
                source_path=url,
                task_data=task,
            )
            self.ui.lineUrl.clear()
            if added_job is not None:
                self.show_pink_message(
                    "Trích xuất thành công",
                    "Đã xử lý URL và thêm tin tuyển dụng vào danh sách.",
                )
            
        except Exception as e:
            self.show_pink_message("Lỗi", str(e), QMessageBox.Critical)

    def handle_text_input(self):
        html_text = self.ui.lineText.toHtml()
        plain_text = self.ui.lineText.toPlainText().strip()
        
        if not plain_text:
            self.show_pink_message("Cảnh báo", "Vui lòng nhập văn bản!", QMessageBox.Warning)
            return
            
        try:
            task = self.process_text(
                plain_text,
                task_id=f"manual_{self.job_id_counter + 1}",
            )
        except Exception as e:
            self.show_pink_message("Lỗi xử lý văn bản", str(e), QMessageBox.Critical)
            return

        self._show_task_text(task)
        added_job = self.add_job_to_system(
            html_text,
            "Văn bản nhập tay",
            source_path=None,
            task_data=task,
        )
        self.ui.lineText.clear()
        if added_job is not None:
            self.show_pink_message(
                "Trích xuất thành công",
                "Đã xử lý văn bản và thêm tin tuyển dụng vào danh sách.",
            )

    def process_text(self, text, task_id):
        """Xử lý phần chung sau khi đã có text; dùng lại được cho PDF và URL."""
        task = pipeline.tao_task_tu_text(text, task_id=task_id)
        task["bio"] = self._get_crf_model().predict(task["tokenized"])
        pipeline.tao_bio_thanh_span_cho_tasks([task])
        task["slot_filling"] = self.slot_filler.dien(task)
        return task

    def _get_crf_model(self):
        """Nạp CRF đã huấn luyện một lần, sau đó tái sử dụng cho các lần dự đoán."""
        if self.crf_model is not None:
            return self.crf_model

        import numpy as np
        from feature_extractor import FeatureExtractor
        from Model_CRF import CRF

        extractor = FeatureExtractor(knowledge_dir=CODE_DIR / "Kho_tri_thuc")
        model_path = MODEL_DIR_CRF / "crf_model.npz"

        if not model_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy model CRF: {model_path}")

        with np.load(model_path, allow_pickle=False) as saved:
            saved_labels = [str(value) for value in saved["thu_tu_nhan"]]
            saved_features = [str(value) for value in saved["ten_feature"]]
            if saved_labels != list(extractor.THU_TU_NHAN):
                raise ValueError("Thứ tự nhãn trong model không khớp FeatureExtractor.")
            if saved_features != list(extractor.TEN_FEATURE):
                raise ValueError("Danh sách feature trong model không khớp FeatureExtractor.")

            model = CRF(extractor)
            model.emission_score = saved["emission_score"].copy()
            model.transition_score = saved["transition_score"].copy()
            model.start = saved["start"].copy()
            model.end = saved["end"].copy()

        self.crf_model = model
        return self.crf_model

    def setup_brief_ui(self):
        """Rebuild the Brief tab's presentation while preserving its data-widget API."""
        self.setFont(QFont("Segoe UI", 11))
        view = self.ui.View_brief
        main_layout = self.ui.verticalLayout_14

        # The .ui file creates an older Brief layout; replace only its contents.
        while main_layout.count():
            item = main_layout.takeAt(0)
            old_widget = item.widget()
            if old_widget is not None:
                old_widget.setParent(None)
                old_widget.deleteLater()

        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea(view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content = QWidget()
        content.setObjectName("briefContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)
        # The inner layout may be taller than the viewport; let the scroll area
        # own that height instead of compressing the cards and clipping titles.
        main_layout = content_layout

        group_style = (
            "QGroupBox { background-color: #ffffff; border: 1px solid #ffb6c1; "
            "border-radius: 8px; margin-top: 16px; padding: 8px 10px 10px 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; "
            "left: 10px; padding: 1px 6px; background-color: #ffe5f2; "
            "color: #8f4265; font-size: 12px; font-weight: bold; }"
        )

        def new_data_label(min_height=46):
            label = QLabel(view)
            label.setTextFormat(Qt.RichText)
            label.setWordWrap(True)
            label.setMinimumHeight(min_height)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setStyleSheet(
                "background-color: white; padding: 5px; border: 1px solid #ccc; "
                "font-size: 14px;"
            )
            return label

        def new_group(title, data_widget):
            box = QGroupBox(title, view)
            box.setStyleSheet(group_style)
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            content_layout = QVBoxLayout(box)
            content_layout.setContentsMargins(7, 7, 7, 7)
            content_layout.addWidget(data_widget)
            return box

        # Company remains the prominent header; its existing data name is retained
        # so the Slot Filling renderer can continue to update it directly.
        self.ui.extractCompany = new_data_label(48)
        self.ui.extractCompany.setAlignment(Qt.AlignCenter)
        self.ui.extractCompany.setStyleSheet(
            "background-color: white; padding: 7px; border: 1px solid #ffb6c1; "
            "border-radius: 8px; font-size: 16px; font-weight: bold;"
        )
        header_layout = QHBoxLayout()
        header_layout.addStretch(1)
        header_layout.addWidget(self.ui.extractCompany, 8)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)

        # Keep the same widget attributes used by the existing Brief data renderer.
        self.ui.extractPosition = new_data_label()
        self.ui.extractSalary = new_data_label()
        self.ui.extractDegree = new_data_label()
        self.ui.extractExperience = new_data_label()
        self.ui.extractCertificate = new_data_label()
        self.ui.extractBenefit = new_data_label()
        self.ui.extractLocation = new_data_label(52)
        self.ui.extractDeadline = new_data_label(52)

        skill_tree = QTreeWidget(view)
        skill_tree.setColumnCount(2)
        skill_tree.setHeaderLabels(["Kỹ năng", "Cấp độ"])
        skill_tree.setColumnWidth(0, 300)
        skill_tree.setColumnWidth(1, 72)
        skill_tree.header().setStretchLastSection(True)
        skill_tree.setMinimumHeight(190)
        skill_tree.setAlternatingRowColors(True)
        skill_tree.setRootIsDecorated(True)
        skill_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        skill_tree.setStyleSheet(
            "QTreeWidget { background: #ffffff; border: 1px solid #ffb6c1; "
            "border-radius: 6px; alternate-background-color: #fff7fa; }"
            "QHeaderView::section { background-color: #fff0f5; color: #8f4265; "
            "font-weight: bold; padding: 5px; border: 0; border-bottom: 1px solid #ffb6c1; }"
        )
        self.ui.extractSkill = skill_tree

        def add_pair_row(left_title, left_widget, right_title, right_widget, left_stretch=1, right_stretch=1):
            row = QGridLayout()
            row.setHorizontalSpacing(12)
            row.setVerticalSpacing(0)
            row.addWidget(new_group(left_title, left_widget), 0, 0)
            row.addWidget(new_group(right_title, right_widget), 0, 1)
            row.setColumnStretch(0, left_stretch)
            row.setColumnStretch(1, right_stretch)
            main_layout.addLayout(row)

        add_pair_row("Position", self.ui.extractPosition, "Salary", self.ui.extractSalary)
        add_pair_row("Degree", self.ui.extractDegree, "Experience", self.ui.extractExperience)
        add_pair_row(
            "Certificate", self.ui.extractCertificate,
            "Skill", self.ui.extractSkill,
            2, 3,
        )
        main_layout.addWidget(new_group("Benefit", self.ui.extractBenefit))
        main_layout.addWidget(new_group("Location", self.ui.extractLocation))
        main_layout.addWidget(new_group("Deadline", self.ui.extractDeadline))

        # Convenient aliases matching the requested setup_brief_ui widget names.
        self.lbl_company = self.ui.extractCompany
        self.lbl_position = self.ui.extractPosition
        self.lbl_salary = self.ui.extractSalary
        self.lbl_degree = self.ui.extractDegree
        self.lbl_experience = self.ui.extractExperience
        self.lbl_cert = self.ui.extractCertificate
        self.lbl_benefit = self.ui.extractBenefit
        self.lbl_location = self.ui.extractLocation
        self.lbl_deadline = self.ui.extractDeadline
        self.tree_skills = self.ui.extractSkill

    @staticmethod
    def _slot_text(value):
        """Convert optional JSON values to safe display text."""
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            return ""
        return str(value).strip()

    @classmethod
    def _level_html(cls, level, related_ok=False):
        level = cls._slot_text(level).casefold()
        badge = ""
        if level == "required":
            badge = '<span style="color:#d32f2f;font-weight:bold;">[Required]</span>'
        elif level == "preferred":
            badge = '<span style="color:#388e3c;font-weight:bold;">[Preferred]</span>'
        related = (
            ' <span style="color:#757575;font-style:italic;">(Tương đương)</span>'
            if related_ok else ""
        )
        return (" " + badge if badge else "") + related

    @staticmethod
    def _html_text(value):
        return html_lib.escape(MainWindow._slot_text(value))

    @classmethod
    def _html_list(cls, lines):
        lines = [line for line in lines if line]
        if not lines:
            return ""
        return "<ul style='margin:0;padding-left:20px;'>" + "".join(
            "<li>{}</li>".format(line) for line in lines
        ) + "</ul>"

    @staticmethod
    def _format_salary_number(value):
        if value is None or value == "":
            return ""
        try:
            number = float(value)
            return "{:,.0f}".format(number) if number.is_integer() else "{:,.2f}".format(number)
        except (TypeError, ValueError, OverflowError):
            return html_lib.escape(str(value))

    @classmethod
    def _render_slot_filling_brief(cls, slots, legacy_entities=None, ui=None):
        """Render one task's structured slots into the existing Brief widgets."""
        slots = slots if isinstance(slots, dict) else {}
        legacy_entities = legacy_entities if isinstance(legacy_entities, dict) else {}

        def value(section, *keys):
            obj = slots.get(section)
            obj = obj if isinstance(obj, dict) else {}
            for key in keys:
                text = cls._slot_text(obj.get(key))
                if text:
                    return text
            return ""

        company = value("company", "name", "raw")
        position = value("position", "title", "raw")
        company = company or cls._slot_text(legacy_entities.get("company"))
        position = position or cls._slot_text(legacy_entities.get("position"))
        if company:
            company = '<span style="font-size:16px;font-weight:bold;">{}</span>'.format(
                html_lib.escape(company)
            )
        if position:
            position = '<span style="font-size:14px;font-weight:bold;">{}</span>'.format(
                html_lib.escape(position)
            )
        ui.extractCompany.setText(company)
        ui.extractPosition.setText(position)

        salary = slots.get("salary")
        salary = salary if isinstance(salary, dict) else {}
        salary_type = cls._slot_text(salary.get("type")).casefold()
        if salary_type == "negotiable":
            salary_text = "Thỏa thuận"
        else:
            min_value = cls._format_salary_number(salary.get("min"))
            max_value = cls._format_salary_number(salary.get("max"))
            currency = cls._slot_text(salary.get("currency"))
            period = cls._slot_text(salary.get("period"))
            amount = " - ".join(part for part in (min_value, max_value) if part)
            if amount and currency:
                amount += " " + html_lib.escape(currency)
            elif currency:
                amount = html_lib.escape(currency)
            if amount and period:
                amount += " / " + html_lib.escape(period)
            salary_text = amount or cls._slot_text(salary.get("raw"))
            salary_text = salary_text or cls._slot_text(legacy_entities.get("salary"))
        ui.extractSalary.setText(html_lib.escape(salary_text))

        deadline = slots.get("deadline")
        deadline = deadline if isinstance(deadline, dict) else {}
        deadline_type = cls._slot_text(deadline.get("type")).casefold()
        if deadline_type == "date":
            deadline_text = cls._slot_text(deadline.get("date")) or cls._slot_text(deadline.get("raw"))
        elif deadline_type == "asap":
            deadline_text = "Càng sớm càng tốt"
        elif deadline_type == "until_filled":
            deadline_text = "Khi tuyển đủ"
        else:
            deadline_text = cls._slot_text(deadline.get("raw")) or cls._slot_text(deadline.get("date"))
        deadline_text = deadline_text or cls._slot_text(legacy_entities.get("deadline"))
        ui.extractDeadline.setText(html_lib.escape(deadline_text))

        experience_lines = []
        experience = slots.get("experience")
        for entry in experience if isinstance(experience, list) else []:
            if not isinstance(entry, dict):
                continue
            text = cls._html_text(entry.get("raw"))
            text += cls._level_html(entry.get("level"), entry.get("related_ok") is True)
            if text.strip():
                experience_lines.append(text)
        if not experience_lines and cls._slot_text(legacy_entities.get("experience")):
            experience_lines.append(cls._html_text(legacy_entities.get("experience")))
        ui.extractExperience.setText(cls._html_list(experience_lines))

        degree_lines = []
        degrees = slots.get("degree")
        for entry in degrees if isinstance(degrees, list) else []:
            if not isinstance(entry, dict):
                continue
            degree_raw = cls._html_text(entry.get("degree_raw"))
            majors = entry.get("majors")
            majors = majors if isinstance(majors, list) else []
            major_text = ", ".join(cls._html_text(major) for major in majors if cls._slot_text(major))
            text = " — ".join(part for part in (degree_raw, major_text) if part)
            text += cls._level_html(entry.get("level"), entry.get("related_ok") is True)
            if text.strip():
                degree_lines.append(text)
        if not degree_lines and cls._slot_text(legacy_entities.get("degree")):
            degree_lines.append(cls._html_text(legacy_entities.get("degree")))
        ui.extractDegree.setText(cls._html_list(degree_lines))

        certificate_lines = []
        certificates = slots.get("certificates")
        for entry in certificates if isinstance(certificates, list) else []:
            if not isinstance(entry, dict):
                continue
            cert_type = cls._slot_text(entry.get("type")).casefold()
            type_labels = {"language": "Ngoại ngữ", "tech": "Kỹ thuật", "technical": "Kỹ thuật"}
            type_label = type_labels.get(cert_type, cert_type.capitalize())
            details = entry.get("detail")
            details = details if isinstance(details, list) else []
            rendered_details = []
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                name = cls._html_text(detail.get("name"))
                grade = cls._html_text(detail.get("grade"))
                rendered = " ".join(part for part in (name, grade) if part)
                if rendered:
                    rendered_details.append(rendered)
            body = "[{}] {}".format(html_lib.escape(type_label), ", ".join(rendered_details)).strip()
            body += cls._level_html(entry.get("level"), entry.get("related_ok") is True)
            if body.strip():
                certificate_lines.append(body)
        if not certificate_lines and cls._slot_text(legacy_entities.get("certificate")):
            certificate_lines.append(cls._html_text(legacy_entities.get("certificate")))
        ui.extractCertificate.setText(cls._html_list(certificate_lines))

        benefit_lines = []
        benefits = slots.get("benefits")
        for entry in benefits if isinstance(benefits, list) else []:
            if not isinstance(entry, dict):
                continue
            raw = cls._html_text(entry.get("raw"))
            category = cls._html_text(entry.get("category"))
            text = raw + (" <span style='color:#757575;'>({})</span>".format(category) if category else "")
            if text.strip():
                benefit_lines.append(text)
        if not benefit_lines and cls._slot_text(legacy_entities.get("benefit")):
            benefit_lines.append(cls._html_text(legacy_entities.get("benefit")))
        ui.extractBenefit.setText(cls._html_list(benefit_lines))

        location_lines = []
        locations = slots.get("locations")
        for entry in locations if isinstance(locations, list) else []:
            if not isinstance(entry, dict):
                continue
            address = cls._slot_text(entry.get("address")) or cls._slot_text(entry.get("raw"))
            address = address.replace("|", ", ")
            city = cls._slot_text(entry.get("city"))
            text = html_lib.escape(address)
            if city:
                text += " <span style='color:#757575;'>({})</span>".format(html_lib.escape(city))
            if text.strip():
                location_lines.append(text)
        if not location_lines and cls._slot_text(legacy_entities.get("location")):
            location_lines.append(cls._html_text(legacy_entities.get("location")))
        ui.extractLocation.setText(cls._html_list(location_lines))

        tree = ui.extractSkill
        tree.clear()
        required_color = QColor("#d32f2f")
        preferred_color = QColor("#388e3c")
        skill_groups = slots.get("skill_groups")
        for group in skill_groups if isinstance(skill_groups, list) else []:
            if not isinstance(group, dict):
                continue
            group_name = cls._slot_text(group.get("name")) or "Kỹ năng khác"
            group_level = cls._slot_text(group.get("level")).casefold()
            group_badge = "[Required]" if group_level == "required" else (
                "[Preferred]" if group_level == "preferred" else ""
            )
            if group.get("related_ok") is True:
                group_badge = (group_badge + " (Tương đương)").strip()
            parent = QTreeWidgetItem([group_name, group_badge])
            if group_level == "required":
                parent.setForeground(1, QBrush(required_color))
            elif group_level == "preferred":
                parent.setForeground(1, QBrush(preferred_color))
            tree.addTopLevelItem(parent)
            skills = group.get("skills")
            for skill in skills if isinstance(skills, list) else []:
                if not isinstance(skill, dict):
                    continue
                skill_level = cls._slot_text(skill.get("level")).casefold()
                skill_badge = "[Required]" if skill_level == "required" else (
                    "[Preferred]" if skill_level == "preferred" else ""
                )
                child = QTreeWidgetItem([
                    cls._slot_text(skill.get("name")) or cls._slot_text(skill.get("raw")),
                    skill_badge,
                ])
                if skill_level == "required":
                    child.setForeground(1, QBrush(required_color))
                elif skill_level == "preferred":
                    child.setForeground(1, QBrush(preferred_color))
                parent.addChild(child)
        tree.expandAll()
        if tree.topLevelItemCount() == 0:
            # Legacy entries only carried a flattened skill string.
            fallback = cls._slot_text(legacy_entities.get("skill"))
            if fallback:
                item = QTreeWidgetItem([fallback, ""])
                tree.addTopLevelItem(item)

    def handle_item_clicked(self, item):
        job_id = item.data(Qt.UserRole)
        selected_job = next((j for j in self.all_jobs if j['id'] == job_id), None)
        if selected_job:
            task = selected_job.get("task") or {}
            normalized_text = task.get("text_da_chuan_hoa_2")
            if normalized_text is not None:
                self._show_task_text(task)
            else:
                self.ui.viewbox_full.setHtml(selected_job['full_text'])
            
            ent = selected_job.get('entities') or {}
            self._render_slot_filling_brief(
                _slot_filling_data(selected_job), ent, self.ui
            )

    def handle_delete_job(self):
        current_item = self.ui.listWidget.currentItem()
        if not current_item:
            self.show_pink_message("Cảnh báo", "Vui lòng chọn một tin để xóa!", QMessageBox.Warning)
            return
        if QMessageBox.question(self, 'Xóa', 'Bạn có chắc muốn xóa?', QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            job_id = current_item.data(Qt.UserRole)
            
            deleted_job = next((j for j in self.all_jobs if j['id'] == job_id), None)
            if deleted_job and deleted_job.get('path'):
                self.loaded_paths.discard(deleted_job['path'])

            self.ui.listWidget.takeItem(self.ui.listWidget.row(current_item))
            self.all_jobs = [j for j in self.all_jobs if j['id'] != job_id]
            self.current_displayed_tasks = [
                j for j in self.current_displayed_tasks if j['id'] != job_id
            ]
            self.processed_tasks = [
                job for job in self.processed_tasks if job['id'] != job_id
            ]
            self.ui.viewbox_full.clear()
            
            self.show_pink_message("Thành công", "Đã xóa!")

    def apply_filters(self, filters=None):
        """Apply FilterPanel criteria to stored jobs and refresh the list."""
        if not isinstance(filters, dict):
            filters = self.filter_panel.get_filter_data()
        visible_jobs = filter_tasks(self.all_jobs, filters)
        self.current_displayed_tasks = list(visible_jobs)
        self.ui.listWidget.clear()
        for job in visible_jobs:
            self.add_item_to_list_widget(job)

    def handle_apply_filter(self):
        """Backward-compatible entry point for older UI connections."""
        self.apply_filters(self.filter_panel.get_filter_data())

    def reset_task_list(self):
        """Clear filters and restore every remaining job to the list."""
        self.filter_panel.reset_filters()
        self.current_displayed_tasks = list(self.all_jobs)
        self.ui.listWidget.clear()
        for job in self.all_jobs:
            self.add_item_to_list_widget(job)
        self._refresh_job_item_styles()

    def export_to_json(self):
        """Export the task JSON records that are currently visible in the list."""
        displayed = self.current_displayed_tasks
        if not displayed:
            QMessageBox.warning(self, "Cảnh báo", "Không có dữ liệu để xuất")
            return

        # Export the original task dict when available; retain legacy, unprocessed
        # entries as their job record so export never silently drops visible rows.
        export_records = [
            job.get("task") if isinstance(job.get("task"), dict) else job
            for job in displayed
        ]

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        default_dir = desktop if os.path.isdir(desktop) else os.getcwd()
        default_path = os.path.join(default_dir, "exported_jobs.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu danh sách việc làm",
            default_path,
            "JSON Files (*.json)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        try:
            with open(file_path, "w", encoding="utf-8") as output_file:
                json.dump(export_records, output_file, ensure_ascii=False, indent=2)
        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Lỗi xuất file",
                "Không thể ghi file JSON:\n{}".format(error),
            )
            return

        QMessageBox.information(
            self,
            "Xuất thành công",
            "Xuất file thành công tại: {}".format(file_path),
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
