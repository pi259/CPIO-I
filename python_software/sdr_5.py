# teste e devolvendo tipo de sinal

import numpy as np
import rtlsdr
import matplotlib.pyplot as plt

def classify_signal(freq):
    if 2412 <= freq <= 2472:
        return "WiFi (2.4GHz)"
    elif 4910 <= freq <= 5825:
        return "WiFi (5GHz)"
    elif 87.5 <= freq <= 108:
        return "FM Radio"
    elif 136 <= freq <= 174:
        return "VHF Radio"
    elif 400 <= freq <= 470:
        return "UHF Radio (Walkie-Talkie)"
    else:
        return "Other"

def scan_signals():
    # initialize the RTL-SDR device
    sdr = rtlsdr.RtlSdr()

    # configure the device
    sdr.sample_rate = 2.048e6  # Hz
    sdr.center_freq = 100e6    # Hz
    sdr.freq_correction = 60   # PPM
    sdr.gain = 'auto'

    # scan for signals
    samples = sdr.read_samples(256*1024)

    # compute the power spectral density (PSD)
    spectrum = np.abs(np.fft.fft(samples))**2
    freqs = np.fft.fftfreq(samples.size, 1/sdr.sample_rate)

    # find the maximum value in the PSD
    max_power = np.argmax(spectrum)
    max_freq = freqs[max_power] * 1e-6

    # classify the signal based on its frequency
    signal_type = classify_signal(max_freq)
    print(f"Detected signal type: {signal_type}")

    # plot the PSD
    plt.plot(freqs, spectrum)
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Power Spectral Density")
    plt.show()

    # clean up
    sdr.close()

if __name__ == "__main__":
    scan_signals()
