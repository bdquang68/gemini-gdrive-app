import streamlit as st
import os, glob, gdown
import google.generativeai as genai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import docx, openpyxl
from pptx import Presentation

# 1) Gemini API
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
if not API_KEY:
    st.error("Thiếu GOOGLE_API_KEY trong Secrets (App settings → Secrets).")
    st.stop()
genai.configure(api_key=API_KEY)

# 2) Đọc file
def read_pdf(p):
    try:
        text=""; r=PdfReader(p)
        for page in r.pages: text += page.extract_text() or ""
        return text
    except Exception as e: return f"\n[PDF lỗi {os.path.basename(p)}: {e}]\n"

def read_docx(p):
    try:
        d=docx.Document(p)
        return "\n".join((para.text or "") for para in d.paragraphs)
    except Exception as e: return f"\n[DOCX lỗi {os.path.basename(p)}: {e}]\n"

def read_excel(p):
    try:
        wb=openpyxl.load_workbook(p, data_only=True); out=[]
        for s in wb.sheetnames:
            for row in wb[s].iter_rows(values_only=True):
                cells=[str(c) for c in row if c is not None]
                if cells: out.append(" | ".join(cells))
        return "\n".join(out)
    except Exception as e: return f"\n[XLSX lỗi {os.path.basename(p)}: {e}]\n"

def read_pptx(p):
    try:
        prs=Presentation(p); out=[]
        for slide in prs.slides:
            for sh in slide.shapes:
                if hasattr(sh,"text"): out.append(sh.text or "")
        return "\n".join(out)
    except Exception as e: return f"\n[PPTX lỗi {os.path.basename(p)}: {e}]\n"

def read_txt(p):
    try: return open(p,"r",encoding="utf-8",errors="ignore").read()
    except Exception as e: return f"\n[TXT lỗi {os.path.basename(p)}: {e}]\n"

def read_file(p):
    pl=p.lower()
    if pl.endswith(".pdf"): return read_pdf(p)
    if pl.endswith(".docx"): return read_docx(p)
    if pl.endswith(".xlsx"): return read_excel(p)
    if pl.endswith(".pptx"): return read_pptx(p)
    if pl.endswith(".txt") or pl.endswith(".csv"): return read_txt(p)
    return ""

# 3) Tải toàn bộ thư mục bằng gdown (có bắt lỗi)
def load_data_from_gdrive(folder_id: str) -> str:
    os.makedirs("data", exist_ok=True)
    # dọn cũ
    for p in glob.glob("data/*"):
        if os.path.isdir(p):
            import shutil; shutil.rmtree(p, ignore_errors=True)
        else:
            try: os.remove(p)
            except: pass

    try:
        gdown.download_folder(
            id=folder_id,
            output="data",
            quiet=True,
            use_cookies=False,   # cần cho Streamlit Cloud
            remaining_ok=True    # không fail nếu vài file không tải được
        )
    except Exception as e:
        st.exception(e)  # hiện full stacktrace để sửa nhanh
        st.error(
            "Không tải được thư mục từ Google Drive.\n\n"
            "Kiểm tra:\n"
            "• Folder ID đúng chưa (chuỗi sau 'folders/')?\n"
            "• Thư mục đã mở 'Anyone with the link → Viewer' chưa?\n"
        )
        return ""

    texts=[]
    for p in glob.glob("data/**/*", recursive=True):
        if os.path.isfile(p):
            texts.append(read_file(p))
    return "\n".join(texts)

# 4) Chunk
def chunk_text(text, chunk_size=1000, overlap=200):
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    ).split_text(text)

# 5) UI
st.title("📂 AI Assistant phân tích dữ liệu từ Google Drive")
folder_id = st.text_input("Nhập Google Drive Folder ID:", "")
data = ""

if folder_id.strip():
    with st.spinner("Đang tải và xử lý dữ liệu..."):
        data = load_data_from_gdrive(folder_id.strip())
    if not data:
        st.stop()
    chunks = chunk_text(data)
    st.success(f"✅ Đã load {len(chunks)} chunks dữ liệu.")

query = st.text_input("Nhập câu hỏi:")
if query and data:
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Dữ liệu:\n{data[:20000]}\n\nCâu hỏi: {query}\n\nTrả lời ngắn gọn, dựa vào dữ liệu."
        with st.spinner("Đang phân tích bằng Gemini..."):
            resp = model.generate_content(prompt)
        st.subheader("🔎 Kết quả AI phân tích")
        st.write(resp.text)
    except Exception as e:
        st.exception(e)
        st.error("Lỗi khi gọi Gemini – kiểm tra lại API key hoặc nội dung câu hỏi.")
