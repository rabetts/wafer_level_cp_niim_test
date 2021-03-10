"""
This script will connect to the device, send configuration, 
run a sequence file, stream one frame,  
display the frame then disconnect from the device.
"""

#from qsi_falcon import qsi_helpers as qsi
import qsi_helpers as qsi
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import platform
import time

from operator import attrgetter
from collections import namedtuple

# Setup default filenames
platform_name = platform.system()
if platform_name == "Windows":
    
    default_reg_file = R'C:\Users\dfrier\Documents\Python Scripts\nickel_testing\cfg\spi_reg_map.csv'
    seq_file         = R'C:\Users\dfrier\Dropbox (Quantum-SI)\Q-Si Chips\nickel\nickel_testing\seq\AFE_ramp_regs.seq'
    config_file      = R'C:\Users\dfrier\Dropbox (Quantum-SI)\Q-Si Software\Falcon 64\chewie\Configuration Files\Unified_Q9001\q9001_CHIPLET0_128R_1024C_RAW_4SP_8p425M_cont.json'
    dump_dir         = R'C:\Users\qsi\Desktop\nickel_testing\runs'

# load up the headers, libs, and connect to our device
initialized = qsi.init()
#if not initialized:
    #sys.exit()

#Assume that the high speed sampler will use c0_clk to drive sampler
hss_clock = 0

def build_regs():
    '''
    Read in a comma separated values file that describes the Q9001 configuration
    registers to build lists of default values for registers and fields within
    those registers.  These lists can later be used to compare the current
    device configuration to the default values using the methods
    def diff_regs() and diff_bits().
    
    Parameters:
        None
    '''
    global default_reg_file
    global default_regs
    global default_bits
    global echo
    
    reg        = namedtuple('reg', ['name','base_addr','value','access'])
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
            reg_name      = cell[2]
            reg_base_addr = int(cell[0])
            reg_value     = int(cell[4],2)
            if 'RO' in cell[7]:
                reg_access = 'RO'
            else:
                reg_access = 'RW'
            bitfields_str = cell[8].split('\n')
            #bitfields = bitfields_str[0]
            bitfield_list = bitfields_str[0].split(' ')
            # now the individual bitfields into another list of named tuples
            # the bitfield list is ordered msb to lsb, calculate position and range based on list order and existence of [x] in names
            bit_pos   = 16
            for bf in bitfield_list:
                bf_name = bf.split('[')
                bf_width = 1
                if ('[' in bf) and (':' in bf):
                    bf_bits = bf.split(':')
                    bf_bits = bf_bits[0].split('[')
                    bf_width = int(bf_bits[1]) + 1
                bit_pos   = bit_pos - bf_width
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
    
def con():
    '''
    Connect to a Nickel or Nano device over USB.
    
    Parameters:
        None
    '''
    # connect to the device
    rc = qsi.lib.quantum_connect_device(0)
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print('Failed to connect to device, error %s' % rc)
        return False
    else:
        # Get the product type
        product_type = qsi.lib.quantum_get_product_type()
        global isDigital
        if (product_type == qsi.lib.LIBQSI_PRODUCT_NANO_D) or (product_type == qsi.lib.LIBQSI_PRODUCT_NICKEL):
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
    qsi.lib.quantum_disconnect_device()

def config(filename=None):
    '''
    Write a configuration file to a connected device.

    Parameters:
        filename - Filename of configuration in json format
    '''
    global config_file
    if filename == None:
        qsi.set_config(config_file)
    else:
        qsi.set_config(filename)
    
def diff_regs():
    '''
    Compare the current Q9001 configuration to the default values and 
    display the differences at the register level.

    Parameters:
        None
    '''
    global default_regs
    global current_regs
    
    for register in default_regs:
        get_name = register.name
        get_reg_value  = spi_get(get_name)
        if get_reg_value != register.value:
            print(register.name + ' = ' + str(get_reg_value) + ' (default = ' + str(register.value) + ')')

def diff_bits():
    '''
    Compare the current Q9001 configuration to the default values and 
    display the differences at the register field level.

    Parameters:
        None
    '''
    global default_bits
    
    for bitfield in default_bits:
        get_name = bitfield.name
        get_reg_value  = spi_get(get_name)
        if get_reg_value != bitfield.value      :
            print(bitfield.name + ' = ' + str(get_reg_value) + ' (default = ' + str(bitfield.value) + ')')

