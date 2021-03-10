# boilerplate stuff to import
import os
import sys
import platform
import numpy as np
import time
import re
from cffi import FFI

# will be updated on connect
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
    #INCLUDE_PATH = 'C:\\Users\\Zhaoyu He\\Documents\\GitHub\\falcon\\build\\software\\qsi_f4_usb_64b\\'
    INCLUDE_PATH = 'C:\\Users\\Zhaoyu He\\Dropbox (Quantum-SI)\\Q-Si Software\\Falcon 64\\Chewie\\Beta\\'
else:
    INCLUDE_PATH = '/usr/include'

HEADERS = ['alarm_event.h', 'qsi_umap_impl.h', 'qsi_tlv_defs.h', 'QSI_API.h']

def load_headers():
    print("Looking for header files in " + INCLUDE_PATH)
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
                    #     continue
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


def init(header_path=None, serial_number_string=None):
    # Initialize libs and connect to a device.
    # If you provide a header_path, then use it.
    # If you provide a serial number string, then connect by serial number.
    global laser_lib
    global INCLUDE_PATH
    if header_path is not None:
        INCLUDE_PATH = header_path

    # load up the headers and shared libs
    load_headers()

    # load up the shared libs
    load_libs()

    # declare the laser alignment entrypoint
    ffi.cdef("int32_t quantum_laser_beamsteering(int32_t row, const char *json_procedure);")

    try:
        laser_lib = ffi.dlopen('libbeamsteer.so')
    except OSError:
        laser_lib = None
        print('Warning: laser library not available')

    lib.quantum_initialize_dll(ffi.NULL)
    connect_success = connect(serial_number_string)
    return connect_success
    
def connect(serial_number_string=None):
    # Connect to a device.
    # If you provide a serial number string, then connect by serial number.
    if serial_number_string is not None:
        rc = lib.quantum_connect_to_device_by_serial_number(text2cffi(serial_number_string))
    else:
        rc = lib.quantum_connect_device(0)
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
    
def enable_logging(fname):
    rc = lib.quantum_enable_logging(text2cffi(fname))
    return
    
def disconnect():
    lib.quantum_disconnect_device()

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

                        [ "sweep", {"motor":"X","span":  40,"step": 2,"goal":"maximize_mean" } ],
                        [ "sweep", {"motor":"Y","span":  80,"step": 4,"goal":"maximize_mean" } ]
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


def wait_locked():
    MCLK_clock_source = text2cffi('MCLK')
    READ_clock_source = text2cffi('READ')
    count_num = 100
    
    count = count_num
    sleep_time = 0.1 # sec
#    while count > 0 and lib.quantum_get_MCLK_lock_status() != lib.LIBQSI_STATUS_CLOCK_LOCKED:
    while count > 0 and lib.quantum_get_clock_lock_status(MCLK_clock_source) != lib.LIBQSI_STATUS_CLOCK_LOCKED:
        time.sleep(sleep_time)
        count -= 1
    if count == 0:
        print("ERROR - quantum_get_clock_lock_status on MCLK never returned LOCKED after %d attempts with %.2f sleep time" % (count_num, sleep_time))
    else:
        print("MCLK returned LOCKED after %d attempt(s)" % (101-count))
            
    count = count_num
    while count > 0 and lib.quantum_get_clock_lock_status(READ_clock_source) != lib.LIBQSI_STATUS_CLOCK_LOCKED:
        time.sleep(sleep_time)
        count -= 1
    if count == 0:
        print("ERROR - quantum_get_clock_lock_status on READ never returned LOCKED after %d attempts with %.2f sleep time" % (count_num, sleep_time))
    else:
        print("READ returned LOCKED after %d attempt(s)" % (101-count))


# define a convenience function that creates a numpy array from a series of frames captured
def capture(num_frames, mode='cds'):
    # capture our requested frames into RAM
    num_frames_actually_captured = ffi.new('uint32_t *')
    frames = ffi.new('streaming_frame_header_t ***')
    lib.quantum_capture_n_frames(num_frames, num_frames_actually_captured, frames)
    if num_frames != num_frames_actually_captured[0]:
        print('ERROR - only captured %s of %d frames?' % (num_frames_actually_captured[0], num_frames))
        return None

    # create a new numpy array
    frame_list = frames[0]
    frame = frame_list[0]
    num_bins = frame.total_bins_available
    if mode == 'rx':
        num_bins = 1
    elif mode == 'raw':
        num_bins = 2

    num_rows = frame.enabled_rows_per_frame
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
        if mode == 'cds':
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

