"""
ProcessRecorder — main entry point.

Usage:
    process-recorder          # Launch GUI
    python -m process_recorder  # Same thing
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    """Launch the ProcessRecorder GUI application."""
    from PyQt6.QtWidgets import QApplication
    from .gui import MainWindow
    from .config import load_config

    app = QApplication(sys.argv)
    app.setApplicationName("ProcessRecorder")
    app.setApplicationVersion("0.1.0")

    config = load_config()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
