import numpy as np
from pymodaq_plugins_transient_absorption.ta_processor import TAProcessor, \
    StatisticsCondition, TACondition
from pymodaq_plugins_transient_absorption.averager import Averager
from dataclasses import asdict


def count_success():
    global success_count
    success_count += 1

def count_fail():
    global fail_count
    fail_count += 1


def make_processor(n_pix):
    ta_processor = TAProcessor()
    ta_condition = \
        TACondition(limit_diff_rms_dark=1, limit_diff_mean_dark=1, min_dark=40,
                    max_dark_attempts=30, limit_diff_rms_white=1,
                    limit_diff_mean_white=1, min_white=20, max_white_attempts=10)
    ranges = [[2, 4], [6, 8]]

    ta_processor.set_up(n_pix, ta_condition, ranges, False)
    ta_processor.acquisition_done.connect(count_success)
    ta_processor.acquisition_failed.connect(count_fail)
    global success_count
    global fail_count
    success_count = 0
    fail_count = 0

    return ta_processor

    
def make_data(n_data, n_pix, signal=0, reference=0, ta=0, deviation=0, offset=0):
    data = np.empty(n_data)
    dest = 0
    while dest < n_data:
        data[dest:dest+n_pix] = 1 + signal + ta + offset
        dest += n_pix
        data[dest:dest+n_pix] = 3 + reference + offset
        dest += n_pix
        data[dest:dest+n_pix] = 2 + signal + offset
        dest += n_pix
        data[dest:dest+n_pix] = 4 + reference + offset
        dest += n_pix
    return data


def test_set_up():
    n_pix = 10
    ta_processor = make_processor(n_pix)

    assert ta_processor.n_pix == n_pix
    assert ta_processor.data_processing_mode == TAProcessor.DARK
    assert asdict(ta_processor.dark_condition) == {
        'pixel_from': 0, 'pixel_to': n_pix, 'limit_diff_rms': 1,
        'limit_diff_mean': 1, 'min_samples': 40, 'max_attempts': 30
        }
    assert len(ta_processor.whitelight_conditions) == 3
    assert asdict(ta_processor.whitelight_conditions[0]) ==  {
        'pixel_from': 2, 'pixel_to': 4, 'limit_diff_rms': 1,
        'limit_diff_mean': 1, 'min_samples': 20, 'max_attempts': 10
        }
    assert asdict(ta_processor.whitelight_conditions[1]) ==  {
        'pixel_from': 6, 'pixel_to': 8, 'limit_diff_rms': 1,
        'limit_diff_mean': 1, 'min_samples': 20, 'max_attempts': 10
        }
    assert asdict(ta_processor.whitelight_conditions[2]) ==  {
        'pixel_from': 0, 'pixel_to': n_pix, 'limit_diff_rms': 0,
        'limit_diff_mean': 0, 'min_samples': 0, 'max_attempts': 0
        }
    assert hasattr(ta_processor, 'ta_averager')
    assert type(ta_processor.ta_averager) == Averager
    assert asdict(ta_processor.ta_averager) == {
        'start': 0, 'end': n_pix, 'stride': 0, 'offset': 0, 'min_samples': 0,
        'limit_diff_rms': 0, 'limit_diff_mean': 0, 'max_attempts': 0
        }


def test_dark_pass():
    n_pix = 10
    ta_processor = make_processor(n_pix)

    n_dark = 40
    dark_data = make_data(n_pix * 2 * n_dark, n_pix)
    dte, store = ta_processor.process_data(dark_data)
    assert not store
    dte, store = ta_processor.process_data(dark_data)
    assert store
    assert ta_processor.data_processing_mode == TAProcessor.IDLE
    assert fail_count == 0
    assert success_count == 1

    return ta_processor, n_pix


def test_dark_fail():
    n_pix = 10
    ta_processor = make_processor(n_pix)

    n_dark = 40
    dark_data1 = make_data(n_pix * 2 * n_dark, n_pix)
    dark_data2 = make_data(n_pix * 2 * n_dark, n_pix, offset=20)
    for i in range(14):
        dte, store = ta_processor.process_data(dark_data1)
        assert not store
        assert fail_count == 0
        assert ta_processor.data_processing_mode == TAProcessor.DARK
        dte, store = ta_processor.process_data(dark_data2)
        assert not store
        assert fail_count == 0
        assert ta_processor.data_processing_mode == TAProcessor.DARK
    dte, store = ta_processor.process_data(dark_data1)
    assert not store
    assert fail_count == 0
    dte, store = ta_processor.process_data(dark_data2)
    assert not store
    assert ta_processor.data_processing_mode == TAProcessor.IDLE
    assert fail_count == 1

    ta_processor.reset()
    for av in ta_processor.dark_averagers:
        assert av.attempts == 0


