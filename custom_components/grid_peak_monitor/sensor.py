"""Public sensors: no computation or large history attributes in the frontend."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

DESCRIPTIONS = {
    "forecast_kw": "Prognose", "minimum_kw": "Minimum", "power_kw": "Netzbezug",
    "last_quarter_kw": "Letzte Viertelstunde", "month_peak_kw": "HA Monatsspitze",
    "allowed_power_kw": "Erlaubte Leistung Restzeit", "additional_power_kw": "Zusätzliche Leistung Restzeit",
    "quality": "Datenqualität", "status": "Zielstatus",
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PeakSensor(coordinator, key, name) for key, name in DESCRIPTIONS.items()])


class PeakSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)},
                                  "name": coordinator.entry.title, "manufacturer": "Daheim im Detail"}
        if key.endswith("_kw"):
            self._attr_native_unit_of_measurement = "kW"
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        attrs = {"grid_peak_monitor": True, "monitor_id": self.coordinator.entry.entry_id,
                 "metric": self.key}
        if self.key == "forecast_kw":
            attrs["snapshot"] = self.coordinator.data
        if self.key == "month_peak_kw":
            snapshot = self.coordinator.data or {}
            attrs.update(observed_quarters=snapshot.get("month_observed"),
                         expected_quarters=snapshot.get("month_expected"),
                         complete=snapshot.get("month_complete"),
                         peak_start=snapshot.get("month_peak_start"))
        return attrs
