import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, QPoint, pyqtSlot
from PyQt5.QtGui import QColor, QFont

class CyberMainUI(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.oldPos = QPoint()
        self.init_ui()

    def init_ui(self):
        # --- ウィンドウ基本設定 ---
        self.setWindowTitle("checkSIGNALs - CYBER_PUNK_V4")
        self.resize(350, 500)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # メインウィジェット
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainFrame")
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- 1. ヘッダー (ドラッグハンドル兼務) ---
        header = QHBoxLayout()
        self.status_indicator = QLabel("● SYSTEM READY")
        self.status_indicator.setObjectName("StatusText")
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setObjectName("CloseBtn")
        
        header.addWidget(self.status_indicator)
        header.addStretch()
        header.addWidget(self.close_btn)
        layout.addLayout(header)

        # --- 2. メインディスプレイ (シグナル表示) ---
        self.display_box = QFrame()
        self.display_box.setObjectName("DisplayBox")
        display_layout = QVBoxLayout(self.display_box)
        
        self.label_symbol = QLabel("USD/JPY")
        self.label_symbol.setAlignment(Qt.AlignCenter)
        self.label_symbol.setObjectName("SymbolLabel")

        self.label_main_signal = QLabel("WAITING")
        self.label_main_signal.setAlignment(Qt.AlignCenter)
        self.label_main_signal.setObjectName("MainSignal")
        self.apply_glow(self.label_main_signal, "#00f3ff") # 初期値はシアン

        self.label_price = QLabel("150.000")
        self.label_price.setAlignment(Qt.AlignCenter)
        self.label_price.setObjectName("PriceLabel")

        display_layout.addWidget(self.label_symbol)
        display_layout.addWidget(self.label_main_signal)
        display_layout.addWidget(self.label_price)
        layout.addWidget(self.display_box)

        # --- 3. 詳細データグリッド ---
        data_layout = QHBoxLayout()
        self.info_left = QLabel("POWER: 0%")
        self.info_left.setObjectName("DataLabel")
        self.info_right = QLabel("VOL: LOW")
        self.info_right.setObjectName("DataLabel")
        
        data_layout.addWidget(self.info_left)
        data_layout.addStretch()
        data_layout.addWidget(self.info_right)
        layout.addLayout(data_layout)

        # スタイルシート適用
        self.setStyleSheet(self.get_cyber_qss())

    def apply_glow(self, widget, color_hex):
        """ネオン発光エフェクト"""
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(25)
        glow.setColor(QColor(color_hex))
        glow.setOffset(0, 0)
        widget.setGraphicsEffect(glow)

    @pyqtSlot(str, str, str)
    def update_signal(self, signal_type, price, power):
        """
        ロジック側から呼ばれる更新関数
        signal_type: 'HIGH', 'LOW', 'WAITING'
        """
        self.label_main_signal.setText(signal_type)
        self.label_price.setText(price)
        self.info_left.setText(f"POWER: {power}%")

        if signal_type == "HIGH":
            self.apply_glow(self.label_main_signal, "#00ff88") # ネオングリーン
            self.label_main_signal.setStyleSheet("color: #00ff88;")
        elif signal_type == "LOW":
            self.apply_glow(self.label_main_signal, "#ff0055") # ネオンピンク
            self.label_main_signal.setStyleSheet("color: #ff0055;")
        else:
            self.apply_glow(self.label_main_signal, "#00f3ff") # シアン
            self.label_main_signal.setStyleSheet("color: #00f3ff;")

    def get_cyber_qss(self):
        return """
            #MainFrame {
                background-color: rgba(5, 5, 10, 230);
                border: 2px solid #00f3ff;
                border-radius: 0px; /* 角をあえて尖らせるのがサイバー風 */
            }
            #StatusText {
                color: #00f3ff;
                font-family: 'Consolas';
                font-size: 10px;
                font-weight: bold;
            }
            #CloseBtn {
                background: transparent;
                color: #ff0055;
                border: 1px solid #ff0055;
                font-family: 'Arial';
            }
            #CloseBtn:hover {
                background: #ff0055;
                color: #000;
            }
            #DisplayBox {
                background-color: rgba(0, 243, 255, 15);
                border-left: 5px solid #00f3ff;
                margin: 10px 0px;
            }
            #SymbolLabel {
                color: rgba(0, 243, 255, 0.6);
                font-family: 'OCR A Extended', 'Consolas';
                font-size: 14px;
            }
            #MainSignal {
                color: #00f3ff;
                font-family: 'Impact';
                font-size: 56px;
                font-weight: bold;
                letter-spacing: 3px;
            }
            #PriceLabel {
                color: #fff;
                font-family: 'Digital-7', 'Consolas'; /* デジタルフォントがあれば最高 */
                font-size: 28px;
            }
            #DataLabel {
                color: #00f3ff;
                font-family: 'Consolas';
                font-size: 11px;
                border-bottom: 1px solid rgba(0, 243, 255, 0.3);
            }
        """

    # --- ドラッグ移動用ロジック ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # フォントの微調整（システムにConsolasがない場合を考慮）
    app.setStyle("Fusion")
    
    gui = CyberMainUI()
    gui.show()
    
    # テスト用：3秒後にシグナルが変化するデモ
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(3000, lambda: gui.update_signal("HIGH", "150.425", "88"))
    QTimer.singleShot(6000, lambda: gui.update_signal("LOW", "149.880", "92"))

    sys.exit(app.exec_())
