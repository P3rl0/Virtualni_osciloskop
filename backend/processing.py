# tuki rabim nastavljat trigger, vrsto triggerja
import numpy as np
from backend.config import load_yaml, HYST_MULTIPLIER
from pathlib import Path


class TriggerProcessor:
    path = Path(__file__).parent

    def __init__(self):
        self.settings = load_yaml(self.path / "config.yaml", area="processing")
        self.run_stop = True  # always start in run

    def process_trigger(self, data, display_samples, sample_rate, active_indices, channel_ranges):
        if not self.run_stop:
            return None

        active_data = [np.array(data[i]) for i in active_indices]
        if not active_data:
            return None

        slope = self.settings["trigger_slope"]
        level = self.settings["trigger_level"]
        pre_trigger_samples = int(display_samples // 2 + self.settings["trigger_offset"] * sample_rate)
        post_trigger_samples = display_samples - pre_trigger_samples

        trigger_channel = self.settings["trigger_channel"]
        if trigger_channel in active_indices:
            channel_data = active_data[active_indices.index(trigger_channel)]
            hysteresis = channel_ranges[trigger_channel] * HYST_MULTIPLIER
        else:
            channel_data = active_data[0]
            hysteresis = channel_ranges[active_indices[0]] * HYST_MULTIPLIER

        search_start = pre_trigger_samples
        search_end = len(channel_data) - post_trigger_samples
        trigg_idx = None
        if search_end > search_start:
            for i in range(search_end, search_start - 1, -1):
                if slope == "rising":
                    if channel_data[i] >= level and channel_data[i - 1] < level - hysteresis:
                        trigg_idx = i
                        break
                else:
                    if channel_data[i] <= level and channel_data[i - 1] > level + hysteresis:
                        trigg_idx = i
                        break
        if trigg_idx is not None:
            if self.settings["trigger_type"] == "single":
                self.run_stop = False
            return np.array(
                [
                    active_data[i][trigg_idx - pre_trigger_samples : trigg_idx + post_trigger_samples]
                    for i in range(len(active_data))
                ]
            )
        elif self.settings["trigger_type"] == "auto":
            return np.array([active_data[i][-display_samples:] for i in range(len(active_data))])
        else:
            return None

    def set_trigger_type(self, trigger_type):
        self.settings["trigger_type"] = trigger_type

    def set_trigger_level(self, trigger_level):
        self.settings["trigger_level"] = trigger_level

    def set_trigger_slope(self, trigger_slope):
        self.settings["trigger_slope"] = trigger_slope

    def set_trigger_channel(self, trigger_channel):
        self.settings["trigger_channel"] = trigger_channel

    def set_trigger_offset(self, trigger_offset):
        self.settings["trigger_offset"] = trigger_offset

    def set_run_stop(self, run_stop: bool):
        self.run_stop = run_stop


class Measurements:
    path = Path(__file__).parent

    def __init__(self):
        self.settings = load_yaml(self.path / "config.yaml", area="processing")
        self.measurements = self.settings["measurements"]

    def compute(self, display_data, sample_rate, active_indices):
        """display_data shape (n_active, display_samples), parallel to active_indices.
        Returns dict keyed by (channel, measurement_name)."""
        results = {}
        for chan, entry in enumerate(self.measurements):
            if chan not in active_indices:
                continue
            row = active_indices.index(chan)
            data = display_data[row]
            for meas, enabled in entry.items():
                if not enabled:
                    continue
                method = getattr(self, meas, None)
                if method is None:
                    results[(chan, meas)] = None
                    continue
                if meas in ("frequency", "rise_time", "fall_time"):
                    results[(chan, meas)] = method(data, sample_rate)
                else:
                    results[(chan, meas)] = method(data)
        return results

    def set_measurement(self, channel, meas_type, enabled):
        if 0 <= channel < len(self.measurements):
            self.measurements[channel][meas_type] = enabled

    @staticmethod
    def mean(data):
        return float(np.mean(data))

    @staticmethod
    def rms(data):
        d = np.asarray(data, dtype=float)
        return float(np.sqrt(np.mean(d * d)))

    @staticmethod
    def min(data):
        return float(np.min(data))

    @staticmethod
    def max(data):
        return float(np.max(data))

    @staticmethod
    def peak_to_peak(data):
        return float(np.max(data) - np.min(data))

    @staticmethod
    def frequency(data, sample_rate):
        d = np.asarray(data, dtype=float)
        if len(d) < 2:
            return None
        pk_pk = float(np.max(d) - np.min(d))
        if pk_pk < 1e-9:
            return None
        midpoint = (float(np.max(d)) + float(np.min(d))) / 2
        hyst = pk_pk * 0.05
        upper = midpoint + hyst / 2
        lower = midpoint - hyst / 2
        # count BOTH rising and falling band-crossings — gap between consecutive crossings = half-period
        crossings = []
        state = None  # 'high' or 'low'
        for i in range(len(d)):
            if d[i] >= upper:
                if state == "low":
                    crossings.append(i)
                state = "high"
            elif d[i] <= lower:
                if state == "high":
                    crossings.append(i)
                state = "low"
        if len(crossings) < 2:
            return None
        avg_half_period = float(np.mean(np.diff(crossings)))
        if avg_half_period == 0:
            return None
        return float(sample_rate) / (2.0 * avg_half_period)

    @staticmethod
    def rise_time(data, sample_rate):
        d = np.asarray(data, dtype=float)
        pk_pk = float(np.max(d) - np.min(d))
        if pk_pk < 1e-9:
            return None
        d_min = float(np.min(d))
        low_thresh = d_min + pk_pk * 0.1
        high_thresh = d_min + pk_pk * 0.9
        # state machine: wait until below 10%, then find first 10% then 90% crossings
        seen_below = False
        idx_low = None
        for i in range(len(d)):
            v = d[i]
            if idx_low is None:
                if not seen_below:
                    if v < low_thresh:
                        seen_below = True
                    continue
                if v >= low_thresh:
                    idx_low = i
            elif v >= high_thresh:
                return (i - idx_low) / sample_rate
        return None

    @staticmethod
    def fall_time(data, sample_rate):
        d = np.asarray(data, dtype=float)
        pk_pk = float(np.max(d) - np.min(d))
        if pk_pk < 1e-9:
            return None
        d_max = float(np.max(d))
        high_thresh = d_max - pk_pk * 0.1
        low_thresh = d_max - pk_pk * 0.9
        # state machine: wait until above 90%, then find first 90% then 10% crossings
        seen_above = False
        idx_high = None
        for i in range(len(d)):
            v = d[i]
            if idx_high is None:
                if not seen_above:
                    if v > high_thresh:
                        seen_above = True
                    continue
                if v <= high_thresh:
                    idx_high = i
            elif v <= low_thresh:
                return (i - idx_high) / sample_rate
        return None
