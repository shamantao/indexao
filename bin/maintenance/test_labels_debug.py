#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("Test Labels v2.3")
window.setMinimumSize(400, 300)

# Palette dark
palette = QPalette()
palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
window.setPalette(palette)

layout = QVBoxLayout(window)

# Test 1: Label simple
label1 = QLabel()
label1.setText("TEST 1: Texte blanc simple")
label1.setMinimumSize(300, 40)
label1.setStyleSheet("color: white; font-size: 18px; border: 2px solid red; padding: 5px;")
label1.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
layout.addWidget(label1)

# Test 2: Label avec données
data = "✅ En cours"
label2 = QLabel()
label2.setText(f"TEST 2: {data}")
label2.setMinimumSize(300, 40)
label2.setStyleSheet("color: #30D158; font-size: 18px; font-weight: bold; border: 2px solid yellow; padding: 5px;")
label2.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
layout.addWidget(label2)

# Test 3: Label constructeur
label3 = QLabel("TEST 3: Constructeur direct")
label3.setMinimumSize(300, 40)
label3.setStyleSheet("color: #FF453A; font-size: 18px; border: 2px solid blue; padding: 5px;")
layout.addWidget(label3)

print("Fenêtre de test créée avec 3 labels")
print(f"Label 1 text: '{label1.text()}'")
print(f"Label 2 text: '{label2.text()}'")
print(f"Label 3 text: '{label3.text()}'")

window.show()
window.raise_()
window.activateWindow()

sys.exit(app.exec())