def seq(filename = None):
    '''
    Open and execute the configured default sequence file.

    Parameters: filename - Filename of sequence file to read and process.
                         - If None provided, the filename stored in seq_file 
                           will be used.
    '''
    f = None
        
    if (filename == None):
        f = open(seq_file)
    else:
        f = open(filename)
        
    
    for line in f:
        if '#' in line:
            line = line.split('#')
            line = line[0]
        # remove lead and trail whitespace
        line = line.strip()
        # split remaining string, which only removes single spaces
        line = line.split()
        if len(line) > 0:
            if line[0] == 'setdevice':
                if len(line) == 3:
                    spi_set(line[1],line[2])
                else:
                    print('invalid setdevice command structure')
            elif line[0] == 'getdevice':
                response = spi_get(line[1])
                print('getdevice ' + line[1] +  ' ---> ' + str(response[0]))
            elif line[0] == 'mm':
                if ('x' in line[2]) or ('X' in line[2]):
                    address = int(line[2], 16)
                else:
                    address = int(line[2], 10)
                if len(line) > 3:
                    if ('x' in line[3]) or ('X' in line[3]):
                        param3 = int(line[3], 16)
                    else:
                        param3 = int(line[3], 10)

                if (line[1] == 'w') and (len(line) == 4):
                    mm_w(address,param3)
                elif (line[1] == 'r') and (len(line) == 3):
                    response = mm_r(address)
                    print('mm r' + line[2] + ' ---> ' + str(response[0]))
                elif (line[1] == 'sb') and (len(line) == 4):
                    mm_sb(address,param3)
                elif (line[1] == 'cb') and (len(line) == 4):
                    mm_cb(address,param3)
                elif (line[1] == 'rb') and (len(line) == 4):
                    response = mm_rb(address,param3)
                    print('mm rb' + line[2] + ' ---> ' + str(response[0]))
            elif line[0] == 'wait':
                if len(line) == 2:
                    delay = 0.001 * int(line[1])
                    wait(delay)
            elif line[0] == 'chip2shadow':
                read_config = qsi.ffi.cast('int32_t', 1)
                read_status = qsi.ffi.cast('int32_t', 1)
                ret = qsi.lib.quantum_nickel_read_config_from_sensor(nickel_handle,read_config,read_status)
                if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
                    print('chip2shadow' + 'FAILED')
                elif echo:
                    print('chip2shadow')
    f.close()

def spi_set(address,value):
    '''
    Write the specified Q9001 register on the connected device with the value provided.
    
    Parameters:
        address - The name of register or register field in dot notation.
        value   - The value to set the register or field.
        
    Example:
        spi_set('c0.afe_ctrl_5.ramp_vrefp','7')  # Set for chiplets 0
        spi_set('c*.afe_ctrl_5.ramp_vrefp','7')  # Set for all chiplets
    '''
    global echo
    
    if ('x' in value) or ('X' in value):
        val_int = int(value,16)
    else:
        val_int = int(value,10)
    addr     = qsi.text2cffi(address)
    val      = qsi.ffi.cast('uint16_t',val_int) 
    optimize = qsi.ffi.cast('int32_t', 0)
    ret = qsi.lib.quantum_nickel_set_on_device_using_dot_notation(nickel_handle,addr,val,optimize)
    if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print('setdevice ' + address + ' ' + value + 'FAILED')
    elif echo:
        print('setdevice ' + address + ' ' + value)
        

def spi_get(address):
    '''
    Get the specified Q9001 register from the connected device.
    
    Parameters:
        address - The name of register or register field in dot notation.
                  e.g. 'c0.afe_ctrl_3.ramp_pd' represents chiplet 0 ramp power down
                  Note: Don't use the wildcard for the register or field name.
                  
    Example: 
        reg_value = spi_get('global.aux_adc_data')
    '''
    read_val = qsi.ffi.new('uint16_t *')
    addr     = qsi.text2cffi(address)
    ret = qsi.lib.quantum_nickel_get_from_device_using_dot_notation(nickel_handle,addr,read_val)
    if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print('getdevice ' + ' ' + address + 'FAILED')
    return read_val[0]

def mm_sb(address, position):
    '''
    Set the bit position at the address specified to 1 on the connected device.
    
    Parameters:
        address  - Address number
        position - Bit position.  Position 0 is the least-significant bit.
    '''
    global echo
    
    source_address = qsi.ffi.new('uint32_t *')
    transfer_status = qsi.ffi.new('libqsi_status_t *')

    write_val = None
    position_set = (0x00000001 << position)

    present_val = mm_r(address)
    
    write_val = present_val | position_set
    source_address[0] = write_val

    ret = qsi.ffi.new('uint32_t *')
    ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

    new_val = mm_r(address)
    
    if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS) or (new_val != (present_val | position_set)):
        print('mm sb ' + str(position) + ' ' + str(format(address,'#04x')) + ' FAILED')
    elif echo:    
        print('mm sb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : value ' + str(format(present_val,'#04x')) + ' ---> ' + str(format(new_val,'#04x')))
    

def mm_cb(address,position):
    '''
    Clear the specified address and bit position to 0 on the connected device.
    
    Parameters:
        address  - Address number
        position - Bit position.  Position 0 is the least-significant bit.
    '''
    global echo
    source_address = qsi.ffi.new('uint32_t *')
    transfer_status = qsi.ffi.new('libqsi_status_t *')

    write_val = None
    position_set = (0x00000001 << position)
    position_clear = (0xFFFFFFFF & (~position_set))
    present_val = mm_r(address)
    write_val = present_val & position_clear
    source_address[0] = write_val

    ret = qsi.ffi.new('uint32_t *')
    ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

    new_val = mm_r(address)
    if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS) or (new_val != (present_val & position_clear)):
        print('mm cb ' + str(position) + ' ' + str(format(address,'#04x')) + ' FAILED')
    elif echo:    
        print('mm cb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : value ' + str(format(present_val,'#04x')) + ' ---> ' + str(format(new_val,'#04x')))

def mm_rb(address,position):
    '''
    Read the specified address and bit position on the connected device and
    return its value.
    
    Parameters:
        address  - Address number
        position - Bit position.  Position 0 is the least-significant bit.
    '''
    global echo

    position_get = (0x00000001 << position)
    present_val = mm_r('r',address)
    read_val = (present_val & position_get) >> position

    if echo:    
        print('mm rb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : bit[' + str(position) + '] = ' + str(read_val))
    return read_val


