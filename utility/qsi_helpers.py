# boilerplate stuff to import
import os
import sys
import platform
import numpy as np
import time
import re
from cffi import FFI
import qsi_cfg as cfg
import datetime as dt
import json
import pandas as pd
from collections import OrderedDict
from datetime import datetime
from scipy.ndimage import convolve
from operator import attrgetter
from collections import namedtuple
from scipy.io import savemat
from scipy.io import loadmat
import shutil
import threading
import subprocess
import warnings
	

from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from scipy import special

import nickel_efuse_lib as nickel_efuse

# will be updated on connect
import qsi_helpers

isDigital = None
product_type = None

ffi = FFI()
lib = None
laser_lib = None


PYTHON_VERSION = 3
if sys.version_info[0] < 3:
	PYTHON_VERSION = 2

platform_name = platform.system()
if platform_name == "Windows":
	default_reg_file = cfg.DEFAULT_REG_FILE_PATH

MAX_AUTO_EXP_CYCLES = 60
INCLUDE_PATH = cfg.INCLUDE_PATH
default_reg_file = cfg.DEFAULT_REG_FILE_PATH
MIN_BLANK_ROWS = 5  # based on where vpulse occurs in blanking period... see dan f.
nickel_handle = None
echo = None
capture_array = None
default_regs = []
default_bits = []
vref_prior = -99

HEADERS = ['alarm_event.h', 'qsi_umap_impl.h', 'qsi_tlv_defs.h', 'QSI_API.h']



def load_headers():
	for header_name in HEADERS:
		packed = False
		nicer_header = ''
		defines_str = ''
		with open(os.path.join(INCLUDE_PATH, header_name), 'r') as f:
			lines = f.readlines()
			defines = {}
			# the python cdef parser is really sucky, so here I'm fixing up lines to pass to it
			# I'm also doing very very basic #define support in a single pass, so nothing complex
			for line in lines:
				line = line.lstrip()
				if len(line) < 1:
					continue
				if line.find('QSI_NO_PYTHON') != -1:
					continue
				if line.find('HELPER') != -1:
					continue
				if line.find('__PACKED__') != -1:
					packed = True
					if 'QSI_API.h' in header_name:
						packed = False # if True, then all structs declared within this cdef are “packed”. (If you need both packed and non-packed structs, use several cdefs in sequence.)
				if line.find("#define") != -1:
					try:
						key = line.split()[1]
						value = line.split()[2]
						if 'BITPOSN(' in value and not value.startswith('('):
							# Replace it with the correct value
							def trans(text):
								ret = re.search('(\d+)', text.group(0))
								# return "LIBQSI_SETBIT_" + ret.group(0)
								return '{:#x}'.format(pow(2, int(ret.group(0))))

							defines[key] = re.sub(r"(BITPOSN\((\d+)\))", trans, value)
						elif '(' in value or '*' in value or '|' in value or '/*' in value or '"' in value or \
								value.startswith('('):
							pass
						elif 'TEST_SHARED_EXPORT' == key:
							pass
						elif '#' in value:
							pass
						else:
							defines[key] = value
					except:
						pass
				if line[0] == '#':
					continue
				if line.startswith("extern"):
					continue
				if line.find("namespace") != -1:
					continue
				if line.find("public") != -1:
					continue
					# if line.find("CTNT_ALL") != -1:
					# line = 'CTNT_ALL = 0xB01'
				if line.startswith("__pragma"):
					continue
				if line == '}\n':
					continue
					# if line.find('TLV_TEMPERATURE') != -1:
					#	  continue
					# if line.find('TLV_STATISTICS') != -1:
					# continue
				line = line.replace("TEST_SHARED_EXPORT ", "", 1)
				line = line.replace("DLL_API ", "", 1)
				line = line.replace("__PACKED__ ", "", 1)
				for key in defines:
					if line.find(key) != -1:
						line = line.replace(key, defines[key], 1)
				nicer_header += line

			# Now add all the defines to the end of the header file as a massive enum
			if len(defines) != 0:
				defines_str += 'enum header_defines_{}\n{{\n'.format(header_name[:-2])

				if PYTHON_VERSION == 2:
					for key, value in defines.viewitems():
						defines_str += '{} = {},\n'.format(key, value)
				else:
					for key, value in defines.items():
						defines_str += '{} = {},\n'.format(key, value)

				defines_str = defines_str[:-2] + '\n};\n'

		nicer_header += defines_str
		ffi.cdef(nicer_header, packed=packed)



def load_libs():
	global lib
	platform_name = platform.system()
	if platform_name == "Darwin":
		lib_name = "libqsi_f4_usb_64b.1.0.0.dylib"
	elif platform_name == 'Windows':
		lib_name = os.path.join(INCLUDE_PATH, 'qsi_f4_usb_64b.dll')
	else:
		lib_name = "libqsi_f4_usb_64b.so"

	lib = ffi.dlopen(lib_name)


def init():
	global laser_lib

	# load up the headers and shared libs
	#try:
	if 1:
		load_headers()
	#except:
		#print('trouble with headers')


	# load up the shared libs
	try:
		load_libs()
	except:
		print('trouble with libs')

	# declare the laser alignment entrypoint
	ffi.cdef("int32_t quantum_laser_beamsteering(int32_t row, const char *json_procedure);")

#	 try:
#		 laser_lib = ffi.dlopen('libbeamsteer.so')
#	 except OSError:
#		 laser_lib = None
#		 print('Warning: laser library not available')

	lib.quantum_initialize_dll(ffi.NULL)

	# connect to the device
	rc = con()
	#rc = lib.quantum_connect_device()
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print('failed to connect to device, error %s' % rc)
		print('not initialized!')
		return False
	else:
		print('initialized!')

		# Get the product type
		product_type = lib.quantum_get_product_type()
		global isDigital
		if product_type == lib.LIBQSI_PRODUCT_NANO_D:
			print("connected to digital product %s" % product_type)
			isDigital = True
		else:
			print("connected to analog product %s" % product_type)
			isDigital = False
		return True


def text2cffi(text):
	if isinstance(text, str):
		pass
	else:
		text = str(text)
	if PYTHON_VERSION == 2:
		return ffi.new('char []', text)
	else:
		return ffi.new('char []', bytes(text, 'utf-8'))


laser_align_config = '''
{
	"description" : "Default alignment for Nano devices, from Kyle Preston's Python code, SFS 2018-03-30",
	"cols" : "all",
	"rows" : "all",
	"timebin" : 0,

	"coarse" : [
		[ "grid", {
			"goal" : "row",
			"m1" : { "motor" : "X", "range" : 2000, "step" :  16 },
			"m2" : { "motor" : "Y", "range" : 2000, "step" : 128 }
		} ]
	],

	"fine" : [
		[ "sequence", {
			"description" : "Initial x/y tuning",
			"steps" : [
				[ "sweep", {"motor":"X","span":1200,"step":16,"goal":"maximize_mean" } ],
				[ "sweep", {"motor":"Y","span":1300,"step":16,"goal":"maximize_mean" } ]
			]
		} ],

		[ "sequence", {
			"description" : "Fast x/y fine-tuning",
			"steps" : [
				[ "sweep", {"motor":"X","span": 48,"step":4,"goal":"maximize_mean" } ],
				[ "sweep", {"motor":"Y","span":150,"step":8,"goal":"maximize_mean" } ]
			]
		} ],

		[ "sequence", {
			"description" : "Iteratively tune tx/ty",
			"steps" : [
				[ "sequence", {
					"description" : "Initial tx/ty tuning",
					"steps" : [
						[ "sweep", {"motor":"TX","span":1000,"step":64,"goal":"maximize_mean" } ],
						[ "sweep", {"motor":"TY","span":1000,"step":64,"goal":"maximize_mean" } ],

						[ "sweep", {"motor":"X","span": 300,"step":16,"goal":"maximize_mean" } ],
						[ "sweep", {"motor":"Y","span": 600,"step":32,"goal":"maximize_mean" } ]
					]
				} ],
				[ "iter", {
					"prct" : 2.0,
					"max_iter" : 100,
					"steps" : [
						[ "sweep", {"motor":"TX","span":400,"step":32,"goal":"maximize_mean" } ],
						[ "sweep", {"motor":"TY","span":800,"step":64,"goal":"maximize_mean" } ],

						[ "sweep", {"motor":"X","span":	 40,"step": 2,"goal":"maximize_mean" } ],
						[ "sweep", {"motor":"Y","span":	 80,"step": 4,"goal":"maximize_mean" } ]
					]
				} ]
			]
		} ],

		[ "sequence", {
			"description" : "Final x/y tuning",
			"steps" : [
				[ "sweep", {"motor":"X","span": 48,"step":4,"goal":"maximize_mean" } ],
				[ "sweep", {"motor":"Y","span":150,"step":8,"goal":"maximize_mean" } ],

				[ "sweep", {"motor":"X","span": 20,"step":1,"goal":"maximize_mean" } ],
				[ "sweep", {"motor":"Y","span": 80,"step":4,"goal":"maximize_mean" } ]
			]
		} ]
	],

	"retune" : [
		[ "sequence", {
			"description" : "Fast retuning of X and Y motors",
			"steps" : [
				[ "sweep", {"motor":"X", "span":40, "step":1, "goal":"maximize_mean"} ],
				[ "sweep", {"motor":"Y", "span":80, "step":2, "goal":"maximize_mean"} ]
			]
		} ]
	],
	"align_mask" : "/usr/share/qsi-datapad/resources/shared/HBEE3_alignment_pixels.csv",

	"options" : [
		"home_motors",
		"write_home_positions",
		"write_final_positions",
		"plot_grid_search",
		"plot_line",
		"plot_hill_climb",
		"plot_simplex",
		"plot_final_image",
		"plot_as_png"
	]
}
'''


def laser_align(row, config_file=None):
	if not laser_lib:
		print('Warning: laser library not available, skip laser alignment')
		return
	if config_file is not None:
		with open(config_file) as f:
			align_config = f.read()
	else:
		align_config = laser_align_config
	laser_lib.quantum_laser_beamsteering(row, text2cffi(align_config))


# define a function to convert from quantum library C pointers to python string
def tostr(ffi_str):
	if ffi_str == ffi.NULL:
		return ''
	else:
		return ffi.string(ffi_str).decode('utf-8')
		
def get_laser_status():
	#SABER_POWER_MODE_TEC_AND_PUMP_OFF = 0,
	#SABER_POWER_MODE_TEC_ON_PUMP_OFF = 1,
	#SABER_POWER_MODE_TEC_ON_PUMP_ON = 2
	
	ret = ffi.new('saber_power_mode_t *')
	lib.quantum_get_saber_power_mode(ret)
	return ret[0]
	
	
def get_laser_power():

	#power_milliwatts = ffi.new('float *')
	#averaging_type = ffi.new('LASER_POWER_AVERAGING_t *')
	#lib.quantum_get_laser_output_power(power_milliwatts, averaging_type)
	
	power_milliwatts = ffi.new('float *')
	lib.quantum_get_requested_laser_output_power(power_milliwatts)
	return power_milliwatts[0]
	

def wait_locked():
	count = 100
	while count > 0 and lib.quantum_get_MCLK_lock_status() != lib.LIBQSI_STATUS_CLOCK_LOCKED:
		time.sleep(0.1)
		count -= 1
	if count == 0:
		print('ERROR! failed to lock to clock? Aligning Laser and then closing program.')
		align_mll()
		time.sleep(2)
		#sys.exit()

	
# define a convenience function that creates a numpy array from a series of frames captured
def capture(num_frames, mode='cds', max_retries=3):
	# capture our requested frames into RAM
	retry = 0
	num_frames_actually_captured = ffi.new('uint32_t *')
	frames = ffi.new('streaming_frame_header_t ***')
	lib.quantum_capture_n_frames(num_frames, num_frames_actually_captured, frames)
	while num_frames != num_frames_actually_captured[0]:
		print('ERROR - only captured %s of %d frames?' % (num_frames_actually_captured[0], num_frames))
		print(f'Retry attempt {retry}: ', end='')
		time.sleep(1)
		print(f'Disconnect ', end='')
		dis()
		time.sleep(1)
		print(f'Connect ', end='')
		con()
		time.sleep(1+ (retry * 60))
		print(f'Sleep Done... continuing')
		if retry==(max_retries - 1):
			input('Enable breakpoints then continue')
		lib.quantum_capture_n_frames(num_frames, num_frames_actually_captured, frames)
		retry+=1

		if retry>=max_retries:
			print('Max retries attempted, failed to capture all frames')
			return(-1)

	# create a new numpy array
	frame_list = frames[0]
	frame = frame_list[0]
	num_bins = frame.total_bins_available
	#if mode == 'rx':
	if mode in ['rx', 'crop']:
		num_bins = 1
	#num_rows = frame.enabled_rows_per_frame
	num_rows = 2*frame.enabled_rows_per_frame # Nickel full chip hack
	max_rows = frame.sensor_frame_images_num_vertical_elements
	num_cols = frame.sensor_frame_images_num_horizontal_elements
	ar = np.zeros((num_frames, num_bins, num_rows, num_cols), dtype=np.int16)

	# copy frame data into the numpy array
	for i in range(num_frames):
		frame = frame_list[i]

		# get a pointer to the CDS data
		byte_ptr = ffi.cast("char *", frame)
		if mode in ['cds', 'crop']:
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.cds_frames_base_offset)
		elif mode == 'rx':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.reset_frames_base_offset)

		# create a numpy array pointer to our image pointer
		img_buffer = np.frombuffer(ffi.buffer(img_ptr, max_rows * num_cols * num_bins * 2), dtype=np.int16)
		img_buffer = np.reshape(img_buffer, (num_bins, max_rows, num_cols))
		np.copyto(ar[i], img_buffer[:, frame.first_valid_row_index:(frame.first_valid_row_index+num_rows), :])

	# clean up
	lib.quantum_n_frames_free(frame_list)

	# return the numpy array to the user
	return ar

def capture_chiplets(num_frames, mode='cds'):
	# capture our requested frames into RAM
	num_frames_actually_captured = ffi.new('uint32_t *')
	frames = ffi.new('streaming_frame_header_t ***')
	lib.quantum_capture_n_frames(num_frames, num_frames_actually_captured, frames)
	if num_frames != num_frames_actually_captured[0]:
		print('ERROR - only captured %s of %d frames?' % (num_frames_actually_captured[0], num_frames))
		print('Aligning Laser and then closing program.')
		align_mll()
		time.sleep(2)
		sys.exit()
		#return None

	# create a new numpy array
	frame_list = frames[0]
	frame = frame_list[0]
#	 num_bins = frame.total_bins_available
	num_bins = 1
	if mode == 'rx':
		num_bins = 1
	elif mode == 'raw':
		num_bins = 2
	elif mode == 'crop':
		num_bins = 2

#	 num_rows = frame.enabled_rows_per_frame
	num_rows = 2*frame.enabled_rows_per_frame # Nickel full chip hack
	if mode != 'pd':
		max_rows = frame.sensor_frame_images_num_vertical_elements
		num_cols = frame.sensor_frame_images_num_horizontal_elements
		first_row_index = frame.first_valid_row_index
	else:
		max_rows = frame.pd_left_right_images_num_vertical_elements
		num_cols = frame.pd_left_right_images_num_horizontal_elements
		first_row_index = frame.pd_left_right_starting_element_index
	ar = np.zeros((num_frames, num_bins, num_rows, num_cols), dtype=np.int16)

	# copy frame data into the numpy array
	for i in range(num_frames):
		frame = frame_list[i]

		# get a pointer to the CDS data
		byte_ptr = ffi.cast("char *", frame)
		if mode == 'cds' or mode == 'crop':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.cds_frames_base_offset)
		elif mode == 'rx':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.reset_frames_base_offset)
		elif mode == 'raw':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.sensor_phase_samples_base_offset)
		elif mode == 'pd':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.pd_input_frame_base_offset)

		# create a numpy array pointer to our image pointer
		img_buffer = np.frombuffer(ffi.buffer(img_ptr, max_rows * num_cols * num_bins * 2), dtype=np.int16)
		img_buffer = np.reshape(img_buffer, (num_bins, max_rows, num_cols))
		np.copyto(ar[i], img_buffer[:, first_row_index:(first_row_index+num_rows), :])

	# clean up
	lib.quantum_n_frames_free(frame_list)

	# return the numpy array to the user
	return ar

