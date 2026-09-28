"""Tests for mflux-web YAML settings: precedence, parsing, and coercion.

Precedence contract: command line > YAML > built-in defaults.
"""

import argparse
from pathlib import Path

import pytest

from mflux.web.seed.cli import (
    USER_YAML_PATH,
    build_parser,
    coerce_value,
    find_yaml,
    load_yaml,
    merge_settings,
    resolve_api_key,
    strip_comment,
)

YAML_FULL = """\
host: 192.168.1.50
port: 8821
output_dir: ~/pictures/mflux
models_dir:
  - ~/AI/models
  - /opt/checkpoints
lora_dir:
  - ~/AI/loras
cache_size: 3
idle_unload: 0
max_upload_mb: 12
api_key: yaml-secret
api_key_file: ~/secrets/key.txt
require_auth: true
allowed_host:
  - mflux.tail1234.ts.net
tls_cert: ~/certs/mflux.pem
tls_key: ~/certs/mflux.key
behind_https: true
log_level: debug
"""


@pytest.fixture()
def yaml_file(tmp_path: Path) -> Path:
    path = tmp_path / "mflux-web.yaml"
    path.write_text(YAML_FULL)
    return path


def parse(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


class TestYamlParsing:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_yaml(tmp_path / "nope.yaml") == {}
        assert load_yaml(None) == {}

    def test_comment_and_blank_lines_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "c.yaml"
        path.write_text("# comment\n\nhost: 0.0.0.0  # trailing\n")
        assert load_yaml(path) == {"host": "0.0.0.0"}

    def test_list_requires_open_key(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- orphan\n")
        with pytest.raises(SystemExit):
            load_yaml(path)

    def test_all_keys_parsed(self, yaml_file: Path) -> None:
        values = load_yaml(yaml_file)
        assert values["host"] == "192.168.1.50"
        assert values["models_dir"] == ["~/AI/models", "/opt/checkpoints"]
        assert values["behind_https"] == "true"


class TestPrecedence:
    def test_yaml_fills_unset_cli_options(self, yaml_file: Path) -> None:
        args = merge_settings(parse([]), load_yaml(yaml_file))
        assert args.host == "192.168.1.50"
        assert args.port == 8821
        assert args.output_dir == Path.home() / "pictures" / "mflux"
        assert args.models_dir == [Path.home() / "AI" / "models", Path("/opt/checkpoints")]
        assert args.cache_size == 3
        assert args.idle_unload == 0
        assert args.max_upload_mb == 12
        assert args.api_key == "yaml-secret"
        assert args.require_auth is True
        assert args.allowed_host == ["mflux.tail1234.ts.net"]
        assert args.behind_https is True
        assert args.log_level == "debug"

    def test_cli_overrides_yaml(self, yaml_file: Path) -> None:
        args = merge_settings(parse(["--host", "127.0.0.1", "--port", "9000"]), load_yaml(yaml_file))
        assert args.host == "127.0.0.1"
        assert args.port == 9000
        # untouched YAML values still apply
        assert args.cache_size == 3

    def test_defaults_without_yaml(self) -> None:
        args = merge_settings(parse([]), {})
        assert args.host == "127.0.0.1"
        assert args.port == 8001
        assert args.cache_size == 1
        assert args.idle_unload == 10
        assert args.require_auth is False
        assert args.models_dir == []
        assert args.log_level == "info"

    def test_scalar_list_options(self, tmp_path: Path) -> None:
        # A single value (no bullet list) still lands as a one-element list.
        path = tmp_path / "scalar.yaml"
        path.write_text("models_dir: ~/AI/models\n")
        args = merge_settings(parse([]), load_yaml(path))
        assert args.models_dir == [Path.home() / "AI" / "models"]


class TestCoercion:
    @pytest.mark.parametrize(
        ("raw", "flags", "expected"),
        [
            ("true", {"is_bool": True}, True),
            ("no", {"is_bool": True}, False),
            ("42", {"is_int": True}, 42),
            ("1.5", {"is_float": True}, 1.5),
            ("~/x", {"is_path": True}, Path.home() / "x"),
            (["a", "b"], {"is_list": True}, ["a", "b"]),
            ("single", {"is_list": True}, ["single"]),
            (["~/a", "~/b"], {"is_list": True, "is_path": True}, [Path.home() / "a", Path.home() / "b"]),
        ],
    )
    def test_coerce(self, raw, flags, expected) -> None:
        assert coerce_value(raw, **flags) == expected


class TestCliFlags:
    def test_booleans_accept_explicit_no(self) -> None:
        # --require-auth/--no-require-auth and --behind-https/--no-behind-https
        assert parse(["--no-require-auth"]).require_auth is False
        assert parse(["--require-auth"]).require_auth is True
        assert parse(["--behind-https"]).behind_https is True
        assert parse(["--no-behind-https"]).behind_https is False


class TestComments:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("# whole line", ""),
            ("host: 0.0.0.0  # trailing", "host: 0.0.0.0  "),
            ("api_key: abcdefghijkl#mnop", "api_key: abcdefghijkl#mnop"),
            ("api_key: 'abc #def'", "api_key: 'abc #def'"),
            ("output_dir: ~/AI/#inbox", "output_dir: ~/AI/#inbox"),
        ],
    )
    def test_hash_starts_a_comment_only_after_whitespace(self, line: str, expected: str) -> None:
        assert strip_comment(line) == expected

    def test_key_with_hash_survives_loading(self, tmp_path: Path) -> None:
        path = tmp_path / "m.yaml"
        path.write_text("api_key: abcdefghijkl#mnop  # the key\n")
        assert load_yaml(path)["api_key"] == "abcdefghijkl#mnop"