def mm_r(address):
    '''
    Read the specified address on the connected device and return its value.
    
    Parameters:
        address - Address number
    '''
    dest_address = qsi.ffi.new('uint32_t **')
    transfer_status = qsi.ffi.new('libqsi_status_t *')
    ret = qsi.ffi.new('uint32_t *')
    ret = qsi.lib.quantum_nios_read(address,1,dest_address,1,transfer_status)
    read_val = dest_address[0][0]
    qsi.lib.quantum_free_memory(dest_address[0])
    if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS):
        print('mm r ' + ' ' + str(format(address,'#04x')) + ' FAILED')
    elif echo:
        print('mm r ' + str(format(address,'#04x')) + '     : value = ' + str(read_val))
    return read_val

def mm_w(address, value):
    '''
    Write the specified 32-bit value into the specified address on the connected device.
    
    Parameters:
        address - Address number
        value   - Value to write
    '''
    global echo
    
    source_address = qsi.ffi.new('uint32_t *')
    transfer_status = qsi.ffi.new('libqsi_status_t *')

    source_address[0] = value

    ret = qsi.ffi.new('uint32_t *')
    ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

    if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS):
        print('mm w ' + str(format(address,'#04x')) + ' FAILED')
    elif echo:    
        print('mm w ' + str(format(address,'#04x')) + ' : value ' + str(format(value,'#04x')))
    
def wait(delay):
    '''
    Wait for the specified time in milliseconds before returning from the method.
    
    Parameters:
        delay - Time to wait in milliseconds
    '''
    delay_ms = delay / 1000
    time.sleep(delay)
    if echo:
        print('wait ' + str(delay_ms))

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
    supply_name = qsi.text2cffi(target_name)
    old_voltage = 0
    new_voltage = 0

    if (verbose):
        # Read and save the current value of the power supply
        read_val  = qsi.ffi.new('float *')
        qsi.lib.quantum_voltage_get(supply_name, read_val)
        old_voltage = read_val[0]

    # Write a new value for the power supply
    voltage = float(target_v)
    qsi.lib.quantum_voltage_set(supply_name, voltage)

    if (verbose != 0):
        # Read the current value of the power supply
        qsi.lib.quantum_voltage_get(supply_name, read_val)
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
    read_val  = qsi.ffi.new('float *')
    supply_name = qsi.text2cffi(target_name)
    qsi.lib.quantum_voltage_get(supply_name, read_val)
    voltage = read_val[0]
    if (verbose):
        print(target_name + ' = {0:2.3f}'.format(voltage))

    return voltage

