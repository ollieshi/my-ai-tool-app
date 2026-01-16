import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import zipfile
import os

# --- 頁面設定 ---
st.set_page_config(
    page_title="AI 圖片去浮水印工具",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS 美化 ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; font-family: 'Inter', sans-serif; }
    h1 { font-weight: 900; text-align: center; color: white; }
    h1 span { color: #3b82f6; } /* 藍色強調 */
    .stFileUploader { background: rgba(255,255,255,0.05); border: 1px dashed rgba(255,255,255,0.2); border-radius: 1rem; padding: 2rem; }
    .stButton > button { background-color: #3b82f6; color: white; border: none; border-radius: 0.5rem; font-weight: bold; transition: 0.3s; }
    .stButton > button:hover { background-color: #2563eb; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4); }
</style>
""", unsafe_allow_html=True)


# --- 核心處理函式 (OpenCV) ---
def remove_watermark_opencv(image_bytes, threshold=200):
    """
    使用 OpenCV 進行浮水印偵測與修復
    :param threshold: 亮度閾值，越高只選越白的地方
    """
    # 1. 轉換圖片格式 (Bytes -> CV2)
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    # 2. 製作遮罩 (Mask) - 假設浮水印通常是白色或高亮的
    # 轉灰階
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 二值化：找出高亮區域 (浮水印通常很亮)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # 3. 膨脹遮罩 (Dilate) - 讓遮罩稍微大一點，蓋住邊緣
    kernel = np.ones((3, 3), np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=1)

    # 4. 修復 (Inpainting) - 使用 Telea 算法修補遮罩區域
    # radius=3 參考周圍 3px 的顏色來修補
    result = cv2.inpaint(img, dilated_mask, 3, cv2.INPAINT_TELEA)

    # 5. 轉回 Bytes (CV2 BGR -> RGB -> Bytes)
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(result_rgb)

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue(), pil_img


# --- 主程式 ---
def main():
    st.markdown("<h1>圖片去浮水印 <span>CV版</span></h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #94a3b8; margin-bottom: 2rem;'>使用 OpenCV 智慧修復 • 無需 API Key • 永久免費</p>",
        unsafe_allow_html=True)

    # 上傳區
    uploaded_files = st.file_uploader("上傳圖片 (支援 JPG, PNG, WEBP)", type=['png', 'jpg', 'jpeg', 'webp'],
                                      accept_multiple_files=True)

    # 設定區 (側邊或上方)
    with st.expander("⚙️ 進階設定 (調整修復強度)", expanded=True):
        st.info("💡 提示：如果浮水印沒清乾淨，請**調低**數值；如果背景被誤刪，請**調高**數值。")
        threshold = st.slider("浮水印亮度偵測閾值 (Threshold)", min_value=150, max_value=250, value=215, step=1)

    if uploaded_files:
        if 'processed_images' not in st.session_state:
            st.session_state.processed_images = {}

        if st.button(f"開始處理 ({len(uploaded_files)} 張)", type="primary"):
            progress_bar = st.progress(0)

            for i, file in enumerate(uploaded_files):
                img_bytes = file.getvalue()

                # 執行 OpenCV 處理
                processed_bytes, _ = remove_watermark_opencv(img_bytes, threshold)

                # 存入 Session State
                st.session_state.processed_images[file.name] = {
                    'original': img_bytes,
                    'processed': processed_bytes
                }
                progress_bar.progress((i + 1) / len(uploaded_files))

            st.success("處理完成！")

    # 結果顯示
    if 'processed_images' in st.session_state and st.session_state.processed_images:
        st.markdown("---")

        # 下載全部
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name, data in st.session_state.processed_images.items():
                clean_name = os.path.splitext(name)[0] + "_clean.png"
                zf.writestr(clean_name, data['processed'])

        st.download_button("📦 下載全部結果 (ZIP)", zip_buffer.getvalue(), "images_clean.zip", "application/zip",
                           use_container_width=True)

        # 個別顯示
        for name, data in st.session_state.processed_images.items():
            with st.container():
                st.markdown(
                    "<div class='result-card' style='background:rgba(255,255,255,0.05); padding:15px; border-radius:10px; margin-bottom:10px;'>",
                    unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 1, 1])

                with c1:
                    st.image(data['original'], caption="原始圖片", use_container_width=True)
                with c2:
                    st.image(data['processed'], caption="修復結果", use_container_width=True)
                with c3:
                    st.write(f"**{name}**")
                    clean_name = os.path.splitext(name)[0] + "_clean.png"
                    st.download_button("⬇️ 下載", data['processed'], file_name=clean_name, mime="image/png",
                                       key=f"btn_{name}")

                st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()