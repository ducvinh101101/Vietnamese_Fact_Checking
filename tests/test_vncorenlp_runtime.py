"""Protect app mode changes and relative output paths from VnCoreNLP side effects."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import src.phobert_fact_checker as runtime


@pytest.fixture(autouse=True)
def isolated_segmenter_cache(monkeypatch):
    monkeypatch.setattr(runtime, "_SEGMENTERS", {})


def test_segmenter_constructor_does_not_change_process_working_directory(tmp_path):
    before = Path.cwd()
    marker = object()

    def changing_factory(**kwargs):
        os.chdir(kwargs["save_dir"])
        return marker

    assert runtime.load_segmenter_once(tmp_path, changing_factory) is marker
    assert Path.cwd() == before


def test_second_verifier_reuses_segmenter_instead_of_reconfiguring_running_jvm(tmp_path):
    marker = object()
    assert runtime.load_segmenter_once(tmp_path, lambda **kwargs: marker) is marker

    def cannot_restart_jvm(**kwargs):
        raise ValueError("VM is already running, can't set classpath/options")

    assert runtime.load_segmenter_once(tmp_path, cannot_restart_jvm) is marker


def test_failed_initialization_restores_directory_and_allows_retry(tmp_path):
    before = Path.cwd()

    def failing_factory(**kwargs):
        os.chdir(kwargs["save_dir"])
        raise RuntimeError("test initialization error")

    with pytest.raises(RuntimeError, match="test initialization"):
        runtime.load_segmenter_once(tmp_path, failing_factory)
    assert Path.cwd() == before
    marker = object()
    assert runtime.load_segmenter_once(tmp_path, lambda **kwargs: marker) is marker


def test_concurrent_initialization_only_starts_one_segmenter(tmp_path):
    calls, marker = [], object()

    def factory(**kwargs):
        calls.append(kwargs)
        return marker

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: runtime.load_segmenter_once(tmp_path, factory), range(12)))
    assert all(result is marker for result in results)
    assert len(calls) == 1


def test_different_model_directory_requires_explicit_restart(tmp_path):
    runtime.load_segmenter_once(tmp_path, lambda **kwargs: object())
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(RuntimeError, match="khởi động lại"):
        runtime.load_segmenter_once(other, lambda **kwargs: object())
