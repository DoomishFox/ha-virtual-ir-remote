# Virtual IR Remote

Create Home Assistant Remote entities backed by MQTT infrared emitters. Each
MQTT blaster has one remote, with named commands grouped by virtual device
(for example, Fan or TV).

## Requirements

- Home Assistant Core 2026.10.0 or newer, with the Infrared building block.
  Development validation uses Core 2026.10.0.dev0; older releases are not supported.
- The MQTT integration and a discovered MQTT device with exactly one enabled
  infrared emitter entity.
- Known protocol parameters for the commands you want to send. NEC48 is currently
  supported; physical command capture/learning is not implemented.

## Install with HACS

Once this repository is published at
https://github.com/DoomishFox/ha-virtual-ir-remote:

1. In HACS, open **Custom repositories**.
2. Add that repository URL with type **Integration**.
3. Download **Virtual IR Remote** and restart Home Assistant.
4. In **Settings → Devices & services → Add integration**, select
   **Virtual IR Remote** and choose your MQTT IR blaster.

This is a HACS custom repository, not a listing in the default HACS catalog.
For manual installation, copy `custom_components/virtual_ir_remote` into your
Home Assistant configuration's `custom_components` directory, then restart.

## Configure commands

On the integration page, use **Add command** under the appropriate remote.
Enter a virtual device name, command name, protocol, address, and command bytes.
NEC48 uses a one-byte hexadecimal address and exactly two comma-separated
hexadecimal command bytes. For example: virtual device `Fan`, command `power`,
address `01`, command bytes `03, 03`.

Optionally assign a command to the **Turn on** and/or **Turn off** actions.
Commands are displayed as **virtual device — command**. Use **Add remote** to
link another MQTT blaster; a blaster cannot belong to two remotes.

## Home Assistant actions

Use your remote's actual entity ID:

```yaml
action: remote.send_command
target:
  entity_id: remote.bedroom_ir_sender
data:
  device: Fan
  command: power
```

For commands assigned to power actions:

```yaml
action: remote.turn_on
target:
  entity_id: remote.bedroom_ir_sender
data:
  activity: Fan
```

Use `remote.turn_off` for the assigned off command. The activity may be omitted
when only one virtual device has power assignments. A toggle command assigned
to both actions still toggles power: this integration cannot observe or guarantee
the appliance's actual state. The Remote's state is not the appliance's state.

Emitter entity renames and MQTT topic changes are handled by Home Assistant's
registries and MQTT integration. Virtual IR Remote does not publish MQTT
payloads or compress timings itself. An unavailable emitter makes its remote
unavailable.

## Development and distribution

### Tests

Tests live in the repository's top-level `tests/` directory, separate from the
runtime files HACS installs. They use
[`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
and exercise this repository's `custom_components.virtual_ir_remote` directly;
no Home Assistant Core source checkout or real MQTT broker is needed.

With Python 3.14, run from this repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements_test.txt
python3 -m pytest --cov --cov-report=term-missing
```

The pinned harness currently installs Home Assistant 2026.9.3. This is the
standalone regression-test baseline; the conservative HACS minimum remains
2026.10.0. Update the harness pin deliberately when adopting newer Core APIs.
Tests disable network sockets and mock MQTT discovery and command publishing.

Coverage includes NEC48 encoding, emitter selection, config and command flows,
entity renames and availability, power actions, error handling, lifecycle, and
package metadata/translations. GitHub Actions runs the same test command for
pushes and pull requests.

Developed with GPT-5.6 Sol and GPT-6 Astra because I was tired of navigating HA's abysmal documentation.

Licensed under Apache-2.0. See [LICENSE](LICENSE).
