"""
app.py
Handwritten Image/PDF -> Editable Text OCR app.

Run with:
    streamlit run app.py

Features:
- Batch upload of multiple images/PDFs at once
- 7 languages: English, Hindi, Kannada, Tamil, Telugu, Bengali, Marathi
- Model choice: Claude / GPT / Gemini vision models
- Inline preview + edit of extracted text per page
- Layout-preserving export to DOCX and PDF (headings, bullets, tables)
- Cloud save to Google Drive / Dropbox
- 4 live-switchable visual themes
"""

import io
import os

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

from ocr_utils import LANGUAGES, MODELS, run_ocr, OcrResult, OcrBlock
from export_utils import build_docx, build_pdf
from themes import inject_theme, THEMES

load_dotenv()

# Optional heavy imports done lazily where used (pdf2image, heic, cloud) to keep startup fast.

st.set_page_config(page_title="Handwriting OCR Studio", page_icon="✍️", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar: theme, language, model, API keys, cloud settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("✍️ OCR Studio")

    theme_name = st.selectbox("Theme", list(THEMES.keys()), index=0)
    inject_theme(st, theme_name)

    st.divider()
    language_name = st.selectbox("Language", list(LANGUAGES.keys()), index=0)
    model_label = st.selectbox("Model", list(MODELS.keys()), index=0)

    st.divider()
    with st.expander("API Keys (session only)", expanded=False):
        st.caption("Keys entered here are stored only for this session and override your .env file.")
        anthropic_key = st.text_input("Anthropic API Key", type="password",
                                       value=os.environ.get("ANTHROPIC_API_KEY", ""))
        openai_key = st.text_input("OpenAI API Key", type="password",
                                    value=os.environ.get("OPENAI_API_KEY", ""))
        google_key = st.text_input("Google API Key", type="password",
                                    value=os.environ.get("GOOGLE_API_KEY", ""))
        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        if google_key:
            os.environ["GOOGLE_API_KEY"] = google_key

    with st.expander("Cloud Save Settings", expanded=False):
        st.caption("Optional -- needed only if you use the cloud save buttons below.")
        dropbox_token = st.text_input("Dropbox Access Token", type="password",
                                       value=os.environ.get("DROPBOX_ACCESS_TOKEN", ""))
        if dropbox_token:
            os.environ["DROPBOX_ACCESS_TOKEN"] = dropbox_token
        google_client_secret_path = st.text_input(
            "Google OAuth client_secret.json path",
            value=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "client_secret.json"),
        )
        os.environ["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = google_client_secret_path

    st.divider()
    st.caption("How to use: pick a theme + language + model → drop image(s)/PDF(s) "
               "→ click 'Extract text' → edit preview → download or cloud-save.")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "results" not in st.session_state:
    st.session_state.results = []   # list[OcrResult]

# ---------------------------------------------------------------------------
# Main: batch upload
# ---------------------------------------------------------------------------

st.title("Handwriting → Editable Text")
st.write("Upload one or more handwritten images or PDFs. Each page is processed and returned as editable text.")

uploaded_files = st.file_uploader(
    "Drop images or PDFs (batch upload supported)",
    type=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "heic", "gif", "pdf"],
    accept_multiple_files=True,
)


def load_images_from_upload(uploaded_file):
    """Returns a list of (page_number, PIL.Image) for a single uploaded file, handling multi-page PDFs and HEIC."""
    name = uploaded_file.name
    suffix = name.lower().split(".")[-1]
    data = uploaded_file.read()

    if suffix == "pdf":
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(data, dpi=200)
        return [(i + 1, p.convert("RGB")) for i, p in enumerate(pages)]

    if suffix == "heic":
        import pillow_heif
        heif_file = pillow_heif.read_heif(data)
        img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
        return [(1, img.convert("RGB"))]

    img = Image.open(io.BytesIO(data))
    return [(1, img.convert("RGB"))]


col_extract, col_clear = st.columns([1, 1])
extract_clicked = col_extract.button("🔍 Extract text", type="primary", use_container_width=True,
                                      disabled=not uploaded_files)
if col_clear.button("🗑️ Clear results", use_container_width=True):
    st.session_state.results = []
    st.rerun()