##############################################
## Streaming:
## First call start_streaming().
## Then use get_streaming_frames() to grab some frames when you want them.
## When done, call stop_streaming().
##
## get_streaming_frames() sets capture_frames_enable = True, which makes
##     streaming_callback() start to grab frames as they arrive.

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
    print("Start streaming")
    
    if not streaming:
        abort_streaming = False
        ret = lib.quantum_streaming_capture_sequence(streaming_callback, 0, ffi.NULL, 0)
        if ret == lib.LIBQSI_STATUS_SUCCESS:
            streaming = True
            print("Success starting streaming")
        else:
            print("Error starting streaming %d" % ret)
            # Can retry here if needed      
    return

def stop_streaming():
    global abort_streaming
    print("Stop streaming")
    
    if streaming:
        lib.quantum_stream_disable()
        abort_streaming = True
        
    while (streaming == True):
        # Still streaming
        time.sleep(0.1)
    return

# This callback only works once load_headers() has executed
#@ffi.callback("int32_t(libqsi_stream_notify_type_t, libqsi_stream_source_t, uint8_t *, uint32_t, uint32_t, libqsi_frame_type_t, void *)")
@ffi.callback("int32_t(uint32_t, uint32_t, uint8_t *, uint32_t, uint32_t, uint32_t, void *)")
def streaming_callback(notify_type, stream_source, packet_buffer, packet_size, max_packet_size, frame_type, user_defined):
    # This is called every time a frame is available
    global streaming, streaming_callback_count, capture_frame_ndx, capture_frames_enable, current_streaming_frame_header, req_header
    
    ret = lib.STATUSMGR_ACK
    
    if notify_type == lib.LIBQSI_STREAM_NOTIFY_PACKET and frame_type == lib.LIBQSI_FRAMETYPE_PROCESSED_FRAMES:
#        print('process frame -- notify_type: %s, frame_type: %s' % (notify_type, frame_type))

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
#    # get a pointer to the CDS data
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
    print('setting device config: %s' % filename)
    results = ffi.new('int32_t *')
    rc = lib.quantum_JSON_configuration_from_file(text2cffi(filename), lib.LIBQSI_CFG_ALL, results)
    if rc != lib.LIBQSI_STATUS_SUCCESS:
        desc = lib.quantum_get_status_description(rc)
        print('ERROR failed to load config: ', ffi.string(desc).decode('UTF-8'))


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
        args = '{"stabilization_time":300}'  # default recommendation is 300 seconds
        if user_args is not None:
            args = user_args
        lib.quantum_laser_blocking(lib.LIBQSI_LASER_ON, infoCB, text2cffi(args), ffi.NULL)
        lib.quantum_set_MCLK_source(lib.LIBQSI_REFSRC_RECOVERED)
        wait_locked()


#enable automatic ICW power stabilization
def enable_ICW(verbose):
    lib.quantum_start_ICW_stabilization()
    if verbose == 1:
        print('ICW power stablization is ACTIVE.')


#disable automatic ICW power stabilization
def disable_ICW(verbose):
    lib.quantum_end_ICW_stabilization()
    if verbose == 1:
        print('ICW power stabilization is DISABLED')


#perform motor movement relative to current position
#Legacy API call:   quantum_manipulate_alignment_motor(motor_identifier_t motor_index, int32_t number_of_steps, int32_t step_increment, float coil_current, int32_t coil_sleep_modifier_percentage, int32_t *current_offset_from_home)
#Preferred API call:       quantum_move_motor_relative(motor_identifier_t motor_index, int32_t number_of_steps, int32_t step_increment, float coil_current, int32_t coil_sleep_modifier_percentage, int32_t *current_offset_from_home, int32_t override_travel_restrictions)
def move_motor_relative(motor_index, number_of_steps, override_travel_restrictions, motor_settings, verbose):
    
    lib.quantum_move_motor_relative(motor_index, number_of_steps, motor_settings['step_increment'], motor_settings['maximum_coil_current'], motor_settings['coil_sleep_modifier_percentage'], motor_settings['current_offset_from_home'], override_travel_restrictions)
   
    if verbose == 1:
        print('Motor: ',motor_index,' moved: ', number_of_steps, ' steps to new position: ', motor_settings['current_offset_from_home'][0])
    
    
