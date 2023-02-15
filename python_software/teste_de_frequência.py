import rtlsdr
import numpy as np

# initialize the RTL-SDR dongle
sdr = rtlsdr.RtlSdr()

# set the sample rate
sdr.sample_rate = 2.4e6

# set the center frequency
freq = 100000000
if freq >= 24e6 and freq <= 1766e6:
    sdr.center_freq = freq
else:
    print("Error: frequency is not within supported range")
    sdr.close()
    exit()

# read samples
samples = sdr.read_samples(512*1024)

# process and analyze the samples
# ...

# close the RTL-SDR dongle
sdr.close()
