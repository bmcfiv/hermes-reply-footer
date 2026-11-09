"""reply-footer: no-op by default; reminder, skip_sources and the reply check when configured."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("reply_footer_plugin", Path(__file__).resolve().parents[1] / "__init__.py")
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)

LONG = "x" * 500


class Ctx:
    def __init__(self, **settings):
        self.settings, self.hooks = settings, {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, fn):
        self.hooks[name] = fn


def hooks(**settings):
    ctx = Ctx(**settings)
    plugin.register(ctx)
    return ctx.hooks["pre_llm_call"], ctx.hooks["post_llm_call"]


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)
    return tmp_path


def log_lines(home):
    f = home / "logs" / plugin.LOG_NAME
    return f.read_text().splitlines() if f.exists() else []


def test_unconfigured_plugin_does_nothing(home):
    pre, post = hooks()
    assert pre(platform="cli") is None
    assert post(session_id="s", platform="cli", assistant_response=LONG) is None
    assert log_lines(home) == []


def test_reminder_is_injected_as_context():
    pre, _ = hooks(reminder="  End with a summary.  ")
    assert pre(platform="cli") == {"context": "End with a summary."}


@pytest.mark.parametrize("platform", ["cron", "Subagent", "batch", "webhook"])
def test_default_skip_sources(platform):
    pre, _ = hooks(reminder="r")
    assert pre(platform=platform) is None


def test_delegated_child_session_is_skipped_by_default():
    pre, _ = hooks(reminder="r")
    assert pre(platform="cli", parent_session_id="parent") is None


def test_skip_sources_is_configurable():
    pre, _ = hooks(reminder="r", skip_sources=["telegram"])
    assert pre(platform="telegram") is None
    assert pre(platform="cron") == {"context": "r"}
    pre, _ = hooks(reminder="r", skip_sources=[])
    assert pre(platform="cli", parent_session_id="parent") == {"context": "r"}


def test_check_logs_ok_and_miss_only_when_enabled(home):
    _, post = hooks(check_pattern=r"^\*\*Next\*\*", log=False)
    post(session_id="s", platform="cli", assistant_response=LONG)
    assert log_lines(home) == []
    _, post = hooks(check_pattern=r"^\*\*Next\*\*", log=True)
    post(session_id="s1", platform="cli", assistant_response=LONG)
    post(session_id="s2", platform="cli", assistant_response=LONG + "\n**Next** nothing")
    first, second = log_lines(home)
    assert " MISS " in first and "session=s1" in first and "platform=cli" in first
    assert " OK " in second and "session=s2" in second


def test_check_respects_min_chars_and_skip_sources(home):
    _, post = hooks(check_pattern="zzz", log=True, min_chars=600)
    post(session_id="s", platform="cli", assistant_response=LONG)
    post(session_id="s", platform="cron", assistant_response="y" * 700)
    assert log_lines(home) == []


def test_invalid_regex_fails_open(home):
    _, post = hooks(check_pattern="(", log=True)
    assert post(session_id="s", platform="cli", assistant_response=LONG) is None
    assert log_lines(home) == []


def test_hooks_fail_open(monkeypatch):
    class Boom(Ctx):
        def get_config(self, key, default=None):
            raise RuntimeError("config unavailable")

    ctx = Boom()
    plugin.register(ctx)
    assert ctx.hooks["pre_llm_call"](platform="cli") is None
    assert ctx.hooks["post_llm_call"](assistant_response=LONG) is None