# define a convenience function that creates a numpy array from a series of frames captured
def capture_raw(num_frames, mode='raw'):
	# capture our requested frames into RAM
	num_frames_actually_captured = ffi.new('uint32_t *')
	frames = ffi.new('streaming_frame_header_t ***')
	lib.quantum_capture_n_frames(num_frames, num_frames_actually_captured, frames)
	if num_frames != num_frames_actually_captured[0]:
		print('ERROR - only captured %s of %d frames?' % (num_frames_actually_captured[0], num_frames))
		print('Aligning Laser and then closing program.')
		align_mll()
		time.sleep(2)
		sys.exit()
		#return None

	# create a new numpy array
	frame_list = frames[0]
	frame = frame_list[0]
	num_bins = frame.total_bins_available
	if mode == 'rx':
		num_bins = 1
	elif mode == 'raw':
		num_bins = 10
	num_rows = frame.enabled_rows_per_frame
	max_rows = frame.sensor_frame_images_num_vertical_elements
	num_cols = frame.sensor_frame_images_num_horizontal_elements
	ar = np.zeros((num_frames, num_bins, num_rows, num_cols), dtype=np.int16)

	# copy frame data into the numpy array
	for i in range(num_frames):
		frame = frame_list[i]

		# get a pointer to the CDS data
		byte_ptr = ffi.cast("char *", frame)
		if mode == 'cds':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.cds_frames_base_offset)
		elif mode == 'rx':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.reset_frames_base_offset)
		elif mode == 'raw':
			img_ptr = ffi.cast("int16_t *", byte_ptr + frame.sensor_phase_samples_base_offset)

		# create a numpy array pointer to our image pointer
		img_buffer = np.frombuffer(ffi.buffer(img_ptr, max_rows * num_cols * num_bins * 2), dtype=np.int16)
		img_buffer = np.reshape(img_buffer, (num_bins, max_rows, num_cols))
		np.copyto(ar[i], img_buffer[:, frame.first_valid_row_index:(frame.first_valid_row_index+num_rows), :])

	# clean up
	lib.quantum_n_frames_free(frame_list)

	# return the numpy array to the user
	return ar




##############################################
## Streaming:
## First call start_streaming().
## Then use get_streaming_frames() to grab some frames when you want them.
## When done, call stop_streaming().
##
## get_streaming_frames() sets capture_frames_enable = True, which makes
##	   streaming_callback() start to grab frames as they arrive.

# these globals keep track of streaming state of hardware
streaming_callback_count = 0
streaming = False

# these globals are used to coordinate capturing of frame data
capture_nrows = 0
capture_ncols = 0
capture_nbins = 0
capture_nframes = 0
capture_frame_ndx = 0
capture_image = None
capture_frames_enable = False
abort_streaming = False
req_header = False # requesting a header
current_streaming_frame_header = None

def start_streaming():
	# Start an infinite stream. Once it's running, you can get_streaming_frames()
	global streaming, abort_streaming
	#print("Start streaming")
	
	if not streaming:
		abort_streaming = False
		try:
			ret = lib.quantum_streaming_capture_sequence(streaming_callback, 0, ffi.NULL, 0)
			if ret == lib.LIBQSI_STATUS_SUCCESS:
				streaming = True
				#print("Success starting streaming")
				return True
			else:
				print("Error starting streaming %d" % ret)
				# Can retry here if needed	
				print('Aligning Laser and then closing program.')
				align_mll()
				time.sleep(2)
				sys.exit()
				#return False
		except:
			return False



def stop_streaming():
	global abort_streaming
	#print("Stop streaming")
	
	try:
		if streaming:
			lib.quantum_stream_disable()
			abort_streaming = True
		return True
	except:
		return False
	


# This callback only works once load_headers() has executed
#@ffi.callback("int32_t(libqsi_stream_notify_type_t, libqsi_stream_source_t, uint8_t *, uint32_t, uint32_t, libqsi_frame_type_t, void *)")
@ffi.callback("int32_t(uint32_t, uint32_t, uint8_t *, uint32_t, uint32_t, uint32_t, void *)")
def streaming_callback(notify_type, stream_source, packet_buffer, packet_size, max_packet_size, frame_type, user_defined):
	# This is called every time a frame is available
	global streaming, streaming_callback_count, capture_frame_ndx, capture_frames_enable, current_streaming_frame_header, req_header
	
	ret = lib.STATUSMGR_ACK
	
	if notify_type == lib.LIBQSI_STREAM_NOTIFY_PACKET and frame_type == lib.LIBQSI_FRAMETYPE_PROCESSED_FRAMES:
#		 print('process frame -- notify_type: %s, frame_type: %s' % (notify_type, frame_type))

		streaming_frame_header = ffi.cast("streaming_frame_header_t *", packet_buffer)
		streaming_callback_count += 1
		if req_header:
			current_streaming_frame_header = streaming_frame_header
			req_header = False
		
		if ((capture_frames_enable) and (capture_image is not None) and (capture_nframes > 0)):
			image_frame_callback(streaming_frame_header)
			capture_frame_ndx += 1
			
			if (capture_frame_ndx == capture_nframes):
				capture_frames_enable = False
		
	if ((notify_type == lib.LIBQSI_STREAM_NOTIFY_COMPLETED) or (notify_type == lib.LIBQSI_STREAM_NOTIFY_ABORTED) or (abort_streaming)):
		streaming = False
		ret = lib.STREAMING_CALLBACK_RC_STOP_CAPTURE
	return ret


def image_frame_callback(streaming_frame_header):
	# Grab one of n frames from the buffer and copy it into the capture_image array
	
	frame = streaming_frame_header[0]
	num_bins = frame.total_bins_available
#	 # get a pointer to the CDS data
	byte_ptr = ffi.cast("char *", streaming_frame_header)
	
	mode = 'cds' # cds only for now
	if mode == 'cds':
		img_ptr = ffi.cast("int16_t *", byte_ptr + frame.cds_frames_base_offset)
		max_rows = frame.sensor_frame_images_num_vertical_elements
		max_cols = frame.sensor_frame_images_num_horizontal_elements
		first_row_index = frame.first_valid_row_index
		
	# create a numpy array pointer to our image pointer
	img_buffer = np.frombuffer(ffi.buffer(img_ptr, max_rows * max_cols * num_bins * 2), dtype=np.int16)
	img_buffer = np.reshape(img_buffer, (num_bins, max_rows, max_cols))
	np.copyto(capture_image[capture_frame_ndx], img_buffer[:capture_nbins, first_row_index:(first_row_index+capture_nrows), :capture_ncols])
	return


def streaming_frame_info():
	# Plucks the next streaming frame header from the incoming stream of frames.
	# If streaming is not active, or the function times out waiting for a header,
	# then the function returns None.
	global req_header, current_streaming_frame_header
	streaming_frame_header = None
	if streaming:
		req_header = True
		# Wait for the next header to come in
		for i in range(1000):
			if not req_header:
				streaming_frame_header = current_streaming_frame_header
				current_streaming_frame_header = None
				break
			time.sleep(0.01)

	frame_info = streaming_frame_header[0]
	return frame_info


def get_streaming_frames(frames, bins=None, rows=None, cols=None, verbose=False):
	# Run this after start_streaming()
	global capture_nrows, capture_ncols, capture_nbins, capture_nframes, capture_frame_ndx, capture_frames_enable, capture_image
	nframes = 0
	timeout = 0
	last_frame = 0
	
	# If bins, rows, or cols is not provided, capture the max number
	frame_info = streaming_frame_info()
	max_bins = frame_info.total_bins_available
	enabled_rows = frame_info.enabled_rows_per_frame
	max_cols = frame_info.sensor_frame_images_num_horizontal_elements
	
	if bins is None:
		bins = max_bins
	if rows is None:
		rows = enabled_rows
	if cols is None:
		cols = max_cols
	
	if (streaming and not capture_frames_enable):
		capture_nrows = rows
		capture_ncols = cols
		capture_nbins = bins
		capture_nframes = frames
		capture_frame_ndx = 0
		capture_image = np.zeros((frames, bins, rows, cols), dtype = np.int16)
		capture_frames_enable = True
		
		if verbose:
			print("Capturing %d streaming frames" % capture_nframes)
		
		while timeout < 1000:
			if not capture_frames_enable:
				break
			if (last_frame != capture_frame_ndx):
				last_frame = capture_frame_ndx
				timeout = 0
			timeout += 1
			time.sleep(0.01)

		nframes = capture_frame_ndx
		if (nframes != frames):
			print("failed to capture all requested frames %d %d" % (nframes,frames))
			# Could trim the output array here

		capture_frames_enable = False
	else:
		print("streaming interface stopped %d %d" % (streaming, capture_frames_enable))
		
	image = np.copy(capture_image)
	capture_image = None
		
	return image

###############################################

def set_config(filename):
	#print('setting device config: %s' % filename)
	results = ffi.new('int32_t *')
	rc = lib.quantum_JSON_configuration_from_file(text2cffi(filename), lib.LIBQSI_CFG_ALL, results)
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		desc = lib.quantum_get_status_description(rc)
		print('ERROR failed to load config: ', ffi.string(desc).decode('UTF-8'))
		print('Closing program.')
		sys.exit()
		#return False	
	return True
	
	
def get_sensor_ID():
	rc = lib.quantum_get_sensor_id()
	#print('sensor ID = '+str(rc) )
	return rc

	
def set_mll_atten(percentage_atten):
	atten = ffi.new('float *')
	atten = percentage_atten

	rc = lib.quantum_set_laser_attenuation(atten)	
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print('could not set MLL attenuation!')

def set_mll_power(power_mW):
	power = ffi.new('float *')
	power = power_mW

	rc = lib.quantum_set_requested_laser_output_power(power)   
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print('could not set MLL power!')  
		
def set_mll_power_get_atten(power_mW):
	power = ffi.new('float *')
	power = power_mW

	rc = lib.quantum_set_requested_laser_output_power(power)   
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print('could not set MLL power!') 
		return -1
	else:
		#get attenuator info 
		motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_ATTENUATOR)
		return current_offset
		
		
def get_motor_info(motor_ind):		 
	#define MOTOR_X				1
	#define MOTOR_Y				2
	#define MOTOR_THETA_X		3
	#define MOTOR_THETA_Y		4
	#define MOTOR_ATTENUATOR	5
	#define MOTOR_ICW			6
	#define MOTOR_ROLL			7
	
	deg_step = ffi.new('float *')
	max_step = ffi.new('int32_t *')
	min_step = ffi.new('int32_t *')
	home = ffi.new('int32_t *')
	current_offset = ffi.new('int32_t *')
	coil_sleep = ffi.new('int32_t *')
	coil_max_current = ffi.new('float *')
	lib.quantum_get_motor_info(motor_ind, deg_step, max_step, min_step, home, current_offset, coil_sleep, coil_max_current)

	#print(" Motor {} is at {} with a max of {} and min of {}; home_is_CW: {}; coil_sleep_prec_mod: {}; max_coil_cur: {}".format(motor_ind, current_offset[0], max_step[0],min_step[0], home[0], coil_sleep[0], coil_max_current[0]))
		
	return motor_ind, current_offset[0], coil_sleep[0],coil_max_current[0], min_step[0], max_step[0], deg_step[0]
	
   
def set_motor(motor_ind, new_position):	  
  
	deg_step = ffi.new('float *')
	max_step = ffi.new('int32_t *')
	min_step = ffi.new('int32_t *')
	home = ffi.new('int32_t *')
	current_offset = ffi.new('int32_t *')
	coil_sleep = ffi.new('int32_t *')
	coil_max_current = ffi.new('float *')
	lib.quantum_get_motor_info(motor_ind, deg_step, max_step, min_step, home, current_offset, coil_sleep, coil_max_current)

	step = ffi.new('int32_t *')
	step[0] = 1
	new_offset = ffi.new('int32_t *')
	new_offset[0] = new_position
	lib.quantum_seek_alignment_motor(motor_ind, new_offset[0], step[0], coil_max_current[0], coil_sleep[0], current_offset)
	
	

		
		
		
	

def nios_read(address):
	addrVals = ffi.new('uint32_t **')
	transfer_status = ffi.new('int32_t *')
	lib.quantum_nios_read(address, 1, addrVals, 0, transfer_status)
	if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
		print("failed to read address %s from nios" % address)
		return False
	addr = addrVals[0]
	return addr[0]
	
def nios_write(address, val):
	addrVals = ffi.new('uint32_t **')
	transfer_status = ffi.new('int32_t *')
	lib.quantum_nios_read(address, 1, addrVals, 0, transfer_status)
	if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
		print("failed to read address %s from nios" % address)
		return False
	addr = addrVals[0]
	addr[0] = val
	lib.quantum_nios_write(address, 1, 0, addr, transfer_status)
	if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
		print("failed to write address %s to nios" % address)
		return False
	lib.quantum_free_memory(addrVals[0])
	return True

def set_laser(mode, force=False, user_args=None):
	# define a callback function needed by the falcon library
	@ffi.callback("int32_t(int32_t percentage_complete, const char *brief_info, const char *extended_info, libqsi_status_t sm_status, void *udef_info)")
	def infoCB(percentage_complete, brief_info, extended_info, sm_status, udef_info):
		print('progress: %s%% : %s : %s' % (percentage_complete, tostr(brief_info), tostr(extended_info)))
		return 0

	if mode == 'OFF':
		lib.quantum_set_MCLK_source(lib.LIBQSI_REFSRC_OSCILLATOR)
		wait_locked()
		if force:
			lib.quantum_laser_blocking(lib.LIBQSI_LASER_OFF, infoCB, ffi.NULL, ffi.NULL)
		else:
			lib.quantum_laser_blocking(lib.LIBQSI_LASER_STANDBY, infoCB, ffi.NULL, ffi.NULL)
	else:
		args = '{"stabilization_time":300}'	 # default recommendation is 300 seconds
		
		if user_args is not None:
			args = user_args
		lib.quantum_laser_blocking(lib.LIBQSI_LASER_ON, infoCB, text2cffi(args), ffi.NULL)
		 #lib.quantum_laser(lib.LIBQSI_LASER_ON, infoCB, text2cffi(args), ffi.NULL)
		lib.quantum_set_MCLK_source(lib.LIBQSI_REFSRC_RECOVERED)
		wait_locked()

def disable_laser_lib_shutoff(timeout_seconds):
	lib.quantum_disable_lid_safety(timeout_seconds)
	
def set_laser_tec(new_status):
	# new_status = "pump_on_tec_on" "pump_off_tec_on" "pump_off_tec_off"
	mode = text2cffi(new_status)
	operation_status = ffi.new('int32_t *')
	rc = lib.quantum_tlv_set((lib.SABER_TLV_BASE_INDEX + lib.TLV_SABER_CFG_POWER_MODE), lib.LIBQSI_DEVICE_NIOS, len(mode),operation_status,mode)
	print("rc = {0}".format(rc))

	
def simple_capture():
	cdsData = capture(10, 'cds')
	cdsImg = cdsData.mean(axis=0)
	data = cdsImg[0, :, :]
	print('cds data mean: %s stdev: %s' % (data.mean(), data.std()))


def set_streaming(mode='CDS'):
	lib.quantum_change_dataengine_streaming_mode(lib.DATASTREAM_PROCESSOR_CDS_STREAM)
	lib.quantum_synchronize_fpga_sensor_interface()	 # needed when we change FPGA streaming mode
	wait_locked()
	
def set_CDS_SINGLE_BIN():
	lib.quantum_change_dataengine_streaming_mode(lib.DATASTREAM_PROCESSOR_SINGLE_BIN)
	lib.quantum_synchronize_fpga_sensor_interface()	 # needed when we change FPGA streaming mode
	wait_locked()
	
def set_CROP_RAW():
	lib.quantum_change_dataengine_streaming_mode(lib.DATASTREAM_PROCESSOR_RAW_CROP_STREAM)
	lib.quantum_synchronize_fpga_sensor_interface()	 # needed when we change FPGA streaming mode
	wait_locked()

def set_mclk_offset(n):
	n = int(n)
	# chnage mclk1+ mclk2 (recovered from laser)
	#set_clk_offsets('MCLK', 0x6, [0,n,n,0])
	# change laser trigger 2
	#set_clk_offsets('MCLK', 0x8, [0,0,0,n])
	set_clk_offsets('MCLK', 0x1, [n,0,0,0])  # altnernate mclk sweep.  use negative offsets here (match chewie)

def set_clk_offsets(name, bits, clock_phase_step_array):
	#example: set_clk_offsets('MCLK', 0x9, [i,0,0,i])
	max_movement = ffi.new('int32_t *', 25)
	tvco_read = ffi.new('double *')
	clock_base_offset_array_read = ffi.new('int32_t[4]')
	clock_phase_step_array_read = ffi.new('int32_t[4]')
	
	rc = lib.quantum_timing_clock_set_position(lib.LIBQSI_DEVICE_NIOS,
			text2cffi(name), max_movement, bits, clock_phase_step_array,
			tvco_read, clock_base_offset_array_read, 
			clock_phase_step_array_read)
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		desc = lib.quantum_get_status_description(rc)
		print('ERROR setting mclk phase offset: ', ffi.string(desc).decode('UTF-8'))

def set_clock_base_offsets(name, base_offsets):
	tvco_read = ffi.new('double *')
	base_offsets_read = ffi.new('int32_t[4]')
	steps = ffi.new('int32_t[4]')
	max_movement = ffi.new('int32_t *', 10)

	rc = lib.quantum_timing_clock_set_bases(lib.LIBQSI_DEVICE_NIOS, text2cffi(name), base_offsets, tvco_read, base_offsets_read, steps, max_movement)
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		desc = lib.quantum_get_status_description(rc)
		print('ERROR setting base offsets: ', ffi.string(desc).decode('UTF-8'))










