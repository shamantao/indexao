#!/usr/bin/env python3
"""
Fenêtre de statut moderne pour IndexaoManager
PyQt6 avec design macOS moderne
"""
import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

# Référence globale pour éviter garbage collection
_status_window = None


class StatusWindow(QWidget):
    def __init__(self, status_data):
        super().__init__()
        self.status_data = status_data
        # Debug: afficher les données reçues
        import sys
        print(f"\n[DEBUG StatusWindow] __init__ appelé", file=sys.stderr)
        print(f"[DEBUG StatusWindow] Données reçues:", file=sys.stderr)
        for k, v in status_data.items():
            print(f"  {k}: {repr(v)}", file=sys.stderr)
        self.setup_ui()
        print(f"[DEBUG StatusWindow] setup_ui terminé", file=sys.stderr)
        
    def setup_ui(self):
        self.setWindowTitle("Indexao - Statut Détaillé (Tuiles)")
        self.setMinimumSize(950, 800)
        
        # Forcer palette DARK (au lieu de light)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))  # Fond sombre
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))  # Texte blanc
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))  # Base sombre
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))  # Texte blanc
        palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))  # Bouton sombre
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))  # Texte bouton blanc
        self.setPalette(palette)
        
        # CSS pour dark mode
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #2d2d2d;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: white;
                background-color: #2d2d2d;
            }
            QPushButton {
                background-color: #0A84FF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0969DA;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 6px;
                text-align: center;
                height: 24px;
                background-color: #3a3a3a;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #30D158;
                border-radius: 5px;
            }
            QTextEdit {
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px;
                background-color: #2d2d2d;
                font-family: 'Menlo', 'Courier New', monospace;
                font-size: 12px;
                color: white;
            }
        """)
        
        # Layout principal
        main_grid = QGridLayout(self)
        main_grid.setSpacing(16)
        main_grid.setContentsMargins(20, 20, 20, 20)
        
        # === Section Services ===
        services_group = QGroupBox("🔧 Services")
        services_layout = QVBoxLayout()
        services_layout.setSpacing(12)
        
        # Meilisearch
        meili_val = self.status_data.get('meilisearch', '❌')
        meili_color = "#30D158" if '✅' in meili_val else "#FF453A"
        meili_line = QLabel()
        meili_line.setText(f"🔍 Meilisearch: {meili_val}")
        meili_line.setMinimumHeight(35)
        meili_line.setStyleSheet(f"color: {meili_color}; font-size: 17px; padding: 8px; font-weight: bold; background-color: rgba(48, 209, 88, 0.1);" if '✅' in meili_val else f"color: {meili_color}; font-size: 17px; padding: 8px; font-weight: bold; background-color: rgba(255, 69, 58, 0.1);")
        meili_line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        services_layout.addWidget(meili_line)
        
        # Indexao
        indexao_val = self.status_data.get('indexao', '❌')
        indexao_color = "#30D158" if '✅' in indexao_val else "#FF453A"
        indexao_line = QLabel()
        indexao_line.setText(f"⚡ Indexao API: {indexao_val}")
        indexao_line.setMinimumHeight(35)
        indexao_line.setStyleSheet(f"color: {indexao_color}; font-size: 17px; padding: 8px; font-weight: bold; background-color: rgba(48, 209, 88, 0.1);" if '✅' in indexao_val else f"color: {indexao_color}; font-size: 17px; padding: 8px; font-weight: bold; background-color: rgba(255, 69, 58, 0.1);")
        indexao_line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        services_layout.addWidget(indexao_line)
        
        services_group.setLayout(services_layout)
        main_grid.addWidget(services_group, 0, 0)  # Ligne 0, Colonne 0
        
        # === Section Scan en cours ===
        scan_group = QGroupBox("📁 Indexation")
        scan_layout = QVBoxLayout()
        scan_layout.setSpacing(8)
        
        scan_status = self.status_data.get('scan_status', 'Aucun scan')
        scan_status_label = QLabel()
        scan_status_label.setText(f"📄 {scan_status}")
        scan_status_label.setMinimumHeight(30)
        scan_status_label.setStyleSheet("color: #64D2FF; font-size: 16px; padding: 6px; font-weight: 600;")
        scan_status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scan_layout.addWidget(scan_status_label)
        
        volume_label = QLabel()
        volume_label.setText(f"📁 Volume: {self.status_data.get('volume_name', '-')}")
        volume_label.setMinimumHeight(30)
        volume_label.setStyleSheet("color: #BF5AF2; font-weight: bold; font-size: 15px; padding: 6px;")
        volume_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scan_layout.addWidget(volume_label)
        
        progress_text = self.status_data.get('progress', '0/0')
        progress_label = QLabel()
        progress_label.setText(f"📊 Progression: {progress_text}")
        progress_label.setMinimumHeight(30)
        progress_label.setStyleSheet("color: #FFFFFF; font-size: 15px; padding: 6px; font-weight: 500;")
        progress_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scan_layout.addWidget(progress_label)
        
        # Barre de progression
        if '/' in progress_text:
            try:
                current, total = progress_text.split('/')
                current, total = int(current), int(total)
                progress_bar = QProgressBar()
                progress_bar.setMaximum(total)
                progress_bar.setValue(current)
                progress_bar.setFormat(f"{current}/{total} ({current/total*100 if total else 0:.1f}%)")
                scan_layout.addWidget(progress_bar)
            except:
                pass
        
        scan_group.setLayout(scan_layout)
        main_grid.addWidget(scan_group, 0, 1)  # Ligne 0, Colonne 1
        
        # === Section Queue ===
        queue_group = QGroupBox("📋 File d'Attente Persistante")
        queue_layout = QVBoxLayout()
        queue_layout.setSpacing(8)
        
        queue_stats = self.status_data.get('queue', {})
        for icon, label_text, key, color in [
            ("⏳", "En attente", 'pending', '#FF9F0A'),
            ("▶️", "En cours", 'processing', '#0A84FF'),
            ("✅", "Terminés", 'done', '#30D158'),
            ("❌", "Erreurs", 'error', '#FF453A')
        ]:
            value = queue_stats.get(key, 0)
            line = QLabel()
            line.setText(f"{icon} {label_text}: {value:,}")
            line.setMinimumHeight(32)
            line.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 16px; padding: 6px 10px; background-color: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15); border-radius: 4px;")
            line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            queue_layout.addWidget(line)
        
        queue_group.setLayout(queue_layout)
        main_grid.addWidget(queue_group, 1, 0)  # Ligne 1, Colonne 0
        
        # === Section Ressources ===
        resources_group = QGroupBox("💻 Ressources Système")
        resources_layout = QVBoxLayout()
        resources_layout.setSpacing(8)
        
        for icon, label_text, key in [
            ("🖥️", "CPU", 'cpu'),
            ("💾", "RAM", 'ram'),
            ("🎮", "GPU", 'gpu')
        ]:
            line = QLabel()
            line.setText(f"{icon} {label_text}: {self.status_data.get(key, '?')}")
            line.setMinimumHeight(28)
            line.setStyleSheet("color: #FFD60A; font-size: 15px; padding: 5px; font-weight: 600;")
            line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            resources_layout.addWidget(line)
        
        resources_group.setLayout(resources_layout)
        main_grid.addWidget(resources_group, 1, 1)  # Ligne 1, Colonne 1
        
        # === Section Réseau ===
        network_group = QGroupBox("🌐 Réseau")
        network_layout = QVBoxLayout()
        network_layout.setSpacing(8)
        
        for icon, label_text, key in [
            ("⬇️", "Meilisearch IN", 'net_in_proc'),
            ("⬆️", "Meilisearch OUT", 'net_out_proc'),
            ("📥", "Machine IN", 'net_in'),
            ("📤", "Machine OUT", 'net_out')
        ]:
            line = QLabel()
            line.setText(f"{icon} {label_text}: {self.status_data.get(key, '?')}")
            line.setMinimumHeight(28)
            line.setStyleSheet("color: #64D2FF; font-size: 14px; padding: 5px; font-weight: 500;")
            line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            network_layout.addWidget(line)
        
        network_group.setLayout(network_layout)
        main_grid.addWidget(network_group, 2, 0, 1, 2)  # Ligne 2, colonnes 0-1 (span 2)
        
        # === JSON Copiable ===
        json_group = QGroupBox("📋 Données Copiables (JSON)")
        json_layout = QVBoxLayout()
        
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(False)  # Permet copier-coller
        self.json_text.setPlainText(json.dumps(self.status_data, indent=2, ensure_ascii=False))
        self.json_text.setMaximumHeight(150)
        json_layout.addWidget(self.json_text)
        
        copy_btn = QPushButton("📋 Copier dans le Presse-Papier")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        json_layout.addWidget(copy_btn)
        
        json_group.setLayout(json_layout)
        main_grid.addWidget(json_group, 3, 0, 1, 2)  # Ligne 3, colonnes 0-1
        
        # Bouton Fermer
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #8E8E93;
            }
            QPushButton:hover {
                background-color: #636366;
            }
        """)
        close_btn.clicked.connect(self.close)
        main_grid.addWidget(close_btn, 4, 0, 1, 2)  # Ligne 4, colonnes 0-1
        
        # Forcer le rafraîchissement
        self.update()
        self.repaint()
        
    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.json_text.toPlainText())
            # Feedback visuel
            btn = self.sender()
            if isinstance(btn, QPushButton):
                btn.setText("✅ Copié!")
                QTimer.singleShot(2000, lambda: btn.setText("📋 Copier dans le Presse-Papier"))


# Référence globale pour éviter garbage collection
_status_window = None

def show_status_window(status_data):
    """Fonction appelée depuis IndexaoManager"""
    global _status_window
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Fermer fenêtre précédente si existe
    if _status_window is not None:
        try:
            _status_window.close()
        except:
            pass
    
    _status_window = StatusWindow(status_data)
    _status_window.setWindowFlags(_status_window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    _status_window.show()
    _status_window.raise_()
    _status_window.activateWindow()
    
    return _status_window


if __name__ == "__main__":
    # Test standalone
    test_data = {
        'meilisearch': '✅ En cours',
        'indexao': '✅ En cours',
        'scan_status': 'Scan en cours',
        'volume_name': 'pcloud_drive',
        'progress': '45000/66321',
        'queue': {'pending': 21321, 'processing': 100, 'done': 44900, 'error': 0},
        'cpu': '12.5%',
        'ram': '256.3 Mo',
        'gpu': 'N/A (ARM)',
        'net_in_proc': '2.1 MB',
        'net_out_proc': '450 KB',
        'net_in': '1234.5 Mo',
        'net_out': '567.8 Mo'
    }
    
    app = QApplication(sys.argv)
    window = StatusWindow(test_data)
    window.show()
    sys.exit(app.exec())