def test_dark_fail_then_pass():
    n_pix = 10
    ta_processor = make_processor(n_pix)

    n_dark = 40
    dark_data1 = make_data(n_pix * 2 * n_dark, n_pix)
    dark_data2 = make_data(n_pix * 2 * n_dark, n_pix, offset=20)
    dte, store = ta_processor.process_data(dark_data1)
    assert not store
    dte, store = ta_processor.process_data(dark_data2)
    assert not store
    for av in ta_processor.dark_averagers:
        assert av.samples == 0
    assert ta_processor.data_processing_mode == TAProcessor.DARK
    dte, store = ta_processor.process_data(dark_data1)
    assert not store
    dte, store = ta_processor.process_data(dark_data1)
    assert store


def test_white_pass():
    ta_processor, n_pix = test_dark_pass()
    global success_count
    success_count = 0
    n_white = 20
    white_data = \
        make_data(n_pix * 2 * n_white, n_pix, signal=100, reference=110)
    ta_processor.data_processing_mode = TAProcessor.IDLE
    dte, store = ta_processor.process_data(white_data)
    assert not store
    ta_processor.data_processing_mode = TAProcessor.WHITELIGHT
    dte, store = ta_processor.process_data(white_data)
    assert not store
    dte, store = ta_processor.process_data(white_data)
    assert store
    for av in ta_processor.whitelight_averagers[:-1]:
        assert av.attempts == 1
        assert av.samples == 20
    assert ta_processor.whitelight_averagers[-1].attempts == 0
    assert ta_processor.whitelight_averagers[-1].samples == 40

    return ta_processor, n_pix


def test_white_fail():
    ta_processor, n_pix = test_dark_pass()
    n_white = 20
    global success_count
    success_count = 0
    white_data1 = \
        make_data(n_pix * 2 * n_white, n_pix, signal=100, reference=110)
    white_data2 = \
        make_data(n_pix * 2 * n_white, n_pix, signal=100, reference=110,
                  offset = 10)
    for i in range(4):
        dte, store = ta_processor.process_data(white_data1)
        assert not store
        ta_processor.data_processing_mode = TAProcessor.WHITELIGHT
        dte, store = ta_processor.process_data(white_data2)
        assert not store
    dte, store = ta_processor.process_data(white_data1)
    assert not store
    assert fail_count == 0
    dte, store = ta_processor.process_data(white_data2)
    assert not store
    assert ta_processor.data_processing_mode == TAProcessor.IDLE
    assert fail_count == 1

    for av in ta_processor.whitelight_averager[:-1]:
        assert av.attempts == 1
        assert av.samples == 0
    assert ta_processor.whitelight_averager[-1].attempts == 0
    assert ta_processor.whitelight_averager[-1].samples == 0


def test_white_then_pass():
    ta_processor, n_pix = test_dark_pass()
    n_white = 20
    global success_count
    success_count = 0
    white_data1 = \
        make_data(n_pix * 2 * n_white, n_pix, signal=100, reference=110)
    white_data1 = \
        make_data(n_pix * 2 * n_white, n_pix, signal=100, reference=110,
                  offset = 10)
    for i in range(10):
        dte, store = ta_processor.process_data(white_data1)
        assert not store
        ta_processor.data_processing_mode = TAProcessor.WHITELIGHT
        dte, store = ta_processor.process_data(white_data2)
        assert not store
    dte, store = ta_processor.process_data(dark_data1)
    assert not store
    assert fail_count == 0
    dte, store = ta_processor.process_data(dark_data2)
    assert not store
    assert ta_processor.data_processing_mode == TAProcessor.IDLE
    assert fail_count == 1

    for av in ta_processor.whitelight_averager[:-1]:
        assert av.attempts == 1
        assert av.samples == 0
    assert ta_processor.whitelight_averager[-1].attempts == 0
    assert ta_processor.whitelight_averager[-1].samples == 0


def test_accumulation():
    assert False


def test_rejection():
    assert False


def test_success():
    assert False


if __name__ == '__main__':
    test_set_up()
    test_dark_pass()
    test_dark_fail()
    test_dark_fail_then_pass()
    test_white_pass()
    test_white_fail()
    test_white_fail_then_pass()
    test_accumulation()
    test_rejection()
    test_success()
