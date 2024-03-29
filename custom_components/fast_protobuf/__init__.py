"""The fast_protobuf integration."""
from __future__ import annotations

import asyncio
import contextlib
import awesomeversion
import logging
import subprocess
import sys

import google.protobuf
from google.protobuf.internal import api_implementation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_start
from homeassistant.components import persistent_notification

PROTOBUF_VERSION = google.protobuf.__version__
PROTOBUF_MIN_VERSION = "4.22.1"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast protobuf from a config entry."""

    current_type = api_implementation.Type()

    if current_type in ("upb", "cpp"):
        _LOGGER.warning(
            "Already using %s %s implementation of protobuf, enjoy :)",
            PROTOBUF_VERSION,
            current_type,
        )
        return True

    version_to_build = PROTOBUF_VERSION

    if awesomeversion.AwesomeVersion(PROTOBUF_VERSION) < awesomeversion.AwesomeVersion(
        PROTOBUF_MIN_VERSION
    ):
        version_to_build = PROTOBUF_MIN_VERSION

    persistent_notification.async_create(
        hass,
        f"Building protobuf upb {version_to_build} in the background to replace {current_type} {PROTOBUF_VERSION}, this will be cpu intensive",
        "Protobuf is rebuilding the in background",
        "fast_protobuf",
    )
    _LOGGER.warning(
        "Building protobuf upb %s in the background to replace %s %s, this will be cpu intensive",
        version_to_build,
        current_type,
        PROTOBUF_VERSION,
    )

    @callback
    def _async_reinstall_protobuf(_hass: HomeAssistant) -> None:
        # Create an untracked task to build the wheel in the background
        # so we don't block shutdown if its not done by the time we exit
        # since they can just try again next time.
        future = hass.loop.run_in_executor(
            None, reinstall_protobuf, hass, version_to_build
        )
        asyncio.ensure_future(future)

    entry.async_on_unload(async_at_start(hass, _async_reinstall_protobuf))
    return True


def reinstall_protobuf(hass: HomeAssistant, version: str) -> str:
    """Build a wheel for the current platform."""
    python_bin = sys.executable
    _LOGGER.info("Building protobuf wheel for %s", version)
    with contextlib.suppress(subprocess.CalledProcessError):
        run_command(
            "apk add "
            "autoconf automake libtool m4 gcc musl-dev "
            "openssl-dev libffi-dev zlib-dev jpeg-dev make git cmake"
        )
    try:
        run_command(
            f"{python_bin} -m pip install 'protobuf=={version}' --upgrade --no-dependencies --force-reinstall --no-binary protobuf"
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.warning(
            "Building the new wheel failed with error: %s", err, exc_info=True
        )
        persistent_notification.create(
            hass,
            f"Error: {err}, check the logs for more information",
            "Protobuf failed to build: {err.stderr}, {err.stdout}",
            "fast_protobuf",
        )
        return

    _LOGGER.warning("Restart Home Assistant to use the new wheel")
    persistent_notification.create(
        hass,
        "Restart Home Assistant to use the new wheel",
        "Protobuf is finished building",
        "fast_protobuf",
    )


def run_command(
    cmd: str, env: dict[str, str] | None = None, timeout: int | None = None
) -> None:
    """Implement subprocess.run but handle timeout different."""
    try:
        subprocess.run(
            cmd,
            shell=True,  # nosec
            check=True,
            env=env,
            timeout=timeout,
            close_fds=False,
            capture_output=True,
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.error(
            "Error running command: %s: %s - stderr:%s, stdout:%s",
            cmd,
            err,
            err.stderr,
            err.stdout,
        )
        raise
