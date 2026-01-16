import streamlit as st
import requests
import json
import base64
import io
import zipfile
import os

# --- 設定頁面配置 (必須在第一行) ---
st.set_page_config(
    page_title="AI 圖片去浮水印 PRO",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS 樣式注入 (深色質感介面) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');

    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        font-family: 'Inter', sans-serif;
        color: white;
    }

    h1 { font-weight: 900 !important; text-align: center; padding-bottom: 1rem; }
    h1 span { color: #f43f5e; }

    .stFileUploader {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px dashed rgba(255,255,255,0.1);
        border-radius: 1.5rem;
        padding: 2rem;
        transition: all 0.3s ease;
    }
    .stFileUploader:hover { border-color: #f43f5e; transform: scale(1.01); }

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

    /* 結果卡片 */
    .result-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 1rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* 隱藏預設選單 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# --- 功能函式 ---

def get_api_key():
    """從 Streamlit Secrets 安全獲取 API Key"""
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        return None


def process_image_with_gemini(api_key, image_bytes, mime_type):
    """
    呼叫 Gemini API 進行圖像修復
    使用 requests 直接呼叫 REST API 以確保 responseModalities 參數生效
    """
    # 修正重點：使用目前支援 Image Output 的模型
    model_name = "gemini-2.0-flash-exp"
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
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"]  # 關鍵：要求回傳圖片
        }
    }

    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 429:
            return {"error": "API 請求過於頻繁 (Rate Limit)，請稍後再試。"}

        if response.status_code != 200:
            # 嘗試解析錯誤訊息
            try:
                err_json = response.json()
                err_msg = err_json.get('error', {}).get('message', response.text)
                return {"error": f"API 錯誤 ({response.status_code}): {err_msg}"}
            except:
                return {"error": f"API 錯誤 ({response.status_code})"}

        result = response.json()

        try:
            # 嘗試讀取回傳的圖片
            inline_data = result['candidates'][0]['content']['parts'][0]['inlineData']['data']
            return inline_data  # 回傳 Base64 字串
        except (KeyError, IndexError, TypeError):
            if 'promptFeedback' in result and 'blockReason' in result['promptFeedback']:
                return {"error": f"內容被阻擋: {result['promptFeedback']['blockReason']}"}
            if 'candidates' in result and result['candidates'] and 'finishReason' in result['candidates'][0]:
                return {"error": f"生成停止: {result['candidates'][0]['finishReason']}"}

            return {"error": "API 未返回圖片，請確認模型狀態。"}

    except requests.exceptions.RequestException as e:
        return {"error": f"網路連線錯誤: {str(e)}"}


# --- 主程式邏輯 ---

def main():
    st.markdown("<h1>AI 圖片去浮水印 <span>PRO</span></h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #94a3b8; margin-bottom: 2rem;'>Powered by Gemini 2.0 Flash • 自動移除浮水印</p>",
        unsafe_allow_html=True)

    # 1. 檢查 API Key
    api_key = get_api_key()
    if not api_key:
        st.warning("⚠️ 尚未設定 API Key")
        st.info("請前往 Streamlit Cloud 的 **Settings -> Secrets** 設定 `GOOGLE_API_KEY`。")
        st.stop()

    # 2. Session State 初始化
    if 'processed_images' not in st.session_state:
        st.session_state.processed_images = {}

        # 3. 上傳區
    uploaded_files = st.file_uploader("拖放圖片到這裡", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True)

    # 4. 處理邏輯
    if uploaded_files:
        # 判斷是否有新檔案
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_images]

        btn_text = "開始處理"
        if new_files:
            btn_text = f"開始處理 ({len(new_files)} 張新圖片)"

        if st.button(btn_text, type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(uploaded_files)

            for i, file in enumerate(uploaded_files):
                # 如果已經成功處理過，跳過
                if file.name in st.session_state.processed_images and st.session_state.processed_images[file.name][
                    'status'] == 'success':
                    progress_bar.progress((i + 1) / total)
                    continue

                status_text.text(f"正在 AI 運算中: {file.name} ...")

                # 讀取檔案
                file_bytes = file.getvalue()

                # 呼叫 API
                result = process_image_with_gemini(api_key, file_bytes, file.type)

                if isinstance(result, str):  # 成功 (回傳 Base64)
                    processed_bytes = base64.b64decode(result)
                    st.session_state.processed_images[file.name] = {
                        'original': file_bytes,
                        'processed': processed_bytes,
                        'status': 'success'
                    }
                else:  # 失敗 (回傳 Error Dict)
                    st.session_state.processed_images[file.name] = {
                        'original': file_bytes,
                        'processed': None,
                        'status': 'error',
                        'error_msg': result.get('error', 'Unknown Error')
                    }

                progress_bar.progress((i + 1) / total)

            status_text.text("處理完成！")
            st.success("任務結束")

    # 5. 結果顯示與下載
    if st.session_state.processed_images and uploaded_files:
        st.markdown("---")

        # 準備 ZIP 下載
        zip_buffer = io.BytesIO()
        valid_count = 0
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, data in st.session_state.processed_images.items():
                if data['status'] == 'success':
                    clean_name = os.path.splitext(name)[0] + "_cleaned.png"
                    zf.writestr(clean_name, data['processed'])
                    valid_count += 1

        if valid_count > 0:
            st.download_button(
                label="📦 下載全部結果 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="watermark_removed.zip",
                mime="application/zip",
                use_container_width=True
            )

        # 顯示個別卡片
        current_names = [f.name for f in uploaded_files]
        for name in current_names:
            if name in st.session_state.processed_images:
                data = st.session_state.processed_images[name]

                with st.container():
                    st.markdown("<div class='result-card'>", unsafe_allow_html=True)
                    cols = st.columns([1, 1, 1])

                    with cols[0]:
                        st.caption("原始圖片")
                        st.image(data['original'], use_container_width=True)

                    with cols[1]:
                        if data['status'] == 'success':
                            st.caption("去浮水印結果")
                            st.image(data['processed'], use_container_width=True)
                        else:
                            st.error(f"❌ 失敗: {data.get('error_msg')}")

                    with cols[2]:
                        st.write(f"**{name}**")
                        if data['status'] == 'success':
                            clean_name = os.path.splitext(name)[0] + "_cleaned.png"
                            st.download_button(
                                label="⬇️ 下載圖片",
                                data=data['processed'],
                                file_name=clean_name,
                                mime="image/png",
                                key=f"btn_{name}"
                            )
                    st.markdown("</div>", unsafe_allow_html=True)

        if st.button("清除結果並重新開始"):
            st.session_state.processed_images = {}
            st.rerun()


if __name__ == "__main__":
    main()