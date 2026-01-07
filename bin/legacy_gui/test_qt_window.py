#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("Test Qt")
window.setMinimumSize(400, 300)

central = QWidget()
window.setCentralWidget(central)
layout = QVBoxLayout(central)

# Test labels avec différents styles
label1 = QLabel("Label 1: Texte noir normal")
label1.setStyleSheet("color: black; font-size: 14px; background-color: white; padding: 10px;")
label1.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
layout.addWidget(label1)

label2 = QLabel("Label 2: Texte bleu gras")
label2.setStyleSheet("color: #007AFF; font-size: 14px; font-weight: bold; background-color: white; padding: 10px;")
label2.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
layout.addWidget(label2)

label3 = QLabel("Label 3: Texte vert")
label3.setStyleSheet("color: #34C759; font-size: 14px; background-color: white; padding: 10px;")
label3.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
layout.addWidget(label3)

window.show()
window.raise_()
window.activateWindow()

print("Fenêtre de test affichée")
sys.exit(app.exec())
