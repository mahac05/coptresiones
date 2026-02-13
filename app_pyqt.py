# app_pyqt.py
# -*- coding: utf-8 -*-
"""
Красивый UI для обработки видео на PyQt6.
Поддержка тёмной и светлой темы с Material Design эстетикой.
Мульти-выбор файлов, параллельные задачи, drag-and-drop.
"""

import sys
import os
import logging
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider, QProgressBar, QFrame,
    QStackedWidget, QFileDialog, QRadioButton, QButtonGroup,
    QGraphicsDropShadowEffect, QSizePolicy, QScrollArea, QTextEdit,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject, QMimeData
from PyQt6.QtGui import QFont, QColor, QIcon, QFontMetrics, QDragEnterEvent, QDropEvent

from backend import FFmpegConverter
from core.models import ConversionRequest, CompressionRequest, JobResult
from core.settings import (
    TOOLTIPS, PRESETS, get_crf_description,
    DEFAULT_AUDIO_FORMAT, DEFAULT_AUDIO_BITRATE, DEFAULT_CRF,
    DEFAULT_PRESET_RU, DEFAULT_COMP_AUDIO_BITRATE,
    AUDIO_BITRATE_OPTIONS, COMP_AUDIO_BITRATE_OPTIONS,
    MAX_PARALLEL_TASKS,
)
from core.service import ProcessingService


# ─── Темы ───────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg_primary": "#0f0f1a",
        "bg_secondary": "#1a1a2e",
        "bg_card": "rgba(37, 37, 66, 0.8)",
        "bg_sidebar": "rgba(26, 26, 46, 0.95)",
        "text_primary": "#ffffff",
        "text_secondary": "#a0a0b0",
        "text_muted": "#606080",
        "border": "rgba(255, 255, 255, 0.08)",
        "border_light": "rgba(255, 255, 255, 0.05)",
        "accent": "#00d4ff",
        "accent_secondary": "#7c3aed",
        "success": "#22c55e",
        "error": "#ef4444",
        "input_bg": "rgba(30, 30, 55, 0.9)",
        "slider_bg": "rgba(255, 255, 255, 0.1)",
        "log_bg": "rgba(15, 15, 30, 0.95)",
        "log_text": "#c0c0d0",
        "help_color": "#00b8d4",
    },
    "light": {
        "bg_primary": "#f0f4f8",
        "bg_secondary": "#e2e8f0",
        "bg_card": "rgba(255, 255, 255, 0.9)",
        "bg_sidebar": "rgba(241, 245, 249, 0.98)",
        "text_primary": "#1e293b",
        "text_secondary": "#64748b",
        "text_muted": "#94a3b8",
        "border": "rgba(0, 0, 0, 0.08)",
        "border_light": "rgba(0, 0, 0, 0.05)",
        "accent": "#0891b2",
        "accent_secondary": "#7c3aed",
        "success": "#16a34a",
        "error": "#dc2626",
        "input_bg": "#f8fafc",
        "slider_bg": "#e2e8f0",
        "log_bg": "#f8fafc",
        "log_text": "#334155",
        "help_color": "#0891b2",
    }
}


# ─── Сигналы для thread-safe обновления UI ──────────────────────────
class WorkerSignals(QObject):
    progress = pyqtSignal(int, str)      # percent, file_path
    finished = pyqtSignal(object, str)   # JobResult, file_path
    error = pyqtSignal(str, str)         # error_msg, file_path
    log = pyqtSignal(str)                # log message


