import streamlit as st
import os
import gdown
import google.generativeai as genai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import docx
import openpyxl
from pptx import Presentation

# ================================
# 1. Cấu hình Gemini API
# ================================
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# ================================
# 2. Hàm đọc các loại file
# ================================
def read_pdf(path):
    text = ""
    reader = PdfReader(path)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def read_docx(path):
    text = ""
    doc = docx.Document(path)
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def read_excel(path):
    text = ""
    wb = openpyxl.load_workbook(path)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        for row in ws.iter_rows(values_only=True):
            text += " ".join([str(c) for c in row if c]) + "\n"
    return text

def read_pptx(path):
    text = ""
    prs = Presentation(path)
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

def read_file(path):
    if path.endswith(".pdf"):
        return read_pdf(path)
    elif path.endswith(".docx"):
        return read_docx(path)
    elif path.endswith(".xlsx"):
        return read_excel(path)
    elif path.endswith(".pptx"):
        return read_pptx(path)
    elif path.endswith(".txt"):
        return open(path, "r", encoding="utf-8").read()
    else:
        return ""

# ================================
# 3. Load dữ liệu từ Google Drive
# ================================
def load_data_from_gdrive(folder_id):
    # tải toàn bộ file trong folder về (sử dụng gdown)
    os.makedirs("data", exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    gdown.download_folder(url, output="data", quiet=True)

    corpus = ""
    for file in os.listdir("data"):
        path = os.path.join("data", file)
        corpus += read_file(path) + "\n"
    return corpus

# ================================
# 4. Chunk dữ liệu
# ================================
def chunk_text(text, chunk_size=1000, overlap=200):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_text(text)

# ================================
# 5. Giao diện Streamlit
# ================================
st.title("📂 AI Assistant phân tích dữ liệu từ Google Drive")

folder_id = st.text_input("Nhập Google Drive Folder ID:", "")

if folder_id:
    with st.spinner("Đang tải và xử lý dữ liệu..."):
        data = load_data_from_gdrive(folder_id)
        chunks = chunk_text(data)
        st.success(f"Đã load {len(chunks)} chunks dữ liệu.")

    # Hỏi AI
    query = st.text_input("Nhập câu hỏi:")
    if query:
        model = genai.GenerativeModel("gemini-pro")
        prompt = f"Dữ liệu: {data[:3000]}\n\nCâu hỏi: {query}"
        response = model.generate_content(prompt)
        st.subheader("🔎 Kết quả AI phân tích:")
        st.write(response.text)
