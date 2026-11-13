"""HA adapter around the independently testable accounting core."""
from datetime import timedelta
import logging
from uuid import uuid4

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_state_change_event, async_track_state_report_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ENERGY, MAX_AGE, RESOLUTION, POWER, SIGN, TARGET
from .core import Monitor, Sample, finite

_LOGGER = logging.getLogger(__name__)


def sample(state, *, energy=False):
    if state is None:
        return Sample(None, 0)
    value = finite(state.state)
    unit = state.attributes.get("unit_of_measurement")
    scales = {"kWh": 1, "Wh": .001, "MWh": 1000} if energy else {"kW": 1, "W": .001}
    if unit not in scales:
        value = None
    remote_stamp = state.attributes.get("grid_peak_source_reported_at")
    if remote_stamp is not None:
        # A mirrored source keeps its original report time. Repeated polling must
        # never make a disconnected or cached source appear fresh.
        stamp = dt_util.parse_datetime(str(remote_stamp))
        if stamp is None or stamp.tzinfo is None:
            return Sample(None, 0)
    else:
        stamp = getattr(state, "last_reported", None) or state.last_updated
    return Sample(value * scales[unit] if value is not None else None, stamp.timestamp())


class PeakCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=10))
        self.entry = entry
        self.options = {**entry.data, **entry.options}
        self.monitor = Monitor(target=self.options.get(TARGET, 8), sign=self.options.get(SIGN, 1),
                               max_age=self.options.get(MAX_AGE, 120), zone=hass.config.time_zone,
                               energy_resolution=self.options.get(RESOLUTION, 0))
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._unsubs = []
        self._save_scheduled = False

    async def initialize(self):
        data = await self.store.async_load()
        signature = [self.options[POWER], self.options[ENERGY]]
        if data and data.get("sources") == signature:
            self.monitor.restore(data.get("engine"), dt_util.utcnow().timestamp())
        elif data:
            # Never combine different counters or overwrite their only archive.
            key = f"{DOMAIN}.{self.entry.entry_id}.source_backup.{uuid4().hex}"
            await Store(self.hass, 1, key).async_save(data)
            # Store logs write failures instead of raising. Verify the saved
            # backup before computing/scheduling a replacement active archive.
            if await Store(self.hass, 1, key).async_load() != data:
                raise ConfigEntryNotReady("Previous source archive could not be backed up")
        self.data = self._compute()
        ids = [self.options[POWER], self.options[ENERGY]]
        self._unsubs = [async_track_state_change_event(self.hass, ids, self._changed),
                        async_track_state_report_event(self.hass, ids, self._changed)]

    def _dump(self):
        return {"sources": [self.options[POWER], self.options[ENERGY]], "engine": self.monitor.dump()}

    @callback
    def _save_snapshot(self):
        self._save_scheduled = False
        return self._dump()

    def _compute(self):
        output = self.monitor.update(dt_util.utcnow().timestamp(),
            sample(self.hass.states.get(self.options[POWER])),
            sample(self.hass.states.get(self.options[ENERGY]), energy=True))
        # Frequent source reports must not postpone persistence indefinitely.
        if not self._save_scheduled:
            self._save_scheduled = True
            self.store.async_delay_save(self._save_snapshot, 15)
        return output

    @callback
    def _changed(self, event):
        self.async_set_updated_data(self._compute())

    async def _async_update_data(self):
        return self._compute()

    async def shutdown(self):
        for unsubscribe in self._unsubs:
            unsubscribe()
        self._unsubs.clear()
        await self.store.async_save(self._dump())

    async def set_target(self, value):
        if finite(value) is None or not 0 < value <= 1000:
            raise ValueError("invalid target")
        self.monitor.target = float(value)
        self.monitor.warning_since, self.monitor.warning_active = None, False
        # The number's value survives restart without reloading the integration.
        options = dict(self.entry.options)
        options[TARGET] = float(value)
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_set_updated_data(self._compute())