def dateit(d):
	d=int(d)
	if d < 10:
			dud = '0'+str(d)
	else:
		dud = str(d)
	return dud
	
def get_date_time():
	now	 = dt.datetime.now()
	test_str1 = str(str(now.year) + "-"+ "-".join([str(i) for i in [dateit(now.month),dateit(now.day)]]))
	test_str2 = str(str(now.hour) + ":"+ ":".join([str(i) for i in [dateit(now.minute),dateit(now.second)]]))
	test_str = test_str1 + ' ' + test_str2
	image_str = str(str(now.year) + "-"+ "-".join([str(i) for i in [dateit(now.month),dateit(now.day),dateit(now.hour),dateit(now.minute),dateit(now.second)]]))
	test_time = time.time() - 1.58584e9
	return test_str, test_time, image_str
	

def append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_mode_bin,setting,test_duration,test_no,test_fmb,trd):
	f_string = setting['Date_stamp']
	f_time = setting['Time_stamp']
	
	
	parameters=[f_string,f_time,test_duration,setting['Lot'],setting['Wafer'],setting['Chip_position'],cfg.PRODUCTION_TESTER,cfg.PRODUCTS[int(setting['Product_number'])],cfg.PROCESS_STEPS[int(setting['Process_step'])],hard_bin,failure_mode_bin,0,test_fmb,test_no,
				'not_app',parameter_name,
				parameter_value, 'none','not_app','not_app','not_app','none','none','not_app',
				setting['Engineering_Mode'],setting['Efuse_Value'],cfg.TRD_FILES[int(setting['Product_number'])],trd['program_file_rev'][0],cfg.BASE_CONFIGURATION_FILES[int(setting['Product_number'])],setting['Data_file_full_path']]

	return test_data + [parameters]
				   
					
def append_test_results(test_data,parameter_value,results,trd,setting,test_duration):

	#trd file columns
	#program_file_rev	test_no	module_file_rev config_file	module_name	parameter_name	hard_bin	failure_mode_bin	parameter_units	product	test_performed	information_only	stop_on_fail	low_limit	high_limit

	
	#setting
	# Lot, Wafer, Data_file, Chip_position, Data_file_full_path, PRODUCTION_TESTER, TRD_FILE, PRODUCT, PROGRAM_FILE, ENGINEERING, EFUSE, Data_directory

	#results = [ hard_bin,	failure_mode_bin, info_only_hard_bin,	info_only_failure_mode]
	
	#test file columns
  
	#TEST_DATA_COLUMNS = ['TIMESTAMP','test_time','test_duration','lot','wafer','chip','tester','product','process_step','chip_hard_bin','chip_failure_mode_bin','chip_failure_mode_bin','trd_hard_bin','trd_failure_mode_bin',
							  #	 'test_no','test_type','parameter_name','parameter_value','parameter_unit','test_performed','information_only',
							  #	 'stop_on_fail','low_limit','high_limit','save_image','engineering_mode','Write_Efuse','trd_file','program_file_rev','cmos_configuration_file','Data_file_full_path']
	
	#the columns to be saved are in qsi_cfg.py TEST_DATA_COLUMNS
	


	
	
	f_string = setting['Date_stamp']
	f_time = setting['Time_stamp']
	
	


	parameters=[f_string,f_time,test_duration,setting['Lot'],setting['Wafer'],setting['Chip_position'],cfg.PRODUCTION_TESTER,cfg.PRODUCTS[int(setting['Product_number'])],cfg.PROCESS_STEPS[int(setting['Process_step'])],results[0],results[1],trd['hard_bin'][0],
				trd['failure_mode_bin'][0],trd['test_no'][0],trd['test_type'][0],trd['parameter_name'][0],
				parameter_value, trd['parameter_units'][0],trd['test_performed'][0],trd['information_only'][0],trd['stop_on_fail'][0],trd['low_limit'][0],trd['high_limit'][0],
				trd['save_image'][0],setting['Engineering_Mode'],setting['Efuse_Value'],cfg.TRD_FILES[int(setting['Product_number'])],trd['program_file_rev'][0],cfg.BASE_CONFIGURATION_FILES[int(setting['Product_number'])],setting['Data_file_full_path']]
	
   
	return test_data + [parameters]
	

		
		
		
		
def assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,test_duration):

	#figure outwhether test limits are applied or parameter_out is a boolean
	test_out = True
	
	if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
		if t['test_type'][0]=='parameter':
			test_out = False
			if t['low_limit'][0]=='none' and t['high_limit'][0]=='none':  #no limits on this parameter
				test_out = True
			elif t['low_limit'][0]=='none' and t['high_limit'][0]!='none': #only high limit
				if float(parameter_out) <= float(t['high_limit'][0]):
					test_out = True
			elif t['low_limit'][0]!='none' and t['high_limit'][0]=='none': #only low limit
				if float(parameter_out) >= float(t['low_limit'][0]):
					test_out = True
			else:  #both limits
				if float(parameter_out) >= float(t['low_limit'][0]) and float(parameter_out) <= float(t['high_limit'][0]):
					test_out = True			  
		else:  #test is pass_fail type
			if parameter_out:
				test_out = True
				parameter_out = 1
			else:
				test_out = False
				parameter_out = 0

  
		if is_yes(t['test_performed'][0]): #the test is in the TRD file and is done	 
			if not test_out: #test failed  
				if is_yes(t['information_only'][0]):
					#act like the test passes
					results = [hard_bin,failure_mode_bin,1,0]
					test_data = append_test_results(test_data,parameter_out,results,t,setting,test_duration)
				else:
					if is_yes(t['stop_on_fail'][0]): #stop on fail so load up current failure modes
						#results = [ hard_bin,	failure_mode_bin, info_only_hard_bin,	inffo_only_failure_mode]
						results = [int(t['hard_bin'][0]),fmb,int(t['hard_bin'][0]),fmb]
						test_data = append_test_results(test_data,parameter_out,results,t,setting,test_duration)
						continue_test = False

						hard_bin = int(t['hard_bin'][0])
						failure_mode_bin = fmb
					else:
						hard_bin = int(t['hard_bin'][0])
						failure_mode_bin = fmb
						results = [int(t['hard_bin'][0]), fmb,int(t['hard_bin'][0]),fmb]				 
						test_data = append_test_results(test_data,parameter_out,results,t,setting,test_duration)
			else:  #test passed
				#results = [ hard_bin,	failure_mode_bin, info_only_hard_bin,	inffo_only_failure_mode]
				results = [hard_bin,failure_mode_bin,1,0]
				test_data = append_test_results(test_data,parameter_out,results,t,setting,test_duration)
		else: #the test is in the TRD file but is not done so just add a line
			#results = [ hard_bin,	failure_mode_bin, info_only_hard_bin,	inffo_only_failure_mode]
			results = [hard_bin,failure_mode_bin,0,0]
			parameter_out = -1
			#test_data = append_test_results(test_data,parameter_out,results,t,setting,test_duration)
	 

	
	
	return test_data, continue_test, hard_bin, failure_mode_bin
	
	



