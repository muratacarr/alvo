"""Source-level rules for the web app that tests of behaviour cannot see."""

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[4] / "apps" / "web"
PACKAGE = json.loads((WEB / "package.json").read_text(encoding="utf-8"))


def test_every_web_dependency_is_pinned_to_an_exact_version() -> None:
    for section in ("dependencies", "devDependencies"):
        for name, version in PACKAGE[section].items():
            assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{name}@{version}"


def test_ant_design_styles_sit_between_tailwind_base_and_utilities() -> None:
    # Without an explicit order, Tailwind's reset would override Ant Design's component styles.
    css = (WEB / "src" / "index.css").read_text(encoding="utf-8")
    order = re.search(r"@layer\s+theme,\s*base,\s*antd,\s*components,\s*utilities;", css)
    assert order, "layer order must be declared"
    assert css.index("@layer") < css.index('@import "tailwindcss"')


def test_the_app_registers_ant_design_styles_in_that_layer() -> None:
    providers = (WEB / "src" / "AntProviders.tsx").read_text(encoding="utf-8")
    assert re.search(r"<StyleProvider\s+layer>", providers)
    main = (WEB / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "<AntProviders>" in main  # wraps the whole application


def test_ant_design_is_imported_from_the_package_root_so_unused_parts_are_dropped() -> None:
    for path in (WEB / "src").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"from ['\"]antd/(es|lib)/", text), path.name


def test_no_third_party_hosts_are_referenced_by_the_html_shell() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://", html)
