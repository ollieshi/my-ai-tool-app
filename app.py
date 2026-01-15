import streamlit as st
import requests
import json
import base64
import io
import zipfile
import os
from PIL import Image

# --- 設定頁面配置 ---
st.set_page_config(
    page_title="AI 圖片去浮水印 PRO",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS 樣式注入 (保持原有的深色玻璃風格) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');

    /* 整體背景 */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        font-family: 'Inter', sans-serif;
        color: white;
    }

    /* 標題樣式 */
    h1 {
        font-weight: 900 !important;
        text-align: center;
        padding-bottom: 1rem;
    }

    h1 span {
        color: #f43f5e;
    }

    /* 上傳區塊樣式 */
    .stFileUploader {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px dashed rgba(255,255,255,0.1);
        border-radius: 1.5rem;
        padding: 2rem;
        transition: all 0.3s ease;
    }

    .stFileUploader:hover {
        border-color: #f43f5e;
        transform: scale(1.01);
    }

    /* 按鈕樣式 */
    .stButton > button {
        background-color: #f43f5e;
        color: white;
        border-radius: 0.75rem;
        border: none;
        padding: 0.5rem 1.5rem;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s;
    }

    .stButton > button:hover {
        background-color: #e11d48;
        box-shadow: 0 10px 15px -3px rgba(244, 63, 94, 0.3);
    }

    /* 結果卡片樣式 */
    .result-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 1rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* 下載按鈕特殊樣式 */
    .download-btn {
        background-color: #10b981 !important;
    }

    /* 隱藏預設的主選單和 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

</style>
""", unsafe_allow_html=True)


# --- 輔助函式 ---

def get_api_key():
    """獲取 API Key，優先從環境變數，其次從 Streamlit secrets"""
    # 嘗試從環境變數獲取 (適合 Heroku)
    api_key = os.environ.get("GOOGLE_API_KEY")
    # 如果環境變數沒有，嘗試從 st.secrets 獲取 (適合本地開發)
    if not api_key:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except:
            return None
    return api_key


def image_to_base64(image):
    """將 PIL Image 轉換為 Base64 字串"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def process_image_with_gemini(api_key, image_bytes, mime_type):
    """呼叫 Gemini API 進行處理"""
    model_name = "gemini-2.5-flash-image-preview"  # 使用與原 HTML 相同的模型
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    base64_data = base64.b64encode(image_bytes).decode('utf-8')

    payload = {
        "contents": [{
            "parts": [
                {
                    "text": "Inpaint all text overlays and visual artifacts to restore the underlying background. Return a clean, high-quality image."},
                {"inlineData": {"mimeType": mime_type, "data": base64_data}}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"]
        }
    }

    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # 檢查 HTTP 錯誤

        result = response.json()

        # 解析回應
        try:
            inline_data = result['candidates'][0]['content']['parts'][0]['inlineData']['data']
            return inline_data  # 返回 base64 字串
        except (KeyError, IndexError) as e:
            if 'promptFeedback' in result and 'blockReason' in result['promptFeedback']:
                return {"error": f"內容被阻擋: {result['promptFeedback']['blockReason']}"}
            return {"error": "API 未返回圖片，請稍後重試。"}

    except requests.exceptions.RequestException as e:
        return {"error": f"網路或 API 錯誤: {str(e)}"}


# --- 主程式邏輯 ---

def main():
    st.markdown("<h1>AI 圖片去浮水印 <span>PRO</span></h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #94a3b8; margin-bottom: 2rem;'>Powered by Gemini 2.5 • 自動移除浮水印與修補背景</p>",
        unsafe_allow_html=True)

    # 1. API Key 檢查
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ 未偵測到 API Key。請在 Heroku 環境變數或 .streamlit/secrets.toml 中設定 `GOOGLE_API_KEY`。")
        return

    # 2. 初始化 Session State
    if 'processed_images' not in st.session_state:
        st.session_state.processed_images = {}  # 格式: {filename: {'original': bytes, 'processed': bytes, 'status': str}}

    # 3. 檔案上傳區
    uploaded_files = st.file_uploader("拖放圖片到這裡或點擊上傳", type=['png', 'jpg', 'jpeg', 'webp'],
                                      accept_multiple_files=True)

    # 4. 處理邏輯
    if uploaded_files:
        start_btn = st.button(f"開始處理 ({len(uploaded_files)} 張圖片)")

        if start_btn:
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, uploaded_file in enumerate(uploaded_files):
                file_bytes = uploaded_file.getvalue()
                mime_type = uploaded_file.type
                file_name = uploaded_file.name

                status_text.text(f"正在處理: {file_name} ...")

                # 呼叫 API
                result = process_image_with_gemini(api_key, file_bytes, mime_type)

                if isinstance(result, str):  # 成功，返回的是 Base64 字串
                    processed_bytes = base64.b64decode(result)
                    st.session_state.processed_images[file_name] = {
                        'original': file_bytes,
                        'processed': processed_bytes,
                        'status': 'success'
                    }
                else:  # 失敗，返回的是 dict 含 error
                    st.session_state.processed_images[file_name] = {
                        'original': file_bytes,
                        'processed': None,
                        'status': 'error',
                        'error_msg': result.get('error', 'Unknown Error')
                    }

                progress_bar.progress((idx + 1) / len(uploaded_files))

            status_text.text("處理完成！")
            st.success("所有圖片處理完畢，請查看下方結果。")

    # 5. 結果顯示區
    if st.session_state.processed_images:
        st.markdown("---")
        st.subheader("處理結果")

        # 建立 ZIP 下載
        zip_buffer = io.BytesIO()
        has_success_files = False
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, data in st.session_state.processed_images.items():
                if data['status'] == 'success':
                    has_success_files = True
                    # 檔名處理：加上 _cleaned
                    clean_name = os.path.splitext(name)[0] + "_cleaned.png"
                    zf.writestr(clean_name, data['processed'])

        if has_success_files:
            st.download_button(
                label="📦 下載全部結果 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="watermark_removed_images.zip",
                mime="application/zip",
                use_container_width=True
            )

        # 網格顯示結果
        for name, data in st.session_state.processed_images.items():
            with st.container():
                st.markdown(f"<div class='result-card'>", unsafe_allow_html=True)
                cols = st.columns([1, 1, 1])

                with cols[0]:
                    st.image(data['original'], caption="原始圖片", use_container_width=True)

                with cols[1]:
                    if data['status'] == 'success':
                        st.image(data['processed'], caption="✨ 去浮水印後", use_container_width=True)
                    else:
                        st.error(f"處理失敗: {data.get('error_msg')}")
                        st.image(data['original'], caption="處理失敗", use_container_width=True)

                with cols[2]:
                    st.write(f"**{name}**")
                    if data['status'] == 'success':
                        st.success("處理成功")
                        clean_name = os.path.splitext(name)[0] + "_cleaned.png"
                        st.download_button(
                            label="⬇️ 下載此圖",
                            data=data['processed'],
                            file_name=clean_name,
                            mime="image/png",
                            key=f"btn_{name}"
                        )
                    else:
                        st.error("失敗")

                st.markdown("</div>", unsafe_allow_html=True)

            # 清除按鈕
        if st.button("清除所有結果並重新開始"):
            st.session_state.processed_images = {}
            st.rerun()


if __name__ == "__main__":
    main()