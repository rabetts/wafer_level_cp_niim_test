import json
import os
import time
import sys
import traceback
import tkinter as tk
from tkinter import messagebox
import numpy as np
import pandas as pd
from collections import OrderedDict
import shutil

import qsi_cfg as cfg
import qsi_helpers as qsi
sys.path.append(cfg.UTILITY_FILE_PATH)
sys.path.append(cfg.MODULE_FILE_PATH)

from qsi_NickelB_init_tests_rev0 import qsi_init_001
from qsi_NickelB_vref_tests_rev0 import qsi_vref_001
from qsi_NickelB_dark_tests_rev0 import qsi_dark_001
from qsi_NickelB_illum_tests_rev0 import qsi_illum_001
from qsi_NickelB_summarize_tests_rev0 import qsi_summarize_001
from qsi_NickelB_assembly_fails_rev0 import qsi_assembly_fail_001







def run_all(results):
	# dark + gsl/picoquant mclk sweeps
	test_items = [qsi_init_001(),qsi_vref_001(),qsi_dark_001(),qsi_illum_001()]
	#test_items = [qsi_init_001(),qsi_vref_001(),qsi_dark_001()]
	#test_items = [qsi_init_001(),]
	# dark tests only
	#test_items = [qsi_init_001(),qsi_vref_001(),qsi_dark_001()]
	#test_items = [qsi_init_001(),qsi_vref_001(), qsi_illum_001()]

	#load up current lot/wfr/part/data_file settings
	try:
		dd = pd.read_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
		setting = dict(zip(dd['condition'].to_list(),dd['value'].to_list()))
	except:
		raise Exception('Problem with qsi_current.csv file!')
   
	
	#load up trd file (already checked that it is OK in main program
	trd = pd.read_csv(cfg.TRD_FILE_PATH + cfg.TRD_FILES[int(setting['Product_number'])], low_memory=False).astype('str')
	
	##########################################################
	#copy rev controlled config file to temporary config file that is modified during tests
	#only do this for first module!!!!! ON other modules just keep cfg.CURRENT_CONFIG_PATH the same
	##########################################################
	shutil.copy(cfg.CONFIGURATION_FILE_PATH+cfg.BASE_CONFIGURATION_FILES[int(setting['Product_number'])], cfg.CURRENT_CONFIG_PATH)
	
	#load up test_consitions from csv file for this product
	try:
		dd = pd.read_csv(cfg.TC_FILE_PATH + cfg.TC_FILES[int(setting['Product_number'])])
		test_conditions = dict(zip(dd['condition'].to_list(),dd['value'].to_list()))
	except:
		messagebox.showinfo('Error!', 'Invalid test conditions file, consult engineering')
		return
	
	#these test_conditions are dependent on the tester, included in test_conditions dict so they are saved on every test
	test_conditions['dark_Y'] = cfg.dark_Y	 #value of Y for dark tests (no shutter)
	test_conditions['align_theta_X'] = cfg.align_theta_X  #value of theta_X for laser alignment
	test_conditions['align_theta_Y'] = cfg.align_theta_Y  #value of theta_Y for initial laser alignment
	test_conditions['align_atten'] = cfg.atten_alignment #value of atten for initial laser alignment
	
	#it is useful to save the min/max motor positions of X, Y, THETA_X, THETA_Y in test_conditions
	if cfg.LASER_PRESENT:
		motors = [[qsi.lib.MOTOR_X,'X'],[qsi.lib.MOTOR_Y,'Y'],[qsi.lib.MOTOR_THETA_X,'THETA_X'],[qsi.lib.MOTOR_THETA_Y,'THETA_Y']]
		for m in motors:
			motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(m[0])
			test_conditions['beam_steer_'+m[1]+'_min']=min_step
			test_conditions['beam_steer_'+m[1]+'_max']=max_step
	
	t00 = time.time()
	hard_bin = 1
	failure_mode_bin = 0
	continue_test = True
	retest_device = False
	test_data = []
	
	for test in test_items:
		
		if continue_test:
			t0 = time.time()		
			test_data, continue_test, hard_bin, failure_mode_bin,retest_device = test.run(test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,retest_device)
				
			t1 = time.time()
			print(str(test.name) + ' finished, time = '+ str(round((t1-t0), 1)) + ' sec.')

	   
	t11 = time.time()	 
	print('##############')
	print('All tests finished, time = '+ str(round((t11-t00), 1)) + ' sec.')
	print('##############')
	print('')
	
	#add one last row to test_data that summarizes the test
	test_data, continue_test, hard_bin, failure_mode_bin = qsi_summarize_001.run(test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,(t11-t00))
	
	
	#convert test_data into a pandas dataframe with appropriate columns
	test_data = pd.DataFrame(test_data,columns = cfg.TEST_DATA_COLUMNS)
	
	
	results = results.append(test_data)
	
	#return the data and final results for this chip
	return results,hard_bin, failure_mode_bin,retest_device
	
	
def run_assembly_fail(results):

	
	#load up trd file (already checked that it is OK in main program
	trd = pd.read_csv(cfg.TRD_FILE_PATH + cfg.TRD_FILES[int(setting['Product_number'])], low_memory=False).astype('str')
	
 
	hard_bin = 1 #assembly fail
	failure_mode_bin = 0
	continue_test = True
	retest_device = False
	test_data = []
	
	
	#add one last row to test_data that summarizes the test
	test_data, continue_test, hard_bin, failure_mode_bin = qsi_assembly_fail_001.run(test_data,test_conditions,continue_test, hard_bin, failure_mode_bin)
	
   
	print('##############')
	print('Assembly fails added.')
	print('##############')
	print('')
	
	#convert test_datainto a pandas dataframe with appropriate columns
	test_data = pd.DataFrame(test_data,columns = cfg.TEST_DATA_COLUMNS)
	
	
	results = results.append(test_data)
	
	#return the data data and final results for this chip
	return results,hard_bin, failure_mode_bin,retest_device