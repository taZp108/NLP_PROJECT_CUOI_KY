"""Pastel filter column for the recruitment extraction application."""

from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class AspectRatioPixmapLabel(QLabel):
    """Scale the original mascot to the available width without distorting it."""

    def __init__(self, pixmap=None, parent=None):
        super().__init__(parent)
        self._source_pixmap = pixmap if pixmap is not None else QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)

    def resizeEvent(self, event):
        if not self._source_pixmap.isNull() and self.width() > 0 and self.height() > 0:
            self.setPixmap(self._source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        super().resizeEvent(event)

class MultiSelectComboBox(QComboBox):
    """Checkable multi-select combo box mapping data values to display labels."""

    def __init__(self, options, empty_text, selected_text, object_name, parent=None):
        super().__init__(parent)
        self.empty_text = empty_text
        self.selected_text = selected_text
        self.setObjectName(object_name)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._model = QStandardItemModel(self)
        for value, label in options.items():
            item = QStandardItem(label)
            item.setData(value, Qt.UserRole)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            item.setData(Qt.Unchecked, Qt.CheckStateRole)
            self._model.appendRow(item)
        self.setModel(self._model)
        # Consume row clicks ourselves. QComboBox normally closes its popup
        # after activation, which prevents selecting several values at once.
        self.view().viewport().installEventFilter(self)
        self.view().installEventFilter(self)
        self._refresh_text()

    def eventFilter(self, watched, event):
        if watched is self.view().viewport() and event.type() == QEvent.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                self._toggle_item(index.row())
                return True

        if watched is self.view() and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                index = self.view().currentIndex()
                if index.isValid():
                    self._toggle_item(index.row())
                    return True

        return super().eventFilter(watched, event)

    def _toggle_item(self, row):
        item = self._model.item(row)
        if item is None:
            return
        new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
        item.setCheckState(new_state)
        self._refresh_text()

    def _refresh_text(self):
        selected = self.selected_values()
        labels = self.selected_labels()
        if not selected:
            summary = self.empty_text
        elif len(selected) == 1:
            summary = labels[0]
        else:
            summary = "{} {} đã chọn".format(len(selected), self.selected_text)
        self.setCurrentIndex(-1)
        self.lineEdit().setText(summary)
        self.setToolTip(", ".join(labels) if labels else self.empty_text)

    def selected_values(self):
        return [
            self._model.item(row).data(Qt.UserRole)
            for row in range(self._model.rowCount())
            if self._model.item(row).checkState() == Qt.Checked
        ]

    def selected_labels(self):
        return [
            self._model.item(row).text()
            for row in range(self._model.rowCount())
            if self._model.item(row).checkState() == Qt.Checked
        ]

    def set_selected(self, values):
        selected = set(values or [])
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in selected else Qt.Unchecked)
        self._refresh_text()


