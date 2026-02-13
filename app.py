# app.py
# -*- coding: utf-8 -*-
"""
Единое приложение для обработки видео.
Вкладки: конвертация в аудио, сжатие видео.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import logging

from backend import FFmpegConverter
from ui_components import ToolTip, create_help_label
from core.models import ConversionRequest, CompressionRequest, JobResult
from core.settings import (
    TOOLTIPS, PRESETS, get_crf_description,
    DEFAULT_AUDIO_FORMAT, DEFAULT_AUDIO_BITRATE, DEFAULT_CRF,
    DEFAULT_PRESET_RU, DEFAULT_COMP_AUDIO_BITRATE,
    AUDIO_BITRATE_OPTIONS, COMP_AUDIO_BITRATE_OPTIONS,
    MAX_PARALLEL_TASKS,
)
from core.service import ProcessingService


class VideoProcessorApp:
    """Главное окно приложения с вкладками."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎬 Видео Обработчик")
        self._service = ProcessingService(max_workers=MAX_PARALLEL_TASKS)
        self._build_ui()

    def _build_ui(self):
        self.root.geometry("800x620")
        self.root.minsize(700, 550)

        # Современная тема
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass

        # Настройка стилей для вкладок
        style.configure("Tab.TFrame", padding=10)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))

        # === Верхняя панель навигации ===
        self.nav_frame = ttk.Frame(self.root)
        self.nav_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.current_tab = tk.StringVar(value="convert")

        self.btn_convert = ttk.Button(
            self.nav_frame,
            text="🎵 Конвертация в аудио",
            command=lambda: self._switch_tab("convert"),
            width=25
        )
        self.btn_convert.pack(side="left", padx=(0, 5))

        self.btn_compress = ttk.Button(
            self.nav_frame,
            text="📦 Сжатие видео",
            command=lambda: self._switch_tab("compress"),
            width=20
        )
        self.btn_compress.pack(side="left")

        # Контейнер для контента вкладок
        self.content_frame = ttk.Frame(self.root)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Создаём обе вкладки
        self._build_convert_tab()
        self._build_compress_tab()

        # По умолчанию показываем конвертацию
        self._switch_tab("convert")

    def _switch_tab(self, tab_name: str):
        """Переключение между вкладками."""
        self.current_tab.set(tab_name)

        # Скрываем все вкладки
        self.convert_frame.pack_forget()
        self.compress_frame.pack_forget()

        # Обновляем стили кнопок
        if tab_name == "convert":
            self.convert_frame.pack(fill="both", expand=True)
            self.btn_convert.state(["pressed"])
            self.btn_compress.state(["!pressed"])
        else:
            self.compress_frame.pack(fill="both", expand=True)
            self.btn_convert.state(["!pressed"])
            self.btn_compress.state(["pressed"])

    # ==================== КОНВЕРТАЦИЯ ====================

    def _build_convert_tab(self):
        """Создаёт UI для конвертации видео в аудио."""
        self.convert_frame = ttk.Frame(self.content_frame)

        # Переменные
        self.conv_input_var = tk.StringVar()
        self.conv_output_var = tk.StringVar()
        self.conv_format_var = tk.StringVar(value="m4a")
        self.conv_bitrate_var = tk.StringVar(value="192k")

        pad = {"padx": 10, "pady": 6}

        # === Файлы ===
        file_frame = ttk.LabelFrame(self.convert_frame, text="📁 Файлы")
        file_frame.pack(fill="x", pady=8)

        ttk.Label(file_frame, text="Входной файл:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(file_frame, textvariable=self.conv_input_var, width=50).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(file_frame, text="Обзор...", command=self._conv_browse_input).grid(row=0, column=2, **pad)

        # Переменная для выбора способа сохранения
        self.conv_save_mode = tk.StringVar(value="same_folder")

        ttk.Label(file_frame, text="Сохранить:").grid(row=1, column=0, sticky="w", **pad)
        
        save_mode_frame = ttk.Frame(file_frame)
        save_mode_frame.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        
        ttk.Radiobutton(
            save_mode_frame, text="В той же папке", 
            variable=self.conv_save_mode, value="same_folder",
            command=self._conv_update_save_mode
        ).pack(side="left", padx=(0, 15))
        
        ttk.Radiobutton(
            save_mode_frame, text="Выбрать папку...", 
            variable=self.conv_save_mode, value="custom_folder",
            command=self._conv_update_save_mode
        ).pack(side="left")

        # Поле для пользовательской папки (скрыто по умолчанию)
        self.conv_custom_folder_frame = ttk.Frame(file_frame)
        self.conv_custom_folder_frame.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        self.conv_custom_folder_frame.grid_remove()  # Скрываем по умолчанию
        
        ttk.Label(self.conv_custom_folder_frame, text="Папка:").pack(side="left")
        ttk.Entry(self.conv_custom_folder_frame, textvariable=self.conv_output_var, width=45).pack(side="left", padx=(10, 5), fill="x", expand=True)
        ttk.Button(self.conv_custom_folder_frame, text="Обзор...", command=self._conv_browse_output_folder).pack(side="left")

        file_frame.columnconfigure(1, weight=1)

        # === Настройки аудио ===
        audio_frame = ttk.LabelFrame(self.convert_frame, text="🎵 Настройки аудио")
        audio_frame.pack(fill="x", pady=8)

        # Формат
        format_container = ttk.Frame(audio_frame)
        format_container.grid(row=0, column=0, sticky="w", **pad)
        ttk.Label(format_container, text="Формат:").pack(side="left")
        create_help_label(format_container, TOOLTIPS["format"]).pack(side="left", padx=(2, 8))

        ttk.Combobox(
            audio_frame, textvariable=self.conv_format_var,
            values=list(FFmpegConverter.AUDIO_FORMATS.keys()),
            width=10, state="readonly"
        ).grid(row=0, column=1, sticky="w", **pad)

        # Битрейт
        bitrate_container = ttk.Frame(audio_frame)
        bitrate_container.grid(row=0, column=2, sticky="w", **pad)
        ttk.Label(bitrate_container, text="Битрейт:").pack(side="left")
        create_help_label(bitrate_container, TOOLTIPS["bitrate"]).pack(side="left", padx=(2, 8))

        ttk.Combobox(
            audio_frame, textvariable=self.conv_bitrate_var,
            values=AUDIO_BITRATE_OPTIONS,
            width=10
        ).grid(row=0, column=3, sticky="w", **pad)

        # === Кнопка и прогресс ===
        action_frame = ttk.Frame(self.convert_frame)
        action_frame.pack(fill="x", pady=10)

        self.conv_run_btn = ttk.Button(action_frame, text="▶ Конвертировать", command=self._conv_run, width=18)
        self.conv_run_btn.pack(side="left")

        self.conv_progress = ttk.Progressbar(action_frame, orient="horizontal", length=400, mode="determinate")
        self.conv_progress.pack(side="left", padx=15, fill="x", expand=True)

        self.conv_status_label = ttk.Label(action_frame, text="")
        self.conv_status_label.pack(side="right", padx=5)

        # === Журнал ===
        log_frame = ttk.LabelFrame(self.convert_frame, text="📋 Журнал")
        log_frame.pack(fill="both", expand=True, pady=8)

        self.conv_log_text = tk.Text(log_frame, height=10, wrap="word", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.conv_log_text.yview)
        self.conv_log_text.configure(yscrollcommand=scrollbar.set)

        self.conv_log_text.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar.pack(side="right", fill="y", pady=6)

    def _conv_browse_input(self):
        path = filedialog.askopenfilename(
            title="Выберите видео файл",
            filetypes=[("Видео MP4", "*.mp4"), ("Все файлы", "*.*")]
        )
        if path:
            self.conv_input_var.set(path)

    def _conv_update_save_mode(self):
        """Показывает/скрывает поле выбора папки."""
        if self.conv_save_mode.get() == "custom_folder":
            self.conv_custom_folder_frame.grid()
        else:
            self.conv_custom_folder_frame.grid_remove()
            self.conv_output_var.set("")  # Очищаем, если вернулись к "той же папке"

    def _conv_browse_output_folder(self):
        """Выбор папки для сохранения аудио."""
        folder = filedialog.askdirectory(title="Выберите папку для сохранения")
        if folder:
            self.conv_output_var.set(folder)

    def _conv_log(self, msg: str):
        self.conv_log_text.insert("end", msg + "\n")
        self.conv_log_text.see("end")

    def _conv_set_progress(self, value: int):
        self.conv_progress["value"] = value
        self.conv_status_label.configure(text=f"{value}%")

    def _conv_run(self):
        input_file = self.conv_input_var.get().strip()

        if not input_file:
            messagebox.showwarning("Файл не выбран", "Пожалуйста, выберите входной видео файл.")
            return

        ext = self.conv_format_var.get()
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        output_file = ""
        if self.conv_save_mode.get() == "same_folder":
            folder = os.path.dirname(input_file)
            output_file = os.path.join(folder, f"{base_name}.{ext}")
        else:
            custom_folder = self.conv_output_var.get().strip()
            if not custom_folder:
                messagebox.showwarning("Папка не выбрана", "Пожалуйста, выберите папку для сохранения.")
                return
            output_file = os.path.join(custom_folder, f"{base_name}.{ext}")

        self.conv_run_btn.configure(state="disabled")
        self.conv_progress["value"] = 0
        self.conv_status_label.configure(text="")
        self.conv_log_text.delete("1.0", "end")
        self._conv_log("⏳ Начинаем конвертацию...")

        request = ConversionRequest(
            input_file=input_file,
            output_file=output_file,
            output_format=self.conv_format_var.get(),
            bitrate=self.conv_bitrate_var.get()
        )

        def progress_callback(percent: int):
            self.root.after(0, lambda: self._conv_set_progress(percent))

        def result_callback(job_result: JobResult):
            if job_result.ok:
                self.root.after(0, lambda: self._conv_log(f"✅ Готово! Файл успешно создан ({job_result.duration_ms}мс)."))
                self.root.after(0, lambda: self.conv_status_label.configure(text="✅ Готово"))
            else:
                msg = job_result.error_message if job_result.error_message else "Неизвестная ошибка при конвертации"
                self.root.after(0, lambda: self._conv_log(f"❌ {msg}"))
                self.root.after(0, lambda: self.conv_status_label.configure(text="❌ Ошибка"))
            self.root.after(0, lambda: self.conv_run_btn.configure(state="normal"))

        cancel_event = threading.Event()

        self._service.submit_conversion(
            request=request,
            cancel_event=cancel_event,
            on_progress=lambda p, fp: progress_callback(p),
            on_finished=lambda result, fp: result_callback(result),
        )

    # ==================== СЖАТИЕ ====================

    def _build_compress_tab(self):
        """Создаёт UI для сжатия видео."""
        self.compress_frame = ttk.Frame(self.content_frame)

        # Переменные
        self.comp_input_var = tk.StringVar()
        self.comp_output_var = tk.StringVar()
        self.comp_crf_var = tk.IntVar(value=DEFAULT_CRF)
        self.comp_preset_var = tk.StringVar(value=DEFAULT_PRESET_RU)
        self.comp_audio_bitrate_var = tk.StringVar(value=DEFAULT_COMP_AUDIO_BITRATE)

        pad = {"padx": 10, "pady": 6}

        # === Файлы ===
        file_frame = ttk.LabelFrame(self.compress_frame, text="📁 Файлы")
        file_frame.pack(fill="x", pady=8)

        ttk.Label(file_frame, text="Входной файл:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(file_frame, textvariable=self.comp_input_var, width=50).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(file_frame, text="Обзор...", command=self._comp_browse_input).grid(row=0, column=2, **pad)

        # Переменная для выбора способа сохранения
        self.comp_save_mode = tk.StringVar(value="same_folder")

        ttk.Label(file_frame, text="Сохранить:").grid(row=1, column=0, sticky="w", **pad)
        
        save_mode_frame = ttk.Frame(file_frame)
        save_mode_frame.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        
        ttk.Radiobutton(
            save_mode_frame, text="В той же папке", 
            variable=self.comp_save_mode, value="same_folder",
            command=self._comp_update_save_mode
        ).pack(side="left", padx=(0, 15))
        
        ttk.Radiobutton(
            save_mode_frame, text="Выбрать папку...", 
            variable=self.comp_save_mode, value="custom_folder",
            command=self._comp_update_save_mode
        ).pack(side="left")

        # Поле для пользовательской папки (скрыто по умолчанию)
        self.comp_custom_folder_frame = ttk.Frame(file_frame)
        self.comp_custom_folder_frame.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        self.comp_custom_folder_frame.grid_remove()  # Скрываем по умолчанию
        
        ttk.Label(self.comp_custom_folder_frame, text="Папка:").pack(side="left")
        ttk.Entry(self.comp_custom_folder_frame, textvariable=self.comp_output_var, width=45).pack(side="left", padx=(10, 5), fill="x", expand=True)
        ttk.Button(self.comp_custom_folder_frame, text="Обзор...", command=self._comp_browse_output_folder).pack(side="left")

        file_frame.columnconfigure(1, weight=1)

        # === Настройки сжатия ===
        compress_settings = ttk.LabelFrame(self.compress_frame, text="⚙️ Настройки сжатия")
        compress_settings.pack(fill="x", pady=8)

        # Качество (CRF)
        crf_container = ttk.Frame(compress_settings)
        crf_container.grid(row=0, column=0, sticky="w", **pad)
        ttk.Label(crf_container, text="Качество:").pack(side="left")
        create_help_label(crf_container, TOOLTIPS["crf"]).pack(side="left", padx=(2, 8))

        crf_slider_frame = ttk.Frame(compress_settings)
        crf_slider_frame.grid(row=0, column=1, columnspan=2, sticky="ew", **pad)

        self.comp_crf_scale = ttk.Scale(
            crf_slider_frame, from_=18, to=40,
            variable=self.comp_crf_var, orient="horizontal", length=200
        )
        self.comp_crf_scale.pack(side="left", fill="x", expand=True)

        self.comp_crf_label = ttk.Label(crf_slider_frame, text=str(DEFAULT_CRF), width=4, anchor="center")
        self.comp_crf_label.pack(side="left", padx=5)

        self.comp_crf_desc = ttk.Label(crf_slider_frame, text=get_crf_description(DEFAULT_CRF), foreground="#666666")
        self.comp_crf_desc.pack(side="left", padx=5)

        # Скорость (Preset)
        preset_container = ttk.Frame(compress_settings)
        preset_container.grid(row=1, column=0, sticky="w", **pad)
        ttk.Label(preset_container, text="Скорость:").pack(side="left")
        create_help_label(preset_container, TOOLTIPS["preset"]).pack(side="left", padx=(2, 8))

        ttk.Combobox(
            compress_settings, textvariable=self.comp_preset_var,
            values=list(PRESETS.keys()),
            width=22, state="readonly"
        ).grid(row=1, column=1, sticky="w", **pad)

        # Битрейт аудио
        audio_container = ttk.Frame(compress_settings)
        audio_container.grid(row=1, column=2, sticky="w", **pad)
        ttk.Label(audio_container, text="Звук:").pack(side="left")
        create_help_label(audio_container, TOOLTIPS["audio_bitrate"]).pack(side="left", padx=(2, 8))

        ttk.Combobox(
            compress_settings, textvariable=self.comp_audio_bitrate_var,
            values=COMP_AUDIO_BITRATE_OPTIONS,
            width=10, state="readonly"
        ).grid(row=1, column=3, sticky="w", **pad)

        compress_settings.columnconfigure(1, weight=1)

        # Обновление метки CRF
        self.comp_crf_var.trace_add("write", self._comp_update_crf_label)

        # === Кнопка и прогресс ===
        action_frame = ttk.Frame(self.compress_frame)
        action_frame.pack(fill="x", pady=10)

        self.comp_run_btn = ttk.Button(action_frame, text="▶ Сжать видео", command=self._comp_run, width=16)
        self.comp_run_btn.pack(side="left")

        self.comp_progress = ttk.Progressbar(action_frame, orient="horizontal", length=400, mode="determinate")
        self.comp_progress.pack(side="left", padx=15, fill="x", expand=True)

        self.comp_status_label = ttk.Label(action_frame, text="")
        self.comp_status_label.pack(side="right", padx=5)

        # === Журнал ===
        log_frame = ttk.LabelFrame(self.compress_frame, text="📋 Журнал")
        log_frame.pack(fill="both", expand=True, pady=8)

        self.comp_log_text = tk.Text(log_frame, height=10, wrap="word", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.comp_log_text.yview)
        self.comp_log_text.configure(yscrollcommand=scrollbar.set)

        self.comp_log_text.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar.pack(side="right", fill="y", pady=6)

    def _comp_update_crf_label(self, *_):
        crf = int(self.comp_crf_var.get())
        self.comp_crf_label.configure(text=str(crf))
        self.comp_crf_desc.configure(text=get_crf_description(crf))

    def _comp_browse_input(self):
        path = filedialog.askopenfilename(
            title="Выберите видео для сжатия",
            filetypes=[("Видео MP4", "*.mp4"), ("Все файлы", "*.*")]
        )
        if path:
            self.comp_input_var.set(path)

    def _comp_update_save_mode(self):
        """Показывает/скрывает поле выбора папки для сжатия."""
        if self.comp_save_mode.get() == "custom_folder":
            self.comp_custom_folder_frame.grid()
        else:
            self.comp_custom_folder_frame.grid_remove()
            self.comp_output_var.set("")

    def _comp_browse_output_folder(self):
        """Выбор папки для сохранения сжатого видео."""
        folder = filedialog.askdirectory(title="Выберите папку для сохранения")
        if folder:
            self.comp_output_var.set(folder)

    def _comp_log(self, msg: str):
        self.comp_log_text.insert("end", msg + "\n")
        self.comp_log_text.see("end")

    def _comp_set_progress(self, value: int):
        self.comp_progress["value"] = value
        self.comp_status_label.configure(text=f"{value}%")

    def _comp_run(self):
        input_file = self.comp_input_var.get().strip()

        if not input_file:
            messagebox.showwarning("Файл не выбран", "Пожалуйста, выберите входной видео файл.")
            return

        # Формируем путь к выходному файлу с суффиксом "_сжатое"
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_name = f"{base_name}_сжатое.mp4"
        
        if self.comp_save_mode.get() == "same_folder":
            # Сохраняем в той же папке
            folder = os.path.dirname(input_file)
            output_file = os.path.join(folder, output_name)
        else:
            # Пользовательская папка
            custom_folder = self.comp_output_var.get().strip()
            if not custom_folder:
                messagebox.showwarning("Папка не выбрана", "Пожалуйста, выберите папку для сохранения.")
                return
            output_file = os.path.join(custom_folder, output_name)

        self.comp_run_btn.configure(state="disabled")
        self.comp_progress["value"] = 0
        self.comp_status_label.configure(text="")
        self.comp_log_text.delete("1.0", "end")
        self._comp_log("⏳ Начинаем сжатие видео...")

        def progress_callback(percent: int):
            self.root.after(0, lambda: self._comp_set_progress(percent))

        def worker():
            try:
                preset_ru = self.comp_preset_var.get()
                preset_en = PRESETS.get(preset_ru, "medium")

                result = self._service.converter.compress_mp4_video(
                    input_file=input_file,
                    output_file=output_file,
                    crf=int(self.comp_crf_var.get()),
                    preset=preset_en,
                    audio_bitrate=self.comp_audio_bitrate_var.get(),
                    show_progress=True,
                    progress_callback=progress_callback,
                )

                if result.ok:
                    self.root.after(0, lambda: self._comp_log(f"✅ Готово! Видео успешно сжато ({result.duration_ms}мс)."))
                    self.root.after(0, lambda: self.comp_status_label.configure(text="✅ Готово"))
                else:
                    msg = result.error_message if result.error_message else "Ошибка при сжатии"
                    self.root.after(0, lambda: self._comp_log(f"❌ {msg}"))
                    self.root.after(0, lambda: self.comp_status_label.configure(text="❌ Ошибка"))
            finally:
                self.root.after(0, lambda: self.comp_run_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    root = tk.Tk()
    app = VideoProcessorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