# ─── Виджет одного файла в очереди ──────────────────────────────────
class FileTaskWidget(QFrame):
    """Строка файла: имя, прогресс-бар, статус, кнопка отмены."""
    cancel_requested = pyqtSignal(str)  # file_path
    remove_requested = pyqtSignal(str)  # file_path

    # Состояния
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ERROR = "error"

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.state = self.PENDING
        self.cancel_event = threading.Event()

        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(10)

        # Имя файла (обрезается с многоточием)
        self.name_label = QLabel()
        self.name_label.setFixedWidth(200)
        self.name_label.setToolTip(file_path)
        self._set_elided_name(file_path)
        layout.addWidget(self.name_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar, 1)

        # Статус
        self.status_label = QLabel("Ожидание...")
        self.status_label.setFixedWidth(100)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Кнопка отмены / удаления
        self.cancel_btn = QPushButton("❌")
        self.cancel_btn.setFixedSize(32, 32)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setToolTip("Отменить / Удалить")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

    def _set_elided_name(self, path: str):
        name = os.path.basename(path)
        metrics = QFontMetrics(self.name_label.font())
        elided = metrics.elidedText(f"📄 {name}", Qt.TextElideMode.ElideMiddle, 190)
        self.name_label.setText(elided)

    def _on_cancel(self):
        if self.state == self.RUNNING:
            self.cancel_event.set()
            self.set_state(self.CANCELLED)
            self.cancel_requested.emit(self.file_path)
        else:
            self.remove_requested.emit(self.file_path)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)
        self.status_label.setText(f"{value}%")

    def set_state(self, state: str):
        self.state = state
        if state == self.PENDING:
            self.status_label.setText("Ожидание...")
        elif state == self.RUNNING:
            self.status_label.setText("0%")
        elif state == self.FINISHED:
            self.progress_bar.setValue(100)
            self.status_label.setText("✅ Готово")
        elif state == self.CANCELLED:
            self.status_label.setText("❌ Отмена")
        elif state == self.ERROR:
            self.status_label.setText("⚠️ Ошибка")

    def apply_theme(self, t, is_dark):
        self.setStyleSheet(f"""
            QFrame {{
                background: {'rgba(255,255,255,0.03)' if is_dark else 'rgba(0,0,0,0.02)'};
                border: 1px solid {t['border_light']};
                border-radius: 10px;
            }}
        """)
        self.name_label.setStyleSheet(f"color: {t['text_primary']}; font-size: 13px; border: none; background: transparent;")
        color_map = {
            self.FINISHED: t['success'],
            self.ERROR: t['error'],
            self.CANCELLED: t['text_muted'],
        }
        sc = color_map.get(self.state, t['text_secondary'])
        self.status_label.setStyleSheet(f"color: {sc}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; font-size: 14px;
            }}
            QPushButton:hover {{
                background: {'rgba(255,255,255,0.08)' if is_dark else 'rgba(0,0,0,0.06)'};
                border-radius: 16px;
            }}
        """)


# ─── Зона drag-and-drop ─────────────────────────────────────────────
class DropZone(QFrame):
    """Зона для выбора файлов кликом или перетаскиванием."""
    files_selected = pyqtSignal(list)  # list of file paths

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("🎬")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.text_label = QLabel("Нажмите или перетащите видео файлы")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.hint_label = QLabel("Поддерживается множественный выбор")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

    def mousePressEvent(self, event):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите видео файлы", "",
            "Видео (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv);;Все файлы (*.*)"
        )
        if files:
            self.files_selected.emit(files)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in self.VIDEO_EXTENSIONS:
                    files.append(path)
        if files:
            self.files_selected.emit(files)

    def apply_theme(self, t, is_dark):
        self.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_card']};
                border: 2px dashed {t['border']};
                border-radius: 18px;
            }}
            QFrame:hover {{
                border-color: {t['accent']};
                background: {'rgba(0, 212, 255, 0.05)' if is_dark else 'rgba(8, 145, 178, 0.05)'};
            }}
        """)
        self.icon_label.setStyleSheet(f"font-size: 40px; background: transparent; border: none;")
        self.text_label.setStyleSheet(f"color: {t['text_secondary']}; font-size: 15px; background: transparent; border: none;")
        self.hint_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 12px; background: transparent; border: none;")


# ─── Метка-подсказка (?) ─────────────────────────────────────────────
class HelpLabel(QLabel):
    """Метка (?) с тултипом-подсказкой."""
    def __init__(self, tooltip_text: str, parent=None):
        super().__init__("(?)", parent)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setToolTip(tooltip_text)
        self.tooltip_text = tooltip_text

    def apply_theme(self, t):
        self.setStyleSheet(f"color: {t['help_color']}; font-size: 13px; font-weight: bold; background: transparent; border: none;")


# ─── Утилита обрезки пути ───────────────────────────────────────────
def elide_path(path: str, max_chars: int = 45) -> str:
    """Обрезает путь с многоточием в середине."""
    if len(path) <= max_chars:
        return path
    half = (max_chars - 3) // 2
    return path[:half] + "..." + path[-half:]


