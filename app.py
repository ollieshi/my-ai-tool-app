import streamlit as st
import requests
import json
import base64
import io
import zipfile
import os

# --- 設定頁面配置 ---
st.set_page_config(
    page_title="AI 圖片去浮水印 PRO",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS 樣式 (保持原樣) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); font-family: 'Inter', sans-serif; color: white; }
    h1 { font-weight: 900 !important; text-align: center; padding-bottom: 1rem; }
    h1 span { color: #f43f5e; }
    .stFileUploader { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px dashed rgba(255,255,255,0.1); border-radius: 1.5rem; padding: 2rem; transition: all 0.3s ease; }
    .stFileUploader:hover { border-color: #f43f5e; transform: scale(1.01); }
    .stButton > button { background-color: #f43f5e; color: white; border-radius: 0.75rem; border: none; padding: 0.5rem 1.5rem; font-weight: bold; width: 100%; transition: all 0.3s; }
    .stButton > button:hover { background-color: #e11d48; box-shadow: 0 10px 15px -3px rgba(244, 63, 94, 0.3); }
    .result-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 1rem; padding: 1rem; margin-bottom: 1rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# --- 核心邏輯 ---

def get_api_key():
    """
    從 Streamlit Secrets 獲取 API Key。
    這是 Streamlit Cloud 官方推薦的安全方式。
    """
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        return None


def process_image_with_gemini(api_key, image_bytes, mime_type):
    """
    呼叫 Gemini API 進行圖像修復。
    完全對應 HTML 版本中的 fetch 邏輯。
    """
    # 注意：這裡使用 HTML 中指定的模型名稱。如果 2.5 還不可用，請改回 'gemini-2.0-flash-exp'
    model_name = "gemini-2.5-flash-image-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    base64_data = base64.b64encode(image_bytes).decode('utf-8')

    # 建構與 HTML 版本完全相同的 Payload
    payload = {
        "contents": [{
            "parts": [
                {
                    "text": "Inpaint all text overlays and visual artifacts to restore the underlying background. Return a clean, high-quality image."},
                {"inlineData": {"mimeType": mime_type, "data": base64_data}}
            ]
        }],
        # 安全設定：設為 BLOCK_NONE 以避免誤判
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        # 重要：要求 API 回傳圖片格式
        "generationConfig": {
            "responseModalities": ["IMAGE"]
        }
    }

    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        # 處理 429 Too Many Requests (Rate Limit)
        if response.status_code == 429:
            return {"error": "API 請求過於頻繁，請稍後再試 (Error 429)"}

        if response.status_code != 200:
            return {"error": f"API 錯誤 ({response.status_code}): {response.text}"}

        result = response.json()

        # 解析回應 (對應 HTML 中的解析邏輯)
        try:
            # 嘗試抓取回傳的圖片資料
            inline_data = result['candidates'][0]['content']['parts'][0]['inlineData']['data']
            return inline_data  # 成功，返回 base64 字串
        except (KeyError, IndexError, TypeError):
            # 處理被阻擋的情況
            if 'promptFeedback' in result and 'blockReason' in result['promptFeedback']:
                return {"error": f"內容被 AI 安全過濾阻擋: {result['promptFeedback']['blockReason']}"}
            if 'candidates' in result and result['candidates'] and 'finishReason' in result['candidates'][0]:
                return {"error": f"生成停止，原因: {result['candidates'][0]['finishReason']}"}

            return {"error": "API 未返回圖片，請確認模型是否支援 Image Output。"}

    except requests.exceptions.RequestException as e:
        return {"error": f"網路連線錯誤: {str(e)}"}


# --- 主程式 ---

def main():
    st.markdown("<h1>AI 圖片去浮水印 <span>PRO</span></h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #94a3b8; margin-bottom: 2rem;'>Powered by Gemini • 自動移除浮水印與修補背景</p>",
        unsafe_allow_html=True)

    # 1. 獲取 API Key
    api_key = get_api_key()

    # 如果找不到 Key，顯示友善的設定教學
    if not api_key:
        st.warning("⚠️ 尚未設定 API Key")
        st.info("""
        **如何設定：**
        1. 在 Streamlit Cloud 的 App 設定頁面。
        2. 點擊 "Secrets"。
        3. 貼上：`GOOGLE_API_KEY = "你的_API_Key_貼在這裡"`
        4. 按下 Save。
        """)
        st.stop()  # 停止執行後續程式

    # 2. 初始化 Session State
    if 'processed_images' not in st.session_state:
        st.session_state.processed_images = {}

        # 3. 檔案上傳
    uploaded_files = st.file_uploader("拖放圖片到這裡", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True)

    # 4. 處理按鈕
    if uploaded_files:
        # 檢查是否所有檔案都已經處理過
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_images]

        btn_label = "開始處理"
        if new_files:
            btn_label = f"開始處理 ({len(new_files)} 張新圖片)"

        if st.button(btn_label, type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            total_files = len(uploaded_files)

            for idx, uploaded_file in enumerate(uploaded_files):
                file_name = uploaded_file.name

                # 如果已經處理過且成功，就跳過
                if file_name in st.session_state.processed_images and st.session_state.processed_images[file_name][
                    'status'] == 'success':
                    progress_bar.progress((idx + 1) / total_files)
                    continue

                file_bytes = uploaded_file.getvalue()
                mime_type = uploaded_file.type
                status_text.text(f"正在分析並修復: {file_name} ...")

                # 呼叫 API
                result = process_image_with_gemini(api_key, file_bytes, mime_type)

                if isinstance(result, str):  # 成功 (Base64 String)
                    processed_bytes = base64.b64decode(result)
                    st.session_state.processed_images[file_name] = {
                        'original': file_bytes,
                        'processed': processed_bytes,
                        'status': 'success'
                    }
                else:  # 失敗 (Dict with error)
                    st.session_state.processed_images[file_name] = {
                        'original': file_bytes,
                        'processed': None,
                        'status': 'error',
                        'error_msg': result.get('error', 'Unknown Error')
                    }

                progress_bar.progress((idx + 1) / total_files)

            status_text.text("處理完成！")
            st.success("所有圖片處理完畢")

    # 5. 顯示結果
    if st.session_state.processed_images and uploaded_files:
        st.markdown("---")

        # 準備 ZIP 下載
        zip_buffer = io.BytesIO()
        valid_files_count = 0
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, data in st.session_state.processed_images.items():
                if data['status'] == 'success':
                    clean_name = os.path.splitext(name)[0] + "_cleaned.png"
                    zf.writestr(clean_name, data['processed'])
                    valid_files_count += 1

        if valid_files_count > 0:
            st.download_button(
                label=f"📦 下載全部結果 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="watermark_removed.zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_all"
            )

        # 卡片式顯示
        # 過濾出當前上傳列表中的檔案顯示 (避免顯示已刪除的檔案結果)
        current_filenames = [f.name for f in uploaded_files]

        for name in current_filenames:
            if name in st.session_state.processed_images:
                data = st.session_state.processed_images[name]

                with st.container():
                    st.markdown(f"<div class='result-card'>", unsafe_allow_html=True)
                    cols = st.columns([1, 1, 1])

                    with cols[0]:
                        st.text("原始圖片")
                        st.image(data['original'], use_container_width=True)

                    with cols[1]:
                        if data['status'] == 'success':
                            st.text("去浮水印後")
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

        if st.button("清除所有結果"):
            st.session_state.processed_images = {}
            st.rerun()


if __name__ == "__main__":
    main()