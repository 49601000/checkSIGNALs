import streamlit as st
import streamlit.components.v1 as components

class CyberUI:
    """
    checkSIGNALs Cyberpunk Edition UI Component
    Streamlit環境下で動作する高輝度ネオンUI
    """
    def __init__(self):
        self.setup_global_style()

    def setup_global_style(self):
        """Streamlit全体の背景やフォントをサイバーパンク風に上書き"""
        st.markdown("""
            <style>
            /* 全体の背景を漆黒に */
            .stApp {
                background-color: #05050a;
                color: #00f3ff;
            }
            /* サイドバーの装飾 */
            [data-testid="stSidebar"] {
                background-color: #0a0a15;
                border-right: 1px solid #00f3ff;
            }
            /* タイトルのネオン発光 */
            h1, h2, h3 {
                color: #00f3ff !important;
                text-shadow: 0 0 10px #00f3ff, 0 0 20px #00f3ff;
                font-family: 'Courier New', monospace;
                letter-spacing: 2px;
            }
            /* Streamlit標準ボタンのサイバー化 */
            .stButton>button {
                background-color: rgba(0, 243, 255, 0.1);
                color: #00f3ff;
                border: 1px solid #00f3ff;
                border-radius: 0px;
                transition: 0.3s;
                width: 100%;
            }
            .stButton>button:hover {
                background-color: #00f3ff;
                color: #000;
                box-shadow: 0 0 20px #00f3ff;
            }
            </style>
        """, unsafe_allow_html=True)

    def render_signal_card(self, symbol, signal_type, price, power, volume="NORMAL"):
        """
        メインのシグナル表示カード（HTML/CSS注入）
        """
        # 状態に応じたテーマカラーの切り替え
        theme_color = "#00f3ff"  # シアン (Waiting)
        glow_class = "glow-cyan"
        
        if signal_type == "HIGH":
            theme_color = "#00ff88"  # ネオングリーン
            glow_class = "glow-green"
        elif signal_type == "LOW":
            theme_color = "#ff0055"  # ネオンピンク
            glow_class = "glow-pink"

        html_content = f"""
        <div class="cyber-card {glow_class}">
            <div class="scanline"></div>
            <div class="header">
                <span class="system-tag">SYSTEM_CORE_V4</span>
                <span class="status-tag">ONLINE</span>
            </div>
            
            <div class="symbol">{symbol}</div>
            <div class="signal-text">{signal_type}</div>
            <div class="price-display">{price}</div>
            
            <div class="footer-grid">
                <div class="stat-box">
                    <div class="label">POWER</div>
                    <div class="value">{power}%</div>
                </div>
                <div class="stat-box" style="border-left: 1px solid {theme_color}44;">
                    <div class="label">VOL</div>
                    <div class="value">{volume}</div>
                </div>
            </div>
        </div>

        <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        .cyber-card {{
            background: rgba(10, 10, 20, 0.9);
            border: 2px solid {theme_color};
            padding: 20px;
            position: relative;
            overflow: hidden;
            font-family: 'Share Tech Mono', monospace;
            color: {theme_color};
            margin: 10px 0;
            min-height: 220px;
        }}

        /* 走査線アニメーション */
        .scanline {{
            width: 100%;
            height: 2px;
            background: rgba(255, 255, 255, 0.1);
            position: absolute;
            top: 0;
            left: 0;
            animation: scan 4s linear infinite;
            z-index: 10;
        }}
        @keyframes scan {{
            0% {{ top: 0; }}
            100% {{ top: 100%; }}
        }}

        .glow-cyan {{ box-shadow: 0 0 20px rgba(0, 243, 255, 0.3), inset 0 0 10px rgba(0, 243, 255, 0.2); }}
        .glow-green {{ box-shadow: 0 0 25px rgba(0, 255, 136, 0.4), inset 0 0 10px rgba(0, 255, 136, 0.2); border-color: #00ff88; }}
        .glow-pink {{ box-shadow: 0 0 25px rgba(255, 0, 85, 0.4), inset 0 0 10px rgba(255, 0, 85, 0.2); border-color: #ff0055; }}

        .header {{ display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 15px; border-bottom: 1px solid {theme_color}44; padding-bottom: 5px; }}
        .symbol {{ font-size: 18px; letter-spacing: 3px; opacity: 0.8; }}
        .signal-text {{ font-size: 68px; font-weight: bold; text-align: center; margin: 10px 0; text-shadow: 0 0 15px {theme_color}; }}
        .price-display {{ font-size: 32px; text-align: center; color: #fff; letter-spacing: 2px; }}
        
        .footer-grid {{ display: grid; grid-template-columns: 1fr 1fr; margin-top: 20px; border-top: 1px solid {theme_color}44; padding-top: 10px; }}
        .stat-box {{ text-align: center; }}
        .label {{ font-size: 10px; opacity: 0.6; }}
        .value {{ font-size: 18px; font-weight: bold; }}
        </style>
        """
        # HTMLをStreamlitに描画
        components.html(html_content, height=320)

# --- 開発・テスト用実行ブロック ---
if __name__ == "__main__":
    st.set_page_config(page_title="checkSIGNALs Cyber", layout="wide")
    
    ui = CyberUI()
    st.title("⚡ checkSIGNALs V4 - CYBER")
    
    # テスト用入力
    with st.sidebar:
        st.header("Debug Console")
        test_symbol = st.text_input("Symbol", "USD/JPY")
        test_signal = st.radio("Signal State", ["WAITING", "HIGH", "LOW"])
        test_price = st.text_input("Current Price", "150.452")
        test_power = st.slider("Signal Power", 0, 100, 75)

    # メイン表示
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        ui.render_signal_card(test_symbol, test_signal, test_price, test_power)
