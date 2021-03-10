"""
This module will attempt to connect to a nickel device to establish
the nickel handle used throughout functions/methods in the classes
defined.
"""

#from qsi_falcon import qsi_helpers as qsi
import qsi_helpers as qsi
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import platform
import time
import math
import statistics

from operator import attrgetter
from collections import namedtuple

class instrument:
    echo_cmds = False
    def __init__(self):
        self.config_file = './q9001_efuse_prog.json'
        self.seq_file = './test.seq'
        # load up the headers, libs, and connect to our device
        self.initialized = qsi.init()
        if not self.initialized:
            sys.exit()
        self.nickel_handle = qsi.ffi.new('intptr_t *')
        self.chip_id = qsi.ffi.cast('uint32_t', 0x1C00)
        self.nickel_handle = qsi.lib.quantum_nickel_handle_from_chipid(self.chip_id)

    def con(self):
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

    def dis(self):
        '''
        Disconnect from a Nickel or Nano device over USB.
    
        Parameters:
            None
        '''
        qsi.lib.quantum_disconnect_device()

    def config(self,filename=None):
        '''
        Write a configuration file to a connected device.
    
        Parameters:
            filename - Filename of configuration in json format
        '''
        if filename == None:
            qsi.set_config(self.config_file)
        else:
            qsi.set_config(filename)

    def seq(self,filename = None):
        '''
        Open and execute the configured default sequence file.
    
        Parameters: filename - Filename of sequence file to read and process.
                             - If None provided, the filename stored in seq_file
                               will be used.
        '''
        f = None

        if (filename == None):
            print('No file sequence performed')
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
                        spi_interface.wr_reg(self.nickel_handle,line[1],line[2])
                    else:
                        print('invalid setdevice command structure')
                elif line[0] == 'getdevice':
                    response = spi_interface.rd_reg(self.nickel_handle,line[1])
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
                        self.mm_w(address,param3)
                    elif (line[1] == 'r') and (len(line) == 3):
                        response = self.mm_r(address)
                        print('mm r' + line[2] + ' ---> ' + str(response[0]))
                    elif (line[1] == 'sb') and (len(line) == 4):
                        self.mm_sb(address,param3)
                    elif (line[1] == 'cb') and (len(line) == 4):
                        self.mm_cb(address,param3)
                    elif (line[1] == 'rb') and (len(line) == 4):
                        response = self.mm_rb(address,param3)
                        print('mm rb' + line[2] + ' ---> ' + str(response[0]))
                elif line[0] == 'wait':
                    if len(line) == 2:
                        delay = 0.001 * int(line[1])
                        self.wait(delay)
                elif line[0] == 'chip2shadow':
                    read_config = qsi.ffi.cast('int32_t', 1)
                    read_status = qsi.ffi.cast('int32_t', 1)
                    ret = qsi.lib.quantum_nickel_read_config_from_sensor(self.nickel_handle,read_config,read_status)
                    if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
                        print('chip2shadow' + 'FAILED')
                    elif self.echo_cmds:
                        print('chip2shadow')
        f.close()

    @classmethod
    def mm_sb(cls,address, position):
        '''
        Set the bit position at the address specified to 1 on the connected device.
    
        Parameters:
            address  - Address number
            position - Bit position.  Position 0 is the least-significant bit.
        '''
        source_address = qsi.ffi.new('uint32_t *')
        transfer_status = qsi.ffi.new('libqsi_status_t *')

        write_val = None
        position_set = (0x00000001 << position)

        present_val = cls.mm_r(address)

        write_val = present_val | position_set
        source_address[0] = write_val

        ret = qsi.ffi.new('uint32_t *')
        ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

        new_val = cls.mm_r(address)

        if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS) or (new_val != (present_val | position_set)):
            print('mm sb ' + str(position) + ' ' + str(format(address,'#04x')) + ' FAILED')
        elif cls.echo_cmds:
            print('mm sb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : value ' + str(format(present_val,'#04x')) + ' ---> ' + str(format(new_val,'#04x')))

    @classmethod
    def mm_cb(cls,address,position):
        '''
        Clear the specified address and bit position to 0 on the connected device.
    
        Parameters:
            address  - Address number
            position - Bit position.  Position 0 is the least-significant bit.
        '''
        source_address = qsi.ffi.new('uint32_t *')
        transfer_status = qsi.ffi.new('libqsi_status_t *')

        write_val = None
        position_set = (0x00000001 << position)
        position_clear = (0xFFFFFFFF & (~position_set))
        present_val = cls.mm_r(address)
        write_val = present_val & position_clear
        source_address[0] = write_val

        ret = qsi.ffi.new('uint32_t *')
        ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

        new_val = cls.mm_r(address)
        if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS) or (new_val != (present_val & position_clear)):
            print('mm cb ' + str(position) + ' ' + str(format(address,'#04x')) + ' FAILED')
        elif cls.echo_cmds:
            print('mm cb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : value ' + str(format(present_val,'#04x')) + ' ---> ' + str(format(new_val,'#04x')))

    @classmethod
    def mm_rb(cls,address,position):
        '''
        Read the specified address and bit position on the connected device and
        return its value.
    
        Parameters:
            address  - Address number
            position - Bit position.  Position 0 is the least-significant bit.
        '''

        position_get = (0x00000001 << position)
        present_val = cls.mm_r(address)
        read_val = (present_val & position_get) >> position

        if cls.echo_cmds:
            print('mm rb ' + str(position) + ' ' + str(format(address,'#04x')) + ' : bit[' + str(position) + '] = ' + str(read_val))
        return read_val

    @classmethod
    def mm_r(cls,address):
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
        elif cls.echo_cmds:
            print('mm r ' + str(format(address,'#04x')) + '     : value = ' + str(read_val))
        return read_val

    @classmethod
    def mm_w(cls,address, value):
        '''
        Write the specified 32-bit value into the specified address on the connected device.
    
        Parameters:
            address - Address number
            value   - Value to write
        '''
        source_address = qsi.ffi.new('uint32_t *')
        transfer_status = qsi.ffi.new('libqsi_status_t *')

        source_address[0] = value

        ret = qsi.ffi.new('uint32_t *')
        ret = qsi.lib.quantum_nios_write(address,1,1,source_address,transfer_status)

        if (ret != qsi.lib.LIBQSI_STATUS_SUCCESS):
            print('mm w ' + str(format(address,'#04x')) + ' FAILED')
        elif cls.echo_cmds:
            print('mm w ' + str(format(address,'#04x')) + ' : value ' + str(format(value,'#04x')))

    def wait(self,delay):
        '''
        Wait for the specified time in milliseconds before returning from the method.
    
        Parameters:
            delay - Time to wait in milliseconds
        '''
        delay_ms = delay / 1000
        time.sleep(delay)
        if self.echo_cmds:
            print('wait ' + str(delay_ms))

    def v_set(self,target_name, target_v, verbose=False):
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

    def v_get(self,target_name, verbose=False):
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

    def m_get(self,name, monitor_type):
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

