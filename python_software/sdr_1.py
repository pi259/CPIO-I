import struct, numpy, sys, math, cmath, wave, filters, time, datetime
import queue, threading

monitor_strength = "-e" in sys.argv
use_autocorrelation = "-a" in sys.argv
debug_autocorrelation = "--aa" in sys.argv
am = "--am" in sys.argv

CENTER=int(sys.argv[1])
INPUT_RATE = int(sys.argv[2])
STEP = int(sys.argv[3])
IF_BANDWIDTH=int(sys.argv[4])
freqs = []
for i in range(5, len(sys.argv)):
	if sys.argv[i] == ".":
		break
	freqs.append(int(sys.argv[i]))

INGEST_SIZE = INPUT_RATE // 10

IF_RATE = 25000
AUDIO_BANDWIDTH = 4000
AUDIO_RATE = 12500

THRESHOLD_SNR = 9 # 9dB SNR = 1.5 bit
THRESHOLD_AC = 0.09
HISTERESIS_UP = -3      # not recording -> recording
HISTERESIS_DOWN = 3    # recording -> stop

assert (INPUT_RATE // IF_RATE) == (INPUT_RATE / IF_RATE)
assert (IF_RATE // AUDIO_RATE) == (IF_RATE / AUDIO_RATE)

# Makes sure IF demodulation carrier will be a multiple of STEP Hz 
# and it is in bandwidth range (80% of INPUT_RATE)
assert (INPUT_RATE / STEP == INPUT_RATE // STEP)
for f in freqs:
	if_freq = abs(CENTER - f)
	assert(if_freq / STEP == if_freq // STEP)
	assert(if_freq < (0.4 * INPUT_RATE))

MAX_DEVIATION = IF_BANDWIDTH / 2
DEVIATION_X_SIGNAL = 0.25 / (math.pi * MAX_DEVIATION / (IF_RATE / 2))

tau = 2 * math.pi
silence = numpy.zeros(IF_RATE // 10)

class Demodulator:
	def __init__(self, freq):
		self.freq = freq
		self.wav = None

		self.histeresis = HISTERESIS_UP
		self.old_histeresis = 0
		self.is_recording = False
		self.memory_up = []
		self.insert_timestamp = False

		# Energy (signal strength) estimation
		self.dbfs_avg = None
		self.dbfs_off = 0
		self.display_count = 0

		# Autocorrelation average
		self.ac_avg = None

		# IF
		self.if_freq = freq - CENTER
		# works because both if_freq and INPUT_RATE are multiples of STEP
		self.carrier_table = [ cmath.exp((0-1j) * tau * t * (self.if_freq / INPUT_RATE))
				for t in range(0, INGEST_SIZE * 2) ]
		self.carrier_table = numpy.array(self.carrier_table)
		self.if_period = INPUT_RATE // STEP
		self.if_phase = 0
		self.last_if_sample = numpy.array([])

		# IF filtering
		# complex samples, filter goes from -freq to +freq
		self.if_filter = filters.low_pass(INPUTTE, IF_BANDWIDTH / 2, 48)
		self.if_decimator = filters.decimator(INPUT_RATE // IF_RATE)

		# Audio filter
		self.audio_filter = filters.low_pass(IF_RATE, AUDIO_BANDWIDTH, 24)
		self.audio_decimator = filters.decimator(IF_RATE // AUDIO_RATE)
		self.dc_filter = filters.high_pass(AUDIO_RATE, 100, 6)

		# Thread
		def worker():
			while True:
				iqsamples = self.queue.get()
				if iqsamples is None:
					break
				self._ingest(iqsamples)
				self.queue.task_done()

		self.queue = queue.Queue()
		self.thread = threading.Thread(target=worker)
		self.thread.start()

	def create_wav(self):
		self.wav = wave.open("%d.wav" % self.freq, "w")
		self.wav.setnchannels(1)
		self.wav.setsampwidth(2)
		self.wav.setframerate(AUDIO_RATE)

	def close_queue(self):
		self.queue.put(None)

	def drain_queue(self):
		self.thread.join()

	def ingest(self, iqsamples):
		self.queue.put(iqsamples)

	def _ingest(self, iqsamples):
		self.tmbase = time.time()

		# Center frequency of samples on desired frequency

		# Get a cosine table in correct phase
		carrier = self.carrier_table[self.if_phase:self.if_phase + len(iqsamples)]
		# Advance phase
		self.if_phase = (self.if_phase + len(iqsamples)) % self.if_period
		# Demodulate
		ifsamples = iqsamples * carrier
		# print("%s %f" % ('f demod', time.time() - self.tmbase))

		# Filter IF to radio bandwidth and decimate
		ifsamples = self.if_filter.feed(ifsamples)
		ifsamples = self.if_decimator.feed(ifsamples)
		# print("%s %f" % ('f filter', time.time() - self.tmbase))

		# Get last sample from last batch
		ifsamples = numpy.concatenate((self.last_if_sample, ifsamples))

		# Save last sample to next batch for FM
		self.last_if_sample = ifsamples[-1:]

		# Signal strength
		strength = numpy.sum(numpy.absolute(ifsamples)) / len(ifsamples)
		dbfs = 20 * math.log10(strength)

		if self.dbfs_avg is None:
			self.dbfs_avg = dbfs
		else:
			self.dbfs_avg = 0.03 * dbfs + 0.97 * self.dbfs_avg
		self.display_count = (self.display_count + 1) % 25

		if am:
			# AM
			output_raw = numpy.absolute(ifsamples)[1:]
			# Most of the signal strength comes from the
			# (mute and constant) carrier, so we can use strength
			# to amplify the audio a bit, instead of implementing AGC
			output_raw *= 0.25 / strength
		else:
			# Narrow FM

			# Finds angles (phase) of I/Q pairs
			angles = numpy.angle(ifsamples)

			# Determine phase rotation between samples
			# (Output one element less, that's we always save last sample
			# in remaining_data)
			rotations = numpy.ediff1d(angles)
	
			# Wrap rotations >= +/-180º
			rotations = (rotations + numpy.pi) % (2 * numpy.pi) - numpy.pi
		
			# Convert rotations to baseband signal 
			output_raw = numpy.multiply(rotations, DEVIATION_X_SIGNAL)
	
		squelch, output_raw = self.squelch(dbfs, output_raw)
		if squelch:
			return

		# Filter to audio bandwidth and decimate
		output_raw = self.audio_filter.feed(output_raw)
		output = self.audio_decimator.feed(output_raw)
		output = self.dc_filter.feed(output)
		output = numpy.clip(output, -0.999, +0.999)

		# Scale to WAV integers
		# output = numpy.multiply(output, 127) + 127 # 8-bit WAV
		output = numpy.multiply(output, 32767) # 16-bit WAV
		output = output.astype(int)

		if self.insert_timestamp:
			output = numpy.concatenate((self.gen_timestamp(output), output))
			self.insert_timestamp = False
	
		bits = struct.pack('<%dh' % len(output), *output)
		if not self.wav:
			self.create_wav()
		self.wav.writeframes(bits)
		# print("%s %f" % ('f wav', time.time() - self.tmbase))

	# Determine if audio should be squelched or recorded

	def squelch(self, dbfs, output_raw):
		self.old_histeresis = self.histeresis
		if use_autocorrelation:
			vote = self.vote_by_autocorrelation(output_raw)
		else:
			vote = self.vote_by_dbfs(dbfs)
		self.histeresis += vote
		self.histeresis = min(HISTERESIS_DOWN, max(HISTERESIS_UP, self.histeresis))
		if self.histeresis != self.old_histeresis and monitor_strength:
			print("%d: hist %d" % (self.freq, self.histeresis))

		# Decide start/stop recording
		if not self.is_recording:
			if vote > 0:
				# Save samples so we can record to WAV retroactively
				self.memory_up.append(output_raw)
			else:
				self.memory_up = []

			if self.histeresis >= 0:
				print("%s %f recording" % (str(datetime.datetime.now()), self.freq))
				self.is_recording = True
				self.insert_timestamp = True
				self.histeresis = HISTERESIS_DOWN
				output_raw = numpy.concatenate(tuple(self.memory_up))
				self.memory_up = []
		else:
			if self.histeresis <= 0:
				print("%s %f stopping" % (str(datetime.datetime.now()), self.freq))
				self.is_recording = False
				self.histeresis = HISTERESIS_UP
				self.memory_up = []
				# Return a small silence block to finish audio
				return False, silence

		return not self.is_recording, output_raw

	# Vote record/stop based on signal strengh

	def vote_by_dbfs(self, dbfs):
		if monitor_strength and self.display_count == 0:
			print("%d: signal avg %.1f offavg %.1f hist %d" % \
				(self.freq, self.dbfs_avg, self.dbfs_off, self.histeresis))

		vote = -1
		if dbfs > (self.dbfs_off + THRESHOLD_SNR):
			vote = +1

		if not self.is_recording and vote < 0:
			# Use sample to find background noise level
			if dbfs < self.dbfs_off:
				self.dbfs_off = 0.05 * dbfs + 0.95 * self.dbfs_off
			else:
				self.dbfs_off = 0.005 * dbfs + 0.995 * self.dbfs_off

		return vote

	# Voice record/stop based on signal autocorrelation
		
	def vote_by_autocorrelation(self, output_raw):
		# Calculate autocorrelation metric
		ac_r = numpy.abs(numpy.correlate(output_raw, output_raw, 'same'))
		ac_metric = numpy.sum(ac_r) / numpy.max(ac_r) / len(output_raw)

		if debug_autocorrelation:
			print("%d: autocorrelation %f" % (self.freq, ac_metric))

		if self.ac_avg is None:
			self.ac_avg = ac_metric
		else:
			self.ac_avg = 0.2 * ac_metric + 0.8 * self.ac_avg

		if monitor_strength and self.display_count == 0:
			print("%d: signal avg %.1f autocorrelation %f hist %d" % \
				(self.freq, self.dbfs_avg, self.ac_avg, self.histeresis))

		vote = -1
		if ac_metric > THRESHOLD_AC:
			vote = +1
		return vote

	def gen_timestamp(self, output):
		offset = datetime.timedelta(seconds=(len(output) / AUDIO_RATE))
		now = datetime.datetime.utcnow() - offset
		data = [ 0x81, 0x82 ]
		data.append(127 - 5 + (now.year % 10000) // 1000)
		data.append(127 - 5 + (now.year % 1000) // 100)
		data.append(127 - 5 + (now.year % 100) // 10)
		data.append(127 - 5 + (now.year % 10) // 1)
		data.append(127 - 5 + now.month)
		data.append(127 - 5 + now.day // 10)
		data.append(127 - 5 + now.day % 10)
		data.append(127 - 5 + now.hour // 10)
		data.append(127 - 5 + now.hour % 10)
		data.append(127 - 5 + now.minute // 10)
		data.append(127 - 5 + now.minute % 10)
		data.append(127 - 5 + now.second // 10)
		data.append(127 - 5 + now.second % 10)
		data.append(127 - 5 + (now.microsecond % 1000000) // 100000)
		data.append(127 - 5 + (now.microsecond % 100000) // 10000)
		data = data + [ 0x83, 0x84 ]
		data = numpy.array(data)
		return data.astype(int)

demodulators = {}
for f in freqs:
	demodulators[f] = Demodulator(f)

remaining_data = b''

while True:
	# Ingest data
	data = sys.stdin.buffer.read(INGEST_SIZE * 2)
	if not data:
		break
	data = remaining_data + data

	tmbase = time.time()

	# Save odd byte
	if len(data) % 2 == 1:
		print("Odd byte, that's odd", file=sys.stderr)
		remaining_data = data[-1:]
		data = data[:-1]

	# Convert to complex numbers
	iqdata = numpy.frombuffer(data, dtype=numpy.uint8)
	iqdata = iqdata - 127.5
	iqdata = iqdata / 128.0
	iqdata = iqdata.view(complex)

	# Forward I/Q samples to all channels
	for k, d in demodulators.items():
		d.ingest(iqdata)

for k, d in demodulators.items():
	d.close_queue()

for k, d in demodulators.items():
	d.drain_queue()   