def build_regs():
	global default_reg_file
	global default_regs
	global default_bits
	global echo
	
	reg		   = namedtuple('reg', ['name','base_addr','value','access'])
	bitfield   = namedtuple('bifield',['name','position','max_value','value','access'])

	c0_addr_msb = 0x00
	c1_addr_msb = 0x01 << 8
	c2_addr_msb = 0x02 << 8
	c3_addr_msb = 0x03 << 8
	global_addr_msb = 0x10 << 11

	f = open(default_reg_file)
	for row in f:
		cell = row.split(',')
		if str(cell[0]) != ' ':
			# found a register, grab the "register" namedtuple elements
			reg_name	  = cell[2]
			reg_base_addr = int(cell[0])
			reg_value	  = int(cell[4],2)
			if 'RO' in cell[7]:
				reg_access = 'RO'
			else:
				reg_access = 'RW'
			bit_parent = cell[2]
			bitfields_str = cell[8].split('\n')
			#bitfields = bitfields_str[0]
			bitfield_list = bitfields_str[0].split(' ')
			# now the individual bitfields into another list of named tuples
			# the bitfield list is ordered msb to lsb, calculate position and range based on list order and existence of [x] in names
			bit_pos	  = 16
			bit_range = 16
			for bf in bitfield_list:
				bf_name = bf.split('[')
				bf_width = 1
				if ('[' in bf) and (':' in bf):
					bf_bits = bf.split(':')
					bf_bits = bf_bits[0].split('[')
					bf_width = int(bf_bits[1]) + 1
				bit_pos	  = bit_pos - bf_width
				bit_max = (0x01 << bf_width) - 1
				#create a bit mask to extract this bitfield's default
				mask=bit_max << bit_pos
				bit_default = (reg_value & mask) >> bit_pos
				# populate bitfield named tuple.
				if 'C' in cell[7]:
					default_bits.append(bitfield(name='c0.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
					default_bits.append(bitfield(name='c1.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))					
					default_bits.append(bitfield(name='c2.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))					
					default_bits.append(bitfield(name='c3.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))					
				if 'T' in cell[7]:
					default_bits.append(bitfield(name='global.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
			# populate registers named tuple. CRW, CRO, TRW, and TRO should be the only values for "register type" field cell[7]
			if 'C' in cell[7]:
				# first the main registers into one list of named tuples
				default_regs.append(reg(name='c0.'+reg_name,base_addr=(reg_base_addr | c0_addr_msb),value=reg_value,access=reg_access))
				default_regs.append(reg(name='c1.'+reg_name,base_addr=(reg_base_addr | c1_addr_msb),value=reg_value,access=reg_access))
				default_regs.append(reg(name='c2.'+reg_name,base_addr=(reg_base_addr | c2_addr_msb),value=reg_value,access=reg_access))
				default_regs.append(reg(name='c3.'+reg_name,base_addr=(reg_base_addr | c3_addr_msb),value=reg_value,access=reg_access))
			if 'T' in cell[7]:
				default_regs.append(reg(name='global.'+reg_name,base_addr=(reg_base_addr | global_addr_msb),value=reg_value,access=reg_access))
				
			default_regs = sorted(default_regs,key=attrgetter('base_addr'))
			default_bits = sorted(default_bits,key=attrgetter('name'))

			if echo:
				for entry in default_regs:
					print(entry.name)	 
				for entry in default_bits:
					print(entry.name)


					
def char_initialize():
	global nickel_handle
	# initialize and send base configuration file
	try:
		initialized = init()
	except:
		return False
	if not initialized:
		#sys.exit()
		return False
	try:
		chip_id = ffi.cast('uint32_t', 0x1C00)
		nickel_handle = lib.quantum_nickel_handle_from_chipid(chip_id)
		build_regs()
		return True
	except:
		return False
		
		

	
		
		
def read_config(filename):
	with open(filename) as f:
		config_temp = json.load(f)
	f.close()
	return config_temp
	
def write_config(filename, cfg):
	with open(filename, 'w') as outfile:
		json.dump(cfg, outfile, sort_keys = False, indent = 2)		
	outfile.close()
		
def spi_get(address):
	read_val = ffi.new('uint16_t *')
	addr	 = text2cffi(address)
	ret = lib.quantum_nickel_get_from_device_using_dot_notation(nickel_handle,addr,read_val)
	if ret != lib.LIBQSI_STATUS_SUCCESS:
		print('getdevice ' + ' ' + address + 'FAILED')
	return read_val[0]
	
def ROI_Ntb(func):
	def func_wrapper(ROI, Ntb, *args, **kwargs):
		frm = func(*args, **kwargs)
		return frm[0, 0:Ntb, ROI[0]:ROI[1]:ROI[2], ROI[3]:ROI[4]:ROI[5]]
	return func_wrapper		  
		
def get_one_full_frm(mode='cds'):
	max_tries = 10
	i = 0
	frm = capture(1, mode = mode)
	while (frm is None) and (i < max_tries):
		print("Retry capture")
		frm = capture(1, mode = mode)
		i += 1

	return np.double(frm)		
	
		
def get_one_frm(ROI, Ntb, mode = 'cds'):
	return ROI_Ntb(get_one_full_frm)(ROI, Ntb, mode)
	
def set_rst_level(ROI, Ntb, target,adcBit):
	global vref_prior
	if target <= 0:	 # If target is negative or 0, do nothing.
		print('VREFSH = ' + str(get_Vrefsh()) + ', RST_LEVEL = ' + str(np.mean(get_one_frm(ROI, Ntb, 'rx'))))
		return
	# use previous die vref_prior, but use config default for 1st die
	if vref_prior == -99:
		vref = get_Vrefsh()
	else:
		vref = vref_prior
		if set_Vrefsh(vref) == False:
			return False

	print('Original vref_ctrl = '+str(vref))

	set_CROP_RAW()

	rst_fr = get_one_frm(ROI, Ntb, 'crop')
	#rst_fr = rst_fr[:, :, :, 0:(rst_fr.shape[-1] / 16 * 15)]

	rst_cands = np.zeros(4)

	if Ntb>1:
		rst_cands[0] = np.mean(rst_fr[0].flatten())
		rst_cands[1] = np.mean(rst_fr[1].flatten())
		
		print('original bin0 reset mean = '+str(rst_cands[0]))
		print('original bin1 reset mean = '+str(rst_cands[1]))
	else:
		rst_cands[0] = np.mean(rst_fr[0].flatten())
		rst_cands[1] = 2**adcBit  # 2^adcBit - bug ?
		print('original bin0 reset mean = '+str(rst_cands[0]))
	
	
	
	#if np.min(rst_cands[0:2]) < target:
	#if np.mean(rst_cands[0:2]) < target:
	if np.mean(rst_cands[0]) < target:
		j = 0
		#while np.min(rst_cands[0:2]) < target and j<5:
		while np.min(rst_cands[0]) < target and j < MAX_AUTO_EXP_CYCLES:

			rst_cands[2] = rst_cands[0] #storing previous iteration values
			rst_cands[3] = rst_cands[1] #storing previous iteration values
		   
			vref += 1
			print('New vref_ctrl = '+str(vref), 'vref_range = '+str(qsi_helpers.get_vref_range()))
			if set_Vrefsh(vref) == False:
				return False
			if cfg.chip_type!='NickelG':
				set_CROP_RAW()
			rst_fr = get_one_frm(ROI, Ntb, 'crop')
			if Ntb>1:
				rst_prev0 = rst_cands[0]
				rst_prev1 = rst_cands[1]
				rst_cands[0] = np.mean(rst_fr[0].flatten())
				rst_cands[1] = np.mean(rst_fr[1].flatten())
				print('New bin0 reset mean = '+str(rst_cands[0]))
				#print('New bin1 reset mean = '+str(rst_cands[1]))
			else:
				rst_cands[0] = np.mean(rst_fr[0].flatten())
				#rst_cands[1] = 2^adcBit
				print('New bin0 reset mean = '+str(rst_cands[0]))
			
			j +=1
		vref_last = vref - 1
	else:
		j = 0
		while np.mean(rst_cands[0]) >= target and j < MAX_AUTO_EXP_CYCLES:
			rst_cands[2] = rst_cands[0] #storing previous iteration values
			#rst_cands[3] = rst_cands[1] #storing previous iteration values
			
			vref -= 1
			print('New vref_ctrl = '+str(vref), 'vref_range = '+str(qsi_helpers.get_vref_range()))

			if set_Vrefsh(vref) == False:
				return False
			if cfg.chip_type!='NickelG':
				set_CROP_RAW()
			rst_fr = get_one_frm(ROI, Ntb, 'crop')
			#rst_fr = rst_fr[:,:,0:(rst_fr.shape[-1]/16*15)]

			if Ntb>1:
				rst_cands[0] = np.mean(rst_fr[0].flatten())
				rst_cands[1] = np.mean(rst_fr[1].flatten())
				#print('New bin0 reset mean = '+str(rst_cands[0]))
				#print('New bin1 reset mean = '+str(rst_cands[1]))
			else:
				rst_cands[0] = np.mean(rst_fr[0].flatten())
				#rst_cands[1] = 2**adcBit  # 2^adcBit, assume bug
				print('New bin0 reset mean = '+str(rst_cands[0]))
			
			j += 1
			
		vref_last = vref + 1		
	
	#keep_current = np.abs(np.min(rst_cands[0:2]) - target) <  np.abs(np.min(rst_cands[2:4]) - target)
	keep_current = np.abs(np.min(rst_cands[0]) - target) < np.abs(np.min(rst_cands[2]) - target)

	if keep_current:
		if Ntb>1:
			print('final vref_ctrl = ' + str(vref) + ', RST_LEVEL_bin0 = ' + str(round(rst_cands[0],1)) + ' RST_LEVEL_bin1 = ' + str(round(rst_cands[1],1)))
		else:
			print('final vref_ctrl = ' + str(vref) + ', RST_LEVEL_bin0 = ' + str(round(rst_cands[0],1)) )
		vref_prior = vref
	else:
		if set_Vrefsh(vref) == False:
				return False
		if Ntb>1:
			print('final vref_ctrl = ' + str(vref_last) + ', RST_LEVEL_bin0 = ' + str(round(rst_cands[2],1)) + ' RST_LEVEL_bin1 = ' + str(round(rst_cands[3],1)))
		else:
			print('final vref_ctrl = ' + str(vref_last) + ', RST_LEVEL_bin0 = ' + str(round(rst_cands[2],1)) )
		vref_prior = vref_last
	if cfg.chip_type != 'NickelG':
		set_CDS_SINGLE_BIN()
	#return get_Vrefsh()
	return True
		
def get_Vrefsh():	
	result = spi_get('c0.afe_ctrl_5.vref_ctrl')
	if get_vref_range() == 0:
		result -= 17 #29
	return result
	
def set_Vrefsh(integer):
	# if get_vref_range() == 1 or get_vref_range() == 2:
	# 	print('vref_range not supported.')
	# 	return False
		#raise Exception('vref_range not supported.')
	if integer < -29 or integer > 31:
		print('vref_ctrl must be in range of [-29,31].')
		return False
		#raise Exception('vref_ctrl must be -29 ~ 31.')
	#print('Vref_ctrl is set to ' + str(integer))
	if integer < 0:
		if get_vref_range() == 3:
			if cfg.chip_type!='NickelG':
				set_vref_range(1)
				print('Vref_range set to 1')
			integer += 10
		elif get_vref_range() in [1,2]:
			if cfg.chip_type!='NickelG':
				set_vref_range(0)
				print('Vref_range set to 0')
			integer += 10
	elif integer > 27:
		if get_vref_range() < 3:
			if cfg.chip_type!='NickelG':
				print('Set vref_range to 3)')
				set_vref_range(3)
			integer -= 15

	if cfg.chip_type=='NickelG':
		config_temp = read_config(cfg.CONFIGURATION_FILE_PATH + cfg.OFF_CHIP_CDS_CONFIG_PATH)
	else:
		config_temp = read_config(cfg.CURRENT_CONFIG_PATH )

	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["0"]["vref_ctrl"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["1"]["vref_ctrl"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["2"]["vref_ctrl"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["3"]["vref_ctrl"]= int(integer)
	if cfg.chip_type=='NickelG':
		write_config(cfg.CURRENT_CONFIG_PATH_OFF_CHIP_CDS , config_temp)
		set_config(cfg.CURRENT_CONFIG_PATH_OFF_CHIP_CDS)
	else:
		write_config(cfg.CURRENT_CONFIG_PATH , config_temp)
		set_config(cfg.CURRENT_CONFIG_PATH )

	return True
	
def get_vref_range():
	return spi_get('c0.afe_ctrl_5.vref_range')
	
def set_vref_range(integer):

	config_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["0"]["vref_range"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["1"]["vref_range"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["2"]["vref_range"]= int(integer)
	config_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["3"]["vref_range"]= int(integer)
	write_config(cfg.CURRENT_CONFIG_PATH , config_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )
	#print('Vref_range is set to ' + str(integer)) 
		

	

	
def is_yes(val):
	if val=='YES' or val=='Y' or val=='y' or val=='Yes' or val=='yes' or val=='1' or val=='1.0':
		return True
	else:
		return False
		
def is_no(val):
	if val=='NO' or val=='N' or val=='n' or val=='No' or val=='no' or val=='0' or val=='0.0':
		return True
	else:
		return False
		
		
def copy_wo_replace(file1,dir2,num_tries):
	#file1 is the full path name of the file where it resides 
	file_name = os.path.split(file1)[1]
	new_file_name = os.path.join(dir2,file_name)
	
	if	not os.path.exists(new_file_name):	
		shutil.copy(file1,new_file_name)
	else:
		i =1
		file_prefix = file_name.split('.')[0]
		file_suffix = file_name.split('.')[1]
		while i<num_tries:	#give up after num_tries times
			new_file_name = os.path.join(dir2,file_prefix+'_'+str(i)+'.'+file_suffix)
			if	not os.path.exists(new_file_name):	
				shutil.copy(file1,new_file_name)
				return
			else:
				i+=1

def copy_conditional(file1,dir2):
	#file1 is the full path name of the file where it resides 
	file_name = os.path.split(file1)[1]
	new_file_name = os.path.join(dir2,file_name)
	
	if	not os.path.exists(new_file_name):	
		shutil.copy(file1,new_file_name)
		  
				
def set_SB_mode():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Trigger_Source"]= 0
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )	  

def set_PP_mode():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Trigger_Source"]= 1
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )   

def get_PP_mode():
	#returns 1 if PP mode, 0 if single bin mode
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	return cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Trigger_Source"]
	 

		  
def coarse_mll_alignment():
	print('Performing Coarse Laser Alignment, this may take 2+ minutes!')
	ret = lib.quantum_coarse_alignment_blocking(ffi.NULL, ffi.NULL, ffi.NULL)
	if ret == lib.LIBQSI_STATUS_SUCCESS:
		return True
	else:
		return False
	
	
	
	"""
	# define a callback function needed by the falcon library
	@ffi.callback("int32_t(int32_t percentage_complete, const char *brief_info, const char *extended_info, libqsi_status_t sm_status, void *udef_info)")
	def infoCB(percentage_complete, brief_info, extended_info, sm_status, udef_info):
		print('progress: %s%% : %s : %s' % (percentage_complete, tostr(brief_info), tostr(extended_info)))
		return 0
   
	#lib.quantum_coarse_alignment_nonblocking(ffi.NULL, infoCB, ffi.NULL)
	thread = threading.Thread(target=lib.quantum_coarse_alignment_nonblocking(ffi.NULL, infoCB, ffi.NULL))
	thread.join()
	thread.start()
	"""
	
def get_voltage(target_name):  
	# Read and display the	value for the supply
	try:
		read_val  = ffi.new('float *')
		supply_name = text2cffi(target_name)
		lib.quantum_voltage_get(supply_name, read_val)
		return read_val[0]
	except:
		return -10.0

def m_get(name, monitor_type): #read out monitored power supply voltage/Current
	'''
	Display a power monitor.

	Parameters:
		name		 - Name of the power monitor
		monitor_type - "V" for voltage, "I" for current, "VI" for voltage and current

	Example:
		m_get("12V","VI")
	'''
	# Read a monitored value
	#monitor_name = text2cffi('VA18')
	try:
		monitor_name = text2cffi(name)
		monitor_val = ffi.new('monm_information_t *')

		lib.quantum_get_monitor_info(monitor_name, monitor_val)

		if "V" in monitor_type:
			# Voltage monitor uses index 0
			#print(str(ffi.string(monitor_val.name), 'utf-8'), "Voltage Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[0].act, monitor_val.entry[0].ref_val, monitor_val.entry[0].avg))

			return	"{0:2.3f}".format(monitor_val.entry[0].act)
			
		if "I" in monitor_type:
			# Current monitor uses index 1
			#print (str(ffi.string(monitor_val.name), 'utf-8'), "Current Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[1].act, monitor_val.entry[1].ref_val, monitor_val.entry[1].avg))
			return "{0:2.3f}".format(monitor_val.entry[1].act)
			
	except:
		return -10.0
	
def chip_power_enable_disable(power_flag): #0 to disable, 1 to enable		
	lib.quantum_manually_set_chip_power_enable(power_flag)

	   
def get_sensor_chip_information():
	target = ffi.new('char **')
	lib.quantum_get_sensor_chip_information(target)
	print(target[0])
	lib.quantum_free_memory(target)


def get_chip_temperatures():
	temperature1 = temperature2 = -20.0
	target_database = lib.LIBQSI_TLVDB_CM
	tlv_number1 = lib.TLV_STAT_SENSOR_TEMP1
	tlv_number2 = lib.TLV_STAT_SENSOR_TEMP2
	temperature = 0.0;
	read_len  = ffi.new('int32_t *')
	data = ffi.new('char **')

	rc = lib.quantum_tlv_ez_get(target_database, tlv_number1, read_len, data)
	if rc == lib.LIBQSI_STATUS_SUCCESS:
		temp_string = tostr(data[0])
		if temp_string == "OPEN" or temp_string == "SHORT" or temp_string == "N/A":
			temperature1 = -10.0
		else:
			temperature1 = float(temp_string)
			
	rc = lib.quantum_tlv_ez_get(target_database, tlv_number2, read_len, data)
	if rc == lib.LIBQSI_STATUS_SUCCESS:
		temp_string = tostr(data[0])
		if temp_string == "OPEN" or temp_string == "SHORT" or temp_string == "N/A":
			temperature2 = -10.0
		else:
			temperature2 = float(temp_string)
	return temperature1, temperature2


def set_temperature(temp):
	if temp < 15 or temp > 35:
		raise Exception('Temperature setting point must be 15 ~ 35 C')
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	cfg_temp["Configuration_Records"]["PID_Configurations"]["Sensor_TEC"]["Sp"] = float(temp)
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )
	
def set_gain_register(gain):
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	cfg_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["0"]["pga_gain"]= int(gain)
	cfg_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["1"]["pga_gain"]= int(gain)
	cfg_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["2"]["pga_gain"]= int(gain)
	cfg_temp["Configuration_Records"]["Chip_Configuration"]["Registers"]["chiplet_registers"]["3"]["pga_gain"]= int(gain)
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )
	
def get_chip_set_voltage(name):
	if name in ['VDAC','VA18','VD18','VSUB','VNEG','B0_L_VHI','B12_L_VHI','B0_R_VHI','B12_R_VHI','VDRAIN','VDDP','VDAC_NEG','VEFUSE',
					'B0_L_OUT_DAC','B1_L_OUT_DAC','B2_L_OUT_DAC','B0_R_OUT_DAC','B1_R_OUT_DAC','B2_R_OUT_DAC',
					'B0_R_H_DAC','B0_R_L_DAC','B1_R_H_DAC','B1_R_L_DAC','B2_R_H_DAC','B2_R_L_DAC',
					'B0_L_H_DAC','B0_L_L_DAC','B1_L_H_DAC','B1_L_L_DAC','B2_L_H_DAC','B2_L_L_DAC']:
		cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
		return cfg_temp["Configuration_Records"]["Power_Configuration"]["Supplies"][name] 
	else:
		print('not a chip voltage setting')
		return -1
	   
	   
	
def set_chip_voltage(name,V):
	if name in ['VDAC','VA18','VD18','VSUB','VNEG','B0_L_VHI','B12_L_VHI','B0_R_VHI','B12_R_VHI','VDRAIN','VDDP','VDAC_NEG','VEFUSE',
					'B0_L_OUT_DAC','B1_L_OUT_DAC','B2_L_OUT_DAC','B0_R_OUT_DAC','B1_R_OUT_DAC','B2_R_OUT_DAC',
					'B0_R_H_DAC','B0_R_L_DAC','B1_R_H_DAC','B1_R_L_DAC','B2_R_H_DAC','B2_R_L_DAC',
					'B0_L_H_DAC','B0_L_L_DAC','B1_L_H_DAC','B1_L_L_DAC','B2_L_H_DAC','B2_L_L_DAC']:
					
		cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )	 
		cfg_temp["Configuration_Records"]["Power_Configuration"]["Supplies"][name]= float(V)

		write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
		set_config(cfg.CURRENT_CONFIG_PATH )
	else:
		print('not a chip voltage setting')
		
		
	
	
	
	
def set_blk_row(blk_row):
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]= int(blk_row)
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin1"]= int(blk_row)
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )

def get_blk_row():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH )
	return cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]
	
	
def get_readout_row():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	return cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Readout"]

def get_sample_phase():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	return cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phases"] 

def get_tint():
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	sample_phase = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phases"]
	col_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Valid_Columns"] + cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Blanking"] 
	row_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Readout"] + cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]
	ADC_clock_freq = cfg_temp["Configuration_Records"]["Clocks"]["Master_Clock"]["Output_Freq1"]
	
	# if cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Trigger_Source"]==1: #PP mode
	# 	PP_mult = 2.0
	# else:
	# 	PP_mult = 1.0
	if cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_Start"]==\
			cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_End"]: #PP mode
		PP_mult = 1.0   # Non-ping-pong mode
	else:
		PP_mult = 2.0   # ping-pong mode

	return PP_mult * float(row_num) * float(sample_phase) * float(col_num) /  float(ADC_clock_freq) * 1000.0 # unit in millisec	 
	
	
def get_min_tint(current_tint):

	#set to min blanking rows
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]=MIN_BLANK_ROWS
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin1"]=MIN_BLANK_ROWS
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )
	min_tint = get_tint()
	
	#set back to current tint
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	sample_phase = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phases"]
	col_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Valid_Columns"] + cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Blanking"] 
	row_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Readout"] 
	ADC_clock_freq = cfg_temp["Configuration_Records"]["Clocks"]["Master_Clock"]["Output_Freq1"]
	
	# if cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Trigger_Source"]==1: #PP mode
	# 	PP_mult = 2.0
	# else:
	# 	PP_mult = 1.0
	if cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_Start"]==\
			cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_End"]: #PP mode
		PP_mult = 1.0   # Non-ping-pong mode
	else:
		PP_mult = 2.0   # ping-pong mode

	blanks = float(current_tint)*float(ADC_clock_freq)/1000.0/float(col_num)/PP_mult/ float(sample_phase) - float(row_num) 
	if blanks < MIN_BLANK_ROWS:
		blanks = MIN_BLANK_ROWS
		
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]=int(blanks)
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin1"]=int(blanks)
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH )
	
	return min_tint
	
  
def set_tint(target_tint_msec):
	cfg_temp = read_config(cfg.CURRENT_CONFIG_PATH)
	sample_phase = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phases"]
	col_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Valid_Columns"] + \
			  cfg_temp["Configuration_Records"]["Timing_Generator"]["Sample_Phase_Blanking"]
	row_num = cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Readout"] 
	ADC_clock_freq = cfg_temp["Configuration_Records"]["Clocks"]["Master_Clock"]["Output_Freq1"]
	
	if cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_Start"]==\
			cfg_temp["Configuration_Records"]["Clocks"]["B_Clock"]["Pattern_End"]: #PP mode
		PP_mult = 1.0   # Non-ping-pong mode
	else:
		PP_mult = 2.0   # ping-pong mode
	#frame_tint_msec = float(target_tint_msec) / PP_mult
	blanks = float(target_tint_msec)*float(ADC_clock_freq)/1000.0/float(col_num)/PP_mult/float(sample_phase) - float(row_num)#
	#blanks = (float(target_tint_msec) * (float(ADC_clock_freq) / 1000.0 / float(col_num) / float(sample_phase))) - float(row_num)

	if blanks < MIN_BLANK_ROWS:
		blanks = MIN_BLANK_ROWS
		
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin0"]=int(blanks)
	cfg_temp["Configuration_Records"]["Timing_Generator"]["Rows_Blanked_Bin1"]=int(blanks)
	write_config(cfg.CURRENT_CONFIG_PATH , cfg_temp)
	set_config(cfg.CURRENT_CONFIG_PATH)
	
	return
	
	
