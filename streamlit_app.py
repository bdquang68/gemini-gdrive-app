import streamlit as st
import os, glob, gdown
import google.generativeai as genai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import docx
import openpyxl
from pptx import Presentation

# ================================
# 1) Cấu hình Gemini API
# ================================
# Lưu ý: GOOGLE_API_KEY phải là key AI Studio (bắt đầu bằng "AIza...")
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# ================================
# 2) Hàm đọc các loại file
# ================================
def read_pdf(path: str) -> str:
    try:
        text = ""
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        return f"\n[PDF đọc lỗi {os.path.basename(path)}: {e}]\n"

def read_docx(path: str) -> str:
    try:
        text = ""
        doc = docx.Document(path)
        for para in doc.paragraphs:
            text += (para.text or "") + "\n"
        return text
    except Exception as e:
        return f"\n[DOCX đọc lỗi {os.path.basename(path)}: {e}]\n"

def read_excel(path: str) -> str:
    try:
        text = ""
        wb = openpyxl.load_workbook(path, data_only=True)
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    text += " | ".join(cells) + "\n"
        return text
    except Exception as e:
        return f"\n[XLSX đọc lỗi {os.path.basename(path)}: {e}]\n"

def read_pptx(path: str) -> str:
    try:
        text = ""
        prs = Presentation(path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += (shape.text or "") + "\n"
        return text
    except Exception as e:
        return f"\n[PPTX đọc lỗi {os.path.basename(path)}: {e}]\n"

def read_txt(path: str) -> str:
    try:
        return open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        return f"\n[TXT đọc lỗi {os.path.basename(path)}: {e}]\n"

def read_file(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):
        return read_pdf(path)
    if p.endswith(".docx"):
        return read_docx(path)
    if p.endswith(".xlsx"):
        return read_excel(path)
    if p.endswith(".pptx"):
        return read_pptx(path)
    if p.endswith(".txt") or p.endswith(".csv"):
        return read_txt(path)
    # Bỏ qua file không hỗ trợ
    return ""

# ================================
# 3) Tải dữ liệu từ Google Drive (theo Folder ID)
# ================================
def load_data_from_gdrive(folder_id: str) -> str:
    """
    - Yêu cầu thư mục đã bật 'Anyone with the link - Viewer'
      hoặc service account có quyền đọc.
    - Dùng gdown.download_folder(id=...) thay vì URL.
    """
    os.makedirs("data", exist_ok=True)

    try:
        # Xoá nội dung cũ để tránh trộn file
        for f in glob.glob("data/*"):
            if os.path.isdir(f):
                # xóa thư mục con cũ
                import shutil
                shutil.rmtree(f, ignore_errors=True)
            else:
                os.remove(f)

        gdown.download_folder(
            id=folder_id,
            output="data",
            quiet=True,
            use_cookies=False,  # cần thiết trên Streamlit Cloud
        )
    except Exception as e:
        st.error(
            "Không tải được thư mục từ Google Drive.\n"
            f"Lỗi: {e}\n\n"
            "Cách khắc phục:\n"
            "• Kiểm tra đúng Folder ID (phần sau 'folders/').\n"
            "• Bật 'Anyone with the link → Viewer' cho thư mục, "
            "hoặc chia sẻ cho service account nếu bạn dùng Google API.\n"
        )
        return ""

    # Đọc tất cả file trong thư mục và các thư mục con
    texts = []
    for path in glob.glob("data/**/*", recursive=True):
        if os.path.isfile(path):
            texts.append(read_file(path))

    return "\n".join(texts)

# ================================
# 4) Chunk dữ liệu
# ================================
def chunk_text(text: str, chunk_size=1000, overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    return splitter.split_text(text)

# ================================
# 5) Giao diện Streamlit
# ================================
st.title("📂 AI Assistant phân tích dữ liệu từ Google Drive")

folder_id = st.text_input("Nhập Google Drive Folder ID:", "")

data = ""
if folder_id.strip():
    with st.spinner("Đang tải và xử lý dữ liệu..."):
        data = load_data_from_gdrive(folder_id.strip())

    if data:
        chunks = chunk_text(data)
        st.success(f"Đã load {len(chunks)} chunks dữ liệu.")
    else:
        st.stop()

# ================================
# 6) Hỏi AI (Gemini)
# ================================
query = st.text_input("Nhập câu hỏi:")
if query and data:
    try:
        # cắt bớt đầu vào để an toàn context (có thể thay bằng RAG sau)
        context = data[:20000]
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Dữ liệu:\n{context}\n\nCâu hỏi: {query}\n\nTrả lời ngắn gọn, dựa vào dữ liệu."
        with st.spinner("Đang gọi mô hình Gemini..."):
            response = model.generate_content(prompt)
        st.subheader("🔎 Kết quả AI phân tích:")
        st.write(response.text)
    except Exception as e:
        st.error(f"Lỗi khi gọi Gemini: {e}")