#perform motor movement to absolute position
#Legacy API call:   quantum_seek_alignment_motor(motor_identifier_t motor_index, int32_t desired_step_index, int32_t step_increment, float coil_current, int32_t coil_sleep_modifier_percentage, int32_t *current_offset_from_home)
#Preferred API call:       quantum_move_motor_absolute(motor_identifier_t motor_index, int32_t desired_step_index, int32_t step_increment, float coil_current, int32_t coil_sleep_modifier_percentage, int32_t *current_offset_from_home, int32_t override_travel_restrictions)
def move_motor_absolute(motor_index, desired_step_index, override_travel_restrictions, motor_settings, verbose):
    pre_move_position = motor_settings['current_offset_from_home'][0]
    
    lib.quantum_move_motor_absolute(motor_index, desired_step_index, motor_settings['step_increment'], motor_settings['maximum_coil_current'], motor_settings['coil_sleep_modifier_percentage'], motor_settings['current_offset_from_home'], override_travel_restrictions)

    if verbose == 1:
        print('\nMotor: ',motor_index,' moved from position: ', pre_move_position, ' to current position: ', motor_settings['current_offset_from_home'][0])


#report motor settings and status information
#Legacy API call:  quantum_get_alignment_motor_info(motor_identifier_t motor_index, float *degrees_per_step, int32_t *maximum_steps, int32_t *home_is_CW, int32_t *current_offset_from_home, int32_t *coil_sleep_modifier_percentage, float *maximum_coil_current)
#Preferred API call:         quantum_get_motor_info(motor_identifier_t motor_index, float *degrees_per_step, int32_t *maximum_steps, int32_t *minimum_steps, int32_t *home_is_CW, int32_t *current_offset_from_home, int32_t *coil_sleep_modifier_percentage, float *maximum_coil_current)
def get_motor_info(motor_index, verbose):
    degrees_per_step = ffi.new('float *')
    maximum_steps = ffi.new('int32_t *')
    minimum_steps = ffi.new('int32_t *')
    home_is_CW = ffi.new('int32_t *')
    current_offset_from_home = ffi.new('int32_t *')
    coil_sleep_modifier_percentage = ffi.new('int32_t *')
    maximum_coil_current = ffi.new('float *')
    step_increment = 8     #the size of the sub-movemements used to achieve a 'number_of_steps' movement 
         
    lib.quantum_get_motor_info(motor_index, degrees_per_step, maximum_steps, minimum_steps, home_is_CW, current_offset_from_home, coil_sleep_modifier_percentage, maximum_coil_current)
    
    motor_settings = {'motor_id': motor_index, \
                      'degrees_per_step':degrees_per_step[0], \
                      'maximum_steps': maximum_steps[0], \
                      'minimum_steps': minimum_steps[0], \
                      'home_is_CW':home_is_CW[0], \
                      'current_offset_from_home':current_offset_from_home, \
                      'coil_sleep_modifier_percentage':coil_sleep_modifier_percentage[0], \
                      'maximum_coil_current': maximum_coil_current[0], \
                      'step_increment':step_increment, \
                      }
    
    if verbose == 1:
        print('\nGet_Motor_Info: ', \
              '  motor_id: ', motor_index, \
              '  degrees_per_step: ', degrees_per_step[0], \
              '  maximum_steps: ', maximum_steps[0], \
              '  minimum_steps: ', minimum_steps[0], \
              '  home_is_CW: ', home_is_CW[0], \
              '  current_offset_from_home: ', current_offset_from_home[0], \
              '  coil_sleep_modifier_percentage: ', coil_sleep_modifier_percentage[0], \
              '  maximum_coil_current: ', maximum_coil_current[0], \
              '  step_increment: ', step_increment, \
              '\n')

    return motor_settings