def fit_mclk(y_bin0,y_bin1,mclk_step,m_beg,m_end,knee0,amp0,bgnd0,tau0,res0,file_name,fig_title,save_fig,test_conditions,rej_bin,rej_mclk):
	#rej_bin and rej_mclk are the bin and mclk value that rejection will be calculated in order to find the #photons that illuminated the chip
	#print(y_bin0)
	#print(y_bin1)
	
	def interpolate(x,y_bin,x_rej):
		idx1 = (np.abs(x-x_rej)).argmin()
		x1 = float(x[idx1])
		y1 = float(y_bin[idx1])
		x0 = float(x[idx1-1])
		y0 = float(y_bin[idx1-1])
		x2 = float(x[idx1+1])
		y2 = float(y_bin[idx1+1])	
		if x_rej>x1:
			y = y1 + (y2-y1)/(x2-x1)*(x_rej-x1)
		else:
			y = y0 + (y1-y0)/(x1-x0)*(x_rej-x0)
		return(y)
	 
	def funcexp1(t,x0,a1,t1,bgnd,t0):  #t0 is the resolution function width
		y = []
		for tt in t:
			y = y + [bgnd + a1/2.0*special.erfc((tt-x0)/t0)+a1/2.0*special.erfc((t0/2.0/t1)-(tt-x0)/t0)*np.exp(t0*t0/4.0/t1/t1-(tt-x0)/t1)]
		return	y
	
	def funcexp2(t,x0,a1):	#t0 is the resolution function width
		t0 = 20.0
		t1 = 20.0
		bgnd=0.0
		y = []
		for tt in t:
			y = y + [bgnd + a1/2.0*special.erfc((tt-x0)/t0)+a1/2.0*special.erfc((t0/2.0/t1)-(tt-x0)/t0)*np.exp(t0*t0/4.0/t1/t1-(tt-x0)/t1)]
		return	y
	
	mclk_offsets = [0,-200,200,-400,400]
	for mclk_offset in mclk_offsets:
	
		try:
		#if 1:
			warnings.filterwarnings("ignore") 
			x = np.arange(test_conditions['MCLK start'],test_conditions['MCLK start'] + len(y_bin1)*mclk_step,mclk_step)					
			idx0 = (np.abs(x-m_beg)).argmin()
			idx1 = (np.abs(x-m_end)).argmin()
					
			yy = y_bin1[idx0:idx1]
			xx_bin1 = x[idx0:idx1]
			

			
			#fit two parameters knee + amp first
			params1 = [knee0+mclk_offset,amp0]
			param_bounds1 = [[1000.0,0.0],[2500.0,1000.0]]
			popt, pcov = curve_fit(funcexp2, xx_bin1,yy, p0=params1, bounds=param_bounds1 )
			
			#params0 = (x0,a1,t1, bgnd,t0)	
			params0 = (popt[0],popt[1],tau0,bgnd0,res0)
			param_bounds=([1000.0,0.0,0.1,-50.0,0.01],[2500.0,500.0,200.0,500.0,20.0])
			popt, pcov = curve_fit(funcexp1, xx_bin1,yy, p0=params0, bounds=param_bounds )
			
			param_bounds=([1000.0,0.0,0.1,-50.0,0.01],[2500.0,500.0,200.0,500.0,100.0])
			popt, pcov = curve_fit(funcexp1, xx_bin1,yy, p0=popt, bounds=param_bounds )
			
			param_bounds=([1000.0,0.0,0.1,-50.0,0.01],[2500.0,500.0,200.0,500.0,200.0])
			popt, pcov = curve_fit(funcexp1, xx_bin1,yy, p0=popt, bounds=param_bounds )

			knee1 = popt[0]
			amp1 = popt[1]
			tau1 = popt[2]
			bgnd1 = popt[3]
			res1 = popt[4]

			y_fit_bin1=funcexp1(xx_bin1,popt[0],popt[1],popt[2],popt[3],popt[4])	

			#find median etc for bin0
			beg_fit = m_beg-650
			end_fit = knee0+100


									
			idx0 = (np.abs(x-beg_fit)).argmin()
			idx1 = (np.abs(x-end_fit)).argmin()
					
			yy = y_bin0[idx0:idx1]
			xx_bin0 = x[idx0:idx1]

							
			params0 = (knee0-650,amp0,tau0, bgnd0,res0)	   
			popt, pcov = curve_fit(funcexp1, xx_bin0,yy, p0=params0, bounds=param_bounds )
			knee0 = popt[0]
			amp0 = popt[1]
			tau0 = popt[2]
			bgnd0 = popt[3]
			res0 = popt[4]

			MCLK_diff = knee1 - knee0

			#bin0
			x_max_bin0 = knee0 - 300 #changed to 300 from 200 2020-11-04
			y_max_bin0 = funcexp1([x_max_bin0,x_max_bin0],knee0,amp0,tau0,bgnd0,res0)[0]
			
			#find MCLK set point at 1nsec above bin0 knee position
			MCLK_set = knee0 + 1.0 * 100 / 0.305
			#y_rej_bin0 = funcexp1([MCLK_set,MCLK_set],knee0,amp0,tau0,bgnd0,res0)[0]
			#rejection_bin0_1nsec = y_max_bin0/y_rej_bin0
			rejection_bin0_1nsec = y_max_bin0/interpolate(x,y_bin0,MCLK_set)

			#find MCLK set point at 0.5nsec above bin1 knee position
			MCLK_set = knee0 + 0.5 * 100 / 0.305
			#y_rej_bin0 = funcexp1([MCLK_set,MCLK_set],knee0,amp0,tau0,bgnd0,res0)[0]
			#rejection_bin0_0p5nsec = y_max_bin0/y_rej_bin0
			rejection_bin0_0p5nsec = y_max_bin0/interpolate(x,y_bin0,MCLK_set)
			
			#find MCLK set point at 0.25nsec above bin1 knee position
			MCLK_set = knee0 + 0.25 * 100 / 0.305
			#y_rej_bin0 = funcexp1([MCLK_set,MCLK_set],knee0,amp0,tau0,bgnd0,res0)[0]
			#rejection_bin0_0p25nsec = y_max_bin0/y_rej_bin0
			rejection_bin0_0p25nsec = y_max_bin0/interpolate(x,y_bin0,MCLK_set)
			
			if rej_bin==0:
				#find MCLK at alignment value
				MCLK_set = rej_mclk
				y_rej_bin0_old = funcexp1([MCLK_set,MCLK_set],knee0,amp0,tau0,bgnd0,res0)[0]
				
				#find rejection at alignment value of bin1 knee position
				#use interpolation of data points
				y_rej_bin0 = interpolate(x,y_bin0,rej_mclk)

				print('old rejection at MCLK align = '+str(round(y_max_bin0/y_rej_bin0_old,1)))
				print('new rejection at MCLK align = '+str(round(y_max_bin0/y_rej_bin0,1)))
				rejection_alignment = y_max_bin0/y_rej_bin0


			#bin1 rejection
			#find bin1 rejection
			x_max_bin1 = knee1 - 300 #changed to 300 from 200 2020-11-04
			y_max_bin1 = funcexp1([x_max_bin1,x_max_bin1],knee1,amp1,tau1,bgnd1,res1)[0]
			
			MCLK_set = knee1 + 1.0 * 100 / 0.305
			#y_rej_bin1 = funcexp1([MCLK_set,MCLK_set],knee1,amp1,tau1,bgnd1,res1)[0]
			#rejection_bin1_1nsec = y_max_bin1/y_rej_bin1
			rejection_bin1_1nsec = y_max_bin1/interpolate(x,y_bin1,MCLK_set)

			#find MCLK set point at 0.5nsec above bin1 knee position
			MCLK_set = knee1 + 0.5 * 100 / 0.305
			#y_rej_bin1 = funcexp1([MCLK_set,MCLK_set],knee1,amp1,tau1,bgnd1,res1)[0]
			#rejection_bin1_0p5nsec = y_max_bin1/y_rej_bin1
			rejection_bin1_0p5nsec = y_max_bin1/interpolate(x,y_bin1,MCLK_set)
			
			#find MCLK set point at 0.25nsec above bin1 knee position
			MCLK_set = knee1 + 0.25 * 100 / 0.305
			#y_rej_bin1 = funcexp1([MCLK_set,MCLK_set],knee1,amp1,tau1,bgnd1,res1)[0]
			#rejection_bin1_0p25nsec = y_max_bin1/y_rej_bin1
			rejection_bin1_0p25nsec = y_max_bin1/interpolate(x,y_bin1,MCLK_set)
			
			if rej_bin==1:
				#find rejection at alignment value of bin1 knee position
				MCLK_set = rej_mclk
				y_rej_bin1_old = funcexp1([MCLK_set,MCLK_set],knee1,amp1,tau1,bgnd1,res1)[0]
				
				#find rejection at alignment value of bin1 knee position
				#use interpolation of data points
				y_rej_bin1 = interpolate(x,y_bin1,rej_mclk)

				print('old rejection at MCLK align = '+str(y_max_bin1/y_rej_bin1_old))
				print('new rejection at MCLK align = '+str(y_max_bin1/y_rej_bin1))
				rejection_alignment = y_max_bin1/y_rej_bin1


			y_fit_bin0=funcexp1(xx_bin0,popt[0],popt[1],popt[2],popt[3],popt[4])
			
			
			if is_yes(save_fig):
				props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)		   
				fig2 = plt.figure(figsize=(12,6))
				#fig2.canvas.set_window_title('MCLK Scan')
				axes1=fig2.add_subplot(111)
				axes1.scatter(x, y_bin1,c='r',marker='o')
				axes1.grid()
				axes1.set_title(fig_title,fontweight="bold",fontsize=12)
				axes1.set_ylabel('signal DN',fontweight="bold",fontsize=12)
				axes1.set_xlabel('MCLK',fontweight="bold",fontsize=12)
	 
				axes1.plot(xx_bin1,y_fit_bin1,color='k',lw=3 )
				
				
				textstr_bin0 ='bin0 fit\nknee=%.2f\ntau=%.3f\namp=%.1f\nres=%.2f\nbgnd=%.1f\nrejection_1nsec=%.1f\nrejection_0.5nsec=%.1f\nrejection_0.25nsec=%.1f'%(knee0,tau0,amp0,res0,bgnd0,rejection_bin0_1nsec,rejection_bin0_0p5nsec,rejection_bin0_0p25nsec)
				textstr_bin1 ='bin1 fit\nknee=%.2f\ntau=%.3f\namp=%.1f\nres=%.2f\nbgnd=%.1f\nrejection_1nsec=%.1f\nrejection_0.5nsec=%.1f\nrejection_0.25nsec=%.1f'%(knee1,tau1,amp1,res1,bgnd1,rejection_bin1_1nsec,rejection_bin1_0p5nsec,rejection_bin1_0p25nsec)
				props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)
			  


				axes1.scatter(x, y_bin0,c='b',marker='o')
				axes1.plot(xx_bin0,y_fit_bin0,color='k',lw=3 )
				
				axes1.text(0.02, .6, textstr_bin0, transform=axes1.transAxes, fontsize=9,verticalalignment='top', bbox=props)
				axes1.text(0.02, .3, textstr_bin1, transform=axes1.transAxes, fontsize=9,verticalalignment='top', bbox=props)

				

				plt.grid(b=True, which='major', color='b', linestyle='-')
				plt.tight_layout()
				if is_yes(save_fig):
					plt.savefig	 (file_name)
				#plt.show()
				plt.close 
			
			
			
			#collection uniformity metric
			x = np.arange(test_conditions['MCLK start'],test_conditions['MCLK start'] + len(y_bin0)*mclk_step,mclk_step)
									
			idx_end0 = (np.abs(x-knee0+200)).argmin()		#200 MCLK units back off from knee
			yy = y_bin0[0:idx_end0]
			collection_metric_bin0 = 100.0*np.std(yy)/np.median(yy) #this metric is similar to PRNU
			
			idx_end1 = (np.abs(x-knee1+200)).argmin()		#200 MCLK units back off from knee
			yy = y_bin1[0:idx_end1]
			collection_metric_bin1 = 100.0*np.std(yy)/np.median(yy) #this metric is similar to PRNU
			

			return knee0,knee1,rejection_bin0_1nsec,rejection_bin1_1nsec,rejection_bin0_0p5nsec,rejection_bin1_0p5nsec,rejection_bin0_0p25nsec,rejection_bin1_0p25nsec,amp0,amp1,bgnd0,bgnd1,tau0,tau1,res0,res1,MCLK_diff,rejection_alignment,collection_metric_bin0,collection_metric_bin1
	   
		except:
			print('failed to fit MCLK with offset = '+str(mclk_offset))
		
	#make a plot for diagnostics
	if is_yes(save_fig):
		x = np.arange(test_conditions['MCLK start'],test_conditions['MCLK start'] + len(y_bin0)*mclk_step,mclk_step)
		props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)		   
		fig2 = plt.figure(figsize=(12,6))
		#fig2.canvas.set_window_title('MCLK Scan')
		axes1=fig2.add_subplot(111)
		axes1.scatter(x, y_bin1,c='r',marker='o')
		axes1.grid()
		axes1.set_title(fig_title,fontweight="bold",fontsize=12)
		axes1.set_ylabel('signal DN',fontweight="bold",fontsize=12)
		axes1.set_xlabel('MCLK',fontweight="bold",fontsize=12)
		axes1.scatter(x, y_bin0,c='b',marker='o')
		
		

		plt.grid(b=True, which='major', color='b', linestyle='-')
		plt.tight_layout()
		if is_yes(save_fig):
			plt.savefig	 (file_name)
		#plt.show()
		plt.close 
		
	return 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,-1,-1
	   
	
def fit_line(x,y,init_intercept,init_slope,low_intercept,low_slope,high_intercept,high_slope,file_name,fig_title,fig_xlabel,fig_ylabel,save_fig):
	def funcexp1(t,intercept,slope):  #t0 is the resolution function width
		y = []
		for tt in t:
			y = y + [intercept + slope*tt]
		return	y



	try:
	#if 1:
		param_bounds=([low_intercept,low_slope],[high_intercept,high_slope])	
		params0 = (init_intercept,init_slope)	  
		popt, pcov = curve_fit(funcexp1, x,y, p0=params0, bounds=param_bounds )
		
		if is_yes(save_fig):
			#print('saving linear fit image')
			props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)		   
			fig2 = plt.figure(figsize=(12,6))
			#fig2.canvas.set_window_title('MCLK Scan')
			axes1=fig2.add_subplot(111)
			axes1.scatter(x, y,c='r',marker='o')
			axes1.grid()
			axes1.set_title(fig_title,fontweight="bold",fontsize=12)
			axes1.set_ylabel(fig_ylabel,fontweight="bold",fontsize=12)
			axes1.set_xlabel(fig_xlabel,fontweight="bold",fontsize=12)
			y_fit=funcexp1(x,popt[0],popt[1])
			axes1.plot(x,y_fit,color='k',lw=3 )
			
			
			textstr ='intercept=%.2f\nslope=%.2f'%(popt[0],popt[1])
			props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)
		  

			axes1.text(0.02, .8, textstr, transform=axes1.transAxes, fontsize=9,verticalalignment='top', bbox=props)
			
			

			plt.grid(b=True, which='major', color='b', linestyle='-')
			plt.tight_layout()
			if is_yes(save_fig):
				plt.savefig	 (file_name)
			#plt.show()
			plt.close()
		
		return popt[0], popt[1]
	except:
		return 0.0,0.0
		
		
def poll_mll():
#/* Contents of "state_flags" */
#define CMD_ALIGNMENT_STATE_IDLE					0
#define CMD_ALIGNMENT_STATE_ICW_INITIAL				BITPOSN(0)
#define CMD_ALIGNMENT_STATE_ICW_STABILIZING			BITPOSN(1)
#define CMD_ALIGNMENT_STATE_ICW_INITIAL_PERFORMED	BITPOSN(2)

	alignment_states_flag = ffi.new('uint16_t *')
	percentage_complete = ffi.new('uint16_t *')
	rc = lib.quantum_get_alignment_states(alignment_states_flag, percentage_complete);
	if( rc ):
		#if percentage_complete[0]<100:
			#print('laser alignment percentage completed = '+str(percentage_complete[0]))
		return percentage_complete[0]
		

	   
def align_mll():
	lib.quantum_start_ICW_initial_alignment_by_freq(1064)
	percent = 0
	i = 0
	while percent<100 and i<100:
		time.sleep(1)
		i=i+1
		percent = poll_mll()
		#print('\niteration = '+str(i))
		
	if i>=100:
		print('laser stabilization failed, shutting down program')
		sys.exit()
	else:
		print('laser aligned')
		
		
		

def parse_alarm_id(id:str) -> tuple:
	"""Parse an alarm and return the individual elements
​
	Parameters
	----------
	id : str
		Alarm identification string.
​
	Returns
	-------
	tuple - (int, int, int, int, str)
		alarm_id, device, component, component_id, alt_description
​
	"""
	# The string is in the formate alarmId-device-component-componentId-alt_ref
	
	elements = id.split("-", 5)
	
	i = len(elements)
	
	if i > 0:
		alarm_id = int(elements[0])
	else:
		alarm_id = lib.ALMEVT_ID_NONE
		
	if i > 1:
		device = int(elements[1])
	else:
		device = lib.ALMEVT_DEVICE_NONE
		
	if i > 2:
		component = int(elements[2])
	else:
		component = lib.ALMEVT_COMPONENT_NONE
	
	if i > 3:
		component_id = int(elements[3])
	else:
		component_id = 0
	if i > 4:
		alt_ref = elements[4]
	else:
		alt_ref = ""

	return (alarm_id, device, component, component_id, alt_ref)
	
def set_fake_alarms(enable:bool, severity:int) -> int:
	"""Set/clear fake alarms on the device.
	
	Parameters
	----------
	enable : bool
		True - enable the fake alarms
		False - disable the fake alarms
​
	severity : int
		Alarm severity (0-3)
​
	Returns
	-------
	None.
​
	"""
	enable = lib.LIBQSI_TRUE if enable == True else lib.LIBQSI_FALSE
	if severity < lib.ALMEVT_SEVERITY_INFORMATIONAL or severity > lib.ALMEVT_SEVERITY_CRITICAL:
		severity = lib.ALMEVT_SEVERITY_INFORMATIONAL
	
	return lib.quantum_control_fake_alarms(enable, severity)
	
def set_device_tod() -> int:
	"""Sets the time-of-day of the connected system to the current system time.
​
	Returns
	-------
	int
		libqsi_status_t
​
	"""
	t = int(time.time())
	return lib.quantum_set_date_time(t)
	
