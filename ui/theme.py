"""Tema Qt moderno, senza dipendenze grafiche esterne."""

MODERN_STYLESHEET = """
QMainWindow, QWidget { background: #f5f7fb; color: #182235; font-family: 'Segoe UI', 'Inter', 'Arial'; font-size: 13px; }
QDialog { background: #ffffff; }
QLabel { background: transparent; }
QLabel#pageTitle, QLabel#dialogTitle { font-size: 23px; font-weight: 700; color: #14233d; }
QLabel#mutedLabel { color: #64748b; }
QLabel#editSummary, QLabel#summaryCard { border: 1px solid #dae2ee; border-radius: 12px; background: #ffffff; padding: 16px; font-size: 15px; font-weight: 600; }
QTabWidget::pane { border: 0; background: #f5f7fb; }
QTabBar::tab { background: transparent; color: #64748b; padding: 12px 22px; margin-right: 6px; border-bottom: 3px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #2463eb; border-bottom-color: #2463eb; }
QTableView { background: #ffffff; alternate-background-color: #f8fafd; gridline-color: #edf1f7; border: 1px solid #e0e7f0; border-radius: 12px; selection-background-color: #dbeafe; selection-color: #143462; }
QHeaderView::section { background: #edf2f8; border: 0; border-bottom: 1px solid #dce5f0; padding: 12px 8px; font-weight: 700; color: #40516b; }
QTableView::item { padding: 8px; }
QPushButton { background: #ffffff; border: 1px solid #d4dfec; border-radius: 9px; padding: 9px 14px; font-weight: 600; color: #1d3555; }
QPushButton:hover { background: #eaf1ff; border-color: #adc8ff; }
QPushButton:disabled { color: #96a3b4; background: #eef1f5; }
QPushButton#primaryButton { color: #ffffff; background: #2563eb; border-color: #2563eb; }
QPushButton#primaryButton:hover { background: #1d4ed8; }
QPushButton#dangerButton { color: #c52836; border-color: #f2c7cf; }
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit, QDoubleSpinBox { background: #ffffff; border: 1px solid #cfdae9; border-radius: 8px; min-height: 28px; padding: 5px 9px; selection-background-color: #bcd5ff; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QDoubleSpinBox:focus { border: 2px solid #4e8df6; }
QStatusBar { background: #eaf0f8; color: #475569; }
"""
