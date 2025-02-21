from __future__ import annotations

import logging

from benqprojector import BenQProjector
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BenQProjectorCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BenQ Serial Projector number."""
    coordinator: BenQProjectorCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entities_config = [
        ["con", "Contrast", "mdi:contrast", 100],
        ["bri", "Brightness", "mdi:brightness-6", 100],
        ["color", "Color", "mdi:palette", 20],
        ["sharp", "Sharpness", None, 20],
        ["micvol", "Microphone Volume", "mdi:microphone", 20],
        ["keyst", "Keystone", None, 20]
    ]

    entities = []

    for entity_config in entities_config:
        if coordinator.supports_command(entity_config[0]):
            entities.append(
                BenQProjectorNumber(
                    coordinator,
                    entity_config[0],
                    entity_config[1],
                    entity_config[2],
                    entity_config[3],
                )
            )

    async_add_entities(entities)


class BenQProjectorNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_available = False
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_native_value = None

    def __init__(
        self,
        coordinator: BenQProjectorCoordinator,
        command: str,
        name: str,
        icon: str | None = None,
        max_value: int = 20,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, command)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{command}"

        self.command = command
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_max_value = max_value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (
            self.coordinator.data
            and (native_value := self.coordinator.data.get(self.command))
        ):
            try:
                self._attr_native_value = float(native_value)
                self._attr_available = True
                self.async_write_ha_state()
            except ValueError as ex:
                _LOGGER.error(
                    "ValueError for %s = %s, %s",
                    self.command,
                    self.coordinator.data.get(self.command),
                    ex,
                )
            except TypeError as ex:
                _LOGGER.error("TypeError for %s, %s", self.command, ex)
        else:
            _LOGGER.debug("%s is not available", self.command)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated = False

        if self.coordinator.power_status in [
            BenQProjector.POWERSTATUS_POWERINGON,
            BenQProjector.POWERSTATUS_ON,
        ]:
            if (
                self.coordinator.data
                and (new_value := self.coordinator.data.get(self.command))
            ):
                try:
                    new_value = float(new_value)
                    if self._attr_native_value != new_value:
                        self._attr_native_value = new_value
                        updated = True

                    if self._attr_available is not True:
                        self._attr_available = True
                        updated = True
                except ValueError as ex:
                    _LOGGER.error(
                        "ValueError for %s = %s, %s",
                        self.command,
                        self.coordinator.data.get(self.command),
                        ex,
                    )
                    if self._attr_available is not False:
                        self._attr_available = False
                        updated = True
                except TypeError as ex:
                    _LOGGER.error("TypeError for %s, %s", self.command, ex)
                    if self._attr_available is not False:
                        self._attr_available = False
                        updated = True
            elif self._attr_available is not False:
                self._attr_available = False
                updated = True
        elif self._attr_available is not False:
            _LOGGER.debug("%s is not available", self.command)
            self._attr_available = False
            updated = True

        # Only update the HA state if state has updated.
        if updated:
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.debug("async_set_native_value")
        if self.coordinator.power_status == BenQProjector.POWERSTATUS_ON:
            if self._attr_native_value == value:
                return

            while self._attr_native_value < value:
                if self.coordinator.send_command(self.command, "+") == "+":
                    self._attr_native_value += self._attr_native_step
                else:
                    break

            while self._attr_native_value > value:
                if self.coordinator.send_command(self.command, "-") == "-":
                    self._attr_native_value -= self._attr_native_step
                else:
                    break

            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        else:
            self._attr_available = False

        self.async_write_ha_state()