# ═══════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ═══════════════════════════════════════════════════════════════════
class VideoProcessorApp(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self.current_theme = "dark"

        # Сервис обработки — заменяет thread-per-file + Semaphore
        self._service = ProcessingService(max_workers=MAX_PARALLEL_TASKS)

        # Списки файлов и виджетов для каждой вкладки
        self.conv_file_widgets: dict[str, FileTaskWidget] = {}
        self.comp_file_widgets: dict[str, FileTaskWidget] = {}

        # Списки help-label для тем
        self._help_labels: list[HelpLabel] = []

        self.conv_output_folder = ""
        self.comp_output_folder = ""

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        self.setWindowTitle("🎬 Видео Обработчик")
        self.setMinimumSize(950, 700)
        self.resize(1050, 780)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Боковая панель ===
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 15)
        sidebar_layout.setSpacing(0)

        self.logo = QLabel("🎬 Обработчик")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.logo)
        sidebar_layout.addSpacing(35)

        # Навигация
        self.nav_audio = QPushButton("🎵  Аудио")
        self.nav_audio.setCheckable(True)
        self.nav_audio.setChecked(True)
        self.nav_audio.setMinimumHeight(55)
        self.nav_audio.clicked.connect(lambda: self._switch_tab(0))

        self.nav_compress = QPushButton("📦  Сжатие")
        self.nav_compress.setCheckable(True)
        self.nav_compress.setMinimumHeight(55)
        self.nav_compress.clicked.connect(lambda: self._switch_tab(1))

        sidebar_layout.addWidget(self.nav_audio)
        sidebar_layout.addWidget(self.nav_compress)
        sidebar_layout.addStretch()

        # Переключатель темы
        self.theme_btn = QPushButton("🌙 Тёмная тема")
        self.theme_btn.setMinimumHeight(50)
        self.theme_btn.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self.theme_btn)

        main_layout.addWidget(self.sidebar)

        # === Контент ===
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_convert_page())
        self.stack.addWidget(self._create_compress_page())

        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        main_layout.addWidget(content_wrapper)

    # ─── Темы ───────────────────────────────────────────────────────
    def _toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_theme()

    def _apply_theme(self):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"

        self.theme_btn.setText("☀️ Светлая тема" if is_dark else "🌙 Тёмная тема")

        # Главный стиль
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {t['bg_primary']};
            }}
            QWidget {{
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                color: {t['text_primary']};
                font-size: 15px;
            }}
            QComboBox {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                border: 2px solid {t['border']};
                border-radius: 10px;
                padding: 10px 15px;
                min-width: 120px;
                font-size: 15px;
            }}
            QComboBox:hover {{
                border-color: {t['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 35px;
            }}
            QComboBox QAbstractItemView {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                selection-background-color: {t['accent']};
                font-size: 15px;
            }}
            QSlider::groove:horizontal {{
                background: {t['slider_bg']};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {t['accent']};
                width: 22px;
                height: 22px;
                margin: -7px 0;
                border-radius: 11px;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                border-radius: 4px;
            }}
            QProgressBar {{
                background: {t['slider_bg']};
                border: none;
                border-radius: 6px;
                height: 12px;
                text-align: center;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                border-radius: 6px;
            }}
            QRadioButton {{
                color: {t['text_secondary']};
                spacing: 10px;
                font-size: 15px;
            }}
            QRadioButton::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 11px;
                border: 2px solid {t['border']};
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                border-color: {t['accent']};
                background: {t['accent']};
            }}
            QRadioButton:hover {{
                color: {t['text_primary']};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Боковая панель
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_sidebar']};
                border-right: 1px solid {t['border']};
            }}
        """)

        self.logo.setStyleSheet(f"""
            color: {t['text_primary']};
            font-size: 22px;
            font-weight: bold;
            padding: 20px;
            background: transparent;
        """)

        # Стили навигации
        nav_checked = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 212, 255, 0.2), stop:1 rgba(124, 58, 237, 0.2));
                color: {t['accent']};
                border: none;
                border-left: 4px solid {t['accent']};
                border-radius: 0;
                padding: 18px 22px;
                font-size: 17px;
                font-weight: bold;
                text-align: left;
            }}
        """
        nav_unchecked = f"""
            QPushButton {{
                background: transparent;
                color: {t['text_secondary']};
                border: none;
                border-left: 4px solid transparent;
                border-radius: 0;
                padding: 18px 22px;
                font-size: 17px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.03)'};
                color: {t['text_primary']};
            }}
        """
        self.nav_audio.setStyleSheet(nav_checked if self.nav_audio.isChecked() else nav_unchecked)
        self.nav_compress.setStyleSheet(nav_checked if self.nav_compress.isChecked() else nav_unchecked)

        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {t['text_secondary']};
                border: 2px solid {t['border']};
                border-radius: 12px;
                padding: 12px 18px;
                font-size: 15px;
                margin: 8px 15px;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)

        self.stack.setStyleSheet("background: transparent;")

        # Обновляем виджеты
        self._update_themed_widgets(t, is_dark)

    def _update_themed_widgets(self, t, is_dark):
        # Карточки настроек
        card_style = f"""
            QFrame {{
                background: {t['bg_card']};
                border: 1px solid {t['border_light']};
                border-radius: 18px;
            }}
        """
        for attr in ['conv_settings_card', 'comp_settings_card']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(card_style)

        # Заголовки
        for attr in ['conv_header', 'comp_header']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"font-size: 30px; font-weight: bold; color: {t['text_primary']};")

        # Drop zones
        for attr in ['conv_drop_zone', 'comp_drop_zone']:
            if hasattr(self, attr):
                getattr(self, attr).apply_theme(t, is_dark)

        # Кнопки запуска
        btn_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                color: #ffffff;
                border: none;
                border-radius: 14px;
                padding: 16px 32px;
                font-size: 17px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #33e0ff, stop:1 #9456ff);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00b8d4, stop:1 #6a2ec0);
            }}
            QPushButton:disabled {{
                background: {t['slider_bg']};
                color: {t['text_muted']};
            }}
        """
        for attr in ['conv_run_btn', 'comp_run_btn']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(btn_style)

        # Вторичные кнопки
        sec_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {t['accent']};
                border: 2px solid {t['accent']};
                border-radius: 12px;
                padding: 14px 26px;
                font-size: 15px;
            }}
            QPushButton:hover {{
                background: {'rgba(0, 212, 255, 0.1)' if is_dark else 'rgba(8, 145, 178, 0.1)'};
            }}
        """
        for attr in ['conv_folder_btn', 'comp_folder_btn']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(sec_btn_style)

        # CRF
        if hasattr(self, 'comp_crf_value'):
            self.comp_crf_value.setStyleSheet(f"color: {t['accent']}; font-size: 15px;")

        # Help labels
        for hl in self._help_labels:
            hl.apply_theme(t)

        # Журналы
        log_style = f"""
            QTextEdit {{
                background: {t['log_bg']};
                color: {t['log_text']};
                border: 1px solid {t['border_light']};
                border-radius: 10px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }}
        """
        for attr in ['conv_log', 'comp_log']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(log_style)

        # Лейблы журнала
        for attr in ['conv_log_label', 'comp_log_label']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {t['text_secondary']}; font-size: 14px; font-weight: bold;")

        # Файловые виджеты
        for fw in list(self.conv_file_widgets.values()) + list(self.comp_file_widgets.values()):
            fw.apply_theme(t, is_dark)

        # Путь к папке
        for attr in ['conv_folder_label', 'comp_folder_label']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.text():
                    w.setStyleSheet(f"color: {t['success']}; font-size: 14px;")

    def _switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.nav_audio.setChecked(index == 0)
        self.nav_compress.setChecked(index == 1)
        self._apply_theme()

    # ─── Вспомогательные ────────────────────────────────────────────
    def _make_help(self, key: str) -> HelpLabel:
        hl = HelpLabel(TOOLTIPS[key])
        self._help_labels.append(hl)
        return hl

    def _make_scroll_page(self, inner_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    # ==================== КОНВЕРТАЦИЯ ====================

    def _create_convert_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.setContentsMargins(35, 35, 35, 35)

        # Заголовок
        self.conv_header = QLabel("🎵 Конвертация в аудио")
        layout.addWidget(self.conv_header)

        # Зона выбора файлов
        self.conv_drop_zone = DropZone()
        self.conv_drop_zone.files_selected.connect(self._conv_add_files)
        layout.addWidget(self.conv_drop_zone)

        # Список файлов
        self.conv_file_list_widget = QWidget()
        self.conv_file_list_layout = QVBoxLayout(self.conv_file_list_widget)
        self.conv_file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.conv_file_list_layout.setSpacing(6)

        conv_file_scroll = QScrollArea()
        conv_file_scroll.setWidgetResizable(True)
        conv_file_scroll.setWidget(self.conv_file_list_widget)
        conv_file_scroll.setMaximumHeight(200)
        conv_file_scroll.setMinimumHeight(0)
        conv_file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conv_file_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.conv_file_scroll = conv_file_scroll
        layout.addWidget(conv_file_scroll)

        # Настройки
        self.conv_settings_card = QFrame()
        card_layout = QVBoxLayout(self.conv_settings_card)
        card_layout.setContentsMargins(28, 22, 28, 28)
        card_layout.setSpacing(18)

        title_label = QLabel("⚙️ Настройки")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title_label)

        # Формат и битрейт
        format_layout = QHBoxLayout()

        fmt_lbl = QLabel("Формат:")
        format_layout.addWidget(fmt_lbl)
        format_layout.addWidget(self._make_help("format"))

        self.conv_format = QComboBox()
        self.conv_format.addItems(list(FFmpegConverter.AUDIO_FORMATS.keys()))
        self.conv_format.setCurrentText(DEFAULT_AUDIO_FORMAT)
        format_layout.addWidget(self.conv_format)
        format_layout.addSpacing(35)

        br_lbl = QLabel("Битрейт:")
        format_layout.addWidget(br_lbl)
        format_layout.addWidget(self._make_help("bitrate"))

        self.conv_bitrate = QComboBox()
        self.conv_bitrate.addItems(AUDIO_BITRATE_OPTIONS)
        self.conv_bitrate.setCurrentText(DEFAULT_AUDIO_BITRATE)
        format_layout.addWidget(self.conv_bitrate)
        format_layout.addStretch()

        card_layout.addLayout(format_layout)

        # Сохранение
        save_label = QLabel("Сохранить:")
        card_layout.addWidget(save_label)

        self.conv_save_same = QRadioButton("В той же папке")
        self.conv_save_custom = QRadioButton("Выбрать папку")
        self.conv_save_same.setChecked(True)

        self.conv_save_group = QButtonGroup()
        self.conv_save_group.addButton(self.conv_save_same)
        self.conv_save_group.addButton(self.conv_save_custom)
        self.conv_save_custom.toggled.connect(self._conv_save_mode_changed)

        save_layout = QHBoxLayout()
        save_layout.addWidget(self.conv_save_same)
        save_layout.addWidget(self.conv_save_custom)
        save_layout.addStretch()
        card_layout.addLayout(save_layout)

        self.conv_folder_btn = QPushButton("📁 Выбрать папку...")
        self.conv_folder_btn.hide()
        self.conv_folder_btn.clicked.connect(self._conv_pick_folder)
        card_layout.addWidget(self.conv_folder_btn)

        self.conv_folder_label = QLabel("")
        self.conv_folder_label.hide()
        card_layout.addWidget(self.conv_folder_label)

        layout.addWidget(self.conv_settings_card)

        # Кнопка запуска
        self.conv_run_btn = QPushButton("▶ Конвертировать")
        self.conv_run_btn.setMinimumWidth(220)
        self.conv_run_btn.setMinimumHeight(55)
        self.conv_run_btn.clicked.connect(self._conv_run)
        layout.addWidget(self.conv_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Журнал
        self.conv_log_label = QLabel("📋 Журнал")
        layout.addWidget(self.conv_log_label)

        self.conv_log = QTextEdit()
        self.conv_log.setReadOnly(True)
        self.conv_log.setMaximumHeight(180)
        self.conv_log.setMinimumHeight(80)
        layout.addWidget(self.conv_log)

        layout.addStretch()

        return self._make_scroll_page(page)

    def _conv_add_files(self, files: list):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        for f in files:
            if f not in self.conv_file_widgets:
                fw = FileTaskWidget(f)
                fw.remove_requested.connect(self._conv_remove_file)
                fw.cancel_requested.connect(lambda p: self._conv_log_msg(f"❌ Отменено: {os.path.basename(p)}"))
                fw.apply_theme(t, is_dark)
                self.conv_file_widgets[f] = fw
                self.conv_file_list_layout.addWidget(fw)
        # Обновляем высоту скролла
        count = len(self.conv_file_widgets)
        self.conv_file_scroll.setMaximumHeight(min(200, count * 54 + 10))
        self._conv_log_msg(f"📂 Добавлено файлов: {len(files)}")

    def _conv_remove_file(self, path: str):
        fw = self.conv_file_widgets.pop(path, None)
        if fw:
            self.conv_file_list_layout.removeWidget(fw)
            fw.deleteLater()
            count = len(self.conv_file_widgets)
            self.conv_file_scroll.setMaximumHeight(min(200, max(0, count * 54 + 10)))

    def _conv_save_mode_changed(self, checked):
        self.conv_folder_btn.setVisible(checked)
        self.conv_folder_label.setVisible(checked and bool(self.conv_output_folder))

    def _conv_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.conv_output_folder = folder
            t = THEMES[self.current_theme]
            self.conv_folder_label.setText(f"📁 {elide_path(folder)}")
            self.conv_folder_label.setToolTip(folder)
            self.conv_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.conv_folder_label.show()

    def _conv_log_msg(self, msg: str):
        self.conv_log.append(msg)

    def _conv_run(self):
        # Собираем файлы в ожидании
        pending = [fw for fw in self.conv_file_widgets.values() if fw.state == FileTaskWidget.PENDING]
        if not pending:
            self._conv_log_msg("⚠️ Нет файлов для конвертации!")
            return

        if self.conv_save_custom.isChecked() and not self.conv_output_folder:
            self._conv_log_msg("⚠️ Выберите папку для сохранения!")
            return

        ext = self.conv_format.currentText()
        bitrate = self.conv_bitrate.currentText()

        # Сигналы для thread-safe обновления UI
        signals = WorkerSignals()
        signals.progress.connect(self._conv_update_progress)
        signals.finished.connect(self._conv_task_finished)
        signals.log.connect(self._conv_log_msg)

        for fw in pending:
            fw.set_state(FileTaskWidget.RUNNING)
            t_obj = THEMES[self.current_theme]
            fw.apply_theme(t_obj, self.current_theme == "dark")

            base = os.path.splitext(os.path.basename(fw.file_path))[0]
            folder = self.conv_output_folder if self.conv_save_custom.isChecked() else os.path.dirname(fw.file_path)
            output_file = os.path.join(folder, f"{base}.{ext}")

            request = ConversionRequest(
                input_file=fw.file_path,
                output_file=output_file,
                output_format=ext,
                bitrate=bitrate,
            )

            self._service.submit_conversion(
                request=request,
                cancel_event=fw.cancel_event,
                on_progress=lambda p, fp: signals.progress.emit(p, fp),
                on_finished=lambda result, fp: signals.finished.emit(result, fp),
                on_log=lambda msg: signals.log.emit(msg),
            )

        self._conv_log_msg(f"⏳ Запущено задач: {len(pending)} (макс. параллельно: {self._service.max_workers})")

    def _conv_update_progress(self, value, file_path):
        fw = self.conv_file_widgets.get(file_path)
        if fw and fw.state == FileTaskWidget.RUNNING:
            fw.set_progress(value)

    def _conv_task_finished(self, result, file_path):
        fw = self.conv_file_widgets.get(file_path)
        if not fw:
            return
        t = THEMES[self.current_theme]
        name = os.path.basename(file_path)
        if fw.state == FileTaskWidget.CANCELLED:
            self._conv_log_msg(f"❌ Отменено: {name}")
        elif isinstance(result, JobResult) and result.ok:
            fw.set_state(FileTaskWidget.FINISHED)
            self._conv_log_msg(f"✅ Готово: {name} ({result.duration_ms}мс)")
        else:
            fw.set_state(FileTaskWidget.ERROR)
            error_detail = result.error_message if isinstance(result, JobResult) else ""
            self._conv_log_msg(f"⚠️ Ошибка: {name}" + (f" — {error_detail}" if error_detail else ""))
        fw.apply_theme(t, self.current_theme == "dark")

    # ==================== СЖАТИЕ ====================

    def _create_compress_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.setContentsMargins(35, 35, 35, 35)

        # Заголовок
        self.comp_header = QLabel("📦 Сжатие видео")
        layout.addWidget(self.comp_header)

        # Зона выбора файлов
        self.comp_drop_zone = DropZone()
        self.comp_drop_zone.files_selected.connect(self._comp_add_files)
        layout.addWidget(self.comp_drop_zone)

        # Список файлов
        self.comp_file_list_widget = QWidget()
        self.comp_file_list_layout = QVBoxLayout(self.comp_file_list_widget)
        self.comp_file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.comp_file_list_layout.setSpacing(6)

        comp_file_scroll = QScrollArea()
        comp_file_scroll.setWidgetResizable(True)
        comp_file_scroll.setWidget(self.comp_file_list_widget)
        comp_file_scroll.setMaximumHeight(200)
        comp_file_scroll.setMinimumHeight(0)
        comp_file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        comp_file_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.comp_file_scroll = comp_file_scroll
        layout.addWidget(comp_file_scroll)

        # Настройки
        self.comp_settings_card = QFrame()
        card_layout = QVBoxLayout(self.comp_settings_card)
        card_layout.setContentsMargins(28, 22, 28, 28)
        card_layout.setSpacing(18)

        title_label = QLabel("⚙️ Настройки сжатия")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title_label)

        # CRF
        crf_layout = QHBoxLayout()
        crf_lbl = QLabel("Качество (CRF):")
        crf_layout.addWidget(crf_lbl)
        crf_layout.addWidget(self._make_help("crf"))
        crf_layout.addStretch()

        self.comp_crf_value = QLabel("23 (стандартное)")
        crf_layout.addWidget(self.comp_crf_value)
        card_layout.addLayout(crf_layout)

        self.comp_crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.comp_crf_slider.setRange(18, 40)
        self.comp_crf_slider.setValue(23)
        self.comp_crf_slider.valueChanged.connect(self._comp_crf_changed)
        card_layout.addWidget(self.comp_crf_slider)

        # Пресет и аудио
        preset_layout = QHBoxLayout()

        preset_lbl = QLabel("Скорость:")
        preset_layout.addWidget(preset_lbl)
        preset_layout.addWidget(self._make_help("preset"))

        self.comp_preset = QComboBox()
        self.comp_preset.addItems(list(PRESETS.keys()))
        self.comp_preset.setCurrentText(DEFAULT_PRESET_RU)
        preset_layout.addWidget(self.comp_preset)
        preset_layout.addSpacing(35)

        audio_lbl = QLabel("Звук:")
        preset_layout.addWidget(audio_lbl)
        preset_layout.addWidget(self._make_help("audio_bitrate"))

        self.comp_audio = QComboBox()
        self.comp_audio.addItems(COMP_AUDIO_BITRATE_OPTIONS)
        self.comp_audio.setCurrentText(DEFAULT_COMP_AUDIO_BITRATE)
        preset_layout.addWidget(self.comp_audio)
        preset_layout.addStretch()

        card_layout.addLayout(preset_layout)

        # Сохранение
        save_label = QLabel("Сохранить:")
        card_layout.addWidget(save_label)

        self.comp_save_same = QRadioButton("В той же папке")
        self.comp_save_custom = QRadioButton("Выбрать папку")
        self.comp_save_same.setChecked(True)

        self.comp_save_group = QButtonGroup()
        self.comp_save_group.addButton(self.comp_save_same)
        self.comp_save_group.addButton(self.comp_save_custom)
        self.comp_save_custom.toggled.connect(self._comp_save_mode_changed)

        save_layout = QHBoxLayout()
        save_layout.addWidget(self.comp_save_same)
        save_layout.addWidget(self.comp_save_custom)
        save_layout.addStretch()
        card_layout.addLayout(save_layout)

        self.comp_folder_btn = QPushButton("📁 Выбрать папку...")
        self.comp_folder_btn.hide()
        self.comp_folder_btn.clicked.connect(self._comp_pick_folder)
        card_layout.addWidget(self.comp_folder_btn)

        self.comp_folder_label = QLabel("")
        self.comp_folder_label.hide()
        card_layout.addWidget(self.comp_folder_label)

        layout.addWidget(self.comp_settings_card)

        # Кнопка запуска
        self.comp_run_btn = QPushButton("▶ Сжать видео")
        self.comp_run_btn.setMinimumWidth(220)
        self.comp_run_btn.setMinimumHeight(55)
        self.comp_run_btn.clicked.connect(self._comp_run)
        layout.addWidget(self.comp_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Журнал
        self.comp_log_label = QLabel("📋 Журнал")
        layout.addWidget(self.comp_log_label)

        self.comp_log = QTextEdit()
        self.comp_log.setReadOnly(True)
        self.comp_log.setMaximumHeight(180)
        self.comp_log.setMinimumHeight(80)
        layout.addWidget(self.comp_log)

        layout.addStretch()

        return self._make_scroll_page(page)

    def _comp_add_files(self, files: list):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        for f in files:
            if f not in self.comp_file_widgets:
                fw = FileTaskWidget(f)
                fw.remove_requested.connect(self._comp_remove_file)
                fw.cancel_requested.connect(lambda p: self._comp_log_msg(f"❌ Отменено: {os.path.basename(p)}"))
                fw.apply_theme(t, is_dark)
                self.comp_file_widgets[f] = fw
                self.comp_file_list_layout.addWidget(fw)
        count = len(self.comp_file_widgets)
        self.comp_file_scroll.setMaximumHeight(min(200, count * 54 + 10))
        self._comp_log_msg(f"📂 Добавлено файлов: {len(files)}")

    def _comp_remove_file(self, path: str):
        fw = self.comp_file_widgets.pop(path, None)
        if fw:
            self.comp_file_list_layout.removeWidget(fw)
            fw.deleteLater()
            count = len(self.comp_file_widgets)
            self.comp_file_scroll.setMaximumHeight(min(200, max(0, count * 54 + 10)))

    def _comp_crf_changed(self, value):
        desc = get_crf_description(value)
        self.comp_crf_value.setText(f"{value} {desc}")

    def _comp_save_mode_changed(self, checked):
        self.comp_folder_btn.setVisible(checked)
        self.comp_folder_label.setVisible(checked and bool(self.comp_output_folder))

    def _comp_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.comp_output_folder = folder
            t = THEMES[self.current_theme]
            self.comp_folder_label.setText(f"📁 {elide_path(folder)}")
            self.comp_folder_label.setToolTip(folder)
            self.comp_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.comp_folder_label.show()

    def _comp_log_msg(self, msg: str):
        self.comp_log.append(msg)

    def _comp_run(self):
        pending = [fw for fw in self.comp_file_widgets.values() if fw.state == FileTaskWidget.PENDING]
        if not pending:
            self._comp_log_msg("⚠️ Нет файлов для сжатия!")
            return

        if self.comp_save_custom.isChecked() and not self.comp_output_folder:
            self._comp_log_msg("⚠️ Выберите папку для сохранения!")
            return

        crf = self.comp_crf_slider.value()
        preset_ru = self.comp_preset.currentText()
        preset_en = PRESETS.get(preset_ru, "medium")
        audio_br = self.comp_audio.currentText()

        signals = WorkerSignals()
        signals.progress.connect(self._comp_update_progress)
        signals.finished.connect(self._comp_task_finished)
        signals.log.connect(self._comp_log_msg)

        for fw in pending:
            fw.set_state(FileTaskWidget.RUNNING)
            t_obj = THEMES[self.current_theme]
            fw.apply_theme(t_obj, self.current_theme == "dark")

            base = os.path.splitext(os.path.basename(fw.file_path))[0]
            folder = self.comp_output_folder if self.comp_save_custom.isChecked() else os.path.dirname(fw.file_path)
            output_file = os.path.join(folder, f"{base}_сжатое.mp4")

            request = CompressionRequest(
                input_file=fw.file_path,
                output_file=output_file,
                crf=crf,
                preset=preset_en,
                audio_bitrate=audio_br,
            )

            self._service.submit_compression(
                request=request,
                cancel_event=fw.cancel_event,
                on_progress=lambda p, fp: signals.progress.emit(p, fp),
                on_finished=lambda result, fp: signals.finished.emit(result, fp),
                on_log=lambda msg: signals.log.emit(msg),
            )

        self._comp_log_msg(f"⏳ Запущено задач: {len(pending)} (макс. параллельно: {self._service.max_workers})")

    def _comp_update_progress(self, value, file_path):
        fw = self.comp_file_widgets.get(file_path)
        if fw and fw.state == FileTaskWidget.RUNNING:
            fw.set_progress(value)

    def _comp_task_finished(self, result, file_path):
        fw = self.comp_file_widgets.get(file_path)
        if not fw:
            return
        t = THEMES[self.current_theme]
        name = os.path.basename(file_path)
        if fw.state == FileTaskWidget.CANCELLED:
            self._comp_log_msg(f"❌ Отменено: {name}")
        elif isinstance(result, JobResult) and result.ok:
            fw.set_state(FileTaskWidget.FINISHED)
            self._comp_log_msg(f"✅ Готово: {name} ({result.duration_ms}мс)")
        else:
            fw.set_state(FileTaskWidget.ERROR)
            error_detail = result.error_message if isinstance(result, JobResult) else ""
            self._comp_log_msg(f"⚠️ Ошибка: {name}" + (f" — {error_detail}" if error_detail else ""))
        fw.apply_theme(t, self.current_theme == "dark")


# ═══════════════════════════════════════════════════════════════════
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))
    window = VideoProcessorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
