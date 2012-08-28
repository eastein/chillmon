#!/usr/bin/env python

"""
Here is a growing collection of libraries and example python scripts for controlling a variety of Adafruit electronics with a Raspberry Pi

In progress!

Adafruit invests time and resources providing this open source code, please support Adafruit and open-source hardware by purchasing products from Adafruit!

Written by Limor Fried, Kevin Townsend and Mikey Sklar for Adafruit Industries. BSD license, all text above must be included in any redistribution

To download, we suggest logging into your Pi with Internet accessibility and typing: git clone https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code.git

Refactored into a class structure and pluggable access objects added by Eric Stein
"""
import RPi.GPIO as GPIO
import threading

# change these as desired - they're the pins connected from the
# SPI port on the ADC to the Cobbler
SPICLK = 18
SPIMISO = 23
SPIMOSI = 24
SPICS = 25

class Pin(object) :
	def read(self) :
		raise NotImplemented

class TMP36(Pin) :
	F = 0
	C = 1
	K = 2

	"""
	Choose a scale if you don't want C.  K and F also available as constants in the class scope.
	"""
	def __init__(self, temp_scale=None) :
		if temp_scale is None :
			temp_scale = self.C
		
		self.temp_scale = temp_scale

	@classmethod
	def c2f(self, c) :
		# convert celsius to fahrenheit 
		return ( c * 9.0 / 5.0 ) + 32

	@classmethod
	def c2k(self, c) :
		# celsius to kelvin
		return c + 273.15

	def setup_mcp3008(self, mcp, channel_number) :
		self.mcp = mcp
		self.channel_number = channel_number

	def read(self) :
		millivolts = self.mcp.readadc(self.channel_number)
		c = ((millivolts - 100.0) / 10.0) - 40.0
		if self.temp_scale == TMP36.C :
			return c
		elif self.temp_scale == TMP36.F :
			return TMP36.c2f(c)
		elif self.temp_scale == TMP36.K :
			return TMP36.c2k(c)

class MCP3008(object) :
	SPI_LOCK = threading.Lock()

	def __init__(self, mv_aref) :
		self.mv_aref = mv_aref
		self.channels = [None] * 8
		# set up the SPI interface pins
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(SPIMOSI, GPIO.OUT)
		GPIO.setup(SPIMISO, GPIO.IN)
		GPIO.setup(SPICLK, GPIO.OUT)
		GPIO.setup(SPICS, GPIO.OUT)

	# read SPI data from MCP3008 chip, 8 possible adc's (0 thru 7)
	def _readadc(self, adcnum, clockpin=SPICLK, mosipin=SPIMOSI, misopin=SPIMISO, cspin=SPICS):
		if ((adcnum > 7) or (adcnum < 0)):
		        return -1
		GPIO.output(cspin, True)

		GPIO.output(clockpin, False)  # start clock low
		GPIO.output(cspin, False)     # bring CS low

		commandout = adcnum
		commandout |= 0x18  # start bit + single-ended bit
		commandout <<= 3    # we only need to send 5 bits here
		for i in range(5):
		        if (commandout & 0x80):
		                GPIO.output(mosipin, True)
		        else:   
		                GPIO.output(mosipin, False)
		        commandout <<= 1
		        GPIO.output(clockpin, True)
		        GPIO.output(clockpin, False)

		adcout = 0
		# read in one empty bit, one null bit and 10 ADC bits
		for i in range(12):
		        GPIO.output(clockpin, True)
		        GPIO.output(clockpin, False)
		        adcout <<= 1
		        if (GPIO.input(misopin)):
		                adcout |= 0x1

		GPIO.output(cspin, True)

		adcout /= 2       # first bit is 'null' so drop it
		
		return adcout * ( self.mv_aref / 1024.0)

	def readadc(self, *args, **kwargs) :
		self.SPI_LOCK.acquire(True)
		try :
			return self._readadc(*args, **kwargs)
		finally :
			self.SPI_LOCK.release()

	def setup_channel(self, channel_number, pinobject) :
		pinobject.setup_mcp3008(self, channel_number)
		self.channels[channel_number] = pinobject