#perform motor homing
#Legacy API call:       quantum_home_alignment_motor(motor_identifier_t motor_index)
#Preferred API call:    quantum_home_alignment_motor(motor_identifier_t motor_index)
def home_motor(motor_index, verbose):
    lib.quantum_home_alignment_motor(motor_index)

    if verbose == 1:
        print('\nMotor: ', motor_index, 'is homed.')


#define motor index table
#Legacy API call:       (none)
#Preferred API call:    (none)
#NOTE: These values are set in the QSI_API.h, but are exposed here for custom configuration
def set_motor_table(verbose):
    motor_table = {'MOTOR_X': 1, \
                   'MOTOR_Y': 2, \
                   'MOTOR_THETA_X': 3, \
                   'MOTOR_THETA_Y': 4, \
                   'MOTOR_ATTENUATOR': 5, \
                   'MOTOR_ICW': 6, \
                   'MOTOR_ROLL': 7, \
                   'MOTOR_UNUSED_7': 8, \
                  }

    if verbose == 1:
        print('\nSet_Motor_Table: ', motor_table)

    return motor_table

#define the motor currents and offset to home
#Legacy API call:       quantum_align_motor(motor_identifier_t motor_index, float alignment_current, float homing_current, int32_t steps_to_home, int32_t sleep_coil_percentage_of_drive)
#Preferred API call:    quantum_align_motor(motor_identifier_t motor_index, float alignment_current, float homing_current, int32_t steps_to_home, int32_t sleep_coil_percentage_of_drive);
def align_motor(motor_index, alignment_current, homing_current, steps_to_home, sleep_coil_percentage_of_drive, verbose):
    lib.quantum_align_motor(motor_index, alignment_current, homing_current, steps_to_home, sleep_coil_percentage_of_drive)

    if verbose == 1:
        print('Motor: ', motor_index, ' settings updated to:', \
              'Alignment current: ', alignment_current, \
              'Homing current: ', homing_current, \
              'Steps to home: ', steps_to_home, \
              'Sleep coil percentage', sleep_coil_percentage_of_drive)

def simple_capture():
    cdsData = capture(10, 'cds')
    if cdsData is not None:
        cdsImg = cdsData.mean(axis=0)
        data = cdsImg[0, :, :]
        print('cds data mean: %s stdev: %s' % (data.mean(), data.std()))

def set_streaming(mode='CDS'):
    if (mode == 'CDS'):
        lib.quantum_change_dataengine_streaming_mode(lib.DATASTREAM_PROCESSOR_CDS_STREAM)
    else:
        lib.quantum_change_dataengine_streaming_mode(lib.DATASTREAM_PROCESSOR_RAW_STREAM)
    lib.quantum_synchronize_fpga_sensor_interface()  # needed when we change FPGA streaming mode
    wait_locked()
    
def get_streaming_mode(verbose=False):
    mode = lib.quantum_get_datastream_processor()
    if verbose:
        if mode == lib.DATASTREAM_PROCESSOR_CDS_STREAM:
            print("Streaming mode is currently CDS")
        elif mode == lib.DATASTREAM_PROCESSOR_RAW_STREAM:
            print("Streaming mode is currently RAW")
    return mode

def optimize_vref():
    mode_start = get_streaming_mode()
    if isDigital:
        vref_target = 750.0
    else:
        vref_target = 3000.0

    current_vref = ffi.new('float *')
    if isDigital:
        vrefsh_t = text2cffi('vrefsh_t')
        vrefsh_b = text2cffi('vrefsh_b')
    else:
        vrefsh_t = text2cffi('vrefsht')
        vrefsh_b = text2cffi('vrefshb')
    lib.quantum_voltage_get(vrefsh_t, current_vref)
    cur_vref = current_vref[0]
    vref_range = 0.25
    vref_inc = 0.01
    set_streaming(mode='RAW')
    start_col = 0
    end_col = 512
    vref = cur_vref - vref_range
    best_vref = -1
    while vref <= (cur_vref + vref_range):
        lib.quantum_voltage_set(vrefsh_t, vref)
        lib.quantum_voltage_set(vrefsh_b, vref)
        imgData = capture(10, 'rx')
