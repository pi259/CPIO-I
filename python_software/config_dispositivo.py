from rtlsdr import RtlSdr

# iniciando o dispositivo rtl-sdr
sdr = RtlSdr()

# configurando o dispositivo
sdr.sample_rate = 2.048e6  # Hz
sdr.center_freq = 1e6      # Hz
sdr.freq_correction = 60   # PPM
sdr.gain = 'auto'

print(sdr.read_samples(512))
