import numpy as np
from dataclasses import dataclass


@dataclass
class AveragerData:

    start: int
    end: int
    stride: int
    offset: int = 0
    min_samples: int = 0
    limit_diff_rms: float = 0
    limit_diff_mean: float = 0
    max_attempts: int = 0

    def __post_init__(self):
        self._init()


class Averager(AveragerData):

    SUCCESS  = 0
    CONTINUE = 1
    FAIL     = 2

    def _init(self):
        self.n_pix = self.end - self.start
        self.sum_values = np.zeros(self.n_pix)
        self.sum_squared_values = np.zeros(self.n_pix)
        self.changed = False
        self.samples = 0
        self.attempts = 0
        self._prev_mean = None
        self._prev_rms = None

    def clear(self):
        self.sum_values.fill(0)
        self.sum_squared_values.fill(0)
        self.samples = 0

    def reset(self):
        self.clear()
        self._prev_mean = None
        self._prev_rms = None
        self.attempts = 0

    @classmethod
    def average(cls, sum_values, sum_squared_values, samples):
        if samples < 2:
            raise RuntimeError("Averager: need at lest two samples")
        return sum_values / samples, \
            np.sqrt((samples * sum_squared_values - sum_values**2) \
                          / (samples * (samples - 1)))

    def _average(self):
        self._mean, self._rms = \
            self.average(self.sum_values, self.sum_squared_values, self.samples)
        self.changed = False

    @property
    def mean(self):
        if self.changed:
            self._average()
        return self._mean

    @property
    def rms(self):
        if self.changed:
            self._average()
        return self._rms

    def take_data(self, data):
        pos = self.offset
        while pos < len(data):
            selected_data = \
                data[pos + self.start:pos + self.end].astype(np.float64)
            self.sum_values += selected_data
            self.sum_squared_values += selected_data**2
            pos += self.stride
            self.samples += 1
        self.changed = True
    
        if self.min_samples == 0 or self.samples < self.min_samples:
            return self.CONTINUE

        if self._prev_mean is not None:
            diff_rms1 = \
                sum(abs(self.rms - self._prev_rms) / self.rms) / self.n_pix
            diff_rms2 = \
                sum(abs(self.rms - self._prev_rms) / self._prev_rms) \
                / self.n_pix
            diff_mean = \
                sum(abs(self.mean - self._prev_mean) / self.rms) \
                / self.n_pix
            if (self.limit_diff_rms > 0 and diff_rms1 > self.limit_diff_rms) \
               or (self.limit_diff_rms > 0 and diff_rms2 > self.limit_diff_rms) \
               or \
               (self.limit_diff_mean > 0 and diff_mean > self.limit_diff_mean):
                pass
            else:
                return self.SUCCESS

        self.attempts += 1
        if self.max_attempts > 0 and self.attempts >= self.max_attempts:
            return self.FAIL

        if self.changed:
            self._average()
        self._prev_mean, self._prev_rms = self._mean, self._rms
        self.clear()
        return self.CONTINUE


class AveragerFactory:

    @classmethod
    def make(cls, condition, n_stride, offset, dark_averager=None):
        return Averager(condition.start, condition.end, stride, offset,
                        condition.min_samples, condition.limit_diff_rms,
                        condition.limit_diff_mean, condition.max_attempts,
                        dark=dark_averager.mean)
        