class TestValidation:
    def test_unknown_key_is_rejected(self) -> None:
        with pytest.raises(SystemExit, match="require_auht"):
            merge_settings(parse([]), {"require_auht": "true"})

    def test_bad_log_level_is_rejected(self) -> None:
        with pytest.raises(SystemExit, match="log_level"):
            merge_settings(parse([]), {"log_level": "verbose"})

    def test_log_level_is_case_insensitive(self) -> None:
        assert merge_settings(parse([]), {"log_level": "DEBUG"}).log_level == "debug"


class TestApiKeyPrecedence:
    def resolve(self, argv: list[str], yaml_values: dict, environ: dict) -> str | None:
        cli = parse(argv)
        merged = merge_settings(argparse.Namespace(**vars(cli)), yaml_values)
        return resolve_api_key(cli, merged, environ)

    def test_cli_key_beats_yaml_key_file(self, tmp_path: Path) -> None:
        key_file = tmp_path / "key.txt"
        key_file.write_text("file-key-123456\n")
        assert self.resolve(["--api-key", "cli-key-123456"], {"api_key_file": str(key_file)}, {}) == "cli-key-123456"

    def test_cli_key_file_beats_environment(self, tmp_path: Path) -> None:
        key_file = tmp_path / "key.txt"
        key_file.write_text("file-key-123456\n")
        environ = {"MFLUX_WEB_API_KEY": "env-key-123456"}
        assert self.resolve(["--api-key-file", str(key_file)], {}, environ) == "file-key-123456"

    def test_environment_beats_yaml(self) -> None:
        environ = {"MFLUX_WEB_API_KEY": "env-key-123456"}
        assert self.resolve([], {"api_key": "yaml-key-123456"}, environ) == "env-key-123456"

    def test_yaml_key_file_is_used_last(self, tmp_path: Path) -> None:
        key_file = tmp_path / "key.txt"
        key_file.write_text("file-key-123456\n")
        assert self.resolve([], {"api_key_file": str(key_file)}, {}) == "file-key-123456"

    def test_key_and_key_file_at_one_level_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="not both"):
            self.resolve([], {"api_key": "yaml-key-123456", "api_key_file": str(tmp_path / "k")}, {})

    def test_unreadable_key_file_is_a_clean_error(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="cannot read"):
            self.resolve(["--api-key-file", str(tmp_path / "missing.txt")], {}, {})

    def test_no_key(self) -> None:
        assert self.resolve([], {}, {}) is None


class TestFindYaml:
    def test_cli_path_wins(self, tmp_path: Path) -> None:
        (tmp_path / "mflux-web.yaml").write_text("port: 1\n")
        chosen = tmp_path / "chosen.yaml"
        chosen.write_text("port: 2\n")
        assert find_yaml(chosen, {"MFLUX_WEB_YAML": str(tmp_path / "mflux-web.yaml")}, tmp_path) == chosen

    def test_environment_beats_working_directory(self, tmp_path: Path) -> None:
        (tmp_path / "mflux-web.yaml").write_text("port: 1\n")
        env_file = tmp_path / "env.yaml"
        env_file.write_text("port: 2\n")
        assert find_yaml(None, {"MFLUX_WEB_YAML": str(env_file)}, tmp_path) == env_file

    def test_working_directory_file_is_found(self, tmp_path: Path) -> None:
        local = tmp_path / "mflux-web.yaml"
        local.write_text("port: 1\n")
        assert find_yaml(None, {}, tmp_path) == local

    def test_user_config_is_the_fallback(self, tmp_path: Path) -> None:
        expected = USER_YAML_PATH if USER_YAML_PATH.is_file() else None
        assert find_yaml(None, {}, tmp_path) == expected

    @pytest.mark.parametrize("source", ["cli", "env"])
    def test_missing_explicit_file_is_an_error(self, tmp_path: Path, source: str) -> None:
        missing = tmp_path / "missing.yaml"
        cli_path, environ = (missing, {}) if source == "cli" else (None, {"MFLUX_WEB_YAML": str(missing)})
        with pytest.raises(SystemExit, match="not found"):
            find_yaml(cli_path, environ, tmp_path)