#        print('captured rx shape: %s' % str(imgData.shape))
        avgData = np.mean(imgData, axis=0)
        mean = avgData[0, :, start_col:end_col].mean()
        print('vref: %.4f mean: %.1f' % (vref, mean))
        if mean >= vref_target:
            best_vref = vref
            break
        else:
            vref += vref_inc

    if best_vref == -1:
        best_vref = cur_vref
    lib.quantum_voltage_set(vrefsh_t, best_vref)
    lib.quantum_voltage_set(vrefsh_b, best_vref)
    
    if mode_start == lib.DATASTREAM_PROCESSOR_CDS_STREAM:
        set_streaming(mode='CDS')
    return best_vref


def optimize_vref2():
    mode_start = get_streaming_mode()
    if isDigital:
        vref_target = 750.0
    else:
        vref_target = 3000.0

    current_vref = ffi.new('float *')
    if isDigital:
        vrefsh_t = text2cffi('vrefsh_t')
        vrefsh_b = text2cffi('vrefsh_b')
    else:
        vrefsh_t = text2cffi('vrefsht')
        vrefsh_b = text2cffi('vrefshb')
    lib.quantum_voltage_get(vrefsh_t, current_vref)
    cur_vref = current_vref[0]
    vref_range = 0.25
    vref_inc = 0.01
    set_streaming(mode='RAW')
    start_col = 0
    end_col = 512
    vref_low = cur_vref - vref_range
    vref = vref_low
    best_vref = -1
    found = False
    while vref <= (cur_vref + vref_range):
        lib.quantum_voltage_set(vrefsh_t, vref)
        lib.quantum_voltage_set(vrefsh_b, vref)
        imgData = capture(10, 'rx')
        print('captured rx shape: %s' % str(imgData.shape))
        avgData = np.mean(imgData, axis=0)
        mean = avgData[0, :, start_col:end_col].mean()
        print('vref: %s mean: %s' % (vref, mean))
        if mean > vref_target:
            found = (vref > vref_low)
            best_vref = vref - vref_inc
            break
        else:
            vref += vref_inc

    if not found:
        print('warning, could not find optimal vref, reverting to config default')
        best_vref = cur_vref
    lib.quantum_voltage_set(vrefsh_t, best_vref)
    lib.quantum_voltage_set(vrefsh_b, best_vref)
    
    if mode_start == lib.DATASTREAM_PROCESSOR_CDS_STREAM:
        set_streaming(mode='CDS')
    return best_vref, found


def set_vref(best_vref):
    if isDigital:
        vrefsh_t = text2cffi('vrefsh_t')
        vrefsh_b = text2cffi('vrefsh_b')
    else:
        vrefsh_t = text2cffi('vrefsht')
        vrefsh_b = text2cffi('vrefshb')
    lib.quantum_voltage_set(vrefsh_t, best_vref)
    lib.quantum_voltage_set(vrefsh_b, best_vref)

def set_mclk_offset(offset):
    lib.quantum_NANO_MCLK_set_position(offset)

def set_clock_base_offsets(name, base_offsets):
    tvco_read = ffi.new('double *')
    base_offsets_read = ffi.new('int32_t[4]')
    steps = ffi.new('int32_t[4]')
    max_movement = ffi.new('int32_t *', 10)

    rc = lib.quantum_timing_clock_set_bases(lib.LIBQSI_DEVICE_NIOS, text2cffi(name), base_offsets, tvco_read, base_offsets_read, steps, max_movement)
    if rc != lib.LIBQSI_STATUS_SUCCESS:
        desc = lib.quantum_get_status_description(rc)
        print('ERROR setting base offsets: ', ffi.string(desc).decode('UTF-8'))
        
def set_clk_offsets(name, bits, clock_phase_step_array):
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
     
def timegen_row_configure(selected_rows, readout_rows, blanking_rows):
    lib.quantum_timgen_row_configure(selected_rows, readout_rows, blanking_rows)
    
