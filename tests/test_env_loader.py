from src.env_loader import load_dotenv


def test_load_dotenv_skips_empty_comments_and_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# c\nEMPTY_KEY=\nNEW_KEY="abc"\nEXISTING_KEY=file\n', encoding="utf-8")
    monkeypatch.delenv("NEW_KEY", raising=False)
    monkeypatch.delenv("EMPTY_KEY", raising=False)
    monkeypatch.setenv("EXISTING_KEY", "shell")
    assert load_dotenv(env) == ["NEW_KEY"]
    import os

    assert os.environ["NEW_KEY"] == "abc" and os.environ["EXISTING_KEY"] == "shell"
    assert "EMPTY_KEY" not in os.environ