class FilterPanel(QWidget):
    """Compact, scrollable, pastel-pink filter panel.

    Widgets have stable object names and ``get_filter_values`` provides a
    small integration point for the application's filtering logic.
    """

    LOCATIONS = {
        "HCM": "Hồ Chí Minh", "HN": "Hà Nội", "HP": "Hải Phòng",
        "DN": "Đà Nẵng", "CT": "Cần Thơ", "BD": "Bình Dương",
        "DNI": "Đồng Nai", "BRVT": "Bà Rịa - Vũng Tàu", "HUE": "Huế",
        "KH": "Khánh Hòa", "QN": "Quảng Ninh", "LD": "Lâm Đồng",
        "QNI": "Quảng Nam", "DNAI": "Bắc Ninh", "HDU": "Hải Dương",
        "QNG": "Quảng Ngãi", "BDH": "Bình Định", "PY": "Phú Yên",
        "NTH": "Ninh Thuận", "BTH": "Bình Thuận", "LA": "Long An",
        "TG": "Tiền Giang", "BT": "Bến Tre", "TV": "Trà Vinh",
        "VL": "Vĩnh Long", "DT": "Đồng Tháp", "AG": "An Giang",
        "KG": "Kiên Giang", "HG": "Hậu Giang", "ST": "Sóc Trăng",
        "BL": "Bạc Liêu", "CM": "Cà Mau", "BP": "Bình Phước",
        "TN": "Tây Ninh", "BTR": "Bà Rịa", "TH": "Thanh Hóa",
        "NA": "Nghệ An", "HT": "Hà Tĩnh", "QB": "Quảng Bình",
        "QT": "Quảng Trị", "KT": "Kon Tum", "GL": "Gia Lai",
        "DL": "Đắk Lắk", "DNO": "Đắk Nông", "VP": "Vĩnh Phúc",
        "HY": "Hưng Yên", "TB": "Thái Bình", "HNA": "Hà Nam",
        "ND": "Nam Định", "NB": "Ninh Bình", "HG2": "Hà Giang",
        "CB": "Cao Bằng", "BK": "Bắc Kạn", "TQ": "Tuyên Quang",
        "LC": "Lào Cai", "YB": "Yên Bái", "TNG": "Thái Nguyên",
        "LS": "Lạng Sơn", "PT": "Phú Thọ", "DB": "Điện Biên",
        "LC2": "Lai Châu", "SL": "Sơn La", "HB": "Hòa Bình",
    }
    BENEFITS = {
        "insurance": "Bảo hiểm", "bonus": "Thưởng", "leave": "Nghỉ phép",
        "allowance_meal": "Phụ cấp ăn trưa", "allowance_transport": "Phụ cấp đi lại",
        "allowance_other": "Phụ cấp khác", "training": "Đào tạo",
        "travel_culture": "Du lịch / Team building", "equipment": "Thiết bị làm việc",
        "health_wellness": "Sức khỏe / Thể thao", "flexibility": "Làm việc linh hoạt",
    }
    applyRequested = pyqtSignal(dict)
    exportRequested = pyqtSignal()

    def __init__(self, mascot_path=None, parent=None):
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self.setStyleSheet("""
            QWidget#filterPanel { background: transparent; color: #493846; font-family: "Segoe UI"; font-size: 9pt; }
            QScrollArea { background: transparent; border: 0; }
            QGroupBox {
                background: rgba(255,255,255,238);
                border: 1px solid #f0a9d0; border-radius: 11px;
                margin-top: 11px; padding: 12px 10px 10px;
                color: #74445f; font-family: "Segoe UI";
                font-weight: 700; font-size: 10pt;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit {
                background: #fffafd; border: 1px solid #efc5dc; border-radius: 8px;
                padding: 8px 10px; color: #493846; min-height: 18px;
                selection-background-color: #ed8bc3;
            }
            QLineEdit:focus { border: 1px solid #dc72b0; }
            QComboBox {
                background: #fffafd; border: 1px solid #efc5dc; border-radius: 8px;
                padding: 7px 10px; color: #493846; min-height: 20px;
            }
            QComboBox:focus { border: 1px solid #dc72b0; }
            QComboBox QAbstractItemView {
                background: #fffafd; selection-background-color: #fde2f0;
                border: 1px solid #efc5dc; color: #493846;
            }
            QCheckBox { spacing: 7px; color: #493846; padding: 2px 0; }
            QCheckBox::indicator { width: 15px; height: 15px; }
            QCheckBox::indicator:unchecked {
                border: 1px solid #dfa0c3; border-radius: 4px; background: white;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #df70ad; border-radius: 4px; background: #f4a8d0;
            }
            QComboBox QAbstractItemView::indicator {
                width: 14px; height: 14px; border: 1px solid #dfa0c3;
                border-radius: 3px; background: white;
            }
            QComboBox QAbstractItemView::indicator:checked {
                border: 1px solid #df70ad; background: #f4a8d0;
            }
            QSlider::groove:horizontal {
                height: 6px; background: #f4d9e9; border-radius: 3px;
            }
            QSlider::sub-page:horizontal { background: #e88abd; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #fff; border: 2px solid #df70ad; width: 14px;
                margin: -6px 0; border-radius: 8px;
            }
            QLabel#rangeValue { color: #a6467c; font-weight: 700; min-width: 65px; }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fffafd, stop:1 #f6add4);
                border: 1px solid #e99ac6; border-bottom: 2px solid #d779ae;
                border-radius: 9px; color: #a6467c; font-family: Arial; font-size: 10pt; font-weight: 700;
                padding: 10px 12px; min-height: 22px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fff4fa, stop:1 #f39dcb);
            }
            QPushButton:pressed { background: #e98bbf; color: white; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 7, 7, 7)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(self.scroll_area, 1)

        self.content = QWidget()
        self.content.setObjectName("filterContent")
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(5)
        self.scroll_area.setWidget(self.content)

        source_pixmap = QPixmap(mascot_path) if mascot_path else QPixmap()
        self.mascot = AspectRatioPixmapLabel(source_pixmap, self.content)
        self.mascot.setObjectName("filterMascot")
        self.mascot.setMinimumHeight(150)
        self.mascot.setFixedHeight(190)
        self.mascot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.mascot)

        self.filterPosition = self._line_filter(
            "Vị trí / Chức danh", "filterPosition", "Nhập vị trí (VD: Python...)"
        )
        layout.addWidget(self.filterPosition[0])
        self.filterPosition = self.filterPosition[1]

        self.filterCompany = self._line_filter(
            "Công ty", "filterCompany", "Nhập tên công ty..."
        )
        layout.addWidget(self.filterCompany[0])
        self.filterCompany = self.filterCompany[1]

        location_box = self._group("Địa điểm")
        location_layout = QVBoxLayout(location_box)
        location_layout.setContentsMargins(8, 10, 8, 4)
        self.locationDropdown = MultiSelectComboBox(
            self.LOCATIONS, "Bất kỳ đâu", "địa điểm", "filterLocations", location_box
        )
        location_layout.addWidget(self.locationDropdown)
        layout.addWidget(location_box)

        salary_box = self._group("Mức lương")
        salary_layout = QVBoxLayout(salary_box)
        salary_layout.setContentsMargins(8, 10, 8, 4)
        self.salaryCurrency = QComboBox(salary_box)
        self.salaryCurrency.setObjectName("salaryCurrency")
        self.salaryCurrency.addItems(("VND", "USD"))
        salary_layout.addWidget(self.salaryCurrency)
        self.salaryMinLabel, self.salaryMinSlider = self._salary_control(
            "Từ: 0 Tr", "salaryMinLabel", "salaryMinSlider"
        )
        salary_layout.addLayout(self._slider_row(self.salaryMinLabel, self.salaryMinSlider))
        self.salaryMaxLabel, self.salaryMaxSlider = self._salary_control(
            "Đến: 100 Tr", "salaryMaxLabel", "salaryMaxSlider"
        )
        salary_layout.addLayout(self._slider_row(self.salaryMaxLabel, self.salaryMaxSlider))
        self.salaryMaxUnlimited = QCheckBox("Không giới hạn mức tối đa", salary_box)
        self.salaryMaxUnlimited.setObjectName("salaryMaxUnlimited")
        salary_layout.addWidget(self.salaryMaxUnlimited)
        self.salaryMinSlider.valueChanged.connect(self._minimum_changed)
        self.salaryMaxSlider.valueChanged.connect(self._maximum_changed)
        self.salaryMaxUnlimited.toggled.connect(self._max_limit_toggled)
        layout.addWidget(salary_box)
        self.salaryCurrency.currentTextChanged.connect(self.update_salary_slider_ui)
        self.update_salary_slider_ui(self.salaryCurrency.currentText())

        benefits_box = self._group("Phúc lợi")
        benefits_layout = QVBoxLayout(benefits_box)
        benefits_layout.setContentsMargins(8, 10, 8, 4)
        self.benefitChecks = {}
        for code, label in self.BENEFITS.items():
            checkbox = QCheckBox(label, benefits_box)
            checkbox.setObjectName("benefit_{}".format(code))
            checkbox.setProperty("benefitCode", code)
            self.benefitChecks[code] = checkbox
            benefits_layout.addWidget(checkbox)
        layout.addWidget(benefits_box)

        self.btnApply = QPushButton("Áp dụng", self.content)
        self.btnApply.setObjectName("btnApply")
        self.btnExport = QPushButton("Xuất", self.content)
        self.btnExport.setObjectName("btnExport")
        layout.addStretch(1)

        # Keep the original English actions at the bottom edge of the panel,
        # outside the scrolling filter contents.
        self.action_area = QWidget(self)
        action_layout = QVBoxLayout(self.action_area)
        action_layout.setContentsMargins(10, 12, 10, 10)
        action_layout.setSpacing(8)
        original_button_font = QFont("Terminal", 13)
        original_button_font.setBold(True)
        button_style = """
            QPushButton {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 rgb(255, 170, 221));
                border: 2px solid rgb(255, 199, 233); border-radius: 10px;
                color: rgb(223, 109, 180); font-family: "Terminal"; font-size: 13pt; font-weight: bold;
                border-top: 2px solid rgb(255, 237, 255);
                border-left: 2px solid rgb(255, 237, 255);
                border-bottom: 2px solid rgb(231, 166, 208);
                border-right: 2px solid rgb(231, 166, 208);
                padding: 5px 15px; min-height: 30px;
            }
            QPushButton:hover {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFF0F5, stop:1 rgb(255, 175, 227));
            }
            QPushButton:pressed { background-color: rgb(255, 175, 227); color: white; }
        """
        for button, text in ((self.btnApply, "Apply"), (self.btnExport, "Export")):
            button.setText(text)
            button.setFont(original_button_font)
            button.setStyleSheet(button_style)
            button.setMinimumHeight(42)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            action_layout.addWidget(button)
        outer.addWidget(self.action_area, 0)
        self.btnApply.clicked.connect(lambda: self.applyRequested.emit(self.get_filter_values()))
        self.btnExport.clicked.connect(lambda: self.exportRequested.emit())

    def _line_filter(self, title, object_name, placeholder):
        box = self._group(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 10, 8, 8)
        edit = QLineEdit(box)
        edit.setObjectName(object_name)
        edit.setPlaceholderText(placeholder)
        layout.addWidget(edit)
        return box, edit

    def _group(self, title):
        return QGroupBox(title, self.content)

    @staticmethod
    def _salary_control(text, label_name, slider_name):
        label = QLabel(text)
        label.setObjectName(label_name)
        label.setProperty("class", "rangeValue")
        label.setStyleSheet("color: #a6467c; font-weight: 700; min-width: 65px;")
        slider = QSlider(Qt.Horizontal)
        slider.setObjectName(slider_name)
        slider.setRange(0, 100)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        return label, slider

    @staticmethod
    def _slider_row(label, slider):
        row = QHBoxLayout()
        row.setSpacing(7)
        row.addWidget(label)
        row.addWidget(slider, 1)
        return row

    def update_salary_slider_ui(self, currency: str):
        """Update salary ranges, increments and labels for VND or USD."""
        currency = "USD" if str(currency).upper() == "USD" else "VND"
        # VND slider values are in millions; USD slider values are whole dollars.
        upper_bound = 10_000 if currency == "USD" else 100
        step = 100 if currency == "USD" else 1

        self.salaryMinSlider.blockSignals(True)
        self.salaryMaxSlider.blockSignals(True)
        self.salaryMinSlider.setRange(0, upper_bound)
        self.salaryMaxSlider.setRange(0, upper_bound)
        self.salaryMinSlider.setSingleStep(step)
        self.salaryMaxSlider.setSingleStep(step)
        self.salaryMinSlider.setPageStep(step * 5)
        self.salaryMaxSlider.setPageStep(step * 5)
        self.salaryMinSlider.setValue(0)
        self.salaryMaxSlider.setValue(upper_bound)
        self.salaryMinSlider.blockSignals(False)
        self.salaryMaxSlider.blockSignals(False)
        self.salaryMaxSlider.setEnabled(not self.salaryMaxUnlimited.isChecked())
        self._refresh_salary_labels()

    def _salary_value_text(self, value):
        if self.salaryCurrency.currentText() == "USD":
            return "{} $".format(value)
        return "{} Tr".format(value)

    def _refresh_salary_labels(self):
        self.salaryMinLabel.setText(
            "Từ: {}".format(self._salary_value_text(self.salaryMinSlider.value()))
        )
        max_text = (
            "Đến: Không giới hạn"
            if self.salaryMaxUnlimited.isChecked()
            else "Đến: {}".format(self._salary_value_text(self.salaryMaxSlider.value()))
        )
        self.salaryMaxLabel.setText(max_text)

    def _max_limit_toggled(self, checked):
        if not checked and self.salaryMaxSlider.value() < self.salaryMinSlider.value():
            self.salaryMaxSlider.blockSignals(True)
            self.salaryMaxSlider.setValue(self.salaryMinSlider.value())
            self.salaryMaxSlider.blockSignals(False)
        self.salaryMaxSlider.setEnabled(not checked)
        self._refresh_salary_labels()

    def _minimum_changed(self, value):
        if not self.salaryMaxUnlimited.isChecked() and value > self.salaryMaxSlider.value():
            self.salaryMaxSlider.setValue(value)
        self._refresh_salary_labels()

    def _maximum_changed(self, value):
        if value < self.salaryMinSlider.value():
            self.salaryMinSlider.setValue(value)
        self._refresh_salary_labels()

    def get_filter_data(self):
        """Return current selections, including currency-aware salary values."""
        return {
            "position": self.filterPosition.text().strip(),
            "company": self.filterCompany.text().strip(),
            "locations": self.locationDropdown.selected_values(),
            "location_anywhere": not bool(self.locationDropdown.selected_values()),
            "salary_currency": self.salaryCurrency.currentText(),
            "salary_min": self.salaryMinSlider.value(),
            "salary_max": self.salaryMaxSlider.value(),
            "salary_max_unlimited": self.salaryMaxUnlimited.isChecked(),
            # Negotiable salary jobs stay excluded; this panel has no toggle for them.
            "is_negotiable": False,
            "benefits": [code for code, check in self.benefitChecks.items() if check.isChecked()],
        }

    def reset_filters(self):
        """Restore all filter controls to their initial, unselected state."""
        self.filterPosition.clear()
        self.filterCompany.clear()
        self.locationDropdown.set_selected([])
        for checkbox in self.benefitChecks.values():
            checkbox.setChecked(False)
        self.salaryMaxUnlimited.setChecked(False)
        self.salaryCurrency.setCurrentText("VND")
        self.update_salary_slider_ui(self.salaryCurrency.currentText())

    def get_filter_values(self):
        """Backward-compatible alias used by the existing Apply signal."""
        return self.get_filter_data()

