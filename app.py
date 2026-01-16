import streamlit as st
import streamlit.components.v1 as components

# 設定頁面為寬版模式，讓 HTML 有更多空間
st.set_page_config(layout="wide", page_title="AI 去浮水印 (Canvas UI)")

# 1. 從 Streamlit Secrets 獲取 API Key
# 這是為了安全，不要把 Key 寫死在 HTML 裡
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("⚠️ 未偵測到 API Key！請在 Streamlit Cloud 設定 Secrets。")
    st.stop()

# 2. 您的 HTML 代碼 (作為字串)
# 我在裡面做了一個標記：const apiKey = ""; 會被 Python 替換掉
html_code = r"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 圖片去浮水印 PRO - Canvas Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: transparent; min-height: 100vh; }
        /* 調整背景為透明，以融入 Streamlit 的深色模式，或保留原背景 */
        body { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
        .drop-zone-active { border-color: #3b82f6 !important; background-color: rgba(59, 130, 246, 0.1) !important; transform: scale(1.02); }
        .loader { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid #f43f5e; border-radius: 50%; width: 20px; height: 20px; animation: spin 0.8s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .result-card { transition: all 0.3s ease; }
        .result-card:hover { transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0,0,0,0.3); }
        .progress-bar { transition: width 0.3s ease; }
        .custom-scrollbar::-webkit-scrollbar { height: 6px; width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 10px; }
        .custom-checkbox:checked + div { border-color: #f43f5e; background-color: rgba(244, 63, 94, 0.2); }
        .custom-checkbox:checked + div .check-icon { opacity: 1; transform: scale(1); }
    </style>
</head>
<body class="text-white pb-20">
    <div class="max-w-6xl mx-auto px-4 py-12">
        <header class="text-center mb-12">
            <h1 class="text-4xl md:text-5xl font-black tracking-tight mb-3">
                AI 圖片去浮水印 <span class="text-rose-500">PRO</span>
            </h1>
            <p class="text-slate-400 text-lg">上傳圖片 → 選擇圖片 → 自動移除浮水印 → 下載結果</p>
            <div class="flex items-center justify-center gap-4 mt-4">
                <span class="flex items-center gap-2 text-xs text-rose-400">
                    <span class="w-2 h-2 bg-rose-400 rounded-full animate-pulse"></span>
                    Powered by Gemini
                </span>
            </div>
        </header>

        <section id="upload-section" class="mb-10 transition-all duration-300">
            <div id="drop-zone" class="glass rounded-3xl p-16 text-center cursor-pointer hover:border-rose-500/50 transition-all duration-300 group border-2 border-transparent border-dashed">
                <input type="file" id="file-input" class="hidden" accept="image/*" multiple>
                <div class="w-20 h-20 bg-rose-500/20 text-rose-400 rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                </div>
                <p class="text-2xl font-bold text-white mb-2">拖放圖片到這裡</p>
                <p class="text-slate-400">支援 JPG, PNG, WEBP 等格式</p>
            </div>
        </section>

        <section id="selection-section" class="hidden mb-10 animate-fade-in">
            <div class="flex items-center justify-between mb-6 flex-wrap gap-4">
                <div>
                    <h2 class="text-2xl font-bold flex items-center gap-2">
                        <span class="bg-rose-500 w-8 h-8 rounded-full flex items-center justify-center text-sm">1</span>
                        選擇要處理的圖片
                    </h2>
                    <p class="text-slate-400 text-sm mt-1 ml-10">勾選包含浮水印的圖片進行 AI 修復</p>
                </div>
                <div class="flex gap-3">
                    <button id="select-all-btn" class="px-4 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 text-sm font-bold transition">全選</button>
                    <button id="deselect-all-btn" class="px-4 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 text-sm font-bold transition">取消全選</button>
                    <button id="start-process-btn" class="bg-rose-600 hover:bg-rose-500 text-white px-6 py-2 rounded-xl text-sm font-bold shadow-lg shadow-rose-500/20 transition flex items-center gap-2">
                        開始處理 (<span id="selected-count">0</span>)
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </button>
                </div>
            </div>
            <div id="selection-grid" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 custom-scrollbar max-h-[60vh] overflow-y-auto p-2"></div>
        </section>

        <section id="progress-section" class="hidden mb-10">
            <div class="glass rounded-3xl p-8">
                <div class="flex items-center justify-between mb-6">
                    <div class="flex items-center gap-4">
                        <div class="loader"></div>
                        <div>
                            <p id="progress-title" class="font-bold text-lg">AI 處理中...</p>
                            <p id="progress-detail" class="text-sm text-slate-400">正在分析圖片結構</p>
                        </div>
                    </div>
                    <span id="progress-count" class="text-2xl font-black text-rose-400">0/0</span>
                </div>
                <div class="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                    <div id="progress-bar" class="progress-bar bg-gradient-to-r from-rose-500 to-orange-500 h-full rounded-full" style="width: 0%"></div>
                </div>
            </div>
        </section>

        <section id="results-section" class="hidden">
            <div class="flex items-center justify-between mb-6 flex-wrap gap-4 border-t border-slate-700 pt-8">
                <div>
                    <h2 class="text-2xl font-bold flex items-center gap-2">
                        <span class="bg-emerald-500 w-8 h-8 rounded-full flex items-center justify-center text-sm">2</span>
                        處理結果
                    </h2>
                </div>
                <div class="flex items-center gap-3 flex-wrap">
                    <button id="download-all-btn" class="hidden bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-xl font-bold transition flex items-center gap-2 shadow-lg shadow-emerald-500/20">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        全部下載 (ZIP)
                    </button>
                    <button id="reset-btn" class="bg-slate-700/50 hover:bg-slate-700 text-slate-300 px-4 py-2.5 rounded-xl font-bold transition flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        上傳新圖片
                    </button>
                </div>
            </div>
            <div id="results-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 custom-scrollbar"></div>
        </section>
    </div>

    <div id="toast" class="fixed bottom-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-6 py-3 rounded-2xl shadow-2xl opacity-0 transition-all pointer-events-none z-50 text-sm font-bold border border-slate-700"></div>

    <script>
        // 設定 API Key (Python 會自動將這裡的空字串替換成真實 Key)
        const apiKey = ""; 
        // 嘗試使用較新的模型 (雖然仍可能被鎖住圖片輸出)
        const MODEL_IMAGE_EDIT = "gemini-2.0-flash-exp"; 

        // 狀態變數
        let pendingItems = [];
        let results = [];
        let currentBatchItems = []; 

        // 國際化字串 (繁體中文)
        const i18n = {
            processing: "正在處理",
            analyzing: "分析中",
            aiRemoving: "AI 正在移除浮水印並修補背景...",
            unsupportedFormat: "不支援的檔案格式，請上傳圖片",
            readFailed: "檔案讀取失敗",
            apiKeyInvalid: "API Key 無效或環境錯誤",
            apiNoImage: "API 拒絕生成影像 (可能涉及敏感內容或版權)",
            rateLimit: "API 速率限制 (429)，等待 {sec} 秒後重試...",
            readingFiles: "正在讀取圖片...",
            success: "成功",
            failed: "失敗"
        };

        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const uploadSection = document.getElementById('upload-section');
        const selectionSection = document.getElementById('selection-section');
        const selectionGrid = document.getElementById('selection-grid');
        const progressSection = document.getElementById('progress-section');
        const resultsSection = document.getElementById('results-section');
        const progressBar = document.getElementById('progress-bar');
        const progressTitle = document.getElementById('progress-title');
        const progressDetail = document.getElementById('progress-detail');
        const progressCount = document.getElementById('progress-count');
        const resultsGrid = document.getElementById('results-grid');
        const toast = document.getElementById('toast');
        const selectedCountSpan = document.getElementById('selected-count');
        const downloadAllBtn = document.getElementById('download-all-btn');

        function showToast(msg, isError = false) {
            toast.textContent = msg;
            toast.style.backgroundColor = isError ? '#ef4444' : '#1e293b';
            toast.style.borderColor = isError ? '#b91c1c' : '#334155';
            toast.classList.replace('opacity-0', 'opacity-100');
            setTimeout(() => toast.classList.replace('opacity-100', 'opacity-0'), 3000);
        }

        const wait = (ms) => new Promise(res => setTimeout(res, ms));

        // API 請求 (含重試機制)
        async function fetchWithRetry(url, options, maxRetries = 5) {
            const delays = [2000, 4000, 8000, 16000, 32000];
            for (let i = 0; i < maxRetries; i++) {
                try {
                    const response = await fetch(url, options);
                    const data = await response.json();
                    if (response.ok) return data;
                    if (response.status === 429) {
                        const waitTime = delays[i] || 10000;
                        showToast(i18n.rateLimit.replace('{sec}', waitTime/1000), true);
                        await wait(waitTime);
                        continue;
                    }
                    throw new Error(data.error?.message || `HTTP ${response.status}`);
                } catch (e) {
                    if (i === maxRetries - 1) throw e;
                    await wait(2000);
                }
            }
        }

        // 拖放與檔案選擇事件
        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = e => handleFiles(e.target.files);
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('drop-zone-active'); };
        dropZone.ondragleave = () => dropZone.classList.remove('drop-zone-active');
        dropZone.ondrop = (e) => { e.preventDefault(); dropZone.classList.remove('drop-zone-active'); handleFiles(e.dataTransfer.files); };

        async function handleFiles(files) {
            if (!files || files.length === 0) return;
            dropZone.innerHTML = `<div class="loader mx-auto mb-4"></div><p class="text-slate-300">${i18n.readingFiles}</p>`;
            dropZone.style.pointerEvents = 'none';
            pendingItems = [];
            try {
                for (let file of files) {
                    const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|bmp)$/i.test(file.name);
                    if (isImage) {
                        const base64 = await fileToBase64(file);
                        pendingItems.push({ 
                            id: `img_${Date.now()}_${Math.random()}`, 
                            type: 'image', 
                            name: file.name,
                            mimeType: file.type || "image/png", 
                            thumb: base64, 
                            original: base64, 
                            selected: true 
                        });
                    }
                }
                if (pendingItems.length > 0) { renderSelectionGrid(); }
                else { showToast(i18n.unsupportedFormat, true); location.reload(); }
            } catch (err) { console.error(err); showToast(err.message || i18n.readFailed, true); setTimeout(() => location.reload(), 2000); }
        }

        function renderSelectionGrid() {
            uploadSection.classList.add('hidden');
            selectionSection.classList.remove('hidden');
            selectionGrid.innerHTML = '';
            pendingItems.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'relative group';
                div.innerHTML = `<label class="cursor-pointer block relative"><input type="checkbox" class="custom-checkbox hidden" ${item.selected ? 'checked' : ''} onchange="toggleSelection(${index}, this.checked)"><div class="glass rounded-xl overflow-hidden border-2 border-transparent transition-all h-32 md:h-40 flex flex-col relative"><img src="data:${item.mimeType};base64,${item.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition"><div class="check-icon absolute top-2 right-2 w-6 h-6 bg-rose-500 rounded-full flex items-center justify-center text-white shadow-lg transform scale-0 transition-transform duration-200"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg></div><div class="absolute bottom-0 left-0 right-0 bg-black/60 p-1 text-[10px] text-center truncate text-white backdrop-blur-sm">${item.name}</div></div></label>`;
                selectionGrid.appendChild(div);
            });
            updateSelectedCount();
        }

        window.toggleSelection = (index, isChecked) => { pendingItems[index].selected = isChecked; updateSelectedCount(); };
        function updateSelectedCount() {
            const count = pendingItems.filter(i => i.selected).length;
            selectedCountSpan.textContent = count;
            document.getElementById('start-process-btn').disabled = count === 0;
            document.getElementById('start-process-btn').classList.toggle('opacity-50', count === 0);
        }

        document.getElementById('select-all-btn').onclick = () => { pendingItems.forEach(i => i.selected = true); renderSelectionGrid(); };
        document.getElementById('deselect-all-btn').onclick = () => { pendingItems.forEach(i => i.selected = false); renderSelectionGrid(); };

        document.getElementById('start-process-btn').onclick = async () => {
            const selectedItems = pendingItems.filter(i => i.selected);
            if (selectedItems.length === 0) return;
            selectionSection.classList.add('hidden');
            progressSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            downloadAllBtn.classList.add('hidden');
            await processSelectedItems(selectedItems);
        };

        async function processSelectedItems(items) {
            results = [];
            currentBatchItems = items; 
            resultsGrid.innerHTML = '';
            resultsSection.classList.remove('hidden');

            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                let processBase64 = item.thumb; 

                progressTitle.textContent = `${i18n.processing}: ${item.name}`;
                progressCount.textContent = `${i + 1}/${items.length}`;
                progressBar.style.width = `${((i + 1) / items.length) * 100}%`;
                progressDetail.textContent = i18n.aiRemoving;

                try {
                    const cleaned = await removeWatermarkWithGemini(processBase64, item.mimeType);
                    results[i] = {
                        name: item.name,
                        original: processBase64,
                        mimeType: item.mimeType,
                        cleaned,
                        sourceType: item.type
                    };
                    addResultCard(i, item.name, cleaned);
                } catch (e) {
                    console.error("處理錯誤:", e);
                    const isAuthError = e.message.includes("400") || e.message.includes("403") || e.message.includes("key");
                    const errMsg = isAuthError ? i18n.apiKeyInvalid : e.message;
                    results[i] = {
                        name: item.name,
                        original: processBase64,
                        mimeType: item.mimeType,
                        cleaned: null,
                        error: errMsg,
                        sourceType: item.type
                    };
                    addResultCard(i, item.name, null, errMsg);
                }
                if (i < items.length - 1) await wait(3000); 
            }

            const hasSuccess = results.some(r => r && r.cleaned);
            if (hasSuccess) {
                downloadAllBtn.classList.remove('hidden');
            }

            setTimeout(() => progressSection.classList.add('hidden'), 1000);
        }

        downloadAllBtn.onclick = async () => {
            const zip = new JSZip();
            let count = 0;

            results.forEach(item => {
                if (item && item.cleaned) {
                    zip.file(`${item.name}_Clean.png`, item.cleaned, {base64: true});
                    count++;
                }
            });

            if (count === 0) {
                showToast("沒有可下載的圖片", true);
                return;
            }

            try {
                showToast("正在打包 ZIP...", false);
                const content = await zip.generateAsync({type:"blob"});
                saveAs(content, "watermark_removed_images.zip");
                showToast("下載已開始", false);
            } catch (e) {
                console.error(e);
                showToast("打包失敗，請重試", true);
            }
        };

        function fileToBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        async function removeWatermarkWithGemini(base64, mimeType = "image/png") {
            const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL_IMAGE_EDIT}:generateContent?key=${apiKey}`;

            const payload = { 
                contents: [{ 
                    parts: [
                        { text: "Inpaint all text overlays and visual artifacts to restore the underlying background. Return a clean, high-quality image." }, 
                        { inlineData: { mimeType: mimeType, data: base64 } }
                    ] 
                }], 
                safetySettings: [
                    { category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_NONE" },
                    { category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_NONE" },
                    { category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_NONE" },
                    { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_NONE" }
                ],
                generationConfig: { responseModalities: ['IMAGE'] } 
            };

            const data = await fetchWithRetry(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });

            const part = data.candidates?.[0]?.content?.parts?.find(p => p.inlineData);

            if (!part) {
                console.error("API Response missing image data:", JSON.stringify(data, null, 2));

                if (data.promptFeedback?.blockReason) {
                      throw new Error(`Blocked by safety filter: ${data.promptFeedback.blockReason}`);
                }
                if (data.candidates?.[0]?.finishReason) {
                    if (data.candidates[0].finishReason === "NO_IMAGE") {
                          throw new Error(i18n.apiNoImage);
                    }
                    if (data.candidates[0].finishReason !== "STOP") {
                          throw new Error(`Generation stopped: ${data.candidates[0].finishReason}`);
                    }
                }

                throw new Error(data.error?.message || i18n.apiNoImage);
            }
            return part.inlineData.data;
        }

        function addResultCard(index, name, cleaned, error) {
            let div = document.getElementById(`result-card-${index}`);
            if (!div) {
                div = document.createElement('div');
                div.id = `result-card-${index}`;
                div.className = 'result-card glass rounded-2xl overflow-hidden';
                resultsGrid.appendChild(div);
            }

            if (cleaned) { 
                div.innerHTML = `
                    <div class="relative group h-48">
                        <img src="data:image/png;base64,${cleaned}" class="w-full h-full object-cover">
                        <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
                            <a href="data:image/png;base64,${cleaned}" download="${name}_Clean.png" class="bg-white text-slate-900 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-200 shadow-xl transform scale-95 hover:scale-100 transition flex items-center gap-1">
                                下載
                            </a>
                            <button onclick="reprocessItem(${index})" class="bg-slate-700 text-white p-1.5 rounded-lg hover:bg-slate-600 shadow-xl transform scale-95 hover:scale-100 transition" title="重新處理">
                                重試
                            </button>
                        </div>
                    </div>
                    <div class="p-4 flex justify-between items-center text-[10px]">
                        <span class="truncate max-w-[60%]">${name}</span>
                        <span class="text-emerald-400 font-bold flex items-center gap-1">
                            ${i18n.success}
                        </span>
                    </div>`; 
            }
            else { 
                div.innerHTML = `
                    <div class="p-6 text-center text-red-400 text-[10px] h-48 flex items-center justify-center border border-red-500/20 bg-red-500/10 flex-col gap-3">
                        <div>${error || i18n.failed}</div>
                        <button onclick="reprocessItem(${index})" class="bg-red-500/20 hover:bg-red-500/30 text-red-300 px-3 py-1 rounded-lg transition text-xs flex items-center gap-1 cursor-pointer">
                            重試
                        </button>
                    </div>`; 
            }
        }

        async function reprocessItem(index) {
            const item = currentBatchItems[index];
            const div = document.getElementById(`result-card-${index}`);

            if (!item || !div) return;

            div.innerHTML = `
                <div class="h-48 flex items-center justify-center bg-slate-800/50 flex-col gap-2">
                    <div class="loader"></div>
                    <div class="text-[10px] text-slate-400">重新處理中...</div>
                </div>
            `;

            try {
                const cleaned = await removeWatermarkWithGemini(item.thumb, item.mimeType);
                results[index] = { ...item, cleaned };
                addResultCard(index, item.name, cleaned, null);
            } catch (e) {
                console.error("Reprocess error:", e);
                const errMsg = e.message;
                results[index] = { ...item, cleaned: null, error: errMsg };
                addResultCard(index, item.name, null, errMsg);
            }

            const hasSuccess = results.some(r => r && r.cleaned);
            if (hasSuccess) downloadAllBtn.classList.remove('hidden');
        }

        document.getElementById('reset-btn').onclick = () => location.reload();
    </script>
</body>
</html>
"""

# 3. 關鍵步驟：注入 API Key
# 搜尋 HTML 中的 const apiKey = ""; 並替換成 const apiKey = "你的真實Key";
# 注意：這會讓 Key 暴露在瀏覽器端，但對於個人小專案是可接受的
html_with_key = html_code.replace('const apiKey = "";', f'const apiKey = "{api_key}";')

# 4. 渲染 HTML 元件
# height 設定高一點以避免出現內捲軸
components.html(html_with_key, height=1000, scrolling=True)