# tuki rabim nastavljat trigger, vrsto triggerja
import numpy as np
from backend.config import load_yaml
from pathlib import Path

class triggerProcessor:
    path = Path(__file__).parent

    def __init__(self):
        self.settings = load_yaml(self.path / 'config.yaml', area='processing')
        self.run_stop = True    # always start in run

    def process_trigger(self, data, display_samples, sample_rate, active_channel_indices):
        if not self.run_stop:
            return None
        slope = self.settings['trigger_slope']
        level = self.settings['trigger_level']
        pre_trigger_samples = int(display_samples // 2 + self.settings['trigger_offset'] * sample_rate)
        post_trigger_samples = display_samples - pre_trigger_samples

        trigg_physical = self.settings['trigger_channel']
        if trigg_physical not in active_channel_indices:
            trigg_idx = None  # trigger channel not active
        else:
            active_trigger_idx = active_channel_indices.index(trigg_physical)

            channel_data = data[active_trigger_idx]

            search_start = pre_trigger_samples
            search_end = len(channel_data) - post_trigger_samples

            if search_end <= search_start:
                trigg_idx = None  # not enough data
            else:
                for i in range(search_end, search_start - 1, -1):
                    if slope == 'rising':
                        if channel_data[i] >= level and channel_data[i-1] < level:
                            trigg_idx = i
                            break
                    else:
                        if channel_data[i] <= level and channel_data[i-1] > level:
                            trigg_idx = i
                            break
                else:
                    trigg_idx = None
        if trigg_idx is not None:
            if self.settings['trigger_type'] == 'single':
                self.run_stop = False
            return np.array([data[i][trigg_idx - pre_trigger_samples : trigg_idx + post_trigger_samples] for i in range(len(active_channel_indices))])
        elif self.settings['trigger_type'] == 'auto':
            return np.array([data[i][-display_samples:] for i in range(len(active_channel_indices))])
        else:
            return None


    def set_trigger_type(self, trigger_type):
        self.settings['trigger_type'] = trigger_type

    def set_trigger_level(self, trigger_level):
        self.settings['trigger_level'] = trigger_level

    def set_trigger_slope(self, trigger_slope):
        self.settings['trigger_slope'] = trigger_slope
        pass

    def set_trigger_channel(self, trigger_channel):
        self.settings['trigger_channel'] = trigger_channel
        pass

    def set_trigger_offset(self, trigger_offset):
        self.settings['trigger_offset'] = trigger_offset
        pass

    def set_run_stop(self, run_stop: bool):
        self.run_stop = run_stop