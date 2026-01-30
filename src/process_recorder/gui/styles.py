"""
Stylesheet and theme constants for the ProcessRecorder GUI.
"""

# Color palette
COLORS = {
    "bg": "#1e1e2e",
    "bg_secondary": "#282840",
    "bg_card": "#313150",
    "accent": "#7c3aed",
    "accent_hover": "#6d28d9",
    "accent_light": "#a78bfa",
    "success": "#22c55e",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "warning": "#f59e0b",
    "text": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "border": "#3f3f5c",
}

MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg']};
}}

QWidget {{
    color: {COLORS['text']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}

QPushButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton:pressed {{
    background-color: #5b21b6;
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_muted']};
}}

QPushButton#dangerBtn {{
    background-color: {COLORS['danger']};
}}

QPushButton#dangerBtn:hover {{
    background-color: {COLORS['danger_hover']};
}}

QPushButton#secondaryBtn {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
}}

QPushButton#secondaryBtn:hover {{
    background-color: {COLORS['bg_secondary']};
}}

QListWidget {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin: 2px 0;
}}

QListWidget::item:selected {{
    background-color: {COLORS['accent']};
}}

QListWidget::item:hover:!selected {{
    background-color: {COLORS['bg_card']};
}}

QLabel {{
    color: {COLORS['text']};
}}

QLabel#heading {{
    font-size: 18px;
    font-weight: bold;
}}

QLabel#subheading {{
    font-size: 11px;
    color: {COLORS['text_secondary']};
}}

QLabel#statusLabel {{
    font-size: 12px;
    color: {COLORS['text_secondary']};
    padding: 4px 8px;
}}

QProgressBar {{
    background-color: {COLORS['bg_card']};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: white;
    min-height: 8px;
    max-height: 8px;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text']};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['accent']};
}}

QGroupBox {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    padding-top: 28px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLORS['accent_light']};
}}

QStatusBar {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_secondary']};
    border-top: 1px solid {COLORS['border']};
}}

QMenuBar {{
    background-color: {COLORS['bg_secondary']};
    border-bottom: 1px solid {COLORS['border']};
}}

QMenuBar::item:selected {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QMenu {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QTabWidget::pane {{
    background-color: {COLORS['bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
}}

QTabBar::tab {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}
"""
