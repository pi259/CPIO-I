import rtlsdr
import numpy as np
import pandas as pd

def classify_signal(freq):
    if 2412 <= freq <= 2472:
        return "WiFi (2.4GHz)"
    elif 87.5 <= freq <= 108:
        return "FM Radio"
    elif 47 <= freq <= 1000:
        return "VHF Radio"
    elif 470 <= freq <= 960:
        return "UHF Radio (Walkie-Talkie)"
    elif 2402 <= freq <= 2480:
        return "Military (2.4GHz)"
    elif 1435 <= freq <= 1525:
        return "Airforce (1.43-1.52GHz)"
    elif 7.25 <= freq <= 7.75:
        return "Navy (7.25-7.75GHz)"
    else:
        return "Other"

def scan_signals():
    # initialize the RTL-SDR device
    sdr = rtlsdr.RtlSdr()

    # configure the device
    sdr.sample_rate = 2.048e6  # Hz
    sdr.center_freq = 1e8     # Hz
    sdr.freq_correction = 60   # PPM
    sdr.gain = 'auto'

    # create a dataframe to store the results
    signals = []

    # scan for signals
    while sdr.center_freq < 4e9:
        samples = sdr.read_samples(256*1024)

        # compute the power spectral density (PSD)
        spectrum = np.abs(np.fft.fft(samples))**2
        freqs = np.fft.fftfreq(samples.size, 1/sdr.sample_rate)

        # find the maximum value in the PSD
        max_power = np.argmax(spectrum)
        max_freq = freqs[max_power] * 1e-6

        # classify the signal based on its frequency
        signal_type = classify_signal(max_freq)

        # add the results to the dataframe
        signals.append([max_freq, signal_type])

        # move the center frequency to the next band
        sdr.center_freq = sdr.center_freq + sdr.sample_rate

    # create a pandas dataframe from the results
    df = pd.DataFrame(signals, columns=["Frequency (MHz)", "Signal Type"])

    # save the results to an Excel file
    df.to_excel("signals.xlsx", index=False)

    # clean up
    sdr.close()

if __name__ == "__main__":
    scan_signals()
