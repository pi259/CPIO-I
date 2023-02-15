import numpy as np
import matplotlib.pyplot as plt
import rtlsdr

def plot_waveform(samples, sample_rate):
	# Convert samples to numpy array
	samples = np.array(samples)

	# Plot the waveform
	plt.plot(samples)
	plt.xlabel('Sample Index')
	plt.ylabel('Amplitude')
	plt.title('Waveform in Time Domain')
	plt.show()

	# Plot the frequency spectrum
	fft = np.fft.fft(samples)
	frequencies = np.fft.fftfreq(samples.size, 1/sample_rate)
	plt.plot(frequencies, np.abs(fft))
	plt.xlabel('Frequency (Hz)')
	plt.ylabel('Amplitude')
	plt.title('Waveform in Frequency Domain')
	plt.show()

def main():
	# Connect to SDR antenna dongle
	sdr = rtlsdr.RtlSdr()
	sdr.sample_rate = 2.4e6
	sdr.center_freq = 1e6
	sdr.gain = 10
	sdr.set_bandwidth(2.4e6)

	# Read samples from the SDR antenna
	samples = sdr.read_samples(1024)

	# Plot the waveform
	plot_waveform(samples, sdr.sample_rate)

if __name__ == '__main__':
    main()