"""Check the installed package independently of the Core development checkout."""

import json
from pathlib import Path
import tomllib

from awesomeversion import AwesomeVersion
from homeassistant import config_entries, loader
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/virtual_ir_remote"


def test_distribution_metadata() -> None:
    """The HACS package is self-contained and ships its UI translations."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert project["version"] == manifest["version"]
    assert project["urls"]["Homepage"] == manifest["documentation"]
    assert project["urls"]["Issues"] == manifest["issue_tracker"]
    assert manifest["domain"] == "virtual_ir_remote"
    assert manifest["name"] == hacs["name"] == "Virtual IR Remote"
    assert AwesomeVersion(manifest["version"]).valid
    assert manifest["config_flow"] is True
    assert set(manifest["dependencies"]) == {"infrared", "mqtt"}
    assert (
        manifest["documentation"]
        == "https://github.com/DoomishFox/ha-virtual-ir-remote"
    )
    assert manifest["issue_tracker"] == manifest["documentation"] + "/issues"
    assert json.loads((INTEGRATION / "translations/en.json").read_text()) == json.loads(
        (INTEGRATION / "strings.json").read_text()
    )


async def test_custom_integration_loads(hass: HomeAssistant) -> None:
    """Home Assistant must load our custom component rather than a Core copy."""
    integration = await loader.async_get_integration(hass, "virtual_ir_remote")
    assert not integration.is_built_in
    assert integration.pkg_path == "custom_components.virtual_ir_remote"
    result = await hass.config_entries.flow.async_init(
        "virtual_ir_remote", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
