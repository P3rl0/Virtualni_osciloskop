from frontend.formatting import fmt_freq, fmt_time, fmt_volt, normalize_backend_measurements, parse_scale


def test_parse_scale():
    assert parse_scale("1 ms/div") == 1e-3
    assert parse_scale("500 mV/div") == 0.5


def test_formatting_smoke():
    assert "kHz" in fmt_freq(1_000)
    assert "ms" in fmt_time(0.001)
    assert "mV" in fmt_volt(0.5)


def test_backend_measurement_normalization():
    data = {(0, "peak_to_peak"): 2.0, (0, "rms"): 0.7, (0, "frequency"): 1000.0}
    norm = normalize_backend_measurements(data)
    assert norm[1]["Vpp"] == 2.0
    assert norm[1]["Vrms"] == 0.7
    assert norm[1]["Freq"] == 1000.0
    assert norm[1]["Period"] == 0.001
