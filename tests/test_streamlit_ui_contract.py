from pathlib import Path


def test_streamlit_ui_exposes_cached_branches_and_source_links():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "@st.cache_resource" in app
    assert "@st.cache_data" in app
    assert "Nhánh verifier" in app
    assert "Nhánh retrieval" in app
    assert "st.link_button" in app
