"""Local quarter-hour accounting. Standard library only; no device control."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

QUARTER = 900
RETENTION_DAYS = 93
COUNTER_GUARD_VERSION = 2
ACCOUNTING_VERSION = 2
UTC = timezone.utc


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def quarter(at):
    return int(at // QUARTER) * QUARTER


def instant(day, zone):
    return datetime.combine(day, datetime.min.time(), ZoneInfo(zone)).timestamp()


def day_slots(day, zone):
    return list(range(int(instant(day, zone)), int(instant(day + timedelta(days=1), zone)), QUARTER))


@dataclass(frozen=True)
class Sample:
    value: float | None
    at: float


class Monitor:
    """Build each fixed UTC quarter separately from bounded energy anchors.

    Interpolation needs a report on each side, at most max_age seconds apart.
    Startup partials, resets, unavailable states and long gaps stay incomplete.
    A forecast never drops below energy already imported in its own window.
    """

    def __init__(self, *, target=8.0, sign=1, max_age=120, zone="Europe/Vienna", energy_resolution=0):
        if finite(target) is None or not 0 < target <= 1000:
            raise ValueError("invalid target")
        if type(sign) is not int or sign not in (-1, 1):
            raise ValueError("invalid import sign")
        if not 30 <= max_age <= 900:
            raise ValueError("invalid maximum age")
        if finite(energy_resolution) is None or not 0 <= energy_resolution <= 1:
            raise ValueError("invalid energy resolution")
        ZoneInfo(zone)
        self.target, self.sign, self.max_age, self.zone = float(target), sign, max_age, zone
        self.last_energy = None
        self.cursor = None
        self.anchors = {}
        self.bad = {}
        self.records = {}
        self.zero_since = None
        self.last_tick = None
        self.energy_resolution = float(energy_resolution)
        self.proof_since = self.proof_report = self.counter_seen = None
        self.import_since = None
        self.sustained_import = False
        self.counter_value = None
        self.expected_import = 0.0
        self.change_due_since = None
        self.pulse_due_since = None
        self.counter_stalled = False
        self.anchor_methods = {}
        self.warning_since = None
        self.warning_active = False
        self.warning_window = None

    def _mark(self, start, end, reason):
        first = max(quarter(start), self.cursor if self.cursor is not None else quarter(end))
        for at in range(first, quarter(max(start, end - .001)) + QUARTER, QUARTER):
            if self.cursor is None or at >= self.cursor:
                self.bad.setdefault(at, reason)

    def _observe_counter(self, now, imported, energy, reported_at):
        """Detect a frozen counter from sustained, repeatedly reported import.

        Short battery corrections must not accumulate into an hours-long fault
        proof. An export/zero report ends an unconfirmed import episode. Distinct
        power reports bound its energy with the smaller adjacent import value;
        cached polls add no evidence. Confirmation needs both a max_age-long
        import episode and two meter steps overdue by max_age. A large confirmed
        pulse (>4 steps) independently requires progress, even after export.
        A confirmed fault remains latched until the counter actually advances.
        """
        if not self.energy_resolution:
            return False, False
        value = finite(energy.value)
        usable = (imported is not None and value is not None and value >= 0
                  and -5 <= now - energy.at
                  and (self.last_energy is None or energy.at >= self.last_energy.at)
                  and (self.proof_report is None or reported_at >= self.proof_report.at))
        continuous = (usable and self.proof_since is not None and self.last_tick is not None
                      and 0 <= now - self.last_tick <= self.max_age
                      and self.proof_report is not None
                      and reported_at - self.proof_report.at <= self.max_age)
        covered_change = continuous and self.counter_seen is not None and self.proof_since <= self.counter_seen
        if not continuous:
            if self.proof_since is not None and self.last_tick is not None:
                pending = [t for t in (self.change_due_since, self.pulse_due_since, self.last_tick) if t is not None]
                self._mark(min(pending), now, "power_stale" if imported is None else "energy_gap")
            self.proof_since = now if usable else None
            self.expected_import = 0.0
            self.change_due_since = None
            self.pulse_due_since = None
            self.counter_seen = now if usable else None
            self.import_since = now if usable and imported > 0 else None
        prior = self.counter_value if self.counter_value is not None else (self.last_energy.value if self.last_energy else None)
        counter_changed = usable and prior is not None and value != prior
        if counter_changed:
            if covered_change and value - prior > 1000 * max(now - self.counter_seen, .001) / 3600 + 2 * self.energy_resolution:
                self._mark(now, now, "energy_jump")
            if value > prior:
                self.counter_stalled = False
            self.expected_import = 0.0
            self.change_due_since = None
            self.pulse_due_since = None
            self.counter_seen = now
            self.import_since = now if imported > 0 else None
        if usable:
            if imported == 0:
                self.import_since = None
                self.expected_import = 0.0
                self.change_due_since = None
            elif self.import_since is None:
                self.import_since = now
            elif continuous and not counter_changed and reported_at > self.proof_report.at:
                left = max(self.proof_report.at, self.proof_since, self.counter_seen, self.import_since)
                seconds = max(0, min(reported_at, now) - left)
                self.expected_import += min(self.proof_report.value, imported) * seconds / 3600
        self.counter_value = value if usable else None
        self.proof_report = Sample(imported, reported_at) if usable else None
        self.sustained_import = (usable and self.import_since is not None
                                 and min(reported_at, now) - self.import_since >= self.max_age)
        within_budget = self.expected_import <= 2 * self.energy_resolution + 1e-9
        # A large pulse confirmed by multiple reports must not disappear just
        # because power later returns to zero. Use twice the sustained-import
        # margin for this shorter evidence; smaller corrections never add up.
        if usable and self.expected_import > 4 * self.energy_resolution + 1e-9 and self.pulse_due_since is None:
            self.pulse_due_since = now
        if usable and not within_budget:
            if self.change_due_since is None:
                self.change_due_since = now
            if self.sustained_import and now - self.change_due_since >= self.max_age:
                self.counter_stalled = True
                self._mark(self.change_due_since, now, "counter_stalled")
        if usable and self.pulse_due_since is not None and now - self.pulse_due_since >= self.max_age:
            self.counter_stalled = True
            self._mark(self.pulse_due_since, now, "counter_stalled")
        if self.counter_stalled:
            self._mark(now, now, "counter_stalled")
        return (usable and (within_budget or not self.sustained_import) and self.pulse_due_since is None
                and not self.counter_stalled), covered_change

    def _ingest_energy(self, now, sample, covered_change=False):
        value = finite(sample.value)
        if value is None or value < 0 or sample.at > now + 5:
            self._mark(now, now, "energy_invalid")
            return
        if self.cursor is None:
            self.cursor = quarter(now)
        previous = self.last_energy
        if previous and sample.at < previous.at:
            return  # Delayed older events never replace the newer baseline.
        if previous and sample.at == previous.at:
            if value != previous.value:
                self._mark(sample.at, now, "conflicting_report")
            return
        if previous:
            delta, span = value - previous.value, sample.at - previous.at
            if delta < -1e-7:
                self._mark(previous.at, sample.at, "counter_reset")
            elif span > self.max_age:
                # A continuously observed zero-import run can certify a zero delta.
                certified_zero = (delta <= 1e-7 and self.zero_since is not None
                                  and self.zero_since <= previous.at + self.max_age)
                if self.energy_resolution and covered_change:
                    # Boundaries were observed locally. A long source report
                    # interval must not be interpolated backwards over startup.
                    pass
                elif not certified_zero:
                    self._mark(previous.at, sample.at, "energy_gap")
                else:
                    for boundary in range(quarter(previous.at) + QUARTER,
                                          quarter(sample.at) + QUARTER, QUARTER):
                        self.anchors[boundary] = value
            elif delta * 3600 / max(span, .001) > 1000:
                self._mark(previous.at, sample.at, "energy_jump")
            else:
                for boundary in range(quarter(previous.at) + QUARTER,
                                      quarter(sample.at) + QUARTER, QUARTER):
                    # Both adjacent quarters must use the same boundary. A
                    # quantized anchor may already have closed the prior one;
                    # refining only the next baseline would discard energy.
                    if boundary in self.anchor_methods:
                        continue
                    fraction = (boundary - previous.at) / span
                    self.anchors[boundary] = previous.value + delta * fraction
                    self.anchor_methods.pop(boundary, None)
        if sample.at % QUARTER < .001:
            boundary = quarter(sample.at)
            if boundary not in self.anchor_methods:
                self.anchors[boundary] = value
        self.last_energy = Sample(value, sample.at)

    def _close(self, now):
        while self.cursor is not None and self.cursor + QUARTER <= now:
            start, end = self.cursor, self.cursor + QUARTER
            pending = [t for t in (self.change_due_since, self.pulse_due_since) if t is not None]
            if (self.energy_resolution and pending and not self.counter_stalled
                    and min(pending) < end and now < min(pending) + self.max_age):
                break  # Do not finalize a window while a counter fault is still being checked.
            if end not in self.anchors and now - end < self.max_age:
                break
            before, after = self.anchors.get(start), self.anchors.get(end)
            reason = self.bad.get(start)
            if reason is None and (before is None or after is None):
                reason = "missing_boundary"
            kwh = after - before if before is not None and after is not None else None
            if kwh is not None and kwh < -1e-7:
                reason = "counter_reset"
            self.records[start] = {"start": start, "end": end, "kw": None if reason else max(0, kwh) * 4,
                                   "quality": reason or "valid", "source": "HA",
                                   "method": "quantized_counter" if start in self.anchor_methods or end in self.anchor_methods else "counter_interpolation"}
            self.cursor = end
        cutoff = now - RETENTION_DAYS * 86400
        self.records = {k: v for k, v in self.records.items() if k >= cutoff}
        anchor_cutoff = (self.cursor or quarter(now)) - QUARTER
        self.anchors = {k: v for k, v in self.anchors.items() if k >= anchor_cutoff}
        self.anchor_methods = {k: v for k, v in self.anchor_methods.items() if k in self.anchors}
        self.bad = {k: v for k, v in self.bad.items() if k >= (self.cursor or quarter(now))}

    def update(self, now, power, energy):
        if not math.isfinite(now):
            raise ValueError("invalid clock")
        p = finite(power.value)
        power_ok = p is not None and -5 <= now - power.at <= self.max_age
        imported = max(0, self.sign * p) if power_ok else None
        quantized_ok, covered_change = self._observe_counter(now, imported, energy, power.at)
        start = quarter(now)
        if (quantized_ok and self.proof_since <= start and start not in self.anchors):
            self.anchors[start] = float(energy.value)
            self.anchor_methods[start] = "quantized_counter"
        # A missing observation breaks proof of continuous zero power.
        if (self.last_tick is not None and now - self.last_tick > self.max_age) or not power_ok or imported > .001:
            self.zero_since = None
        elif self.zero_since is None:
            self.zero_since = now
        self.last_tick = now
        self._ingest_energy(now, energy, covered_change)
        self._close(now)
        start = quarter(now)
        baseline = self.anchors.get(start)
        fresh_energy = (finite(energy.value) is not None and energy.value >= 0
                        and -5 <= now - energy.at <= self.max_age)
        zero_proof = (self.last_energy is not None and self.zero_since is not None
                      and self.zero_since <= self.last_energy.at + self.max_age
                      and imported == 0 and finite(energy.value) == self.last_energy.value)
        if baseline is None and zero_proof and self.zero_since <= start:
            baseline = self.last_energy.value
            self.anchors[start] = baseline
        issue = self.bad.get(start)
        if not power_ok:
            issue = "power_stale"
        elif self.energy_resolution and self.counter_stalled:
            issue = "counter_stalled"
        elif (self.energy_resolution and not fresh_energy and (self.pulse_due_since is not None
                or self.sustained_import and self.change_due_since is not None)):
            issue = "waiting_report"
        elif not (fresh_energy or zero_proof or quantized_ok and self.proof_since <= start):
            issue = issue or ("waiting_boundary" if quantized_ok else "energy_stale")
        elif baseline is None:
            issue = "waiting_boundary"
        elif self.last_energy is None or self.last_energy.at < start and not (zero_proof or quantized_ok and self.proof_since <= start):
            issue = "waiting_report"
        used = max(0, self.last_energy.value - baseline) if baseline is not None and self.last_energy else None
        remaining = max(0, start + QUARTER - now)
        minimum = used * 4 if issue is None else None
        forecast = (used + imported * remaining / 3600) * 4 if issue is None else None
        allowed = max(0, (self.target / 4 - used) * 3600 / remaining) if issue is None and remaining > 0 else None
        status = self._warning(now, forecast, minimum)
        last = self.records.get(start - QUARTER)
        month = datetime.fromtimestamp(now, ZoneInfo(self.zone)).date().replace(day=1)
        month_start = instant(month, self.zone)
        observed = [r for r in self.records.values() if r["quality"] == "valid" and month_start <= r["start"] < start]
        peak = max(observed, key=lambda r: (r["kw"], -r["start"]), default=None)
        expected = int((start - month_start) / QUARTER)
        return {"start": start, "end": start + QUARTER, "remaining_seconds": int(remaining),
                "power_kw": imported, "used_kwh": used if issue is None else None,
                "minimum_kw": minimum, "forecast_kw": forecast, "target_kw": self.target,
                "allowed_power_kw": allowed,
                "additional_power_kw": allowed - imported if allowed is not None else None,
                "headroom_kw": self.target - forecast if forecast is not None else None,
                "quality": issue or "valid", "status": status,
                "energy_freshness": "quantized_idle" if issue is None and not fresh_energy else "reported" if fresh_energy else "unconfirmed",
                "energy_resolution_kwh": self.energy_resolution,
                "counter_guard_version": COUNTER_GUARD_VERSION,
                "last_quarter_kw": last["kw"] if last and last["quality"] == "valid" else None,
                "month_peak_kw": peak["kw"] if peak else None,
                "month_peak_start": peak["start"] if peak else None,
                "month_observed": len(observed), "month_expected": expected,
                "month_complete": len(observed) == expected and expected > 0}

    def _warning(self, now, forecast, minimum):
        window = quarter(now)
        if self.warning_window != window:
            self.warning_window = window
            self.warning_since, self.warning_active = None, False
        if forecast is None:
            self.warning_since, self.warning_active = None, False
            return "no_data"
        if minimum > self.target + 1e-7:
            return "exceeded"
        if minimum >= self.target - 1e-7:
            return "reached"
        if forecast > self.target:
            if self.warning_since is None:
                self.warning_since = now
            if now - self.warning_since >= 20:
                self.warning_active = True
        elif forecast <= self.target - .2:
            self.warning_since, self.warning_active = None, False
        if self.warning_active:
            return "risk"
        return "checking" if forecast > self.target else "near" if forecast >= .9 * self.target else "below"

    def history(self, day, month, now):
        selected, first = date.fromisoformat(day), date.fromisoformat(month + "-01")
        today = datetime.fromtimestamp(now, ZoneInfo(self.zone)).date()
        oldest = today - timedelta(days=RETENTION_DAYS - 1)
        if selected > today or selected < oldest or first > today or first < oldest.replace(day=1):
            raise ValueError("date outside retained history")
        slots = day_slots(selected, self.zone)
        rows = [self.records.get(t, {"start": t, "end": t + QUARTER, "kw": None,
                    "source": "HA", "quality": "pending" if t + QUARTER > now else "missing"}) for t in slots]
        following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        lo, hi = instant(first, self.zone), instant(following, self.zone)
        month_rows = [r for r in self.records.values() if lo <= r["start"] < hi and r["quality"] == "valid"]
        days = {}
        for row in month_rows:
            key = datetime.fromtimestamp(row["start"], ZoneInfo(self.zone)).date().isoformat()
            item = days.setdefault(key, {"date": key, "kw": 0, "observed": 0})
            item["kw"] = max(item["kw"], row["kw"])
            item["observed"] += 1
        for key, item in days.items():
            item["expected"] = len(day_slots(date.fromisoformat(key), self.zone))
        return {"date": day, "month": month, "zone": self.zone, "rows": rows,
                "observed": sum(r["quality"] == "valid" for r in rows), "expected": len(slots),
                "top": sorted(month_rows, key=lambda r: (-r["kw"], r["start"]))[:5],
                "daily": sorted(days.values(), key=lambda item: item["date"])}

    def dump(self):
        pending = [t for t in (self.change_due_since, self.pulse_due_since) if t is not None]
        return {"version": 1, "accounting_version": ACCOUNTING_VERSION,
                "cursor": self.cursor, "anchors": self.anchors, "bad": self.bad,
                "anchor_methods": self.anchor_methods, "counter_stalled": self.counter_stalled,
                "counter_guard_version": COUNTER_GUARD_VERSION,
                "counter_pending_since": min(pending) if pending else None,
                "records": list(self.records.values()),
                "last_energy": {"value": self.last_energy.value, "at": self.last_energy.at} if self.last_energy else None}

    def restore(self, data, now):
        """Restore only bounded, finite records; never restore a zero-power proof."""
        if not isinstance(data, dict) or data.get("version") != 1:
            return
        try:
            cursor = int(data["cursor"]) if data.get("cursor") is not None else None
            if cursor is not None and (cursor % QUARTER or not now - RETENTION_DAYS * 86400 <= cursor <= now):
                return
            self.cursor = cursor
            self.anchors = {int(k): float(v) for k, v in data.get("anchors", {}).items()
                            if int(k) % QUARTER == 0 and finite(v) is not None and v >= 0
                            and now - RETENTION_DAYS * 86400 <= int(k) <= now + QUARTER}
            self.anchor_methods = {int(k): "quantized_counter" for k in data.get("anchor_methods", {}) if int(k) in self.anchors}
            legacy_boundaries = self.energy_resolution and data.get("accounting_version", 1) < ACCOUNTING_VERSION
            if legacy_boundaries:
                # Preserve old observations, but never certify their inconsistent
                # quantized allocations or reuse a legacy live boundary.
                self.anchors.clear()
                self.anchor_methods.clear()
            # Old guards accumulated isolated peaks and could latch false alarms.
            # Rebuild their proof; never rewrite their historical incomplete rows.
            self.counter_stalled = (data.get("counter_stalled") is True
                                    and data.get("counter_guard_version") == COUNTER_GUARD_VERSION)
            self.bad = {int(k): str(v) for k, v in data.get("bad", {}).items()
                        if int(k) % QUARTER == 0 and now - RETENTION_DAYS * 86400 <= int(k) <= now}
            if legacy_boundaries:
                self._mark(now, now, "legacy_boundary")
            pending = finite(data.get("counter_pending_since"))
            if self.energy_resolution and pending is not None and now - RETENTION_DAYS * 86400 <= pending <= now:
                self._mark(pending, now, "energy_gap")
            self.records = {}
            for row in data.get("records", [])[-RETENTION_DAYS * 100:]:
                start = int(row["start"])
                if start % QUARTER or not now - RETENTION_DAYS * 86400 <= start < quarter(now):
                    continue
                value = finite(row.get("kw"))
                quality = "valid" if row.get("quality") == "valid" and value is not None and value >= 0 else "incomplete"
                if row.get("quality") == "legacy_boundary":
                    quality = "legacy_boundary"
                if legacy_boundaries and row.get("method") == "quantized_counter" and quality == "valid":
                    quality = "legacy_boundary"
                self.records[start] = {"start": start, "end": start + QUARTER,
                    "kw": value if quality == "valid" else None, "quality": quality, "source": "HA",
                    "method": "quantized_counter" if row.get("method") == "quantized_counter" else "counter_interpolation"}
            last = data.get("last_energy")
            if last and finite(last.get("value")) is not None and 0 <= last["value"] and finite(last.get("at")) is not None and last["at"] <= now:
                self.last_energy = Sample(float(last["value"]), float(last["at"]))
        except (TypeError, ValueError, KeyError, OverflowError):
            self.cursor, self.last_energy = None, None
            self.anchors, self.bad, self.records = {}, {}, {}