def m_get(name, monitor_type):
    '''
    Display a power monitor.
    
    Parameters:
        name         - Name of the power monitor
        monitor_type - "V" for voltage, "I" for current, "VI" for voltage and current
        
    Example:
        m_get("12V","VI")
    '''
    # Read a monitored value
    #monitor_name = qsi.text2cffi('VA18')
    monitor_name = qsi.text2cffi(name)
    monitor_val = qsi.ffi.new('monm_information_t *')

    qsi.lib.quantum_get_monitor_info(monitor_name, monitor_val)

    if "V" in monitor_type:
        # Voltage monitor uses index 0
        print(str(qsi.ffi.string(monitor_val.name), 'utf-8'), "Voltage Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[0].act, monitor_val.entry[0].ref_val, monitor_val.entry[0].avg))

    if "I" in monitor_type:
        # Current monitor uses index 1
        print(str(qsi.ffi.string(monitor_val.name), 'utf-8'), "Current Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[1].act, monitor_val.entry[1].ref_val, monitor_val.entry[1].avg))


def pd_ramp():
    spi_set('c*.afe_ctrl_3.ramp_pd','1')
  
def pu_ramp():
    spi_set('c*.afe_ctrl_3.ramp_pd','0')
  

def global_reset():
    spi_set('c*.dig_clk_ctrl.global_reset','1')
    wait(1)
    spi_set('c*.dig_clk_ctrl.global_reset','0')

def afe_reset():
    spi_set('c*.dig_clk_ctrl.afe_reset','1')
    wait(0.1)
    spi_set('c*.dig_clk_ctrl.afe_reset','0')

def aux_afe_reset():
    spi_set('global.aux_ctrl_2.aux_afe_reset','1')
    wait(0.1)
    spi_set('global.aux_ctrl_2.aux_afe_reset','0')

def set_ch(channel):
    if (channel >= 0) and (channel <16):
        ch = 0x1 << channel
        mm_w(0x41230,ch)
    else:
        mm_w(0x41230,0xFFFF)
        
        
def frame_get():
    global capture_array
    # Capture one frame.  Data is indexed [frames][timebins][rows][columns]
    capture_array = qsi.capture_raw(1,'raw')

def hist_cds(reset = 1, signal = 5):
    '''
    Capture one raw frame then display a histogram representing the
    pixels in row 0.

    Parameters:
        reset  - 0-based sample phase number used for reset 
        signal - 0-based sample phase number used for signal 
    '''
    # Capture one frame.  Data is indexed [frames,sample_phases,rows,columns]
    capture_array = qsi.capture_raw(1,'raw')

    # Calculate CDS using specified sample phases
    frame_num = 0

    cds = capture_array[frame_num,signal,:,:] - capture_array[frame_num,reset,:,:]
    print('mean: %f std: %f' % (np.mean(cds), np.std(cds)))

    (n, bins) = np.histogram(cds,bins=np.arange(1,1022,1), density=False)  # Ignore 0 and full scale from histogram

    # Plot data of interest
    plt.figure(figsize=(10,10))

    plt.bar(bins[:-1], n,1)
    plt.title('Frame ' + str(frame_num) + ', CDS of reset(' + str(reset) + ') and signal (' + str(signal) + ')')
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()


def hist(sample_phase = 0):
    '''
    Capture one raw frame then display a histogram representing the
    pixels in row 0.

    Parameters:
        sample_phase - Sample phase of data to display.
    '''
    # Capture one frame.  Data is indexed [frames,timebins,rows,columns]
    capture_array = qsi.capture_raw(1,'raw')
    print('capture array mean %f' % np.mean(capture_array))
    print('capture array std dev %f' % np.std(capture_array))

    capture2 = capture_array[0,sample_phase,:,:]
    print('Phase %s mean %f' % (sample_phase, np.mean(capture2)))
    print('Phase %s std dev %f' % (sample_phase, np.std(capture2)))
    
    (n, bins) = np.histogram(capture2,bins=np.arange(1,1022,1), density=False)  # Ignore 0 and full scale from histogram

    # Plot data of interest
    frame_num = 0
    
    plt.figure(figsize=(10,10))

    plt.bar(bins[:-1], n,1)

    #plt.imshow(capture_array[frame_num][bin_num])
    #plt.plot(capture_array[frame_num][bin_num][0])
    #plt.hist(capture_array[frame_num][bin_num][0],range(10,1000),histtype='step')
    plt.title('Frame '+str(frame_num)+', Bin '+str(sample_phase))
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()
    

def line(sample_phase = 0):
    '''
    Capture one raw frame then display a line graph representing the
    pixels in row 0.

    Parameters:
        sample_phase - Sample phase of data to display.
    '''
    # Capture one frame.  Data is indexed [frames][sample_phase][rows][columns]
    capture_array = qsi.capture_raw(1,'raw')

    #(n, bins) = np.histogram(capture_array[0][0][0:511],bins=np.arange(10,1000,1), density=False)  # NumPy version (no plot)

    # Plot data of interest
    frame_num = 0
    
    plt.figure(figsize=(10,10))

    #plt.plot(.5*(bins[1:]+bins[:-1]), n)
    #plt.bar(bins[:-1], n,1)


    #plt.imshow(capture_array[frame_num][bin_num])
    plt.plot(capture_array[frame_num][sample_phase][1])
    #plt.hist(capture_array[frame_num][sample_phase][0],range(10,1000),histtype='step')
    plt.title('Frame '+str(frame_num)+', Bin '+str(sample_phase))
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()

def lines(count, sample_phase=0):
    '''
    Capture one raw frame then display a line graph representing the
    pixels in the specified number of rows.

    Parameters:
        count        - Create a line graph for rows 0 to count.
        sample_phase - Sample phase of data to display.
    '''
    # Capture one frame.  Data is indexed [frames][sample_phase][rows][columns]
    capture_array = qsi.capture_raw(1,'raw')

    #(n, bins) = np.histogram(capture_array[0][0][0:511],bins=np.arange(10,1000,1), density=False)  # NumPy version (no plot)

    # Plot data of interest
    frame_num = 0
    plt.figure(figsize=(10,10))

    #plt.plot(.5*(bins[1:]+bins[:-1]), n)
    #plt.bar(bins[:-1], n,1)


    #plt.imshow(capture_array[frame_num][sample_phase])
    for i in range(0,count):
        plt.plot(capture_array[frame_num][sample_phase][i])
    #plt.hist(capture_array[frame_num][sample_phase][0],range(10,1000),histtype='step')
    plt.title('Frame '+str(frame_num)+', Bin '+str(sample_phase))
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()

def frame(sample_phase=0):
    '''
    Capture one raw frame then display the specified sample phase

    Parameters:
        sample_phase - Sample phase to display
    '''
    # Capture one raw frame.  Data is indexed [frames][sample_phases][rows][columns]
    capture_array = qsi.capture_raw(1,'raw')

    # Plot data of interest
    frame_num = 0
    plt.figure(figsize=(10,10))

    plt.imshow(capture_array[frame_num][sample_phase])
    #plt.plot(capture_array[frame_num][bin_num][0])
    #plt.hist(capture_array[frame_num][bin_num][0],range(10,1000),histtype='step')
    plt.title('Frame '+str(frame_num)+', Bin '+str(sample_phase))
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()

def phases():
    '''
    Capture one raw frame then display all sample phases
    '''
    # Capture one raw frame.  Data is indexed [frames][sample_phases][rows][columns]
    capture_array = qsi.capture_raw(1,'raw')

    present_val = mm_r(0x41024)
    sample_phases = (present_val & 0xFF)
    frame_num = 0

    # Plot data of interest
    for phase in range(0,sample_phases):
        plt.figure(figsize=(10,10))
    
        plt.imshow(capture_array[frame_num][phase])
        plt.title('Frame '+str(frame_num)+', Phase '+str(phase))
        plt.xlabel('$x$')
        plt.ylabel('$y$')
        plt.show()


def raw2file(filename=None):
    '''
    Capture one raw frame then save it to file.

    Parameters:
        filename     - Filename to write captured frame.
                       If 'None', will default to 'raw_dump.bin'
    '''
    if filename == None:
        output_file = 'raw_dump.bin'
    else:
        output_file = filename
   
    capture_array = qsi.capture_raw(1,'raw');
    np.savetxt(output_file,capture_array[0][0][0:9],fmt='%i',delimiter=",")

def dnl():

    capture_array = qsi.capture_raw(1,'raw')
    value = None

    h = np.zeros(1024)
    diff = np.zeros(1024,dtype=np.float32)
    ave = None
    
    dims = capture_array.shape
    row_count = dims[2]
    sample_count = dims[3]
    
    for row in range(0,row_count-1):
        for sample in range(0,sample_count-1):
            value = (capture_array[0][0][row][sample])
            h[value] +=1

    total =0
    for index in range(1024):
        total = total + h[index]

    ave = total/1024
    for index in range(1,1022):
        diff[index] = (h[index]/ave)-1
    
    plt.plot(diff[1:1022])
    plt.title('Frame '+str(0)+', Bin '+str(0))
    plt.xlabel('$x$')
    plt.ylabel('$y$')
    plt.show()

def ramp(columns = 1024, chiplet = 0, adc = 15):
    '''Write configuration to enable the Q9001 ramp function using the
    specified chiplet and ADC.
    
    Arguments:
        columns - Number of columns to read [0-4095]
        chiplet - Chiplet number to read [0-3]
        adc     - ADC number [0-15]
    '''
    
    if (columns < 0) or (columns > 4095):
        print("columns out-of-range")
        return
    
    if (chiplet < 0) or (chiplet > 3):
        print("chiplet out-of-range")
        return
    
    if (adc < 0) or (adc > 15):
        print("adc out-of-range")
        return
    
    # Ensure the ramp configuation parameters are set appropriately.
    # These should be the default values for all configurations.
    spi_set('c*.afe_ctrl_0.adc_vtr_sel','5')        # ADC trim capacitor
    spi_set('c*.afe_ctrl_0.isf','63')               # Source follower bias current
    spi_set('c*.afe_ctrl_0.adc_vcm_sel','1')        # ADC common mode voltage select
    spi_set('c*.afe_ctrl_0.adc_vfs_sel','1')        # ADC full scale voltage select

    spi_set('c*.afe_ctrl_2.pga_vcm_sel','1')        # PGA Vcmi, Vcmo adjust
    spi_set('c*.afe_ctrl_2.pga_gain','3')           # PGA gain

    spi_set('c*.afe_ctrl_1.ib_80u','3')             # ADC comparator bias
    spi_set('c*.afe_ctrl_1.ib_100u_6','2')          # PGA amplifier bias
    spi_set('c*.afe_ctrl_1.ib_100u_5','2')          # PGA Vfs bias
    spi_set('c*.afe_ctrl_1.ib_100u_4','3')          # PGA reference generator bias
    spi_set('c*.afe_ctrl_1.ib_100u_3','3')          # ADC Vfs bias
    spi_set('c*.afe_ctrl_1.ib_100u_2','2')          # ADC reference generator bias
    spi_set('c*.afe_ctrl_1.ib_100u_1','2')          # ADC DLL charge pump bias
    spi_set('c*.afe_ctrl_1.ib_100u_0','2')          # ADC DLL V to I bias

    spi_set('c*.afe_ctrl_3.bgap_rext_en','0')       # Bandgap external resistor enable

    spi_set('c*.afe_ctrl_2.ain_en','0')             # AFE 
    spi_set('c*.afe_ctrl_2.clk_sel','15')           # AFE clock select

    spi_set('c*.afe_ctrl_3.aout_tile_sel','7')      # PGA Channel AOUT select within each tile
    spi_set('c*.afe_ctrl_3.aout_tile_disable','0xF') # AOUT mux disable 

    spi_set('c*.afe_ctrl_4.tsense_pd','0')          # Temperature sensor power down
    spi_set('c*.afe_ctrl_4.tsense_sel','0')         # Temperature sensor select
    spi_set('c*.afe_ctrl_4.hs_amux_pd','0')         # 
    spi_set('c*.afe_ctrl_4.hs_amux_sel','0')        #
    spi_set('c*.afe_ctrl_4.electrode_sampler_pd','7')   #
    spi_set('c*.afe_ctrl_4.electrode_sampler_sela','5') #
    spi_set('c*.afe_ctrl_4.aout_ramp_sel','0')      # Ramp module AOUT select
    spi_set('c*.afe_ctrl_4.aout_ramp_disable','1')  # Ramp module AOUT mux disable

    spi_set('c*.afe_ctrl_5.ramp_vrefp','7')         # Ramp Vrefp control
    spi_set('c*.afe_ctrl_5.ramp_vrefn','7')         # Ramp Vrefn control
    spi_set('c*.afe_ctrl_5.ramp_gain','3')          # Ramp slope control

    spi_set('c*.ramp_reset_start','1')              # AFE ramp reset start count
    spi_set('c*.ramp_reset_stop','2')               # AFE ramp reset stop count
    spi_set('c*.ramp_hold_start','0xFFFE')          # AFE ramp hold start count
    spi_set('c*.ramp_hold_stop','0xFFFF')           # AFE ramp hold stop count

    # Configure the chiplets to enable the ramp
    spi_set('c*.afe_ctrl_5.vref_range','3')         # Voltage range for the column reference voltage
    spi_set('c*.afe_ctrl_5.vref_ctrl','9')          # Voltage setpoint for the column reference voltage
    spi_set('c*.afe_ctrl_5.vcol_en','0')            # Select AFE input as Ramp Test output
    
    spi_set('c*.afe_ctrl_3.ramp_pd','0')            # Power up the ramp 

    # Set the number of columns to be long enough to allow the full range of ramp output
    spi_set('c*.col_addr_start','0')
    spi_set('c*.col_addr_span',str((columns-1)))

    # Configure the FPGA readout with the same columns
    present_val = mm_r(0x41028)
    write_val = (present_val & 0xFFFF0000) | columns
    mm_w(0x41028,write_val)
    
    # Configure the FPGA to stream chiplet 0, ADC 15
    mm_w(0x41200,(0x00000001<<chiplet))         # FPGA - CHIPLET_EN_DATA_MASK : Look at a single chiplet
    mm_w(0x41230,(0x00000001<<adc))             # FPGA - ADC_EN_DATA_MASK  Enables individual channels' data. Valid only for single channel, or all channel

def ramp_old(columns = 1024, chiplet = 0, adc = 15):
    '''Write configuration to enable the Q9001 ramp function using the
    specified chiplet and ADC.
    
    Arguments:
        columns - Number of columns to read [0-4095]
        chiplet - Chiplet number to read [0-3]
        adc     - ADC number [0-15]
    '''
    
    if (columns < 0) or (columns > 4095):
        print("columns out-of-range")
        return
    
    if (chiplet < 0) or (chiplet > 3):
        print("chiplet out-of-range")
        return
    
    if (adc < 0) or (adc > 15):
        print("adc out-of-range")
        return
    
    # Ensure the ramp configuation parameters are set appropriately.
    # These should be the default values for all configurations.
    spi_set('c*.afe_ctrl_5.ramp_vrefp','7')
    spi_set('c*.afe_ctrl_5.ramp_vrefn','7')
    spi_set('c*.afe_ctrl_5.ramp_gain','3')
    
    # Configure the chiplets to enable the ramp
    spi_set('c*.afe_ctrl_5.vref_range','1')     # Voltage range for the column reference voltage
    spi_set('c*.afe_ctrl_5.vref_ctrl','30')     # Voltage setpoint for the column reference voltage
    spi_set('c*.afe_ctrl_5.vcol_en','0')        # Select AFE input as Ramp Test output
    
    spi_set('c*.afe_ctrl_3.ramp_pd','0')        # Power up the ramp 

    # Set the number of columns to be long enough to allow the full range of ramp output
    spi_set('c*.col_addr_start','0')
    spi_set('c*.col_addr_span',str((columns-1)))

    # Configure the FPGA readout with the same columns
    present_val = mm_r(0x41028)
    write_val = (present_val & 0xFFFF0000) | columns
    mm_w(0x41028,write_val)
    
    # Configure the FPGA to stream chiplet 0, ADC 15
    mm_w(0x41200,(0x00000001<<chiplet))         # FPGA - CHIPLET_EN_DATA_MASK : Look at a single chiplet
    mm_w(0x41230,(0x00000001<<adc))             # FPGA - ADC_EN_DATA_MASK  Enables individual channels' data. Valid only for single channel, or all channel

def nios_msg(i2c=1):
    if i2c == 0:
        qsi.lib.quantum_set_nios_messaging_i2c(0)
    else:
        qsi.lib.quantum_set_nios_messaging_i2c(1)


def cfg_hss_b0(chiplet=0):
    '''Configure the high speed sampler to monitor B0.
    Arguments:
        chiplet - Chiplet number (0-3) to sample B0
                  or use 4 to use the spine samplers
    '''
    global hss_clock
    
    if (chiplet < 0) or (chiplet > 4):
        print("Chiplet %d is unsupported " % chiplet)

    # Configure common parameters for all cases
    spi_set('c*.dig_clk_ctrl.lvds_pad_pd', '0')                 # power up the LVDS pads that receive the input clocks used by samplers
    spi_set('c*.afe_ctrl_4.electrode_sampler_pd','0')           # NOTE: It seems that 3 or more samplers needed to be enabled in
                                                                #       order to get any of the chiplet or spine samplers to work so
                                                                #       power up all 3 electrode samplers for all chiplets

    spi_set('global.aux_ctrl_4.s0_hs_amux_pd','0')              # power up the spine analog mux
    spi_set('global.aux_ctrl_4.aux_ramp_en','0')                # disable the ramp function
    spi_set('global.aux_ctrl_4.aux_vcol_en','0')                # disable the column function
    spi_set('global.aux_ctrl_4.aux_amux_en','1')                # enable analog mux to be chosen as input to PGA

    spi_set('global.aux_ctrl_4.aux_vref_ctrl','10')             # set voltage setpoint for column reference voltage
    spi_set('global.aux_ctrl_4.aux_vref_range','3')             # set voltage range for column reference voltage  (range 0-3)
    spi_set('global.aux_ctrl_2.aux_pga_gain','0')               # set PGA gain  (range 0-3)


    if (chiplet == 0):
        # Configure the chiplet to enable the high speed sampler
        spi_set('c0.dig_clk_ctrl.hss_clk_sel','1')              # select c0_clk as clock for chiplet 0 samplers
        hss_clock = 0
        
        #spi_set('c0.afe_ctrl_4.electrode_sampler_pd','0')       # power up all 3 electrode samplers
        spi_set('c0.afe_ctrl_4.electrode_sampler_sela','0x0')   # select non-vss input for all 3 electrode samplers
        spi_set('c0.afe_ctrl_4.hs_amux_pd','0')                 # power up the chiplet analog mux. Configuration ignored by chip but configure it anyway
        spi_set('c0.afe_ctrl_4.hs_amux_sel','0')                # select hss_out<0> (B0/VSS)
    
        # Configure auxiliary AFE control registers when using chiplet samplers
        spi_set('global.aux_ctrl_4.s0_hs_amux_sel','9')         # select analog mux input from chiplet 0

    elif (chiplet == 1):
        # Configure the chiplet to enable the high speed sampler
        spi_set('c1.dig_clk_ctrl.hss_clk_sel','1')              # select c1_clk as clock for chiplet 1 samplers
        hss_clock = 1

        #spi_set('c1.afe_ctrl_4.electrode_sampler_pd','0')       # power up all 3 electrode samplers
        spi_set('c1.afe_ctrl_4.electrode_sampler_sela','0x0')   # select non-vss input for all 3 electrode samplers
        spi_set('c1.afe_ctrl_4.hs_amux_pd','0')                 # power up the chiplet analog mux. Configuration ignored by chip but configure it anyway
        spi_set('c1.afe_ctrl_4.hs_amux_sel','0')                # select hss_out<0> (B0/VSS)
        
        # Configure auxiliary AFE control registers when using chiplet samplers
        spi_set('global.aux_ctrl_4.s0_hs_amux_sel','5')         # select analog mux input from chiplet 1

    elif (chiplet == 2):
        # Configure the chiplet to enable the high speed sampler
        spi_set('c2.dig_clk_ctrl.hss_clk_sel','1')              # select c2_clk as clock for chiplet 2 samplers
        hss_clock = 2

        #spi_set('c2.afe_ctrl_4.electrode_sampler_pd','0')       # power up all 3 electrode samplers
        spi_set('c2.afe_ctrl_4.electrode_sampler_sela','0x0')   # select non-vss input for all 3 electrode samplers
        spi_set('c2.afe_ctrl_4.hs_amux_pd','0')                 # power up the chiplet analog mux. Configuration ignored by chip but configure it anyway
        spi_set('c2.afe_ctrl_4.hs_amux_sel','0')                # select hss_out<0> (B0/VSS)
        
        # Configure auxiliary AFE control registers when using chiplet samplers
        spi_set('global.aux_ctrl_4.s0_hs_amux_sel','13')         # select analog mux input from chiplet 2

    elif (chiplet == 3):
        # Configure the chiplet to enable the high speed sampler
        spi_set('c3.dig_clk_ctrl.hss_clk_sel','1')              # select c3_clk as clock for chiplet 3 samplers
        hss_clock = 3

        #spi_set('c3.afe_ctrl_4.electrode_sampler_pd','0')       # power up all 3 electrode samplers
        spi_set('c3.afe_ctrl_4.electrode_sampler_sela','0x0')   # select non-vss input for all 3 electrode samplers
        spi_set('c3.afe_ctrl_4.hs_amux_pd','0')                 # power up the chiplet analog mux. Configuration ignored by chip but configure it anyway
        spi_set('c3.afe_ctrl_4.hs_amux_sel','0')                # select hss_out<0> (B0/VSS)

        # Configure auxiliary AFE control registers when using chiplet samplers
        spi_set('global.aux_ctrl_4.s0_hs_amux_sel','3')         # select analog mux input from chiplet 3

    elif (chiplet == 4):

        hss_clock = 1

        # Configure auxiliary AFE control registers when using spine samplers
        spi_set('global.s0_dft_ctrl.s0_sampler_pd','0')         # power up all the spine samplers
        spi_set('global.s0_dft_ctrl.s0_sampler_sela','0x00')    # select non-vss input for all the spine samplers

        spi_set('global.aux_ctrl_4.s0_hs_amux_sel','8')         # select spine analog mux input from B0 sampler
        
    


def aux_sample():
    spi_set('global.aux_adc_static_samp_en','1')    # Enable writing of aux ADC sample to aux_adc_data register
    spi_set('global.aux_adc_static_samp_en','0')    # Disable writing of aux ADC sample to aux_adc_data register
    return (spi_get('global.aux_adc_data'))         # Read the aux ADC sample value

def hss(verbose=0):
    '''
    Capture data from the high speed sampler and plot the result.
    '''
    global hss_clock
    
    samples = []
    # Set the phase offset for all CHIP SI5338 outputs to 0
    phase_offset = [0,0,0,0]
    qsi.set_clk_offsets('CHIP', 0xF, phase_offset)
    for clk_offset in range(0, 350, 1):
        # Display progress indication if requested
        if (verbose != 0) and ((clk_offset & 0xF) == 0):
            print('.', end = '')

        accum_vss=0.0
        avg=0.0
        avg_count=5  # was 10
        index=0
        
        phase_offset[hss_clock] = ((clk_offset)*20)  # Adjust c[0:3]_clk
        
        qsi.set_clk_offsets('CHIP', 0xF, phase_offset)

        #spi_set('global.s0_dft_ctrl.s0_sampler_sela','0x00')    # select from vss input
        #
        #while index < avg_count:
        #    sample = aux_sample()
        #    #print(sample, end=' ')
        #    accum_vss = accum_vss + (sample & 0x3FF)    # 10-bit value
        #    index = index + 1
    
        #spi_set('global.s0_dft_ctrl.s0_sampler_sela','0x3F')    # select from non-vss input

        index=0
        accum_signal=0.0
        while index < avg_count:
            sample = aux_sample()
            #print(sample, end=' ')
            accum_signal = accum_signal + (sample & 0x3FF)    # 10-bit value
            index = index + 1

        avg = accum_signal / avg_count
        samples.append((1023-avg))
        
    #avg = (accum_vss - accum_signal) / avg_count
        #samples.append((1023-avg))
    # Restore the phase offset for CHIP SI5338
    qsi.set_clk_offsets('CHIP', 0xF, [0,0,0,0])
    hssArray = np.array(samples)
    plt.plot(hssArray)


def bclk_pattern_get(pattern_id, index):
    '''
    Gets the b-clock pattern for the specified pattern identifier and index.
    
    Arguments:
        pattern_id - Pattern identifier 
        index      - Pattern index [0-63]
    '''
    read_pattern = qsi.ffi.new('uint64_t *')
    read_pattern[0] = 0
    rc = qsi.lib.quantum_timing_bclock_pattern_get(pattern_id, index, 1, read_pattern);
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print("Failed to read bclock pattern")
    return read_pattern[0]

def bclk_pattern_set(pattern_id, index, pattern):
    '''
    Sets the b-clock pattern for the specified pattern identifier.
    
    Arguments:
        pattern_id - Pattern identifier 
        index      - Pattern index [0-63]
        pattern    - Pattern (64-bit value)
    
    NOTE: The bitstream from the pattern can have at most one transition from
          low to high and one transition from high to low within the 64-bit
          pattern.
          
    Usage:
        bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B0_HIGH_LEFT, index, 0x0000000000000000)
    '''
    write_pattern = qsi.ffi.new('uint64_t *')
    write_pattern[0] = pattern
    rc = qsi.lib.quantum_timing_bclock_pattern_set(pattern_id, index, 1, write_pattern)
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print("Failed to write bclock pattern")
    
def bclk_index_get():
    '''
    Gets the b-clock pattern start and end index.

    Usage:
        start_idx, end_idx = bclk_index_get()
    '''
    read_start = qsi.ffi.new('int *')
    read_end = qsi.ffi.new('int *')
    rc = qsi.lib.quantum_timing_bclock_pattern_index_get(read_start, read_end)
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print("Failed to read bclock index")
    start_index = read_start[0]
    end_index = read_end[0]
    return(start_index, end_index);

def bclk_index_set(start_index, end_index):
    '''
    '''
    rc = qsi.lib.quantum_timing_bclock_pattern_index_set(start_index, end_index)
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print("Failed to write bclock index")

def bclk_init():
    '''
    Initialize the b-clock operational controls to default values.
    '''
    rc = qsi.lib.quantum_timing_bclock_pattern_control_set(qsi.lib.LIBQSI_TIMING_BCLOCK_TRIGGER_CONTROL_DATAENGINE, qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_MODE_NORMAL)
    if rc != qsi.lib.LIBQSI_STATUS_SUCCESS:
        print("Failed to write bclock control")
    

def bclk_continuous(index = 1):
    '''
    Configure the b-clocks to operate in a continuous capture mode.

    Arguments:
        index - Index pattern index to store b-clock patterns (0-63)
    '''
    bclk_init()

    # Currently, if bclock start index == bclock end index, the FPGA will use a differnt
    # set of registers to define the patterns.  These registers will go away, so
    # don't allow index 0 to be selected.
    if index == 0:
        print("Invalid parameter: Can't use index 0 for continuous mode")
        return
    
    if index > 63:
        print("Invalid parameter: Index out of range [0-63]")
        return
    
    # Configure B0 and B2 to be constantly low, B1 to be constantly high
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B0_HIGH_LEFT, index, 0x0)    
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B0_LOW_LEFT,  index, 0xFFFFFFFFFFFFFFFF)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B1_HIGH_LEFT, index, 0xFFFFFFFFFFFFFFFF)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B1_LOW_LEFT,  index, 0x0)    
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B2_HIGH_LEFT, index, 0x0)    
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B2_LOW_LEFT,  index, 0xFFFFFFFFFFFFFFFF)

    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B0_HIGH_RIGHT, index, 0x0)    
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B0_LOW_RIGHT,  index, 0xFFFFFFFFFFFFFFFF)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B1_HIGH_RIGHT, index, 0xFFFFFFFFFFFFFFFF)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B1_LOW_RIGHT,  index, 0x0)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B2_HIGH_RIGHT, index, 0x0)
    bclk_pattern_set(qsi.lib.LIBQSI_TIMING_BCLOCK_PATTERN_B2_LOW_RIGHT,  index, 0xFFFFFFFFFFFFFFFF)
    
    # Set start/end pattern index
    bclk_index_set(index, index)
        
    
# Global stuff here        
echo = None
nickel_handle = qsi.ffi.new('intptr_t *')
chip_id = qsi.ffi.cast('uint32_t', 0x1C00)
nickel_handle = qsi.lib.quantum_nickel_handle_from_chipid(chip_id)
capture_array = None
default_regs = []
default_bits = []

build_regs()


#config(R"C:\Dan\q9001_CHIPLET0123_128R_1024C_Crop_8SP_8p425M_hsync_cont.json")
#config(R"C:\Dan\q9001_testing.json")

#nios_msg(0)
#cfg_hss_b0(0)
#hss(1)

#dis()