class spi_interface:
    def __init__(self,default_reg_file):
        self.echo_cmds = False
        self.reg_file = default_reg_file
        self.default_regs = []
        self.default_bits = []
        self.build_regs()
        self.nickel_handle = qsi.ffi.new('intptr_t *')
        self.chip_id = qsi.ffi.cast('uint32_t', 0x1C00)
        self.nickel_handle = qsi.lib.quantum_nickel_handle_from_chipid(self.chip_id)

    @classmethod
    def wr_reg(cls,nickel_handle,address,value):
        '''
        Write the specified Q9001 register on the connected device with the value provided.
        Parameters:
            address - The name of register or register field in dot notation.
            value   - The value to set the register or field.
        Example:
            wr_reg(nickel_handle, 'c0.afe_ctrl_5.ramp_vrefp','7')  # Set for chiplets 0
            wr_reg(nickel_handle,'c*.afe_ctrl_5.ramp_vrefp','7')  # Set for all chiplets
        '''
        if ('x' in value) or ('X' in value):
            val_int = int(value,16)
        else:
            val_int = int(value,10)

        # This is a hack to ensure that software SPI shadow registers are up to date.
        # Read a SPI register first before writing a specified field.
        # In case of multiple chiplets, read from every chiplet.
        address = address.lstrip()
        if( address[1] == "*" ):
            for chiplet in range(4):
                read_addr = "c%d" % chiplet + address[2:]
                dummy = cls.rd_reg(nickel_handle, read_addr )
        else:
            dummy = cls.rd_reg(nickel_handle, address )
        addr     = qsi.text2cffi(address)
        val      = qsi.ffi.cast('uint16_t',val_int)
        optimize = qsi.ffi.cast('int32_t', 0)
        ret = qsi.lib.quantum_nickel_set_on_device_using_dot_notation(nickel_handle,addr,val,optimize)
        if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
            print('setdevice ' + address + ' ' + value + 'FAILED')

    @classmethod
    def rd_reg(cls,nickel_handle,address):
        '''
        Get the specified Q9001 register from the connected device.
        Parameters:
            address - The name of register or register field in dot notation.
                      e.g. 'c0.afe_ctrl_3.ramp_pd' represents chiplet 0 ramp power down
                      Note: Don't use the wildcard for the register or field name.
        Example:
            reg_value = rd_reg(self.nickel_handle,'global.aux_adc_data')
        '''
        read_val = qsi.ffi.new('uint16_t *')
        addr     = qsi.text2cffi(address)
        ret = qsi.lib.quantum_nickel_get_from_device_using_dot_notation(nickel_handle,addr,read_val)
        if ret != qsi.lib.LIBQSI_STATUS_SUCCESS:
            print('getdevice ' + ' ' + address + 'FAILED')
        return read_val[0]

    def build_regs(self):
        '''
        Read in a comma separated values file that describes the Q9001 configuration
        registers to build lists of default values for registers and fields within
        those registers.  These lists can later be used to compare the current
        device configuration to the default values using the methods
        def diff_regs() and diff_bits().
    
        Parameters:
            None
        '''
        reg        = namedtuple('reg', ['name','base_addr','value','access'])
        bitfield   = namedtuple('bifield',['name','position','max_value','value','access'])

        c0_addr_msb = 0x00
        c1_addr_msb = 0x01 << 8
        c2_addr_msb = 0x02 << 8
        c3_addr_msb = 0x03 << 8
        global_addr_msb = 0x10 << 11

        f = open(self.reg_file)
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
                        self.default_bits.append(bitfield(name='c0.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
                        self.default_bits.append(bitfield(name='c1.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
                        self.default_bits.append(bitfield(name='c2.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
                        self.default_bits.append(bitfield(name='c3.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
                    if 'T' in cell[7]:
                        self.default_bits.append(bitfield(name='global.'+reg_name+'.'+bf_name[0],position=bit_pos,max_value=bit_max,value=bit_default,access=reg_access))
                # populate registers named tuple. CRW, CRO, TRW, and TRO should be the only values for "register type" field cell[7]
                if 'C' in cell[7]:
                    # first the main registers into one list of named tuples
                    self.default_regs.append(reg(name='c0.'+reg_name,base_addr=(reg_base_addr | c0_addr_msb),value=reg_value,access=reg_access))
                    self.default_regs.append(reg(name='c1.'+reg_name,base_addr=(reg_base_addr | c1_addr_msb),value=reg_value,access=reg_access))
                    self.default_regs.append(reg(name='c2.'+reg_name,base_addr=(reg_base_addr | c2_addr_msb),value=reg_value,access=reg_access))
                    self.default_regs.append(reg(name='c3.'+reg_name,base_addr=(reg_base_addr | c3_addr_msb),value=reg_value,access=reg_access))
                if 'T' in cell[7]:
                    self.default_regs.append(reg(name='global.'+reg_name,base_addr=(reg_base_addr | global_addr_msb),value=reg_value,access=reg_access))

                self.default_regs = sorted(self.default_regs,key=attrgetter('base_addr'))
                self.default_bits = sorted(self.default_bits,key=attrgetter('name'))

                if self.echo_cmds:
                    for entry in self.default_regs:
                        print(entry.name)
                    for entry in self.default_bits:
                        print(entry.name)

    def diff_regs(self):
        '''
        Compare the current Q9001 configuration to the default values and
        display the differences at the register level.
    
        Parameters:
            None
        '''
        for register in self.default_regs:
            get_name = register.name
            get_reg_value  = self.rd_reg(self.nickel_handle,get_name)
            if get_reg_value != register.value:
                print(register.name + ' = ' + str(get_reg_value) + ' (default = ' + str(register.value) + ')')

    def diff_bits(self):
        '''
        Compare the current Q9001 configuration to the default values and
        display the differences at the register field level.
    
        Parameters:
            None
        '''
        for bitfield in self.default_bits:
            get_name = bitfield.name
            get_reg_value  = self.rd_reg(self.nickel_handle,get_name)
            if get_reg_value != bitfield.value      :
                print(bitfield.name + ' = ' + str(get_reg_value) + ' (default = ' + str(bitfield.value) + ')')

class efuse:
    def __init__(self):
        self.echo_cmds = False
        self.vefuse = 2.3
        self.vefuse_on = False
        self.nickel_handle = qsi.ffi.new('intptr_t *')
        self.chip_id = qsi.ffi.cast('uint32_t', 0x1C00)
        self.nickel_handle = qsi.lib.quantum_nickel_handle_from_chipid(self.chip_id)

    def set_vefuse(self,vefuse_new=3.3):
        '''
            Set the EFuse voltage level and ensure the supply is enabled
    
        Parameters:
            vefuse - EFuse supply setting
    
        Returns
        -------
        None.
    
        '''
        if (vefuse_new != self.vefuse) or (self.vefuse_on == False):
            read_val  = qsi.ffi.new('float *')
            supply_name = qsi.text2cffi('VEFUSE')
            qsi.lib.quantum_voltage_get(supply_name, read_val)
            voltage = read_val[0]
            if self.echo_cmds==True:
                print('Old VEFUSE Setpoint' + '  = {0:2.3f}'.format(voltage))

            qsi.lib.quantum_voltage_set(supply_name, vefuse_new)
            qsi.lib.quantum_voltage_get(supply_name, read_val)
            voltage = read_val[0]
            if self.echo_cmds==True:
                print('New VEFUSE Setpoint' + '  = {0:2.3f}'.format(voltage))

            qsi.lib.quantum_im_psu_set(supply_name,1) # Make sure the efuse supply is On!
            self.vefuse = vefuse_new
            self.vefuse_on = True

    def cfg_rd_ctrl(self,bank = 0, vref_sel=6, idac_sel=0x10, bl_load_opt=0, sense_mode_sel=1, test_en=0):
        '''
            Configure the EFuse Control 1 register settings for a read operation.
    
        Parameters: 
            bank           - target bank
            vref_sel       - 3 bit comparator reference selection
            idac_sel       - 8 bit test mode current setting
            bl_load_opt    - bitline 2x drive strenght option
            sense_mode_sel - 0 = resistor as comparator reference, 1 = voltage as comparator reference
            test_en        - 0 = normal readback, 1 = test mode
    
        Returns
        -------
        None.
    
        '''
        # s0 and s1_efuse_ctrl_1 bitfields
        vref_sel_mask        = ((vref_sel       & 0x7)  << 12) # 3 bit value in bits [14:12]
        idac_sel_mask        = ((idac_sel       & 0xFF) << 4)  # 8 bit value in bits [11:4]
        bl_load_mask         = ((bl_load_opt    & 0x1)  << 3)  # 1 bit value at bit[3]
        sense_mode_sel_mask  = ((sense_mode_sel & 0x1)  << 2)  # 1 bit value at bit[2]
        test_en_mask         = ((test_en        & 0x1)  << 1)  # 1 bit value at bit[1]
        mode_sel_mask        = 0                               # 1 bit value at bit[0], 0 = readout mode

        # Configure the Chip SPI registers for read mode and the requested recipe
        s0_efuse_ctrl_1 = (0x7FFF & (vref_sel_mask | idac_sel_mask | bl_load_mask | sense_mode_sel_mask | test_en_mask | mode_sel_mask))
        s1_efuse_ctrl_1 = (0x7FFF & (vref_sel_mask | idac_sel_mask | bl_load_mask | sense_mode_sel_mask | test_en_mask | mode_sel_mask))
        if (bank == 0) or (bank == 1):
            spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_1',str(s0_efuse_ctrl_1))
        elif (bank == 2) or (bank == 3):
            spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_1',str(s1_efuse_ctrl_1))

    def cfg_wr_ctrl(self,bank = 0):
        '''
            Configure the EFuse Control 1 register settings for a write operation.
            Only sets the programming mode bit, leaves all others untouched
    
        Parameters:
            bank - target bank
    
        Returns
        -------
        None.
    
        '''
        # Configure the Chip SPI registers for write mode (preserve other bit settings)
        if (bank == 0) or (bank == 1):
            s0_efuse_ctrl_1 = spi_interface.rd_reg(self.nickel_handle,'global.s0_efuse_ctrl_1')
            s0_efuse_ctrl_1 = (s0_efuse_ctrl_1 | 0x1) # set the mode select bit, preserve the others
            spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_1',str(s0_efuse_ctrl_1))
        elif (bank == 2) or (bank == 3):
            s1_efuse_ctrl_1 = spi_interface.rd_reg(self.nickel_handle,'global.s1_efuse_ctrl_1')
            s1_efuse_ctrl_1 = (s1_efuse_ctrl_1 | 0x1) # set the mode select bit, preserve the others
            spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_1',str(s1_efuse_ctrl_1))

    def set_addr(self,bank = 0, row = 0, col = 0, dual_cs_mode=True):
        '''
            Configure the EFuse Control 0 registers for the targeted row byte(s).
            The column address is only important during "test mode" read operations
            In read mode, we can read 2 banks at once, so allow this here via dual_cs_mode param
    
        Parameters:
            bank         - target bank
            row          - target row
            column       - target column
            dual_cs_mode - True=enable 2 chip selects, False= enable only targeted chip select
        Returns
        -------
        None.
    
        '''
        row_mask        = ((row & 0x0F) << 11)
        col_mask        = ((col & 0x07) << 8)
        pulse_mode_mask = 0x0080               # always using the fpga pulse generator

        # Determine the chip select mask
        if (dual_cs_mode):
            cs_mask = 0x03
        else:
            if (bank == 0) or (bank == 1):
                cs_mask = 0x01 << (bank)
            elif (bank == 2) or (bank == 3):
                cs_mask = 0x01 << (bank-2)

        # Determine which banks will be addressed and enabled via chip select
        if (bank == 0) or (bank == 1):
            s0_efuse_ctrl_0_val = str((row_mask | col_mask | pulse_mode_mask  | cs_mask)) # chip select is only valid in bank 0 or 1
            s1_efuse_ctrl_0_val = str((row_mask | col_mask | pulse_mode_mask) & 0xFFF0)   # chip selects should be cleared for bank 2 and 3
        elif (bank == 2) or (bank == 3):
            s0_efuse_ctrl_0_val = str((row_mask | col_mask | pulse_mode_mask  & 0xFFF0)) # chip selects should be cleared for bank 0 and 1
            s1_efuse_ctrl_0_val = str((row_mask | col_mask | pulse_mode_mask) | cs_mask) # chip select is only valid in bank 2 or 3

        spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_0',s0_efuse_ctrl_0_val) # Program the address to the bank 0/1 control register
        spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_0',s1_efuse_ctrl_0_val) # Program the address to the bank 2/3 control register

    def get_data(self,bank = 0):
        '''
            Get EFuse read data register contents for the bank/row
            16 bit result is concatenated row "x" for Bank 0 and 1, or Banks 2 and 3
    
        Parameters:
            bank - target bank
    
        Returns
        -------
        2 concatenated bytes of row read data... {bank 1, bank 0}, or {bank 3, bank 2}
    
        '''
        read_data = 0

        if (bank == 0) or (bank == 1):
            efuse_data_addr   ='global.s0_efuse_data'
        elif (bank == 2) or (bank == 3):
            efuse_data_addr   ='global.s1_efuse_data'

        read_data = spi_interface.rd_reg(self.nickel_handle,efuse_data_addr)

        return read_data

    def set_rd_pattern(self,Tsu_bl=100,Tsu_bl_to_sense=1000,Tsense=1000,Th_sense_to_bl=100,Th_bl=100):
        '''
            Initialize the efuse pattern generator for read operations
    
        Parameters: Setup and Hold times for Read Operation
                    Tsu_bl, Tsu_bl_to_sense, Tsense, Th_sense_to_bl, Th_bl
    
        Returns
        -------
        None.
    
        '''
        # First Configure the FPGA GPIO and Chip GPIO
        # Chiplet 0 and 1 driven by GPIO 0 (prog_en), 1 (sense_en), and 2 (bl_load)
        # Chiplet 2 and 3 driven by GPIO 4 (prog_en), 5 (sense_en), and 6 (bl_load)
        # We first need to make sure the Chip's GPIO are set to inputs, and the
        # EFuse control is set to SPI bit control (we change it to GPIO control eventually)
        # We then configure the FPGA to output the One-Shot pattern gen pulses to GPIO

        # Get the present state of the efuse control 0 registers
        s0_efuse_ctrl_0 = spi_interface.rd_reg(self.nickel_handle,'global.s0_efuse_ctrl_0')
        s1_efuse_ctrl_0 = spi_interface.rd_reg(self.nickel_handle,'global.s1_efuse_ctrl_0')

        # Now make sure glitches on the GPIO are harmless by forcing EFuse programming Chip Selects to all 0
        spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_0',str(s0_efuse_ctrl_0 & 0xFFF0))
        spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_0',str(s1_efuse_ctrl_0 & 0xFFF0))

        # Chip GPIO used for EFuse programming are inputs
        spi_interface.wr_reg(self.nickel_handle,'global.s0_gpio_ctrl','0x5555')
        spi_interface.wr_reg(self.nickel_handle,'global.s1_gpio_ctrl','0x5555')

        # Get the actual ADC clock frequency measured inside the FPGA
        clk_sensor = instrument.mm_r(0x40050)        # frequency measured in kHz
        ns_per_clk = 1.0/clk_sensor * 1000000 # ns per clock period

        # Determine the Read Mode one shot parameters
        bl_load_start   = 0x0000FFFF & int(math.ceil((Tsu_bl/ns_per_clk)))
        sense_en_start  = 0x0000FFFF & (bl_load_start  + int(math.ceil((Tsu_bl_to_sense/ns_per_clk))))
        sense_en_stop   = 0x0000FFFF & (sense_en_start + int(math.ceil((Tsense/ns_per_clk))))
        bl_load_stop    = 0x0000FFFF & (sense_en_stop  + int(math.ceil((Th_sense_to_bl/ns_per_clk))))
        read_period     = 0x0000FFFF & (bl_load_stop   + int(math.ceil((Th_bl/ns_per_clk))))
        # Make sure the write mode pulse is off for read mode (start > stop)
        prog_en_start   = 65535
        prog_en_stop    = 65534

        oneshot_control = read_period
        oneshot_0       = (prog_en_start  << 16) | prog_en_stop
        oneshot_1       = (sense_en_start << 16) | sense_en_stop
        oneshot_2       = (bl_load_start  << 16) | bl_load_stop

        # Program the One-Shot Pulse generators, making sure the trigger is off to start
        instrument.mm_w(0x410C0,oneshot_control)
        instrument.mm_w(0x410C4,oneshot_0)
        instrument.mm_w(0x410C8,oneshot_1)
        instrument.mm_w(0x410CC,oneshot_2)

        # Program FPGA GPIO Pulses to output One Shot Pattern Generators
        instrument.mm_w(0x410E0,0x40000000)    # GPIO0 = One-Shot Pulse 0, Chiplet 0/1 prog_en
        instrument.mm_w(0x410E4,0x50000000)    # GPIO1 = One-Shot Pulse 1, Chiplet 0/1 sense_en
        instrument.mm_w(0x410E8,0x60000000)    # GPIO2 = One-Shot Pulse 2, Chiplet 0/1 bl_load
        instrument.mm_w(0x410F0,0x40000000)    # GPIO4 = One-Shot Pulse 0, Chiplet 2/3 prog_en
        instrument.mm_w(0x410F4,0x50000000)    # GPIO5 = One-Shot Pulse 1, Chiplet 2/3 sense_en
        instrument.mm_w(0x410F8,0x60000000)    # GPIO6 = One-Shot Pulse 2, Chiplet 2/3 bl_load

        # Program the FPGA IO pads to output GPIO0-2 and 4-6 (GPIO3 and 7 unused)
        gp_oe_control = instrument.mm_r(0x4000C) # First read the present state of the OE control register
        gp_oe_control = (gp_oe_control | 0x00000077) & 0xFFFFFF77 # setting OE for GPIO0-2 and 4-6, clearing OE for GPIO4 and 7
        instrument.mm_w(0x4000C, gp_oe_control)

        # Now return the Chip SPI registers to their original state
        spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_0',str(s0_efuse_ctrl_0))
        spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_0',str(s1_efuse_ctrl_0))

        if self.echo_cmds:
            print("ADC Clock Frequency  = " + str(clk_sensor/1000) + " MHz")
            print('Efuse read pattern period = '+ str((read_period * ns_per_clk)) +  ' ns')
            print('bl_load pulse width       = '+ str(((bl_load_stop - bl_load_start)   * ns_per_clk)) +  ' ns')
            print('sense_en pulse width      = '+ str(((sense_en_stop - sense_en_start) * ns_per_clk)) +  ' ns')

    def set_wr_pattern(self,Tsu_prog = 100,Tprog = 10000,Th_prog = 100):
        '''
            Initialize the efuse pattern generator for write operations
    
        Parameters: Setup and Hold times for Write Operation
                    Tsu_prog, Tprog, and Th_prog
    
        Returns
        -------
        None.
    
        '''
        # First Configure the FPGA GPIO and Chip GPIO
        # Chiplet 0 and 1 driven by GPIO 0 (prog_en), 1 (sense_en), and 2 (bl_load)
        # Chiplet 2 and 3 driven by GPIO 4 (prog_en), 5 (sense_en), and 6 (bl_load)
        # We first need to make sure the Chip's GPIO are set to inputs, and the
        # EFuse control is set to SPI bit control (we change it to GPIO control eventually)
        # We then configure the FPGA to output the One-Shot pattern gen pulses to GPIO

        # Get the present state of the efuse control 0 registers
        s0_efuse_ctrl_0 = spi_interface.rd_reg(self.nickel_handle,'global.s0_efuse_ctrl_0')
        s1_efuse_ctrl_0 = spi_interface.rd_reg(self.nickel_handle,'global.s1_efuse_ctrl_0')

        # Now make sure glitches on the GPIO are harmless by forcing EFuse programming Chip Selects to all 0
        spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_0',str(s0_efuse_ctrl_0 & 0xFFF0))
        spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_0',str(s1_efuse_ctrl_0 & 0xFFF0))

        # Chip GPIO used for EFuse programming are inputs
        spi_interface.wr_reg(self.nickel_handle,'global.s0_gpio_ctrl','0x5555')
        spi_interface.wr_reg(self.nickel_handle,'global.s1_gpio_ctrl','0x5555')

        # Get the actual ADC clock frequency measured inside the FPGA
        clk_sensor = instrument.mm_r(0x40050)        # frequency measured in kHz
        ns_per_clk = 1.0/clk_sensor * 1000000 # ns per clock period

        # Make sure the write mode bl_load and sense_en is off (start > stop)
        bl_load_start   = 65535
        sense_en_start  = 65535
        sense_en_stop   = 65534
        bl_load_stop    = 65534
        # Determine the Write Mode one shot parameters
        prog_en_start   = 0x0000FFFF & int(math.ceil((Tsu_prog/ns_per_clk)))
        prog_en_stop    = 0x0000FFFF & (prog_en_start + int(math.ceil((Tprog/ns_per_clk))))
        write_period    = 0x0000FFFF & (prog_en_stop  + int(math.ceil((Th_prog/ns_per_clk))))

        oneshot_control = write_period
        oneshot_0       = (prog_en_start  << 16) | prog_en_stop
        oneshot_1       = (sense_en_start << 16) | sense_en_stop
        oneshot_2       = (bl_load_start  << 16) | bl_load_stop

        # Program the One-Shot Pulse generators, making sure the trigger is off to start
        instrument.mm_w(0x410C0,oneshot_control)
        instrument.mm_w(0x410C4,oneshot_0)
        instrument.mm_w(0x410C8,oneshot_1)
        instrument.mm_w(0x410CC,oneshot_2)

        # Program FPGA GPIO Pulses to output One Shot Pattern Generators
        instrument.mm_w(0x410E0,0x40000000)    # GPIO0 = One-Shot Pulse 0, Chiplet 0/1 prog_en
        instrument.mm_w(0x410E4,0x50000000)    # GPIO1 = One-Shot Pulse 1, Chiplet 0/1 sense_en
        instrument.mm_w(0x410E8,0x60000000)    # GPIO2 = One-Shot Pulse 2, Chiplet 0/1 bl_load
        instrument.mm_w(0x410F0,0x40000000)    # GPIO4 = One-Shot Pulse 0, Chiplet 2/3 prog_en
        instrument.mm_w(0x410F4,0x50000000)    # GPIO5 = One-Shot Pulse 1, Chiplet 2/3 sense_en
        instrument.mm_w(0x410F8,0x60000000)    # GPIO6 = One-Shot Pulse 2, Chiplet 2/3 bl_load

        # Program the FPGA IO pads to output GPIO0-2 and 4-6 (GPIO3 and 7 unused)
        gp_oe_control = instrument.mm_r(0x4000C) # First read the present state of the OE control register
        gp_oe_control = (gp_oe_control | 0x00000077) & 0xFFFFFF77 # setting OE for GPIO0-2 and 4-6, clearing OE for GPIO4 and 7
        instrument.mm_w(0x4000C, gp_oe_control)

        # Now return the Chip SPI registers to their original state
        spi_interface.wr_reg(self.nickel_handle,'global.s0_efuse_ctrl_0',str(s0_efuse_ctrl_0))
        spi_interface.wr_reg(self.nickel_handle,'global.s1_efuse_ctrl_0',str(s1_efuse_ctrl_0))

        if self.echo_cmds:
            print("ADC Clock Frequency        = " + str(clk_sensor/1000) + " MHz")
            print('Efuse write pattern period = '+ str((write_period * ns_per_clk)) +  ' ns')
            print('prog_en pulse width        = '+ str(((prog_en_stop - prog_en_start)   * ns_per_clk)) +  ' ns')

    def fire_oneshot(self):
        '''
            Trigger the FPGA Oneshot pattern generator.
    
        Parameters: None
    
        Returns
        -------
        None.
    
        '''
        oneshot_ctrl = instrument.mm_r(0x410C0)               # get the present value
        oneshot_ctrl = oneshot_ctrl & 0xFFFEFFFF   # make sure the trigger bit starts low
        instrument.mm_w(0x410C0, oneshot_ctrl)                # write it
        instrument.mm_w(0x410C0, (oneshot_ctrl | 0x00010000)) # set the trigger
        instrument.mm_w(0x410C0, oneshot_ctrl)                # the trigger is brought back low

    #-----------------------------------------------------------------------------
    # EFuse High Level Write/Read functions for accessing cells based on the
    # composite representation of the EFuse memory.
    # These functions treat the multiple banks of EFuse as a single
    # array of bytes.  Access performed on bits or bytes (or characters)
    #-----------------------------------------------------------------------------
    def rd_bit(self,byte_index=0, bit_index=0):
        '''
            Read a single bit in the composite EFuse memory map.
    
        Parameters:
            byte_index - target byte index in the composite EFuse array
            bit_index  - bit index of the target byte
    
        Returns
        -------
        A single bit value
    
        '''
        bytes_per_bank = 16

        bank = int(byte_index / bytes_per_bank)
        row  = int(byte_index % bytes_per_bank)

        vefuse = 3.3
        vref_sel = 6
        bit_val=0

        row_list = self.rd_row(vefuse, vref_sel, bank, row)
        bit_val = row_list[bit_index]
        return (bit_val)

    def rd_byte(self,byte_index=0):
        '''
            Read a single byte of the composite EFuse memory map.
    
        Parameters:
            byte_index - target byte index in the composite EFuse array
    
        Returns
        -------
        A single byte value
    
        '''
        bytes_per_bank = 16

        bank = int(byte_index / bytes_per_bank)
        row  = int(byte_index % bytes_per_bank)

        vefuse = 3.3
        vref_sel = 6
        byte_val=0

        row_list = self.rd_row(vefuse, vref_sel, bank, row)
        for bit in range(0,8):
            if row_list[bit]:
                byte_val = byte_val | (1 << bit)

        return (byte_val)

    def rd_char(self,char_index=0):
        '''
            A convenience function for reading a single byte of the composite
            EFuse memory map and returning a character instead of an integer
    
        Parameters:
            byte_index - target byte index in the composite EFuse array
    
        Returns
        -------
        A single byte value in character form
    
        '''
        byte_val = self.rd_byte(char_index)
        return chr(byte_val)

    def rd_efuse(self,ret_type=0):
        '''
            Read the entire composite EFuse memory map.
    
        Parameters:
            ret_type  - Return value type; 0=byte list, 1=char_list
    
        Returns
        -------
        A list of bytes in integer form of ascii character form
    
        '''

        num_banks = 4
        bytes_per_bank = 16

        vefuse = 3.3
        vref_sel = 6
        byte_val=0
        row_list = []
        efuse_bytes = []
        efuse_chars = []

        efuse_banks = self.rd_banks(vefuse, vref_sel)
        for bank in range(0,num_banks):
            for row in range(0,bytes_per_bank):
                row_list = efuse_banks[bank][row]
                byte_val = 0
                for bit in range(0,8):
                    if row_list[bit]:
                        byte_val = byte_val | (1 << bit)
                efuse_bytes.append(byte_val)
                efuse_chars.append(chr(byte_val))
        if ret_type == 1:
            return (efuse_chars)
        else:
            return (efuse_bytes)

    def wr_bit(self,byte_index=0, bit_index=0):
        '''
            Write a single bit in the composite EFuse memory map.
    
        Parameters:
            byte_index - target byte index in the composite EFuse array
            bit_index  - bit index of the target byte
    
        Returns
        -------
        None
    
        '''
        bytes_per_bank = 16
        bank = int(byte_index / bytes_per_bank)
        row  = int(byte_index % bytes_per_bank)
        col  = bit_index
        vefuse = 5.0
        update_recipe=True
        self.wr_cell(vefuse,bank,row,col,update_recipe)

    def wr_byte(self,byte_index=0, byte_val=0):
        '''
            Write a single byte in the composite EFuse memory map.
    
        Parameters:
            byte_index - target byte index in the composite EFuse array
            byte_val   - integer value to be written
        Returns
        -------
        None
    
        '''
        bytes_per_bank = 16
        bank = int(byte_index / bytes_per_bank)
        row  = int(byte_index % bytes_per_bank)
        vefuse = 5.0

        # write the recipe for the first bit that is to be set, remaining cells with the present recipe
        recipe_up_to_date = False
        for col in range(0,8):
            if recipe_up_to_date:
                if ((byte_val & (1 << col)) != 0):
                    self.wr_cell(vefuse,bank,row,col,False)
            else:
                if ((byte_val & (1 << col)) != 0):
                    self.wr_cell(vefuse,bank,row,col,True)
                    recipe_up_to_date = True

    def wr_char(self,char_index=0, char_val=''):
        '''
            A convenience funtion for writing a single byte in the composite
            EFuse memory map from an ascii character parameter instead of
            an integer.
    
        Parameters:
            char_index - target character (byte) index in the composite EFuse array
            char_val   - character value to be written 
        Returns
        -------
        None
    
        '''
        byte_val = ord(char_val)
        self.wr_byte(char_index,byte_val)

    #-----------------------------------------------------------------------------
    # EFuse Low Level Read functions for accessing cells based on Bank/Row/Column
    #-----------------------------------------------------------------------------
    def rd_cell(self,vefuse=3.3, vref_sel=6, bank=0, row=0, col=0):
        '''
            Read a single EFuse cell value
    
        Parameters:
            vefuse   - EFuse voltage
            vref_sel - bit comparator reference voltage selection
            bank     - target bank
            row      - target row
            col      - target cell
    
        Returns
        -------
        Cell Value
    
        '''
        row_list = []
        row_list = self.rd_row(vefuse, vref_sel, bank, row)
        efuse_cell = row_list[col]

        return efuse_cell

    def rd_row(self,vefuse=3.3, vref_sel=6, bank=0, row=0):
        '''
            Read a single Row of data from a single EFuse Bank
    
        Parameters:
            vefuse   - EFuse voltage
            vref_sel - bit comparator reference voltage selection
            bank     - target bank
            row      - target row
        Returns
        -------
        A single Row of values as a list of columns, ordered [0:7]
    
        '''
        idac_sel = 0x10
        bl_load_opt = 0
        sense_mode_sel =1
        test_en = 0
        dual_cs_mode  = False # during readback, we are only looking for one bank's data
        efuse_row = []

        self.set_vefuse(vefuse)
        self.set_rd_pattern(100,1000,1000,100,100)
        self.cfg_rd_ctrl(0, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)
        self.cfg_rd_ctrl(2, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)

        # get the single bank/row data
        self.set_addr(bank, row, 0,dual_cs_mode)
        self.fire_oneshot()
        read_data = self.get_data(bank)
        for col in range(8):
            if (bank == 0) or (bank == 2):
                efuse_row.append((read_data & 2**col) >> col )
            else:
                efuse_row.append((read_data & 2**(col+8)) >> (col+8) ) # bit order is [0:7]

        return efuse_row

    def rd_bank(self,vefuse=3.3, vref_sel=6, bank=0):
        '''
            Read a single Bank's EFuse values
    
        Parameters:
            vefuse   - EFuse voltage
            vref_sel - bit comparator reference voltage selection
            bank     - target bank
        Returns
        -------
        Nested, 2 dimension list of a single Bank of EFuse values
        [row][col] data, with column list ordered [0:7]
    
        '''
        idac_sel = 0x10
        bl_load_opt = 0
        sense_mode_sel =1
        test_en = 0
        dual_cs_mode  = False # during readback, we are only looking for one bank's data
        efuse_bank = []

        self.set_vefuse(vefuse)
        self.set_rd_pattern(100,1000,1000,100,100)
        self.cfg_rd_ctrl(0, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)
        self.cfg_rd_ctrl(2, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)

        # get the single bank's data
        for row in range(16):
            efuse_bank.append([])
            self.set_addr(bank, row, 0,dual_cs_mode)
            self.fire_oneshot()
            read_data = self.get_data(bank)
            for col in range(8):
                if (bank == 0) or (bank == 2):
                    efuse_bank[row].append((read_data & 2**col) >> col )
                else:
                    efuse_bank[row].append((read_data & 2**(col+8)) >> (col+8) ) # row data bit order is [0:7]

        return efuse_bank

    def rd_banks(self,vefuse=3.3, vref_sel=6):
        '''
            Read all Banks' EFuse values
    
        Parameters:
            vefuse   - EFuse voltage
            vref_sel - bit comparator reference voltage selection
        Returns
        -------
        Nested, 3 dimension list of All Banks' EFuse values 
        [bank][row][col] data, with column list ordered [0:7]
    
        '''
        idac_sel = 0x10
        bl_load_opt = 0
        sense_mode_sel =1
        test_en = 0
        dual_cs_mode  = True # during readback, we can look at both banks for chiplets 0/1 or 2/3
        efuse_banks = []

        self.set_vefuse(vefuse)
        self.set_rd_pattern(100,1000,1000,100,100)
        self.cfg_rd_ctrl(0, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)
        self.cfg_rd_ctrl(2, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)

        # get Bank 0 and 1 data in parallel, and then Bank 2 and 3 data in parallel
        for bank in range(0,4,2):
            efuse_banks.append([])
            efuse_banks.append([])
            for row in range(16):
                efuse_banks[bank].append([])
                efuse_banks[bank+1].append([])
                self.set_addr(bank, row, 0,dual_cs_mode) # column number does not matter
                self.fire_oneshot()
                read_data = self.get_data(bank)
                for col in range(8):
                    efuse_banks[bank][row].append((read_data & 2**col) >> col )
                    efuse_banks[bank+1][row].append((read_data & 2**(col+8)) >> (col+8) ) #row data bit order is [0:7]

        return efuse_banks

    #-----------------------------------------------------------------------------
    # EFuse Low Level Write functions for accessing cells based on Bank/Row/Column
    #-----------------------------------------------------------------------------
    def wr_cell(self,vefuse=5.0, bank=0, row=0, col=0, update_recipe=True):
        '''
            Write (burn) a single EFuse cell
    
        Parameters:
            vefuse   - EFuse voltage
            bank     - target bank
            row      - target row
            col      - target cell
            update_recipe - update the vefuse and wr pattern
        Returns
        -------
        None
    
        '''
        dual_cs_mode = False # we are only writing to one cell in one bank

        if update_recipe:
            self.set_vefuse(vefuse)
            self.set_wr_pattern(200,7000,200)

        self.cfg_wr_ctrl(bank)
        self.set_addr(bank,row,col,dual_cs_mode)
        self.fire_oneshot()

    def wr_row(self,vefuse=5.0, bank=0, row=0):
        '''
            Write (burn) an entire row of EFuse cells. Shortcut function used
            mainly for characterization
    
        Parameters:
            vefuse   - EFuse voltage
            bank     - target bank
            row      - target row
    
        Returns
        -------
        None
    
        '''
        dual_cs_mode = False # we are only writing to one cell in one bank per oneshot

        self.set_vefuse(vefuse)
        self.set_wr_pattern(200,7000,200)
        self.cfg_wr_ctrl(bank)
        for col in range(0,8):
            self.set_addr(bank,row,col,dual_cs_mode)
            self.fire_oneshot()

    def wr_bank(self,vefuse=5.0, bank=0):
        '''
            Write (burn) an entire Bank of EFuse cells. Shortcut function used
            mainly for characterization
    
        Parameters:
            vefuse   - EFuse voltage
            bank     - target bank
    
        Returns
        -------
        None
    
        '''
        dual_cs_mode = False # we are only writing to one cell in one bank per oneshot

        self.set_vefuse(vefuse)
        self.set_wr_pattern(200,7000,200)
        self.cfg_wr_ctrl(bank)
        for row in range(0,16):
            for col in range(0,8):
                self.set_addr(bank,row,col,dual_cs_mode)
                self.fire_oneshot()

    def wr_banks(self,vefuse=5.0):
        '''
            Write (burn) all cells in all Banks of EFuse. Shortcut function used
            mainly for characterization
    
        Parameters:
            vefuse   - EFuse voltage
    
        Returns
        -------
        None
    
        '''
        dual_cs_mode = False # we are only writing to one cell in one bank per oneshot

        self.set_vefuse(vefuse)
        self.set_wr_pattern(200,7000,200)
        for bank in range(0,4):
            self.cfg_wr_ctrl(bank)
            for row in range(0,16):
                for col in range(0,8):
                    self.set_addr(bank,row,col,dual_cs_mode)
                    self.fire_oneshot()

    #-----------------------------------------------------------------------------
    # EFuse Low Level Test function for putting a single cell into Test Mode
    # and applying a test current... monitoring a resulting voltage comparison to
    # a programmable reference source.
    #-----------------------------------------------------------------------------
    def test_cell(self,bank=0, row=0, col=0, vref_sel=6, idac_sel=0x10, sense_mode_sel=1):
        '''
            Run "Test Mode" for a single EFuse cell by injecting a programmable
            test current and returning the comparator result
            (comparator reference also programmable).  This function is mainly for
            characterization of EFuse resistances
    
        Parameters:
            bank     - target bank
            row      - target row
            col      - target cell
            vref_sel       - bit comparator reference voltage selection
            idac_sel       - test current selection
            sense_mode_sel - 0 = resistor as comparator reference, 1 = voltage as comparator reference
        Returns
        -------
        Comparator result of test current * cell resistance vs selected reference
    
        '''
        test_en = 1
        bl_load_opt = 0
        dual_cs_mode = False # only read from one bank (i.e. only 1 chip select will be active during this bit test mode

        self.cfg_rd_ctrl(bank, vref_sel, idac_sel, bl_load_opt, sense_mode_sel, test_en)
        self.set_addr(bank, row, col, dual_cs_mode)

        # Fire the read pattern
        self.fire_oneshot()

        # Get the data for the targeted bank
        read_data = self.get_data(bank)

        if (bank == 0) or (bank == 2):
            efuse_data = read_data & 0x00FF
            #print("\")
            bit_data = (efuse_data  >> col) & 1
        else:
            efuse_data = (read_data & 0xFF00) >> 8
            bit_data = (efuse_data  >> col) & 1
        print("\nbank " + str(bank) + ", row " + str(row) + ", col " + str(col) + ", bit=" + str(bit_data))

        return bit_data