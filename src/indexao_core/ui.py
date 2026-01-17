import streamlit as st
import meilisearch
import os
import subprocess
from pathlib import Path
from indexao_core.config import load_config

# Page Configuration
st.set_page_config(
    page_title="Indexao",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for "Finder-like" look
st.markdown("""
<style>
    .file-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
    }
    .path-text {
        color: #888;
        font-family: 'Menlo', 'Consolas', monospace;
        font-size: 11px;
    }
    .filename {
        font-weight: 600;
        font-size: 15px;
        color: #1f1f1f;
        margin-bottom: 4px;
    }
    .stButton button {
        height: 28px;
        padding-top: 0px;
        padding-bottom: 0px;
        font-size: 13px;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Helper for local file opening (macOS specific)
def open_file(path):
    try:
        if os.path.exists(path):
            subprocess.run(["open", path])
            return True
        else:
            st.toast(f"Fichier introuvable: {path}", icon="❌")
    except Exception as e:
        print(f"Error opening file: {e}")
    return False

# Load Config & Initialize Client
@st.cache_resource
def get_meili_client():
    config = load_config()
    client = meilisearch.Client(
        config.meilisearch.url,
        config.meilisearch.api_key if config.meilisearch.api_key else None
    )
    return client

client = get_meili_client()
index = client.index("documents")

# Sidebar
with st.sidebar:
    st.title("Indexao")
    st.caption("v2.1 • Explorer")
    
    # Check server status
    try:
        health = client.health()
        st.success("System Online", icon="🟢")
    except Exception as e:
        st.error(f"Offline: {e}")
        st.stop()
        
    stats = index.get_stats()
    st.markdown(f"**{stats.number_of_documents}** documents indexés")

# Main Search Header
col_search, col_sort = st.columns([0.85, 0.15])
with col_search:
    query = st.text_input("Recherche globale", placeholder="Mots-clés, contenu, traduction...", label_visibility="collapsed")

if query:
    # Perform search
    search_params = {
        'limit': 50,
        'attributesToHighlight': ['content', 'translation'],
        'highlightPreTag': '<mark>',
        'highlightPostTag': '</mark>',
        'cropLength': 200  # Snippet length
    }
    
    results = index.search(query, search_params)
    hits = results.get('hits', [])
    
    st.markdown(f"<div style='margin-bottom: 20px; color:gray'>{len(hits)} résultats trouvés</div>", unsafe_allow_html=True)
    
    for hit in hits:
        # Data preparation
        filename = hit.get('original_filename', 'Unknown')
        vol_path = hit.get('volume_path', '')
        full_path_orig = os.path.join(vol_path, filename)
        full_path_md = full_path_orig + ".md"
        language = hit.get('language', 'N/A')
        
        # Translation status
        translation_content = hit.get('translation')
        has_translation = translation_content and len(translation_content) > 20 and not translation_content.startswith("> ⚠️")
        
        # Determine language flags
        flag_lang = "🇨🇳" if "zh" in language else "📄"
        
        # --- Card Layout ---
        with st.container():
            # Clean Path Visualization (last 3 parts for context)
            try:
                p = Path(vol_path)
                display_path = " / ".join(p.parts[-3:])
            except:
                display_path = vol_path

            c_icon, c_info, c_actions = st.columns([0.05, 0.65, 0.3])
            
            with c_icon:
                st.write("📄") # Or dynamic icon based on extension

            with c_info:
                # Path (Tree style)
                st.markdown(f"<div class='path-text'>📂 ... / {display_path} /</div>", unsafe_allow_html=True)
                # Filename
                st.markdown(f"<div class='filename'>{filename}</div>", unsafe_allow_html=True)
                
                # Preview Snippet (Highlighted)
                formatted = hit.get('_formatted', {})
                snippet = formatted.get('translation') if has_translation else formatted.get('content')
                if snippet:
                    # Strip newlines for compact preview
                    snippet_text = snippet.replace("\n", " ")[:200]
                    st.caption(f"...{snippet_text}...", unsafe_allow_html=True)

            with c_actions:
                st.write("") # v-align spacer
                # Action Buttons
                col_btn_1, col_btn_2 = st.columns(2)
                with col_btn_1:
                    if st.button(f"Ouvrir {flag_lang}", key=f"orig_{hit['id']}", help="Ouvrir le fichier original"):
                        open_file(full_path_orig)
                with col_btn_2:
                    if has_translation:
                         if st.button(f"Ouvrir 🇫🇷", key=f"trans_{hit['id']}", help="Ouvrir le fichier Markdown traduit"):
                            open_file(full_path_md)
                    else:
                        st.button("🇫🇷", disabled=True, key=f"trans_dis_{hit['id']}")

            # Expander for Reading within App
            with st.expander("👁️ Voir le contenu traduit"):
                if has_translation:
                    # Use raw Markdown for proper rendering (Headers matching input)
                    st.markdown(translation_content)
                else:
                    st.warning("Pas de traduction disponible.")
                    st.markdown(hit.get('content', ''))
            
            st.divider()

else:
    # Empty State: Show Folders?
    st.info("👆 Tapez une recherche pour explorer vos documents.")
    
    # Optional: Quick stats or recent files could be here

# Footer
st.markdown("---")
st.caption("Indexao v2.0 - Powered by Meilisearch & Apple Vision")
