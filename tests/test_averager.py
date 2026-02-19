import numpy as np
from pymodaq_plugins_transient_absorption.averager import Averager


def make_data(n_data, n_pix, offset=0):
    data = np.empty(n_data)
    dest = 0
    while dest < n_data:
        data[dest:dest+n_pix] = 1 + offset
        dest += n_pix
        data[dest:dest+n_pix] = 2 + offset
        dest += n_pix
        data[dest:dest+n_pix] = 2 + offset
        dest += n_pix
        data[dest:dest+n_pix] = 3 + offset
        dest += n_pix
    return data


def test_set_up():
    averager = Averager(0, 40, 20, 3, 50, 1, 2, 10)
    assert averager.start == 0
    assert averager.end == 40
    assert averager.stride == 20
    assert averager.offset == 3
    assert averager.min_samples == 50
    assert averager.limit_diff_rms == 1
    assert averager.limit_diff_mean == 2
    assert averager.max_attempts == 10
    assert not averager.changed
    assert not averager.samples
    assert not averager.attempts
    assert averager._prev_mean is None
    assert averager._prev_rms is None


def test_free():
    n_pix = 10
    n_cam = 2
    n_scans = 10
    n_data = n_pix * n_cam * n_scans
    data = make_data(n_data, n_pix)

    for start,end in zip([0, 2], [8, 10]):
        n_used = end -start
        averager_signal = Averager(start=start, end=end, stride=20)
        averager_reference = Averager(start=start, end=end, stride=20, offset=10)
        assert averager_signal.take_data(data) == Averager.CONTINUE
        assert averager_reference.take_data(data) == Averager.CONTINUE
        assert averager_signal.samples == n_scans
        assert averager_reference.samples == n_scans
        assert sum(abs(averager_signal.mean - np.full(n_used, 1.5))) < 1e-12
        assert sum(abs(averager_reference.mean - np.full(n_used, 2.5))) < 1e-12
        assert max(abs(averager_signal.rms - np.full(n_used, 0.52704628))) < 1e-8
        assert max(abs(averager_reference.rms - np.full(n_used, 0.52704628))) \
            < 1e-8


def test_ok():
    n_pix = 10
    n_cam = 2
    n_scans = 10
    n_data = n_pix * n_cam * n_scans
    data = make_data(n_data, n_pix)

    for start,end in zip([0, 2], [8, 10]):
        averager_signal = Averager(start=start, end=end, stride=20,
                                   min_samples=10, limit_diff_rms=2,
                                   limit_diff_mean=2)
        averager_reference = Averager(start=start, end=end, stride=20, offset=10,
                                      min_samples=10, limit_diff_rms=2,
                                      limit_diff_mean=2)
        assert averager_signal.take_data(data) == Averager.CONTINUE
        assert averager_reference.take_data(data) == Averager.CONTINUE
        assert averager_signal.samples == 0
        assert averager_reference.samples == 0
        assert averager_signal.take_data(data) == Averager.SUCCESS
        assert averager_reference.take_data(data) == Averager.SUCCESS
        assert averager_signal.samples == n_scans
        assert averager_reference.samples == n_scans


def test_multiple(fail=False):
    n_pix = 10
    n_cam = 2
    n_scans = 10
    n_data = n_pix * n_cam * n_scans
    data1 = make_data(n_data, n_pix)
    data2 = make_data(n_data, n_pix, offset=10)

    for start,end in zip([0, 2], [8, 10]):
        averager_signal = Averager(start=start, end=end, stride=20,
                                   min_samples=10, limit_diff_rms=1,
                                   limit_diff_mean=1, max_attempts=8)
        averager_reference = Averager(start=start, end=end, stride=20, offset=10,
                                      min_samples=10, limit_diff_rms=1,
                                      limit_diff_mean=1, max_attempts=8)

        for i in range(3):
            assert averager_signal.take_data(data1) == Averager.CONTINUE
            assert averager_reference.take_data(data1) == Averager.CONTINUE
            assert averager_signal.take_data(data2) == Averager.CONTINUE
            assert averager_reference.take_data(data2) == Averager.CONTINUE
            assert averager_signal.samples == 0
            assert averager_reference.samples == 0
        assert averager_signal.take_data(data1) == Averager.CONTINUE
        assert averager_reference.take_data(data1) == Averager.CONTINUE
        if fail:
            assert averager_signal.take_data(data2) == Averager.FAIL
            assert averager_reference.take_data(data2) == Averager.FAIL
        else:
            assert averager_signal.take_data(data1) == Averager.SUCCESS
            assert averager_reference.take_data(data1) == Averager.SUCCESS
        assert averager_signal.samples == n_scans
        assert averager_reference.samples == n_scans

    
def test_fail():
    test_multiple(fail=True)

    
if __name__ == '__main__':
    test_set_up()
    test_free()
    test_ok()
    test_multiple()
    test_fail()