if extract_clicked and uploaded_files:
    st.session_state.results = []
    progress = st.progress(0.0, text="Starting...")
    total_units = 0
    all_units = []  # (filename, page_no, image)

    for uf in uploaded_files:
        try:
            for page_no, img in load_images_from_upload(uf):
                all_units.append((uf.name, page_no, img))
        except Exception as exc:
            st.session_state.results.append(
                OcrResult(uf.name, 1, language_name, "", [], error=f"Could not read file: {exc}")
            )

    total_units = max(len(all_units), 1)
    for idx, (fname, page_no, img) in enumerate(all_units):
        progress.progress((idx) / total_units, text=f"Extracting {fname} (page {page_no})...")
        result = run_ocr(img, model_label, language_name, filename=fname, page_number=page_no)
        st.session_state.results.append(result)

    progress.progress(1.0, text="Done!")

# ---------------------------------------------------------------------------
# Results: inline preview + edit
# ---------------------------------------------------------------------------

if st.session_state.results:
    st.divider()
    st.subheader(f"Extracted text ({len(st.session_state.results)} page(s))")

    for i, res in enumerate(st.session_state.results):
        header = f"{res.filename} — page {res.page_number} — {res.language}"
        with st.expander(header, expanded=(i == 0)):
            if res.error:
                st.error(res.error)
                continue

            edited = st.text_area(
                "Edit extracted text",
                value=res.raw_text,
                height=220,
                key=f"edit_{i}",
            )
            # Push edits back into a plain-paragraph block so exports reflect edits.
            if edited != res.raw_text:
                res.raw_text = edited
                res.blocks = [OcrBlock(kind="paragraph", text=line) for line in edited.split("\n") if line.strip()]

    st.divider()
    st.subheader("Export")

    valid_results = [r for r in st.session_state.results if not r.error]

    export_col1, export_col2 = st.columns(2)

    with export_col1:
        if valid_results and st.button("📄 Generate DOCX", use_container_width=True):
            docx_bytes = build_docx(valid_results)
            st.session_state["_docx_bytes"] = docx_bytes
        if "_docx_bytes" in st.session_state:
            st.download_button("⬇️ Download .docx", data=st.session_state["_docx_bytes"],
                                file_name="extracted_text.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True)

    with export_col2:
        if valid_results and st.button("📑 Generate PDF", use_container_width=True):
            pdf_bytes = build_pdf(valid_results)
            st.session_state["_pdf_bytes"] = pdf_bytes
        if "_pdf_bytes" in st.session_state:
            st.download_button("⬇️ Download .pdf", data=st.session_state["_pdf_bytes"],
                                file_name="extracted_text.pdf",
                                mime="application/pdf",
                                use_container_width=True)

    st.divider()
    st.subheader("☁️ Cloud Save")
    st.caption("Requires credentials set in the sidebar under 'Cloud Save Settings'.")

    cloud_col1, cloud_col2 = st.columns(2)

    with cloud_col1:
        if st.button("Save DOCX to Google Drive", use_container_width=True, disabled="_docx_bytes" not in st.session_state):
            from cloud_utils import upload_to_drive
            try:
                link = upload_to_drive(
                    st.session_state["_docx_bytes"], "extracted_text.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                st.success(f"Uploaded! [Open in Drive]({link})")
            except Exception as exc:
                st.error(f"Google Drive upload failed: {exc}")

        if st.button("Save DOCX to Dropbox", use_container_width=True, disabled="_docx_bytes" not in st.session_state):
            from cloud_utils import upload_to_dropbox
            try:
                link = upload_to_dropbox(st.session_state["_docx_bytes"], "extracted_text.docx")
                st.success(f"Uploaded! [Open in Dropbox]({link})")
            except Exception as exc:
                st.error(f"Dropbox upload failed: {exc}")

    with cloud_col2:
        if st.button("Save PDF to Google Drive", use_container_width=True, disabled="_pdf_bytes" not in st.session_state):
            from cloud_utils import upload_to_drive
            try:
                link = upload_to_drive(st.session_state["_pdf_bytes"], "extracted_text.pdf", "application/pdf")
                st.success(f"Uploaded! [Open in Drive]({link})")
            except Exception as exc:
                st.error(f"Google Drive upload failed: {exc}")

        if st.button("Save PDF to Dropbox", use_container_width=True, disabled="_pdf_bytes" not in st.session_state):
            from cloud_utils import upload_to_dropbox
            try:
                link = upload_to_dropbox(st.session_state["_pdf_bytes"], "extracted_text.pdf")
                st.success(f"Uploaded! [Open in Dropbox]({link})")
            except Exception as exc:
                st.error(f"Dropbox upload failed: {exc}")
else:
    st.info("Upload files above and click 'Extract text' to get started.")
