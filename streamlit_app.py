import streamlit as st
import os, glob, gdown
import google.generativeai as genai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import docx
import openpyxl
from pptx import Presentation

# =============== 1) Cấu hình Gemini API ===============
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
if not API_KEY:
    st.error("Thiếu GOOGLE_API_KEY trong Secrets. Vào App settings → Secrets để thêm API key (AIza...).")
    st.stop()
genai.configure(api_key=API_KEY)

# =============== 2) Hàm đọc file ======================
def read_pdf(path: str) -> str:
    try:
        text = ""
        reader = PdfReader(path)
        for p in reader.pages:
            text += p.extract_text() or ""
        return text
    except Exception as e:
        return f"\n[PDF lỗi {os.path.basename(path)}: {e}]\n"

def read_docx(path: str) -> str:
    try:
        d = docx.Document(path)
        return "\n".join((para.text or "") for para in d.paragraphs)
    except Exception as e:
        return f"\n[DOCX lỗi {os.path.basename(path)}: {e}]\n"

def read_excel(path: str) -> str:
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        lines = []
        for s in wb.sheetnames:
            ws = wb[s]
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception as e:
        return f"\n[XLSX lỗi {os.path.basename(path)}: {e}]\n"

def read_pptx(path: str) -> str:
    try:
        prs = Presentation(path)
        out = []
        for slide in prs.slides:
            for sh in slide.shapes:
                if hasattr(sh, "text"):
                    out.append(sh.text or "")
        return "\n".join(out)
    except Exception as e:
        return f"\n[PPTX lỗi {os.path.basename(path)}: {e}]\n"

def read_txt(path: str) -> str:
    try:
        return open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        return f"\n[TXT lỗi {os.path.basename(path)}: {e}]\n"

def read_file(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):  return read_pdf(path)
    if p.endswith(".docx"): return read_docx(path)
    if p.endswith(".xlsx"): return read_excel(path)
    if p.endswith(".pptx"): return read_pptx(path)
    if p.endswith(".txt") or p.endswith(".csv"): return read_txt(path)
    return ""  # bỏ qua định dạng không hỗ trợ

# =============== 3) Tải dữ liệu từ Google Drive =======
def load_data_from_gdrive(folder_id: str) -> str:
    """
    Cần: thư mục được share 'Anyone with the link - Viewer'
    (hoặc bạn dùng service account và đã share quyền cho SA đó).
    """
    os.makedirs("data", exist_ok=True)

    # dọn sạch data cũ để tránh trộn
    for p in glob.glob("data/*"):
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        else:
            try: os.remove(p)
            except: pass

    try:
        # Dùng id= thay vì url=
        gdown.download_folder(
            id=folder_id,
            output="data",
            quiet=True,
            use_cookies=False,  # cần cho streamlit.cloud
        )
    except Exception as e:
        st.error(
            "Không tải được thư mục từ Google Drive.\n"
            f"Lỗi: {e}\n\n"
            "Cách xử lý:\n"
            "• Kiểm tra đúng Folder ID (chuỗi sau 'folders/').\n"
            "• Bật 'Anyone with the link → Viewer' cho thư mục cần đọc.\n"
        )
        return ""

    # Đọc tất cả file (kể cả thư mục con)
    texts = []
    for path in glob.glob("data/**/*", recursive=True):
        if os.path.isfile(path):
            texts.append(read_file(path))
    return "\n".join(texts)

# =============== 4) Chunk dữ liệu ======================
def chunk_text(text: str, chunk_size=1000, overlap=200):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(text)

# =============== 5) UI ================================
st.title("📂 AI Assistant phân tích dữ liệu từ Google Drive")

folder_id = st.text_input("Nhập Google Drive Folder ID:", "")
data = ""

if folder_id.strip():
    with st.spinner("Đang tải và xử lý dữ liệu..."):
        data = load_data_from_gdrive(folder_id.strip())
    if data:
        chunks = chunk_text(data)
        st.success(f"✅ Đã load {len(chunks)} chunks dữ liệu.")
    else:
        st.stop()

query = st.text_input("Nhập câu hỏi:")
if query and data:
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        context = data[:20000]  # cắt bớt để an toàn context
        prompt = f"Dữ liệu:\n{context}\n\nCâu hỏi: {query}\n\nTrả lời ngắn gọn, dựa vào dữ liệu."
        with st.spinner("Đang phân tích bằng Gemini..."):
            resp = model.generate_content(prompt)
        st.subheader("🔎 Kết quả AI phân tích")
        st.write(resp.text)
    except Exception as e:
        st.error(f"Lỗi khi gọi Gemini: {e}")
