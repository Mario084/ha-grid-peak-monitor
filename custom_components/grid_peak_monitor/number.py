"""User-adjustable target, persisted by the integration."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TargetNumber(hass.data[DOMAIN][entry.entry_id])])


class TargetNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Persönliches Ziel"
    _attr_native_min_value = .1
    _attr_native_max_value = 1000
    _attr_native_step = .1
    _attr_native_unit_of_measurement = "kW"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_target"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)}}

    @property
    def native_value(self):
        return self.coordinator.monitor.target

    @property
    def extra_state_attributes(self):
        return {"grid_peak_target": True, "monitor_id": self.coordinator.entry.entry_id,
                "metric": "target_kw"}

    async def async_set_native_value(self, value):
        await self.coordinator.set_target(value)
