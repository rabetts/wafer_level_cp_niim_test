# -*- coding: utf-8 -*-
"""
This script will connect to the device, write a configuration, read/write/read
a power supply and read a voltage monitor.

"""

import qsi_helpers as qsi
import sys
import platform

##########################################################################
# START
##########################################################################
    
# load up the headers, libs, and connect to our device
initialized = qsi.init()
if not initialized:
    sys.exit()

# Send a configuration to the device
platform_name = platform.system()
if platform_name == "Windows":
    qsi.set_config(R'C:\Users\Zhaoyu He\Dropbox (Quantum-SI)\Q-Si Software\Falcon 64\Chewie\Configuration Files\Unified_Q9001\q9001_CHIPLET0_64R_1024C_RAW_4SP_8p425M_cont.json')
    #qsi.set_config(R'C:\path-to-configuration-files\q9122d_n1_main_array_64_127_ncm_osc_starman_1_unified.json')
else:
    qsi.set_config('/usr/share/qsi-datapad/resources/Nano/q9122d_n1_main_array_64_127_ncm_osc_starman_1_unified.json')

# Read and display the current value for B0_L_OUT_DAC
b0_l_out_dac_val = qsi.ffi.new('float *')
b0_l_out_dac_name = qsi.text2cffi('B0_L_OUT_DAC')
qsi.lib.quantum_voltage_get(b0_l_out_dac_name, b0_l_out_dac_val)
b0_l_out_dac = b0_l_out_dac_val[0]
print()
print('b0_l_out_dac = {0:2.3f}'.format(b0_l_out_dac))

# Write a new value for B0_L_OUT_DAC
b0_l_out_dac += 0.1
qsi.lib.quantum_voltage_set(b0_l_out_dac_name, b0_l_out_dac)

# Read and display the current value for B0_L_OUT_DAC
qsi.lib.quantum_voltage_get(b0_l_out_dac_name, b0_l_out_dac_val)
b0_l_out_dac = b0_l_out_dac_val[0]
print('b0_l_out_dac = {0:2.3f}'.format(b0_l_out_dac))

# Read a monitored value
monitor_name = qsi.text2cffi('VA18')
monitor_val = qsi.ffi.new('monm_information_t *')

qsi.lib.quantum_get_monitor_info(monitor_name, monitor_val)

# Voltage monitor uses index 0
print(str(qsi.ffi.string(monitor_val.name), 'utf-8'), "Voltage Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[0].act, monitor_val.entry[0].ref_val, monitor_val.entry[0].avg))

# Current monitor uses index 1
print(str(qsi.ffi.string(monitor_val.name), 'utf-8'), "Current Actual: {0:2.3f} Ref:{1:2.3f} Avg:{2:2.3f}".format(monitor_val.entry[1].act, monitor_val.entry[1].ref_val, monitor_val.entry[1].avg))


# Disconnect and we are done
qsi.lib.quantum_disconnect_device()