def display_alarms():
	"""Query the device and display active alarms
	
	Returns
	-------
	None.
​
	"""
	n_assertions = ffi.new('uint32_t *')
	n_deassertions = ffi.new('uint32_t *')
	n_alarms = ffi.new('uint32_t *')
	alarms = ffi.new('almevt_header_t ***')
	rc = lib.quantum_alarmlogs_get_alarms(n_assertions, n_deassertions, n_alarms, alarms)
	
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print("Failed to get alarm logs, rc={}".format(int(rc)))
		return
	
	# Re-assign returned values to eliminate using indices
	num_assertions, num_deassertions, num_alarms, alarm_array = n_assertions[0], n_deassertions[0], n_alarms[0], alarms[0]
	
	print("Active alarm log contains {} entries ({} assertions, {} deassertions):".format(num_alarms, num_assertions, num_deassertions))
	
	if (num_alarms != 0):
	
		print("\nSEQ	DATE	  ID	SEVERITY  DESCRIPTION")
		json_char = ffi.new('char *')
		
		for i in range(num_alarms):
			alarm = alarm_array[i]
	
			if (alarm.flags & (lib.ALMEVT_FLAG_IS_ALARM | lib.ALMEVT_FLAG_IS_ALARM_ASSERTED)):
			
				json_char = lib.quantum_eventlogs_convert_alarm_to_json(alarm)
				
				# Convert from char array in json format to a dictionary
				alm = json.loads(tostr(json_char))
				
				print("{0:<6} {1:<6} {2:<10} {3} {4}\n".format(alm['sequenceNumber'], alm['epochTime'], alm['id'], alm['severity'], alm['description']), end="")
	
			# Free buffer holding the json character array
			lib.quantum_free_memory(json_char)
			
	lib.quantum_alarmlogs_free(alarms[0])
	
	
def test_for_alarms():
	"""Query the device and determine if laser is mode-locked
	
	Returns
	-------
	None.
​
	"""
	n_assertions = ffi.new('uint32_t *')
	n_deassertions = ffi.new('uint32_t *')
	n_alarms = ffi.new('uint32_t *')
	alarms = ffi.new('almevt_header_t ***')
	rc = lib.quantum_alarmlogs_get_alarms(n_assertions, n_deassertions, n_alarms, alarms)
	
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print("Failed to get alarm logs, rc={}".format(int(rc)))
		return
	
	# Re-assign returned values to eliminate using indices
	num_assertions, num_deassertions, num_alarms, alarm_array = n_assertions[0], n_deassertions[0], n_alarms[0], alarms[0]
	
	print("Active alarm log contains {} entries ({} assertions, {} deassertions):".format(num_alarms, num_assertions, num_deassertions))
	
	mode_locked = 1	 # 1 = locked, 0 = not locked
	if (num_alarms != 0):
	
		print("\nSEQ	DATE	  ID	SEVERITY  DESCRIPTION")
		json_char = ffi.new('char *')
		
		for i in range(num_alarms):
			alarm = alarm_array[i]
	
			if (alarm.flags & (lib.ALMEVT_FLAG_IS_ALARM | lib.ALMEVT_FLAG_IS_ALARM_ASSERTED)):
			
				json_char = lib.quantum_eventlogs_convert_alarm_to_json(alarm)
				
				# Convert from char array in json format to a dictionary
				alm = json.loads(tostr(json_char))
				
				print("{0:<6} {1:<6} {2:<10} {3} {4}\n".format(alm['sequenceNumber'], alm['epochTime'], alm['id'], alm['severity'], alm['description']), end="")
				if alm['id'] == '12-2-5-0' or alm['id'] == '12-3-5-1' or alm['id'] == '39-5-29-0':
					mode_locked = 0
	
			# Free buffer holding the json character array
			lib.quantum_free_memory(json_char)
			
	lib.quantum_alarmlogs_free(alarms[0])
	return mode_locked
	
	
	
def display_events(since_boot:bool):
	"""Query the device and display events.
	
	Parameters
	----------
	enable : bool
		True - display events since the last boot
		False - display all events
​
	Returns
	-------
	None.
​
	"""
	boot_time = 0
	
	if since_boot == True:
		cur_t = ffi.new('uint64_t *') 
		boot_t = ffi.new('uint64_t *')
		rc = lib.quantum_get_date_time(cur_t, boot_t)
	
		if rc != lib.LIBQSI_STATUS_SUCCESS:
			print("Couldn't retrieve the boot time from the device")
			return
		
		boot_time = boot_t[0]
		
	events = ffi.new('almevt_header_t ***')
	n_events = ffi.new('uint32_t *')
	print("Retrieving events...")
	rc = lib.quantum_eventlogs_get_epoch(boot_time, 0xFFFFFFFFFFFFFFFF, events, n_events)
	
	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print("Failed to get event logs, rc={}".format(int(rc)))
		return
		
	num_events, event_array = n_events[0], events[0]
	
	print("Event log contains {} entries.".format(num_events))
		
	if num_events != 0:
		print("SEQ	  DATE					   ID		   TYPE			 DESCRIPTION")
		
		json_char = ffi.new('char *')
		
		for i in range(num_events):
			event = event_array[i]
			
			json_char = lib.quantum_eventlogs_convert_event_to_json(event)
			
			# Convert from char array in json format to a dictionary
			evt = json.loads(tostr(json_char))
			
			
			sequenceNumber = evt['sequenceNumber'] if 'sequenceNumber' in evt else "?"
			t = int(evt['epochTime']) if 'epochTime' in evt else 0
			t_str = time.ctime(t)
			evtalm_id	= evt['id'] if 'id' in evt else "?"
			descr		= evt['description'] if 'description' in evt else ""
			evtalm_type = evt['type'] if 'type' in evt else "?"
			operation	= evt['operation'] if 'operation' in evt else ""
			severity	= evt['severity'] if 'severity' in evt else ""
			
			if evtalm_type == 'alarm':
				evtalm_type += " " + str(severity) + " " + operation
			
			print("{0:<6} {1:<24} {2:<11} {3:<13} {4:<}".format(sequenceNumber, t_str, evtalm_id, evtalm_type, descr))
			
			# Free buffer holding the json character array
			lib.quantum_free_memory(json_char)
			
	# Free the events
	lib.quantum_eventlogs_free(events[0])
	
	
def get_alarms():
	display_alarms()
	"""
	set_fake_alarms(True, lib.ALMEVT_SEVERITY_CRITICAL)
	
	display_alarms()
	
	# Remove the fake alarms
	set_fake_alarms(False, lib.ALMEVT_SEVERITY_CRITICAL)


	display_alarms()	
	#print("\n")
	
	#display_events(True)
	
	
	total_assertions = ffi.new('uint32_t *')
	total_deassertions = ffi.new('uint32_t *')
	current_alarms = ffi.new('uint32_t *')
	alarms = ffi.new('almevt_header_t ***')
	lib.quantum_alarmlogs_get_alarms(total_assertions,total_deassertions,current_alarms,alarms)
	

	print(current_alarms[0])
	print(total_assertions[0])
	print(total_deassertions[0])
	print(alarms[0][0][0])

	jj = ffi.new('char **')
	jj = lib.quantum_eventlogs_convert_alarm_to_json(alarms[0][0])
	print(jj)
	
	lib.quantum_free_memory(jj)
	lib.quantum_alarmlogs_free(alarms[0])
	"""
	
	
"""
if __name__ == '__main__':
	# load up the headers, libs, and connect to our device
	initialized = init()
	if not initialized:
		sys.exit()
	
	cur_time = ffi.new('uint64_t *') 
	boot_time = ffi.new('uint64_t *')
	lib.quantum_get_date_time(cur_time, boot_time)
​
	print("Device boot time:{0}".format(time.ctime(boot_time[0])))
	print("Device current time:{0}".format(time.ctime(cur_time[0])))
​
	# Ensure that the time of day has been set on the device
	set_device_tod()
​
	# Ensure that there are some alarms present
	print("\nGenerate fake alarms...\n")
​
	set_fake_alarms(True, lib.ALMEVT_SEVERITY_CRITICAL)
	
	display_alarms()
	
	# Remove the fake alarms
	set_fake_alarms(False, lib.ALMEVT_SEVERITY_CRITICAL)
	
	print("\nClearing the fake alarms...\n")
	
	display_alarms()
	
	print("\n")
​
	display_events(True)
	
	
	# Disconnect and we are done
	lib.quantum_disconnect_device()
	
"""	  
 
 
 
 
 

def align_laser(test_conditions,setting):
	print('Aligning laser with simple scan....')
	#get aperture file and ROIs
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)

	##########################################################
	#move MCLK back to 0
	##########################################################
	set_mclk_offset(0)
	mclk = 0
 

	#get motor_Y info 
	motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_Y)
	
	#get a dark frame first
	set_motor(lib.MOTOR_Y, test_conditions['dark_Y']) #with no shutter may also need to move the Y motor to end of range
	set_motor(lib.MOTOR_ATTENUATOR, cfg.atten_0mW)


	dark_frame = capture(10,'cds')

	#only use bin0 for this
	dark_frame = dark_frame[:,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
	dark_frame = np.mean(dark_frame,axis=0)
					
	#only take pixels with apertures above them
	dark_frame = np.multiply(dark_frame,aper).flatten()
	dark_frame = dark_frame[dark_frame !=0.0]
	dark_frame = np.mean(dark_frame)
	
	#print('dark_level = '+str(dark_frame))
	#illuminate
	set_motor(lib.MOTOR_X,int(setting['MOTOR_X'])) #set MOTOR_X to previous value to begin alignment
	set_motor(lib.MOTOR_Y, int(setting['MOTOR_Y'])) #set MOTOR_Y to previous value to begin alignment
	set_motor(lib.MOTOR_THETA_X,int(setting['MOTOR_THETA_X'])) #set MOTOR_X to previous value to begin alignment
	set_motor(lib.MOTOR_THETA_Y, int(setting['MOTOR_THETA_Y'])) #set MOTOR_Y to previous value to begin alignment
	set_motor(lib.MOTOR_ATTENUATOR, cfg.atten_alignment)
	
	#wide scans of each motor
	#align_motor(motor,motor_name,dark_frame,motor_scan_step,motor_range,max_signal,lower_signal,percentile,ROI,aper,setting,test_conditions,mclk)
	sig_Y_prev,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_Y,'MOTOR_Y',dark_frame,20,800,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
	sig_X,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_X,'MOTOR_X',dark_frame,25,800,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
	if lower_flag==1:
		sig_Y_prev = 0.0  #laser power/mclk changed after scanning X then sig_y_prev no longer valid
	sig_TY,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_THETA_Y,'MOTOR_THETA_Y',dark_frame,50,800,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
	if lower_flag==1:
		sig_Y_prev = 0.0 #laser power/mclk changed after scanning THETA_Y then sig_y_prev no longer valid
		
	#narrow scans of each motor
	kk=0
	while kk<7:
		sig_Y,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_Y,'MOTOR_Y',dark_frame,5,100,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
		if lower_flag==1:
			sig_Y_prev = 0.0
		#print('sig_Y = '+str(round(sig_Y,1)))
		#print('sig_Y_prev = '+str(round(sig_Y_prev,1)))
		if np.abs((sig_Y-sig_Y_prev)/sig_Y)<0.05 and sig_Y>test_conditions['min_align_signal']:	
			
			break
		sig_Y_prev = sig_Y
		
		sig_X,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_X,'MOTOR_X',dark_frame,10,100,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
		if lower_flag:
			sig_Y_prev = 0.0
		sig_TY,dark_frame, mclk, lower_flag = align_motor(lib.MOTOR_THETA_Y,'MOTOR_THETA_Y',dark_frame,50,400,250.0,150.0,50.0,ROI,aper,setting,test_conditions,mclk)
		if lower_flag:
			sig_Y_prev = 0.0
		
		
		
		kk = kk + 1

	
	if float(sig_Y) < test_conditions['min_align_signal']:
		print('could not align the laser with simple scan')
		return False, mclk
	else:
		print('aligned laser with simple scan')
		return True, mclk
		

def align_motor(motor,motor_name,dark_frame,motor_scan_step,motor_range,max_signal,lower_signal,percentile,ROI,aper,setting,test_conditions,mclk):
	
	lower_flag = 0  #flag to determine whether the signal was lowered by laser power, tint, or MCLK
	motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(motor)
	#set the motor_range to be +/- motor_range from the current position
	if current_offset - motor_range > min_step:
		lower = current_offset - motor_range
	else:
		lower = min_step
	if current_offset + motor_range < max_step:
		upper = current_offset + motor_range
	else:
		upper = max_step 
	min, max, max_motor_step = scan_laser_alignment_motor(motor,lower,upper,motor_scan_step,dark_frame,ROI,aper,percentile)
	print('scan '+ str(motor_name)+': min signal = '+str(round(min,1))+', max signal = '+str(round(max,1))+', max signal motor position = '+str(max_motor_step))
	
	set_motor(motor,max_motor_step)
	
	if float(max) > max_signal:
		motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_ATTENUATOR)
		ret,max = lower_laser_power(lower_signal,current_offset,max_step,10,dark_frame,ROI,aper,percentile)
		lower_flag = 1
		
	if float(max)> max_signal: #still too high of signal lower tint now
		current_tint = get_tint()
		min_tint = get_min_tint(current_tint)*2.0
		
		#lower_tint(target,first,last,step,dark,ROI,aper,percentile)
		ret,max = lower_tint(lower_signal,current_tint,min_tint,current_tint/10.0,dark_frame,ROI,aper,percentile)
		dark_frame, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
		lower_flag = 1
		
	if float(max)> max_signal: #still too high of signal increase MCLK now
		
		#increase_mclk on chips with no optical filter
		ret,max,mclk = increase_mclk(lower_signal,test_conditions['MCLK_detune_start'],5000,10,dark_frame,ROI,aper,percentile) 
		dark_frame, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
		lower_flag = 1

		
	return max, dark_frame, mclk, lower_flag
	
		
