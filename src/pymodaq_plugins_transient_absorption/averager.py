import numpy as np

class Averager:

    SUCCESS  = 0
    CONTINUE = 1
    FAIL     = 2

    def __init__(self, start, end, stride, offset, min_samples=None,
                 limit_diff_rms=None, limit_diff_mean=None, max_attempts=None):
        self.start = start
        self.end = end
        self.n_pix = end - start
        self.stride = stride
        self.offset = offset
        self.min_samples = min_samples
        self.limit_diff_rms = limit_diff_rms
        self.limit_diff_mean = limit_diff_mean
        self.max_attempts = max_attempts
        self.sum_values = np.zeros(self.n_pix)
        self.sum_squared_values = np.zeros(self.n_pix)
        self.samples = 0
        self.prev_mean = None
        self.prev_rms = None
        self.attempts = 0

    def clear(self):
        self.sum_values.fill(0)
        self.sum_squared_values.fill(0)
        self.samples = 0

    def reset(self):
        self.clear()
        self.prev_mean = None
        self.prev_rms = None
        self.attempts = 0

    @classmethod
    def average(cls, sum_values, sum_squared_values, samples):
        return sum_values / samples, \
            np.sqrt((samples * sum_squared_values - sum_values**2) \
                          / (samples * (samples - 1)))

    def get_average(self):
        return self.average(self.sum_values, self.sum_squared_values,
                            self.samples)

    !!improve!!
    def take_data(self, data):
        pos = self.offset
        while pos < len(data):
            selected_data = \
                data[pos + self.start:pos + self.end].astype(np.float64)
            self.sum_values += selected_data
            self.sum_squared_values += selected_data**2
            pos += self.stride
            self.samples += 1
    
        if self.min_samples is None:
            return self.CONTINUE, None, None, None

        if self.samples > self.min_samples:
            self.mean, self.rms = self.get_average()

            if self.prev_mean is not None:
                diff1 = \
                    sum(abs(self.rms - self.prev_rms) / self.rms) / self.n_pix
                diff2 = \
                    sum(abs(self.rms - self.prev_rms) / self.prev_rms) \
                    / self.n_pix
                diff_mean = \
                    sum(abs(self.mean - self.prev_mean) / self.rms) / self.n_pix
                if diff1 < self.limit_diff_rms and diff2 < self.limit_diff_rms \
                   and diff_mean < self.limit_diff_mean:
                    return self.SUCCESS, self.samples, sum_values, \
                        sum_squared_values

            self.attempts += 1
            if self.attempts >= self.max_attempts:
                return self.FAIL, self.samples, sum_values, sum_squared_values
            self.prev_mean, self.prev_rms = self.mean, self.rms

        return self.CONTINUE, None, None, None
