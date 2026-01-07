#!/usr/bin/env python3
"""
Fenêtre de configuration du throttling pour IndexaoManager
PyQt6 avec design macOS moderne
"""
import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QSpinBox, QSlider, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Référence globale pour éviter garbage collection
_throttle_dialog = None


class ThrottleConfigDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.setup_ui()
        
    def _load_config(self):
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except Exception:
            return {'batch_size': 100, 'sleep_ms': 1000, 'max_docs_per_minute': 5000}
    
    def _save_config(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde: {e}")
            return False
    
    def setup_ui(self):
        self.setWindowTitle("Configuration Throttle (Palette Fix)")
        self.setMinimumSize(500, 400)
        
        # Forcer palette light
        from PyQt6.QtGui import QPalette, QColor
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 247))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        self.setPalette(palette)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f7;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #d1d1d6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #1d1d1f;
            }
            QLabel {
                font-size: 13px;
                color: #1d1d1f;
                padding: 4px;
            }
            QSpinBox {
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
                min-width: 120px;
            }
            QSpinBox:focus {
                border: 2px solid #007AFF;
            }
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #0051D5;
            }
            QPushButton:pressed {
                background-color: #004DB8;
            }
            QPushButton#cancelBtn {
                background-color: #8E8E93;
            }
            QPushButton#cancelBtn:hover {
                background-color: #636366;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # === Section Paramètres ===
        params_group = QGroupBox("⚙️ Paramètres de Throttling")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # Batch Size
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 10000)
        self.batch_spin.setValue(self.config.get('batch_size', 100))
        self.batch_spin.setSuffix(" documents")
        batch_label = QLabel("Taille du lot :")
        batch_label.setToolTip("Nombre de documents envoyés à Meilisearch par batch")
        form_layout.addRow(batch_label, self.batch_spin)
        
        # Sleep (ms)
        self.sleep_spin = QSpinBox()
        self.sleep_spin.setRange(0, 60000)
        self.sleep_spin.setValue(self.config.get('sleep_ms', 1000))
        self.sleep_spin.setSuffix(" ms")
        sleep_label = QLabel("Pause entre lots :")
        sleep_label.setToolTip("Délai en millisecondes entre chaque batch")
        form_layout.addRow(sleep_label, self.sleep_spin)
        
        # Max docs/min
        self.max_docs_spin = QSpinBox()
        self.max_docs_spin.setRange(100, 100000)
        self.max_docs_spin.setValue(self.config.get('max_docs_per_minute', 5000))
        self.max_docs_spin.setSuffix(" docs/min")
        max_docs_label = QLabel("Limite de débit :")
        max_docs_label.setToolTip("Maximum de documents indexés par minute")
        form_layout.addRow(max_docs_label, self.max_docs_spin)
        
        params_group.setLayout(form_layout)
        layout.addWidget(params_group)
        
        # === Aperçu ===
        preview_group = QGroupBox("📊 Aperçu")
        preview_layout = QVBoxLayout()
        
        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview_label.setStyleSheet("background-color: #fafafa; padding: 12px; border-radius: 6px; font-family: 'Menlo', Monaco, monospace; color: #000000;")
        self.update_preview()
        preview_layout.addWidget(self.preview_label)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Connecter les changements pour mise à jour preview
        self.batch_spin.valueChanged.connect(self.update_preview)
        self.sleep_spin.valueChanged.connect(self.update_preview)
        self.max_docs_spin.valueChanged.connect(self.update_preview)
        
        # === Boutons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def update_preview(self):
        batch = self.batch_spin.value()
        sleep = self.sleep_spin.value()
        max_docs = self.max_docs_spin.value()
        
        # Calculs
        batches_per_min = 60000 / max(sleep, 1)
        docs_per_min_actual = min(batch * batches_per_min, max_docs)
        time_for_1000 = (1000 / docs_per_min_actual * 60) if docs_per_min_actual > 0 else 0
        
        preview = f"""
<b>Configuration actuelle :</b><br>
• Lots de {batch} documents<br>
• Pause de {sleep} ms entre chaque lot<br>
• Limite : {max_docs} documents/minute<br>
<br>
<b>Performance estimée :</b><br>
• ~{docs_per_min_actual:.0f} documents/minute<br>
• ~{time_for_1000:.1f} secondes pour 1000 documents<br>
• ~{batches_per_min:.1f} lots/minute maximum
"""
        self.preview_label.setText(preview)
    
    def save_and_close(self):
        self.config['batch_size'] = self.batch_spin.value()
        self.config['sleep_ms'] = self.sleep_spin.value()
        self.config['max_docs_per_minute'] = self.max_docs_spin.value()
        
        if self._save_config():
            self.accept()
        else:
            self.reject()


# Référence globale pour éviter garbage collection
_throttle_dialog = None

def show_throttle_config(config_path):
    """Fonction appelée depuis IndexaoManager"""
    global _throttle_dialog
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Fermer dialog précédent si existe
    if _throttle_dialog is not None:
        try:
            _throttle_dialog.close()
        except:
            pass
    
    _throttle_dialog = ThrottleConfigDialog(config_path)
    _throttle_dialog.setWindowFlags(_throttle_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    _throttle_dialog.show()
    _throttle_dialog.raise_()
    _throttle_dialog.activateWindow()
    
    return _throttle_dialog


if __name__ == "__main__":
    # Test standalone
    app = QApplication(sys.argv)
    dialog = ThrottleConfigDialog("/tmp/throttling.json")
    dialog.exec()
    sys.exit(0)
