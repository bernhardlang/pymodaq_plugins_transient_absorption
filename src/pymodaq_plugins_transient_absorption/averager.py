import numpy as np

class Averager:

    SUCCESS  = 0
    CONTINUE = 1
    FAIL     = 2

    def __init__(self, start, end, stride, offset, min_samples=None,
                 limit_diff_rms=None, limit_diff_mean=None, max_attempts=None,
                 dark=None):
        self.start = start
        self.end = end
        self.n_pix = end - start
        self.stride = stride
        self.offset = offset
        self.min_samples = min_samples
        self.limit_diff_rms = limit_diff_rms
        self.limit_diff_mean = limit_diff_mean
        self.max_attempts = max_attempts
        self.dark = dark
        self.sum_values = np.zeros(self.n_pix)
        self.sum_squared_values = np.zeros(self.n_pix)
        self.changed = False
        self.samples = 0
        self._prev_mean = None
        self._prev_rms = None
        self.attempts = 0

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
    
        if self.min_samples is None or self.samples < self.min_samples
            return self.CONTINUE

        if self._prev_mean is not None:
            diff_rms1 = \
                sum(abs(self._rms - self._prev_rms) / self._rms) / self.n_pix
            diff_rms2 = \
                sum(abs(self._rms - self._prev_rms) / self._prev_rms) \
                / self.n_pix
            diff_mean = \
                sum(abs(self._mean - self._prev_mean) / self._rms) \
                / self.n_pix
            if diff_rms1 < self.limit_diff_rms \
               and diff_rms2 < self.limit_diff_rms \
               and diff_mean < self.limit_diff_mean:
                return self.SUCCESS

        self.attempts += 1
        if self.attempts >= self.max_attempts:
            return self.FAIL

        self._prev_mean, self._prev_rms = self._mean, self._rms
        return self.CONTINUE


class AveragerFactory:

    @classmethod
    def make(cls, condition, n_offset, stride, dark_averager):
        return Averager(condition.start, condition.end, stride, n_pix,
                        condition.min_samples, condition.limit_diff_rms,
                        condition.limit_diff_mean, condition.max_attempts
                        dark=dark_averager.mean)
        
