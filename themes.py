"""
themes.py
Four live-switchable visual themes for the Streamlit app, each injected as CSS.
Fonts load from Google Fonts CDN.
"""

THEMES = {
    "Ink & Paper": {
        "font_import": "https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap",
        "css": """
            .stApp { background-color: #f7f3ea; color: #2b2620; }
            h1, h2, h3 { font-family: 'Fraunces', serif; color: #1f1a12; }
            body, p, div, span, label { font-family: 'IBM Plex Mono', monospace; }
            .stButton>button { background-color: #2b2620; color: #f7f3ea; border-radius: 2px; }
            section[data-testid="stSidebar"] { background-color: #efe8d8; }
        """,
    },
    "Midnight Scribe": {
        "font_import": "https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap",
        "css": """
            .stApp { background-color: #12141c; color: #e6e6f0; }
            h1, h2, h3 { font-family: 'Fraunces', serif; color: #f5c451; }
            body, p, div, span, label { font-family: 'JetBrains Mono', monospace; }
            .stButton>button { background-color: #f5c451; color: #12141c; border-radius: 4px; }
            section[data-testid="stSidebar"] { background-color: #1a1d29; }
        """,
    },
    "Botanical": {
        "font_import": "https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600&family=Manrope:wght@400;500;700&display=swap",
        "css": """
            .stApp { background-color: #eef3ea; color: #223420; }
            h1, h2, h3 { font-family: 'Fraunces', serif; color: #2f5233; }
            body, p, div, span, label { font-family: 'Manrope', sans-serif; }
            .stButton>button { background-color: #4b7a51; color: #eef3ea; border-radius: 8px; }
            section[data-testid="stSidebar"] { background-color: #e2ead9; }
        """,
    },
    "Sunset Draft": {
        "font_import": "https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600&family=Nunito:wght@400;600;700&display=swap",
        "css": """
            .stApp { background: linear-gradient(180deg, #fff2e6 0%, #ffe3d1 100%); color: #4a2c1d; }
            h1, h2, h3 { font-family: 'Fraunces', serif; color: #c1440e; }
            body, p, div, span, label { font-family: 'Nunito', sans-serif; }
            .stButton>button { background-color: #e8672d; color: #fff2e6; border-radius: 10px; }
            section[data-testid="stSidebar"] { background-color: #ffe9db; }
        """,
    },
}


def inject_theme(st, theme_name: str):
    theme = THEMES.get(theme_name, THEMES["Ink & Paper"])
    st.markdown(f"""
        <style>
        @import url('{theme["font_import"]}');
        {theme["css"]}
        </style>
    """, unsafe_allow_html=True)
