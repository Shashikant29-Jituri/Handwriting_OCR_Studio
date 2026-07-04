# Handwriting OCR Studio

Converts handwritten images/PDFs to editable text in **English, Hindi, Kannada, Tamil,
Telugu, Bengali & Marathi**, using your choice of Claude / GPT / Gemini vision models.

## Features
- **Batch upload**: drop multiple images/PDFs at once, all processed in one run
- **7 languages**: English, Hindi, Kannada, Tamil, Telugu, Bengali, Marathi
- **Model choice**: Claude Sonnet/Opus, GPT-5.4/4o, Gemini 3 Flash/3.1 Pro
- **File support**: JPG, PNG, WEBP, BMP, TIFF, HEIC, GIF, multi-page PDF
- **Inline preview + edit** before export
- **Layout-preserving export**: headings, bullet lists, and tables are detected
  and reproduced in both DOCX and PDF (not just one big text blob)
- **DOCX export** (python-docx) and **PDF export** (ReportLab) with correct
  script rendering per language
- **Cloud save** to Google Drive and Dropbox
- **4 switchable themes**: Ink & Paper, Midnight Scribe, Botanical, Sunset Draft

## Setup

```bash
cd ocr_app
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1. Add at least one vision-model API key
Copy `.env.example` to `.env` and fill in the key for whichever provider(s)
you want to use in the model dropdown:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

You can also paste keys directly into the sidebar at runtime instead of using `.env`.

### 2. Add fonts for non-Latin scripts (required for correct PDF rendering)
Download the Noto Sans family for each script from https://fonts.google.com/noto
and place the `.ttf` files in `ocr_app/fonts/`:

```
fonts/
  NotoSans-Regular.ttf
  NotoSansDevanagari-Regular.ttf   (Hindi + Marathi)
  NotoSansKannada-Regular.ttf
  NotoSansTamil-Regular.ttf
  NotoSansTelugu-Regular.ttf
  NotoSansBengali-Regular.ttf
```
Without these, non-English text will fall back to Helvetica in PDF exports
and may render as boxes. DOCX exports rely on Word/LibreOffice's own font
substitution and generally work even without these files, as long as a
matching font is installed on the machine opening the file.

### 3. (Optional) Cloud save credentials
- **Google Drive**: create an OAuth 2.0 Client ID ("Desktop app") in the
  [Google Cloud Console](https://console.cloud.google.com/), download the
  JSON, and point `GOOGLE_OAUTH_CLIENT_SECRET_FILE` at it. First save will
  open a browser window to authorize; a `token.json` is cached afterward.
- **Dropbox**: create an app at https://www.dropbox.com/developers/apps and
  generate an access token, then set `DROPBOX_ACCESS_TOKEN`.

### 4. PDF-to-image support
`pdf2image` requires the `poppler` system binary:
```bash
# macOS
brew install poppler
# Ubuntu/Debian
sudo apt-get install poppler-utils
```

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`), then:
1. Pick a theme, language, and model in the sidebar.
2. Drop one or more images/PDFs onto the uploader.
3. Click **Extract text**.
4. Edit any page's text inline if needed.
5. Click **Generate DOCX** / **Generate PDF**, then download or push straight
   to Google Drive / Dropbox.

## Project structure
```
ocr_app/
├── app.py            # Streamlit UI and orchestration
├── ocr_utils.py       # Multi-provider vision OCR + language/layout schema
├── export_utils.py    # DOCX/PDF generation with font handling
├── cloud_utils.py      # Google Drive / Dropbox upload
├── themes.py          # 4 CSS themes
├── requirements.txt
├── .env.example
└── fonts/             # (you add) Noto Sans TTFs for Indic scripts
```

## Notes on "layout-preserving export"
The OCR prompt asks the model to classify each visual chunk as a heading,
paragraph, bullet, or table row, returned as structured JSON rather than
raw text. Export functions then render that structure natively:
DOCX gets real `List Bullet` styles and Word tables; PDF gets ReportLab
`Table` flowables and bullet paragraph styles. Multi-column pages are
transcribed column-by-column with a labeled break, since arbitrary
visual column reconstruction from a single vision-model pass isn't reliable.