def frame_info():
    # Capture one frame just to get the frame header info
    num_frames_actually_captured = ffi.new('uint32_t *')
    frames = ffi.new('streaming_frame_header_t ***')
    lib.quantum_capture_n_frames(1, num_frames_actually_captured, frames)

    frame_list = frames[0]
    frame_info = frame_list[0]
    return frame_info


def connect_gsl(id_string):
    global laser_lib

    # connect to the device
    rc = lib.quantum_connect_to_device_by_serial_number(text2cffi(id_string))
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
    
def nios_read_bit(address, bit):
    addrVals = ffi.new('uint32_t **')
    transfer_status = ffi.new('int32_t *')
    lib.quantum_nios_read(address, 1, addrVals, 0, transfer_status)
    if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
        print("failed to read address %s from nios" % address)
        return False
    addr = addrVals[0]
    addrVal = addr[0]
    addrVal &= (1 << bit)

    if addrVal > 0:
        return 1
    else:
        return 0
    
def nios_write_bit(address, bit, val):
    addrVals = ffi.new('uint32_t **')
    transfer_status = ffi.new('int32_t *')
    lib.quantum_nios_read(address, 1, addrVals, 0, transfer_status)
    if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
        print("failed to read address %s from nios" % address)
        return False
    addr = addrVals[0]
    addrVal = addr[0]
    if val == 1:
        addrVal = addrVal | (1 << bit)
    else:
        addrVal = addrVal & ~(1 << bit)
    addr[0] = addrVal
    lib.quantum_nios_write(address, 1, 0, addr, transfer_status)
    if transfer_status[0] != lib.LIBQSI_STATUS_SUCCESS:
        print("failed to write address %s to nios" % address)
        return False
    lib.quantum_free_memory(addrVals[0])
    return True

def enable_gsl(atto_hack=False):
    if atto_hack:
        atto_hack_enable_gsl()
    else:
        rc = lib.quantum_set_laser_enabled(1)
        if rc != lib.LIBQSI_STATUS_SUCCESS:
            print("Error enabling gsl %d\n",rc)
    return

def disable_gsl(atto_hack=False):
    if atto_hack:
        atto_hack_disable_gsl()
    else:
        rc = lib.quantum_set_laser_enabled(0)
        if rc != lib.LIBQSI_STATUS_SUCCESS:
            print("Error disabling gsl %d\n",rc)
    return

def gsl_mux_set(port):
    rc = lib.quantum_gsl_mux_set(port)
    if rc != lib.LIBQSI_STATUS_SUCCESS:
        print("Error setting gsl mux %d\n",rc)
    return

def atto_hack_enable_gsl():
    nios_write_bit(0x42400, 18, 1)
    
def atto_hack_disable_gsl():
    nios_write_bit(0x42400, 18, 0)
    
def set_voltage_source(name, voltage):   
    rc = lib.quantum_voltage_set(text2cffi(name), voltage)

    if (rc != lib.LIBQSI_STATUS_SUCCESS):
        print("Error setting %s to %f : %d\n" % (name,voltage,rc))
    else:
#        print("Set voltage %s to %f" % (name, voltage))
        return
    
def get_temperature(target_database, tlv_number):
    temperature = 0.0;
    read_len  = ffi.new('int32_t *')
    data = ffi.new('char **')

    rc = lib.quantum_tlv_ez_get(target_database, tlv_number, read_len, data)
    
    if rc == lib.LIBQSI_STATUS_SUCCESS:
        temp_string = tostr(data[0])
        if temp_string == "OPEN" or temp_string == "SHORT" or temp_string == "N/A":
            rc = lib.LIBQSI_STATUS_UNKNOWN_ERROR;
        else:
            temperature = float(temp_string)
    
    return temperature, rc
    
def get_chip_temperature():
    t1, rc = get_temperature(lib.LIBQSI_TLVDB_CM, lib.TLV_STAT_SENSOR_TEMP1)
    t2, rc = get_temperature(lib.LIBQSI_TLVDB_CM, lib.TLV_STAT_SENSOR_TEMP2)
    chip_temp1 = float(t1)
    chip_temp2 = float(t2)
    return chip_temp1, chip_temp2