def get_dark_median(ROI,aper,setting,test_conditions):
	#print('get dark median....')
	#get aperture file and ROIs
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)

	##########################################################
	#move MCLK back to 0
	##########################################################
	#set_mclk_offset(0)

	#get motor_Y info 
	motor_ind, current_offset_y, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_Y)
	
	#get MOTOR_ATTENUATOR info 
	motor_ind, current_offset_atten, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_ATTENUATOR)

	#set MOTOR_Y and MOTOR_ATTENUATOR to position where there will be dark illumination
	set_motor(lib.MOTOR_Y, test_conditions['dark_Y']) #with no shutter may also need to move the Y motor to end of range
	set_motor(lib.MOTOR_ATTENUATOR, cfg.atten_0mW)


	dark_frame = capture(10,'cds')
	row_num = dark_frame.shape[2]
	col_num = dark_frame.shape[3]
	#only use bin0 for this
	dark_frame_all = dark_frame[:,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
	dark_frame_all = np.mean(dark_frame_all,axis=0)
					
	#only take pixels with apertures above them
	dark_frame_all = np.multiply(dark_frame_all,aper).flatten()
	dark_frame_all = dark_frame_all[dark_frame_all !=0.0]
	dark_frame_all = np.median(dark_frame_all)

	
	#now get dark signal for each chiplet_registers
	dark_frame_0 = dark_frame[:,0,int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	dark_frame_1 = dark_frame[:,0,int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	dark_frame_2 = dark_frame[:,0,ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	dark_frame_3 = dark_frame[:,0,ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	dark_frame_0 = np.mean(dark_frame_0,axis=0)
	dark_frame_1 = np.mean(dark_frame_1,axis=0)
	dark_frame_2 = np.mean(dark_frame_2,axis=0)
	dark_frame_3 = np.mean(dark_frame_3,axis=0)
	
	aper_0 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_0 = np.where(aper_0 > 0.0, 1.0, 0.0)
	aper_1 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_1 = np.where(aper_1 > 0.0, 1.0, 0.0)
	aper_2 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_2 = np.where(aper_2 > 0.0, 1.0, 0.0)
	aper_3 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_3 = np.where(aper_3 > 0.0, 1.0, 0.0)
	
	dark_frame_0 = np.multiply(dark_frame_0,aper_0).flatten()
	dark_frame_1 = np.multiply(dark_frame_1,aper_1).flatten()
	dark_frame_2 = np.multiply(dark_frame_2,aper_2).flatten()
	dark_frame_3 = np.multiply(dark_frame_3,aper_3).flatten()
	
	dark_frame_0 = dark_frame_0[dark_frame_0 !=0.0]
	dark_frame_1 = dark_frame_1[dark_frame_1 !=0.0]
	dark_frame_2 = dark_frame_2[dark_frame_2 !=0.0]
	dark_frame_3 = dark_frame_3[dark_frame_3 !=0.0]
	
	dark_frame_0 = np.median(dark_frame_0)
	dark_frame_1 = np.median(dark_frame_1)
	dark_frame_2 = np.median(dark_frame_2)
	dark_frame_3 = np.median(dark_frame_3)
	
	"""
	print('dark_frame_all = '+str(dark_frame_all))
	print('dark_frame_0 = '+str(dark_frame_0))
	print('dark_frame_1 = '+str(dark_frame_1))
	print('dark_frame_2 = '+str(dark_frame_2))
	print('dark_frame_3 = '+str(dark_frame_3))
	"""
	
	set_motor(lib.MOTOR_Y, current_offset_y) #set MOTOR_Y back to original position
	set_motor(lib.MOTOR_ATTENUATOR, current_offset_atten) #set MOTOR_Y back to original position
	
	return dark_frame_all, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3


def set_laser_power(target,setting,test_conditions):
	motor = lib.MOTOR_ATTENUATOR
	
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)

	##########################################################
	#move MCLK back to 0
	##########################################################
	#set_mclk_offset(0)
	
	
	#find out where signal is relative to target
	dark_all, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
   

	illum_frame = capture(10,'cds')
	row_num = illum_frame.shape[2]
	col_num = illum_frame.shape[3]

	#only use bin0 for this
	illum_frame_all = illum_frame[:,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
	illum_frame_all = np.mean(illum_frame_all,axis=0)
					
	#only take pixels with apertures above them
	illum_frame_all = np.multiply(illum_frame_all,aper).flatten()
	illum_frame_all = illum_frame_all[illum_frame_all !=0.0]
	illum_frame_all = np.median(illum_frame_all)
	
	signal_all = illum_frame_all - dark_all


	#get MOTOR_ATTENUATOR info 
	motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(lib.MOTOR_ATTENUATOR)
	
	if signal_all < target:
		step = 20
		percentile = 50.0
		ret, signal_all = raise_laser_power(target,current_offset,min_step,step,dark_all,ROI,aper,percentile)
	else:
		step = 20
		percentile = 50.0
		ret, signal_all = lower_laser_power(target,current_offset,max_step,step,dark_all,ROI,aper,percentile)
	
	#now recalculate all illuminated values since the laser power has been adjusted
	illum_frame = capture(10,'cds')

	#only use bin0 for this
	illum_frame_all = illum_frame[:,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
	illum_frame_all = np.mean(illum_frame_all,axis=0)
					
	#only take pixels with apertures above them
	illum_frame_all = np.multiply(illum_frame_all,aper).flatten()
	illum_frame_all = illum_frame_all[illum_frame_all !=0.0]
	illum_frame_all = np.median(illum_frame_all)
	
	signal_all = illum_frame_all - dark_all
	
	#now get signal for each chiplet 
	illum_frame_0 = illum_frame[:,0,int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	illum_frame_1 = illum_frame[:,0,int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	illum_frame_2 = illum_frame[:,0,ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	illum_frame_3 = illum_frame[:,0,ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	
	illum_frame_0 = np.mean(illum_frame_0,axis=0)
	illum_frame_1 = np.mean(illum_frame_1,axis=0)
	illum_frame_2 = np.mean(illum_frame_2,axis=0)
	illum_frame_3 = np.mean(illum_frame_3,axis=0)
	
		
	aper_0 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_0 = np.where(aper_0 > 0.0, 1.0, 0.0)
	aper_1 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_1 = np.where(aper_1 > 0.0, 1.0, 0.0)
	aper_2 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_2 = np.where(aper_2 > 0.0, 1.0, 0.0)
	aper_3 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_3 = np.where(aper_3 > 0.0, 1.0, 0.0)
	
	
	illum_frame_0 = np.multiply(illum_frame_0,aper_0).flatten()
	illum_frame_1 = np.multiply(illum_frame_1,aper_1).flatten()
	illum_frame_2 = np.multiply(illum_frame_2,aper_2).flatten()
	illum_frame_3 = np.multiply(illum_frame_3,aper_3).flatten()
	
	illum_frame_0 = illum_frame_0[illum_frame_0 !=0.0]
	illum_frame_1 = illum_frame_1[illum_frame_1 !=0.0]
	illum_frame_2 = illum_frame_2[illum_frame_2 !=0.0]
	illum_frame_3 = illum_frame_3[illum_frame_3 !=0.0]
	
	illum_frame_0 = np.median(illum_frame_0)
	illum_frame_1 = np.median(illum_frame_1)
	illum_frame_2 = np.median(illum_frame_2)
	illum_frame_3 = np.median(illum_frame_3)
	
	signal_0 = illum_frame_0 - dark_frame_0
	signal_1 = illum_frame_1 - dark_frame_1
	signal_2 = illum_frame_2 - dark_frame_2
	signal_3 = illum_frame_3 - dark_frame_3
	
	#print('final illuminated signal = '+str(round(signal_all,1)))
	return ret, signal_all, signal_0, signal_1, signal_2, signal_3

def get_current_signal(setting,test_conditions):
	
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)

	##########################################################
	#move MCLK back to 0
	##########################################################
	#set_mclk_offset(0)
	
	
	#find out where signal is relative to target
	dark_all, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
   

	illum_frame = capture(10,'cds')
	row_num = illum_frame.shape[2]
	col_num = illum_frame.shape[3]

	#only use bin0 for this
	illum_frame_all = illum_frame[:,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
	illum_frame_all = np.mean(illum_frame_all,axis=0)
					
	#only take pixels with apertures above them
	illum_frame_all = np.multiply(illum_frame_all,aper).flatten()
	illum_frame_all = illum_frame_all[illum_frame_all !=0.0]
	illum_frame_all = np.median(illum_frame_all)
	
	signal_all = illum_frame_all - dark_all
	
	#now get signal for each chiplet 
	illum_frame_0 = illum_frame[:,0,int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	illum_frame_1 = illum_frame[:,0,int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	illum_frame_2 = illum_frame[:,0,ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]
	illum_frame_3 = illum_frame[:,0,ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]
	
	illum_frame_0 = np.mean(illum_frame_0,axis=0)
	illum_frame_1 = np.mean(illum_frame_1,axis=0)
	illum_frame_2 = np.mean(illum_frame_2,axis=0)
	illum_frame_3 = np.mean(illum_frame_3,axis=0)
	
		
	aper_0 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_0 = np.where(aper_0 > 0.0, 1.0, 0.0)
	aper_1 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[int(row_num/2):ROI[1]:ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_1 = np.where(aper_1 > 0.0, 1.0, 0.0)
	aper_2 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],int(col_num/2):ROI[4]:ROI[5]]).astype('float')
	aper_2 = np.where(aper_2 > 0.0, 1.0, 0.0)
	aper_3 = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:int(row_num/2):ROI[2],ROI[3]:int(col_num/2):ROI[5]]).astype('float')
	aper_3 = np.where(aper_3 > 0.0, 1.0, 0.0)
	
	
	illum_frame_0 = np.multiply(illum_frame_0,aper_0).flatten()
	illum_frame_1 = np.multiply(illum_frame_1,aper_1).flatten()
	illum_frame_2 = np.multiply(illum_frame_2,aper_2).flatten()
	illum_frame_3 = np.multiply(illum_frame_3,aper_3).flatten()
	
	illum_frame_0 = illum_frame_0[illum_frame_0 !=0.0]
	illum_frame_1 = illum_frame_1[illum_frame_1 !=0.0]
	illum_frame_2 = illum_frame_2[illum_frame_2 !=0.0]
	illum_frame_3 = illum_frame_3[illum_frame_3 !=0.0]
	
	illum_frame_0 = np.median(illum_frame_0)
	illum_frame_1 = np.median(illum_frame_1)
	illum_frame_2 = np.median(illum_frame_2)
	illum_frame_3 = np.median(illum_frame_3)
	
	signal_0 = illum_frame_0 - dark_frame_0
	signal_1 = illum_frame_1 - dark_frame_1
	signal_2 = illum_frame_2 - dark_frame_2
	signal_3 = illum_frame_3 - dark_frame_3
	

	
	#print('final illuminated signal = '+str(round(signal_all,1)))
	return signal_all, signal_0, signal_1, signal_2, signal_3

def increase_mclk(target,first,last,step,dark,ROI,aper,percentile):
	print('increasing mclk...')
	
	
	mclk = first
	
	while mclk<=last:
		mclk = mclk + step
		set_mclk_offset(mclk)

		illum_frame = capture(1,'cds')

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.percentile(illum_frame,percentile)-dark
		

		if current < target:
			print('new MCLK = '+str(mclk)+', signal = '+str(current))
			return True, current, mclk
			
	return False, current, mclk
	
	
	
def lower_tint(target,first,last,step,dark,ROI,aper,percentile):
	print('lowering tint...')
	
	illum_frame = capture(1,'cds')
	#only use bin0 for this
	illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]			 
	#only take pixels with apertures above them
	illum_frame = np.multiply(illum_frame,aper).flatten()
	illum_frame = illum_frame[illum_frame !=0.0]
	current = np.percentile(illum_frame,percentile)-dark
	
	tint = first
	while tint>=last+step+1.0: #add 1.0msec for margin that it does not go into lala land
		tint = tint - step
		set_tint(tint)

		illum_frame = capture(1,'cds')
	   

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.percentile(illum_frame,percentile)-dark
		

		if current < target:
			return True, current
			
	return False, current
	
	
def adjust_tint(target,first,last,step,setting,test_conditions):
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)
	
	#find out where signal is relative to target
	dark, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
	
	ret, current = lower_tint(target,first,last,step,dark,ROI,aper,50)
	return ret,current
	
	
def adjust_mclk(target,setting,test_conditions):
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)
	
	#find out where signal is relative to target
	dark, dark_frame_0, dark_frame_1, dark_frame_2, dark_frame_3 = get_dark_median(ROI,aper,setting,test_conditions)
	
	
	#rc, current, mclk = increase_mclk(target,first,last,step,dark,ROI,aper,percentile)
	rc, current, mclk = increase_mclk(target,test_conditions['MCLK_detune_start'],5000,10,dark,ROI,aper,50)
	
	return current, mclk
	
	
def adjust_MOTOR_Y_off_peak(target,dark,motor_range,step,setting,test_conditions):
	ROI = cfg.illum_ROIS[int(setting['Product_number'])]
	aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')

	#convert all nonzero elements in aper array to 1.0
	aper = np.where(aper > 0.0, 1.0, 0.0)
	
	motor = lib.MOTOR_Y
	motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = get_motor_info(motor)
	#set the motor_range to be +/- motor_range from the current position
	motor_set = current_offset
	
	if current_offset - motor_range > min_step:
		lower = current_offset - motor_range	  
		
		while motor_set>lower:
			motor_set = motor_set - step
			set_motor(motor, motor_set)

			illum_frame = capture(1,'cds')
		   
			#only use bin0 for this
			illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
							
			#only take pixels with apertures above them
			illum_frame = np.multiply(illum_frame,aper).flatten()
			illum_frame = illum_frame[illum_frame !=0.0]
			current = np.percentile(illum_frame,50)-dark
		   
			if current < target:
				print('new signal after adjusting MOTOR_Y = '+str(current))
				return True, current
		return False, 0
		
	elif current_offset + motor_range < max_step:
		upper = current_offset + motor_range

		while motor_set<upper:
			motor_set = motor_set + step
			set_motor(motor, motor_set)

			illum_frame = capture(1,'cds')
		   
			#only use bin0 for this
			illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
							
			#only take pixels with apertures above them
			illum_frame = np.multiply(illum_frame,aper).flatten()
			illum_frame = illum_frame[illum_frame !=0.0]
			current = np.percentile(illum_frame,50)-dark
		   
			if current < target:
				return True, current
		
	else:
		
		return False,current
	
	
	
	return False,current


def lower_laser_power(target,first,last,step,dark,ROI,aper,percentile):
	print('lowering laser power...')
	motor = lib.MOTOR_ATTENUATOR

	motor_set = first
	while motor_set<=last:
		motor_set = motor_set + step
		set_motor(motor, motor_set)

		illum_frame = capture(1,'cds')
	   

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.percentile(illum_frame,percentile)-dark
		

		if current < target:
			return True, current
	return False, current
	
	
def raise_laser_power(target,first,last,step,dark,ROI,aper,percentile):
	print('raising laser power...')
	motor = lib.MOTOR_ATTENUATOR

	motor_set = first
	while motor_set>=last:
		motor_set = motor_set - step
		set_motor(motor, motor_set)

		illum_frame = capture(1,'cds')
	   

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.percentile(illum_frame,percentile)-dark
		#print('current signal = '+str(current))
		if current > target:
			return True, current
	return False, current

def scan_laser_alignment_motor(motor,first,last,step,dark,ROI,aper,percentile):
	first = int(first)
	last = int(last)


	min = 10000.0
	max = -10000.0
	max_motor_step = 0

	motor_set = first
	while motor_set<=last:

		set_motor(motor, motor_set)

		illum_frame = capture(1,'cds')
	   

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.percentile(illum_frame,percentile)-dark

		if current > max:
			max = current
			max_motor_step = motor_set
		if current < min:
			min = current
		#print(str(motor)+' = '+str(motor_set)+', signal = '+str(current))
		motor_set = motor_set + step

	return min, max, max_motor_step
	
 
 
 
def adjust_laser_alignment_motor(motor,first,last,target,tolerance,step,dark,ROI,aper):

	print('\n\n\n')
	print('aligning '+str(motor))


	first = int(first)
	last = int(last)
	print('first='+str(first))
	print('last='+str(last))

	min = 10000.0
	max = -10000.0

	while first<=last:
		midpoint = int((first+last)/2.0)

		set_motor(motor, midpoint)

		illum_frame = capture(1,'cds')
	   

		#only use bin0 for this
		illum_frame = illum_frame[0,0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		
						
		#only take pixels with apertures above them
		illum_frame = np.multiply(illum_frame,aper).flatten()
		illum_frame = illum_frame[illum_frame !=0.0]
		current = np.mean(illum_frame)-dark

		if current > max:
			max = current
		if current < min:
			min = current
		print(str(motor)+' = '+str(midpoint)+', signal = '+str(current))


		if np.abs(current-target)/target  < tolerance:	#tolerance	needed
			break
		else:
			if target<current:
				last = midpoint-step
			else:
				first = midpoint + step	

	return min, max


# todo: remove old efuse
def read_efuse():
	parameter_out = set_config(cfg.CURRENT_CONFIG_PATH)
	if parameter_out:  #successfully write config
		parameter_out = get_sensor_ID()
		if parameter_out:  #successfully got a chip ID

			efuse=nickel_efuse.efuse()
			# Read the contents of all EFuse Banks as a single memory.	Value returned is a list of bytes
			ret_type = 0 # 0 - return a list of bytes, 1 - return a list of characters
			chip_efuse = efuse.rd_efuse(ret_type)
			#print("Q9001 EFuse contains " + str(len(chip_efuse)) + " bytes (" + str(len(chip_efuse) * 8) + " cells).")


			#find the last non-zero byte in the efuse
			i=0
			last = 0
			for cc in chip_efuse:
				if cc!=0:
					last = i
				i = i+1


			ret_type=1
			chip_efuse2 = efuse.rd_efuse(ret_type)


			st = ''
			i=0
			for cc in chip_efuse:
				if cc != 0:
					st = st + chip_efuse2[i]
				i=i+1
			#print('efuse = '+st)

			#now decode lot/wfr/chip from efuse
			lot = ''
			wafer = ''
			chip = ''
			parts = st.split(':')
			for p in parts:
				try:
					if p[0]=='L':
						lot = p[1:]
					if p[0]=='W':
						wafer = p[1:]
					if p[0]=='C':
						chip = p[1:]
				except:
					pass

			#print('lot = '+str(lot)+', wafer = '+str(wafer)+', chip = '+str(chip))
			return st,len(chip_efuse),last,lot,wafer,chip
		else:
			return '',0,0,'','',''
	else:
		return '',0,0,'','',''

def write_efuse(efuse_text):
	parameter_out = set_config(cfg.CURRENT_CONFIG_PATH)
	if parameter_out:  #successfully write config
		parameter_out = get_sensor_ID()
		if parameter_out:  #successfully got a chip ID

			efuse=nickel_efuse.efuse()
			# Read the contents of all EFuse Banks as a single memory.	Value returned is a list of bytes
			ret_type = 0 # 0 - return a list of bytes, 1 - return a list of characters
			chip_efuse = efuse.rd_efuse(ret_type)


			#find the last non-zero byte in the efuse
			i=0
			last = 0
			for cc in chip_efuse:

				if cc!=0:
					last = i
				i = i+1


			#length of string to be written
			if 63-last < len(efuse_text)+1:
				print('not enough space to write additional data')


			else: #write the data
				if efuse_text !='':
					#write a : first
					#byte_index = last+1
					#efuse.wr_char(byte_index,':')

					#now go through characters
					byte_index = last
					for cc in efuse_text:
						byte_index = byte_index + 1
						efuse.wr_char(byte_index,cc)

					ret_type=0
					chip_efuse = efuse.rd_efuse(ret_type)
					ret_type=1
					chip_efuse2 = efuse.rd_efuse(ret_type)

					st = ''
					i=0
					for cc in chip_efuse:
						if cc != 0:
							st = st + chip_efuse2[i]
						i=i+1
					print('new efuse = '+st)


# todo: duplicated from dfrier qsi_nickel_macros.py... resolve duplication
#def set_timing_clock_freq_plan(component: str = "MCLK", ref_source: int = lib.LIBQSI_REFSRC_OSCILLATOR,
def set_timing_clock_freq_plan(component: str = "MCLK", ref_source: int = 0,
							   ref_clk: int = 10000000, output_clk0: int = 67080000, output_clk1: int = 67080000,
							   output_clk2: int = 67080000, output_clk3: int = 67080000) -> int:
	"""Configure the specified SI5338 clock (PLL) device to generate the specified output clock frequenies,
    using a given input source.

    Parameters
    ----------
    component : str, optional
        A string identifying the device. Options are "MCLK", "CHIP" and "GSL".  The default is "MCLK".
    ref_source : int, optional
        The input reference source.  The default is lib.LIBQSI_REFSRC_OSCILLATOR.
    ref_clk : int, optional
        The clock frequrency of the reference source in Hz.  The default is 10000000.
    output_clk0 : int, optional
        The output frequency of all output port 0.  The default is 67080000.
    output_clk1 : int, optional
        The output frequency of all output port 0.  The default is 67080000.
    output_clk2 : int, optional
        The output frequency of all output port 0.  The default is 67080000.
    output_clk3 : int, optional
        The output frequency of all output port 0.  The default is 67080000.

    Returns
    -------
    rc: int (lib.libqsi_status_t)
        status

    Usage
    -----
        set_timing_clock_freq_plan("MCLK", lib.LIBQSI_REFSRC_OSCILLATOR, 10000000, 67080000, 67080000, 67080000, 67080000)
    """
	component_id = text2cffi(component)

	freq_plan = ffi.new('libqsi_freq_plan_v2_config_t *')
	freq_plan.refsrc = ref_source
	freq_plan.refclk = ref_clk
	freq_plan.base_step[0] = 0
	freq_plan.base_step[1] = 0
	freq_plan.base_step[2] = 0
	freq_plan.base_step[3] = 0
	freq_plan.clk[0] = output_clk0
	freq_plan.clk[1] = output_clk1
	freq_plan.clk[2] = output_clk2
	freq_plan.clk[3] = output_clk3
	freq_plan.mode[0] = lib.LIBQSI_OUTPUT_MODE_PLL
	freq_plan.mode[1] = lib.LIBQSI_OUTPUT_MODE_PLL
	freq_plan.mode[2] = lib.LIBQSI_OUTPUT_MODE_PLL
	freq_plan.mode[3] = lib.LIBQSI_OUTPUT_MODE_PLL
	freq_plan.invert[0] = 0
	freq_plan.invert[1] = 0
	freq_plan.invert[2] = 0
	freq_plan.invert[3] = 0
	freq_plan.min_jitter = 0

	rc = lib.quantum_timing_clock_set_frequency_plan(lib.LIBQSI_DEVICE_NIOS, component_id, freq_plan)
	return rc


def gsl_clock_init(pulse2=110):
	"""
    Initialize the clock sources and set the phase offset for the Gain Switched Laser board.

    Returns
    -------
    None.

    """
	set_timing_clock_freq_plan("MCLK", lib.LIBQSI_REFSRC_OSCILLATOR, 10000000, 65000000, 8125000, 65000000,
							   65000000)
	#set_timing_clock_freq_plan("GSL", lib.LIBQSI_REFSRC_OSCILLATOR, 65000000, 8125000, 8125000, 8125000, 8125000)
	set_timing_clock_freq_plan("GSL", lib.LIBQSI_REFSRC_OSCILLATOR, 65000000, 65000000, 65000000, 65000000, 65000000)
	set_timing_clock_freq_plan("CHIP", lib.LIBQSI_REFSRC_OSCILLATOR, 8125000, 8125000, 8125000, 8125000, 8125000)
	set_clk_offsets("GSL", 0xF, [0, pulse2 , 0, 0])
	#set_clk_offsets("GSL", 0xF, [10, pulse2, 12, 13])
	time.sleep(3)
	lib.quantum_synchronize_fpga_sensor_interface()


def gsl_enable(enable=0, vlaser=18.0, vbias=0.4):
	"""
    Configure the non-clock related Gain Switched Laser parameters.

    Parameters
    ----------
    enable : TYPE, optional
        DESCRIPTION. The default is 0.
    vlaser : TYPE, optional
        DESCRIPTION. The default is 15.0.
    vbias : TYPE, optional
        DESCRIPTION. The default is 0.0.

    Returns
    -------
    None.

    """
	lib.quantum_gsl_laser_voltage_set(vlaser)
	lib.quantum_gsl_gate_bias_set(vbias)
	lib.quantum_set_laser_enabled(enable)


def gsl_info():
	"""
    Display GSL related information.

    Returns
    -------
    None.

    """
	# Dump current laser configuration
	# time.sleep(2.0)       # If gsl config was just changed, allow photodiode current value to stabilize before reading
	laser_diode_setpoint = ffi.new('float *')
	laser_diode_voltage = ffi.new('float *')
	laser_diode_current = ffi.new('float *')
	photodiode_current = ffi.new('float *')
	gate_bias_voltage = ffi.new('float *')

	lib.quantum_gsl_laser_voltage_get(laser_diode_setpoint, laser_diode_voltage, laser_diode_current);
	lib.quantum_gsl_photodiode_current_get(photodiode_current)
	lib.quantum_gsl_gate_bias_get(gate_bias_voltage)

	print('Laser diode:')
	print('  Setpoint     = {0:.3f}'.format(laser_diode_setpoint[0]))
	print('  Voltage      = {0:.3f}'.format(laser_diode_voltage[0]))
	print('  Current      = {0:.3f}'.format(laser_diode_current[0]))
	print('  Bias voltage = {0:.3f}'.format(gate_bias_voltage[0]))
	print('  PD current   = {0:.3f}'.format(photodiode_current[0]))

	gsl_csr = ffi.new('gsl_csr_t *')

	lib.quantum_gsl_csr_get(gsl_csr)

	print('  Status        = 0x{0:08X}'.format(gsl_csr[0].status))

	# Note: the status bits are defined in "\device\hybrid\cypress\CY8C4246AZI-M443\BeamSteering\BeamSteeringV2.cydsn\i2c_host_interface.h"
	print('  - Servo power = {0:s}'.format('exceeds limit' if (gsl_csr[0].status & 0x04) else 'within limit'))
	print('  - Laser state = {0:s}'.format('enable' if (gsl_csr[0].status & 0x02) else 'disable'))
	print('  - Lid state   = {0:s}'.format('OPEN' if (gsl_csr[0].status & 0x01) else 'close'))
	print('  Mode          = 0x{0:08X}'.format(gsl_csr[0].mode))
	print('  Board Temp    = {0:.3f}'.format(gsl_csr[0].board_temp))
	print('  X Temp        = {0:.3f}'.format(gsl_csr[0].x_temp))
	print('  Y Temp        = {0:.3f}'.format(gsl_csr[0].y_temp))
	print('  CPU Temp      = {0:.3f}'.format(gsl_csr[0].cpu_temp))
	print('  Monitor_3V    = {0:.3f}'.format(gsl_csr[0].monitor_3v))

	# Get the states flag
	state_flags = ffi.new('uint32_t *')
	rc = lib.quantum_get_device_state_flags(state_flags)
	if rc == lib.LIBQSI_STATUS_SUCCESS:
		print('  NIOS Lid      = {0:s}'.format('OPEN' if (state_flags[0] & lib.STATE_FLAG_LID_OPEN) else 'close'))
	else:
		print('Could not retrieve the Control Module state flags.')


def con(sn: str = None) -> bool:
	'''Connect to a Nickel device over USB.

    Parameters
    ----------
    sn : str, optional
        Serial number of the control module (Control Module TLV 49). The default is None.

    Returns
    -------
    bool
        True if connection to the device was successful, otherwise False
    '''
	rc = lib.LIBQSI_STATUS_SUCCESS
	if (sn == None):
		sn = "NM1950002"

	# Connect to the device
	if (sn == None):
		# Connect to any device
		rc = lib.quantum_connect_device(0)
	else:
		# Connect to a specific device
		rc = lib.quantum_connect_to_device_by_serial_number(text2cffi(sn))

	if rc != lib.LIBQSI_STATUS_SUCCESS:
		print('Failed to connect to device, error %s' % rc)
		return False
	else:
		# Get the product type
		product_type = lib.quantum_get_product_type()
		global isDigital
		if (product_type == lib.LIBQSI_PRODUCT_NANO_D) or (product_type == lib.LIBQSI_PRODUCT_NICKEL):
			print("Connected to digital product %s" % product_type)
		else:
			print("Connected to analog product %s" % product_type)
		return True


def dis():
    '''
    Disconnect from a Nickel or Nano device over USB.

    Parameters:
        None
    '''
    lib.quantum_disconnect_device()

def picoquant_enable(enable:bool = False):
    """Configure the enable/disable of a picoquant laser.
    Parameters
    ----------
    enable : bool, optional
        Enable (True) or disable (False) the laser.  The default is False.
    Returns
    -------
    None.
    """
    component_id = text2cffi("GSL")
    freq_plan = ffi.new('libqsi_freq_plan_v2_config_t *')
    rc = lib.quantum_timing_clock_get_frequency_plan(lib.LIBQSI_DEVICE_NIOS, component_id, freq_plan)
    freq_plan.mode[3] = lib.LIBQSI_OUTPUT_MODE_PLL if enable == True else lib.LIBQSI_OUTPUT_MODE_DISABLE
    rc = lib.quantum_timing_clock_set_frequency_plan(lib.LIBQSI_DEVICE_NIOS, component_id, freq_plan)
    return rc


def picoquant_clock_locked() -> bool:
    """Determine if the SI5338 clock that drives the picoquant laser
    is locked to its reference clock.
    Parameters
    ----------
    none
    Returns
    -------
    bool : True if locked, False if not locked
    """
    rc = False  # Default to not locked
    component_id = text2cffi("GSL")
    if (lib.quantum_get_clock_lock_status(component_id) == lib.LIBQSI_STATUS_CLOCK_LOCKED):
        rc = True
    return rc


def v_set(target_name, target_v, verbose=False):
	'''
    Set a power supply output to the target voltage.

    Parameters:
        target_name - Name of the power supply
        target_v    - Output voltage
        verbose     - true - print results
                    - false - don't print results
    Example:
        v_set("va33",3.300)
    '''
	supply_name = text2cffi(target_name)
	old_voltage = 0
	new_voltage = 0

	if (verbose):
		# Read and save the current value of the power supply
		read_val = ffi.new('float *')
		lib.quantum_voltage_get(supply_name, read_val)
		old_voltage = read_val[0]

	# Write a new value for the power supply
	voltage = float(target_v)
	lib.quantum_voltage_set(supply_name, voltage)

	if (verbose != 0):
		# Read the current value of the power supply
		lib.quantum_voltage_get(supply_name, read_val)
		new_voltage = read_val[0]

		# Print the previous and current values
		print()
		print(target_name + ': previous = {0:2.3f}, current = {1:2.3f}'.format(old_voltage, new_voltage))


def v_get(target_name, verbose=False):
	'''
    Get the configured value for a power supply.

    Parameters:
        target_name - Name of the power supply
        verbose     - true - print results
                    - false - don't print results

    Example:
        ps_value = v_get("va33")
    '''
	# Read the current value for the supply
	read_val = ffi.new('float *')
	supply_name = text2cffi(target_name)
	lib.quantum_voltage_get(supply_name, read_val)
	voltage = read_val[0]
	if (verbose):
		print(target_name + ' = {0:2.3f}'.format(voltage))

	return voltage

def efuse_display_free_space():
	'''Read and display the e-fuse memory free space statistics.
    '''
	total_free_bytes = ffi.new('int *')
	number_of_fragments = ffi.new('int *')
	smallest_fragment = ffi.new('int *')
	largest_fragment = ffi.new('int *')

	rc = lib.quantum_efuse_get_free_space(nickel_handle, total_free_bytes,
											  number_of_fragments, smallest_fragment,
											  largest_fragment);
	if (rc == lib.LIBQSI_STATUS_SUCCESS):
		print("\nTotal free space remaining = {0} bytes\n".format(total_free_bytes[0]))
		print("Total number of fragments  = {0}\n".format(number_of_fragments[0]))
		print("Smallest fragment size     = {0} bytes\n".format(smallest_fragment[0]))
		print("Largest fragment size      = {0} bytes\n".format(largest_fragment[0]))
	elif (rc == lib.LIBQSI_STATUS_CHIP_NOT_INSERTED):
		print("CHIP NOT INSTALLED! {0} {1}\n\n".format(lib.quantum_get_status_description(rc), rc))


def efuse_display_raw():
	'''Read and display the raw e-fuse memory
    '''
	read_data = ffi.new('char **')
	read_length = ffi.new('int *')

	rc = lib.quantum_efuse_read_raw(nickel_handle, read_data, read_length)

	if (rc == lib.LIBQSI_STATUS_SUCCESS):
		print("\nLength: {0}\n".format(read_length[0]))
		ascii_str = ''
		for i in range(read_length[0]):
			if i % 16 == 0:
				print("(0x{0:04x}):".format(i), end='')
			temp = ord(read_data[0][i])
			print("{0:02x} ".format(temp), end='')

			if temp > 30 and temp < 127:
				ascii_str += read_data[0][i].decode('utf-8')
			else:
				ascii_str += str('.')

			if i % 16 == 15:
				print("   {0}".format(ascii_str))
				ascii_str = ''

	lib.quantum_free_memory(read_data[0])


def efuse_read_json() -> int:
	'''Read the sensor e-fuse memory and return the values
    of supported records with valid content in JSON format.

    Returns
    -------
    int (lib.libqsi_status_t)
        status
    str
        JSON formatted string containing valid records
    '''
	json_str = ''  # Default to null string
	json_bytes = ffi.new('char **')
	rc = lib.quantum_efuse_read_json(nickel_handle, json_bytes)
	if (rc == lib.LIBQSI_STATUS_SUCCESS):
		# Convert from a null terminated byte array to a string

		for i in range(200):   # arb length to process all pretty prints...
			if json_bytes[0][i] == b'\x00':
				break
			if ((json_bytes[0][i] == b'\x0d') or (json_bytes[0][i] == b'\x0a') or (json_bytes[0][i] == b' ')):
				continue
			json_str += json_bytes[0][i].decode('utf-8')
	# Free the memory returned by driver call
	lib.quantum_free_memory(json_bytes[0])
	return rc, json_str


def efuse_read_dict() -> int:
	'''Read the sensor e-fuse memory and return the values
    of supported records with valid content in dictionary format.

    Returns
    -------
    int (lib.libqsi_status_t)
        status
    dict
        dict containing valid records
    '''
	rc, json_str = efuse_read_json()

	if (rc == lib.LIBQSI_STATUS_SUCCESS):
		if json_str == '':
			json_dict = {}
		else:
			json_dict = json.loads(json_str)

	return json_dict


def efuse_write_json(efuse_json: str) -> int:
	'''Write the data provided in JSON format to the sensor e-fuse memory.
    ----------
    efuse_json : str
        The e-fuse data in JSON form.  The supported keys are:
            - 'used_counter' with an integer
            - 'lot' with a string
            - 'wafer' with an integer
            - 'die_num' with an integer
            - 'cmos_rev' with an integer
            - 'test_array' with a byte array
        Not all keys are necessary.  Only the keys present in the dictionary
        will be written.

    Returns
    -------
    int (lib.libqsi_status_t)
        status
    '''
	j_record = text2cffi(efuse_json)
	return lib.quantum_efuse_write_json(nickel_handle, j_record)


def efuse_write_dict(efuse_data: dict) -> int:
	'''Write the data provided in dictionary format to the sensor e-fuse memory.
    ----------
    efuse_data : dict
        The e-fuse data in dictionary form.  The supported keys are:
            - 'used_counter' with an integer
            - 'lot' with a string
            - 'wafer' with an integer
            - 'die_num' with an integer
            - 'cmos_rev' with an integer
            - 'test_array' with a byte array
        Not all keys are necessary.  Only the keys present in the dictionary
        will be written.

    Returns
    -------
    int (lib.libqsi_status_t)
        status
    '''
	json_string = json.dumps(efuse_data)
	return efuse_write_json(json_string)


# efuse_data = { 'used_counter' : 0,     # integer
#               'lot': 'S40327',        # string
#               'wafer' : 1,            # integer
#               'die_num' : 1,          # integer
#               'cmos_rev' : 0,         # integer
#               'test_array' : 'data'   # byte array
#             }

# efuse_data = { 'wafer' : 5}

# rc = efuse_write_dict(efuse_data)

# print( "Wrote efuse: {0} {1}\n\n".format(lib.quantum_get_status_description(rc), rc))


def efuse_invalidate_record(record_name):
	name = text2cffi(record_name)

	rc = lib.quantum_efuse_invalidate_record(nickel_handle, name)

	return rc
