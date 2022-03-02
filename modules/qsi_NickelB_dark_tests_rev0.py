#from qsi_falcon import qsi_helpers as qsi
import numpy as np
import pandas as pd
import os
import sys
import json
from collections import OrderedDict
from scipy.io import savemat
import matplotlib.pyplot as plt
from PIL import Image
import time
import shutil

import qsi_cfg as cfg
sys.path.append(cfg.UTILITY_FILE_PATH)
sys.path.append(cfg.MODULE_FILE_PATH)
import qsi_helpers as qsi
#import char_util as char






	 
class qsi_dark_001():
	name = 'qsi_dark_001'

	def __init__(self):
		hard_bin = 1

	   
	def run(self,test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,retest_device):
		
		b_good_image = True # todo: cleanup.  hack to deal with qsi.capture fail
		#load up current lot/wfr/part/data_file settings
		try:
			dd = pd.read_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
			setting = dict(zip(dd['condition'].to_list(),dd['value'].to_list()))
		except:
			raise Exception('Problem with qsi_current.csv file!')
			
		try:
			trd = pd.read_csv(cfg.TRD_FILE_PATH + cfg.TRD_FILES[int(setting['Product_number'])], low_memory=False).astype('str')

		except:
			raise Exception('Problem with trd file!')
		

		
		
		##########################################################
		#turn laser attenuation to max to put device in the dark, move Y motor to lower limit to hopefully get rid of laser coupling
		##########################################################
		if cfg.LASER_PRESENT:
			percentage_atten=test_conditions['dark_atten']
			qsi.set_mll_atten(percentage_atten) #percentage_atten 0 to 1.0
			qsi.set_motor(qsi.lib.MOTOR_Y, test_conditions['dark_Y']) #with no shutter may also need to move the Y motor to end of range

		##########################################################
		#move MCLK to 0
		##########################################################
		qsi.set_mclk_offset(0)
		
		
		##########################################################
		#take some dark images in PP mode at the minimum tint
		##########################################################
		qsi.set_blk_row(5)
		tint_min = qsi.get_tint()
		
		fmb = '420'
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()
		try:
			mintint_done = qsi.is_yes(t['test_performed'][0])
		except:
			mintint_done = False
		
		#if minttint_done is false then skip all tests
		if mintint_done:
			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						parameter_out = tint_min
					except:
						parameter_out = -10.0
						
			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1
			
			#assess the test results based on TRD file limits etc.
			if mintint_done:
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
							retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
		   
			fmb = '421' #capture a two dark frames at the minimum tint
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()
			mintint_done = qsi.is_yes(t['test_performed'][0])
			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					#try:
					if 1:
						b_check_chewie = False
						if b_check_chewie:
							qsi.dis()
							input('disconnect from NIM, press any key to reconnect and continue')
							qsi.con()
							time.sleep(1)
						frame = qsi.capture(2,'cds')
						frame = np.broadcast_to(frame,(frame.shape[0],2,frame.shape[2],frame.shape[3]))
						if qsi.is_yes(t['save_image'][0]): #do we want to save image(s)?
							test_str = setting['Image_stamp']
							#np.save(setting['Data_directory']+'images\\'+setting['Lot']+'_'+str(setting['Wafer'])+'_'+str(setting['Chip_position'])+'_dark_'+test_str+'.npy',frame)
							Image.fromarray(32* frame[0,0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_min_tint_'+test_str+'_bin0.tif') 
							Image.fromarray(32* frame[0,1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_min_tint_'+test_str+'_bin1.tif')
							 
						#calculate a bunch of parameters from the whole frames
						f = frame[0,0,:,:].flatten()
						f2 = (frame[0,0,:,:]-frame[1,0,:,:]).flatten()
						g = frame[0,1,:,:].flatten()
						g2 = (frame[0,1,:,:]-frame[1,1,:,:]).flatten()
						dark_params =  [np.mean(f),np.std(f2)/np.sqrt(2.0),np.mean(g),np.std(g2)/np.sqrt(2.0)]

						#calculate parameters over tiles
						no_col = frame.shape[3]
						no_row = frame.shape[2]
						
						#there are 32 tiles in column direction, 2 tiles in row direction, 64 tiles in all
						col_step = int(no_col/32)
						row_step = int(no_row/2)
					   
						tile_mean_min_tint_bin0 = []
						tile_noise_min_tint_bin0 = []
						tile_mean_min_tint_bin1 = []
						tile_noise_min_tint_bin1 = []
						
						no_bad_tiles_noise_bin0 = 0
						no_bad_tiles_noise_bin1 = 0
						no_bad_tiles_signal_bin0 = 0
						no_bad_tiles_signal_bin1 = 0
						for i in range(32):
							for j in range(2):
								tile_f = frame[0,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
								tile_f2 = (frame[0,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]-frame[1,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]).flatten()
								tile_g = frame[0,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
								tile_g2 = (frame[0,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]-frame[1,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]).flatten()
								
								sig_bin0 = np.mean(tile_f)
								sig_bin1 = np.mean(tile_g)
								noise_bin0 = np.std(tile_f2)/np.sqrt(2.0)
								noise_bin1 = np.std(tile_g2)/np.sqrt(2.0)
								
								tile_mean_min_tint_bin0	 = tile_mean_min_tint_bin0	+ [sig_bin0]
								tile_mean_min_tint_bin1	 = tile_mean_min_tint_bin1	+ [sig_bin1]
								
								tile_noise_min_tint_bin0  = tile_noise_min_tint_bin0  + [noise_bin0]
								tile_noise_min_tint_bin1  = tile_noise_min_tint_bin1  + [noise_bin1]
								
									
								if noise_bin0 < test_conditions['dark_min_tint_tile_min_noise_limit']  or noise_bin0 > test_conditions['dark_min_tint_tile_max_noise_limit']:
									no_bad_tiles_noise_bin0 = no_bad_tiles_noise_bin0 + 1
									
								if noise_bin1 < test_conditions['dark_min_tint_tile_min_noise_limit']  or noise_bin1 > test_conditions['dark_min_tint_tile_max_noise_limit']:
									no_bad_tiles_noise_bin1 = no_bad_tiles_noise_bin1 + 1
									
								if sig_bin0 < test_conditions['dark_min_tint_tile_min_signal_limit']  or sig_bin0 > test_conditions['dark_min_tint_tile_max_signal_limit']:
									no_bad_tiles_signal_bin0 = no_bad_tiles_signal_bin0 + 1
									
								if sig_bin1 < test_conditions['dark_min_tint_tile_min_signal_limit']  or sig_bin1 > test_conditions['dark_min_tint_tile_max_signal_limit']:
									no_bad_tiles_signal_bin1 = no_bad_tiles_signal_bin1 + 1
									

						
						tile_max_signal_min_tint_bin0 = np.max(tile_mean_min_tint_bin0)
						tile_min_signal_min_tint_bin0 = np.min(tile_mean_min_tint_bin0)
						tile_max_noise_min_tint_bin0 = np.max(tile_noise_min_tint_bin0)
						tile_min_noise_min_tint_bin0 = np.min(tile_noise_min_tint_bin0)
						
						tile_max_signal_min_tint_bin1 = np.max(tile_mean_min_tint_bin1)
						tile_min_signal_min_tint_bin1 = np.min(tile_mean_min_tint_bin1)
						tile_max_noise_min_tint_bin1 = np.max(tile_noise_min_tint_bin1)
						tile_min_noise_min_tint_bin1 = np.min(tile_noise_min_tint_bin1)
						
						dark_tile_params_min_tint = [tile_max_signal_min_tint_bin0,tile_min_signal_min_tint_bin0,tile_max_noise_min_tint_bin0,tile_min_noise_min_tint_bin0,
											tile_max_signal_min_tint_bin1,tile_min_signal_min_tint_bin1,tile_max_noise_min_tint_bin1,tile_min_noise_min_tint_bin1]
						
						dark_min_tint_bad_tile_count = [no_bad_tiles_noise_bin0,no_bad_tiles_noise_bin1,no_bad_tiles_signal_bin0,no_bad_tiles_signal_bin1]
						
						parameter_out = True
						
						
					#except:
						#parameter_out = False
						
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
		
				
	   
			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device  #testng is over for this chip
			

			
		


			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			# save whole frame parameters for min tint
			for i in range(len(dark_params)):  
			
				fmb = str(i+422)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_params[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
					
			 
				
			#print(dark_tile_params_min_tint)
			
			
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			# save min/max tile parameters for min tint
			for i in range(len(dark_tile_params_min_tint)):	 
			
				fmb = str(i+430)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_tile_params_min_tint[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
		
	   
			
		##########################################################
		#take some dark images in PP mode at the standard sequencing integration time
		##########################################################
		qsi.set_tint(test_conditions['tint_seq'])
		
	   
		fmb = '451' #capture a single dark frame at the sequencing tint
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()
		try:
			seqtint_done = qsi.is_yes(t['test_performed'][0])
		except:
			seqtint_done = False
			
		if seqtint_done:
			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					#try:
					if 1:
						frame = qsi.capture(2,'cds')
						frame = np.broadcast_to(frame,(frame.shape[0],2,frame.shape[2],frame.shape[3]))
						if qsi.is_yes(t['save_image'][0]): #do we want to save image(s)?
							test_str = setting['Image_stamp']
							Image.fromarray(32* frame[0,0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_seq_tint_'+test_str+'_bin0.tif') 
							Image.fromarray(32* frame[0,1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_seq_tint_'+test_str+'_bin1.tif')
							 
						#calculate a bunch of parameters from the frames
						f = frame[0,0,:,:].flatten()
						f2 = (frame[0,0,:,:]-frame[1,0,:,:]).flatten()
						g = frame[0,1,:,:].flatten()
						g2 = (frame[0,1,:,:]-frame[1,1,:,:]).flatten()
						dark_params_seq =  [np.mean(f),np.std(f2)/np.sqrt(2.0),np.mean(g),np.std(g2)/np.sqrt(2.0)]
						
						
						#calculate parameters over tiles
						no_col = frame.shape[3]
						no_row = frame.shape[2]
						
						#there are 32 tiles in column direction, 2 tiles in row direction, 64 tiles in all
						col_step = int(no_col/32)
						row_step = int(no_row/2)
					   
						tile_mean_seq_tint_bin0 = []
						tile_noise_seq_tint_bin0 = []
						tile_mean_seq_tint_bin1 = []
						tile_noise_seq_tint_bin1 = []
						
						no_bad_tiles_noise_bin0 = 0
						no_bad_tiles_noise_bin1 = 0
						no_bad_tiles_signal_bin0 = 0
						no_bad_tiles_signal_bin1 = 0
						
						for i in range(32):
							for j in range(2):
								tile_f = frame[0,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
								tile_f2 = (frame[0,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]-frame[1,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]).flatten()
								tile_g = frame[0,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
								tile_g2 = (frame[0,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]-frame[1,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step]).flatten()
								
								sig_bin0 = np.mean(tile_f)
								sig_bin1 = np.mean(tile_g)
								noise_bin0 = np.std(tile_f2)/np.sqrt(2.0)
								noise_bin1 = np.std(tile_g2)/np.sqrt(2.0)
								
								tile_mean_seq_tint_bin0	 = tile_mean_seq_tint_bin0	+ [sig_bin0]
								tile_mean_seq_tint_bin1	 = tile_mean_seq_tint_bin1	+ [sig_bin1]
								
								tile_noise_seq_tint_bin0  = tile_noise_seq_tint_bin0  + [noise_bin0]
								tile_noise_seq_tint_bin1  = tile_noise_seq_tint_bin1  + [noise_bin1]
								
								if noise_bin0 < test_conditions['dark_seq_tint_tile_min_noise_limit']  or noise_bin0 > test_conditions['dark_seq_tint_tile_max_noise_limit']:
									no_bad_tiles_noise_bin0 = no_bad_tiles_noise_bin0 + 1
									
								if noise_bin1 < test_conditions['dark_seq_tint_tile_min_noise_limit']  or noise_bin1 > test_conditions['dark_seq_tint_tile_max_noise_limit']:
									no_bad_tiles_noise_bin1 = no_bad_tiles_noise_bin1 + 1
									
								if sig_bin0 < test_conditions['dark_seq_tint_tile_min_signal_limit']  or sig_bin0 > test_conditions['dark_seq_tint_tile_max_signal_limit']:
									no_bad_tiles_signal_bin0 = no_bad_tiles_signal_bin0 + 1
									
								if sig_bin1 < test_conditions['dark_seq_tint_tile_min_signal_limit']  or sig_bin1 > test_conditions['dark_seq_tint_tile_max_signal_limit']:
									no_bad_tiles_signal_bin1 = no_bad_tiles_signal_bin1 + 1
						
						tile_max_signal_seq_tint_bin0 = np.max(tile_mean_seq_tint_bin0)
						tile_min_signal_seq_tint_bin0 = np.min(tile_mean_seq_tint_bin0)
						tile_max_noise_seq_tint_bin0 = np.max(tile_noise_seq_tint_bin0)
						tile_min_noise_seq_tint_bin0 = np.min(tile_noise_seq_tint_bin0)
						
						tile_max_signal_seq_tint_bin1 = np.max(tile_mean_seq_tint_bin1)
						tile_min_signal_seq_tint_bin1 = np.min(tile_mean_seq_tint_bin1)
						tile_max_noise_seq_tint_bin1 = np.max(tile_noise_seq_tint_bin1)
						tile_min_noise_seq_tint_bin1 = np.min(tile_noise_seq_tint_bin1)
						
						dark_tile_params_seq_tint = [tile_max_signal_seq_tint_bin0,tile_min_signal_seq_tint_bin0,tile_max_noise_seq_tint_bin0,tile_min_noise_seq_tint_bin0,
											tile_max_signal_seq_tint_bin1,tile_min_signal_seq_tint_bin1,tile_max_noise_seq_tint_bin1,tile_min_noise_seq_tint_bin1]

						dark_seq_tint_bad_tile_count = [no_bad_tiles_noise_bin0,no_bad_tiles_noise_bin1,no_bad_tiles_signal_bin0,no_bad_tiles_signal_bin1]
						
						parameter_out = True
					#except:
						#parameter_out = False
						
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
			
			
		
			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device  #testng is over for this chip
				
		   

			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			
			for i in range(len(dark_params_seq)):  
			
				fmb = str(i+452)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_params_seq[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			  

			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			# save min/max tile parameters for seq tint
			for i in range(len(dark_tile_params_min_tint)):	 
			
				fmb = str(i+460)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_tile_params_seq_tint[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
		
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			# count # of bad tiles by each criteria min tint
			for i in range(len(dark_min_tint_bad_tile_count)):	
			
				fmb = str(i+470)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_min_tint_bad_tile_count[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
					
			
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			for i in range(len(dark_seq_tint_bad_tile_count)):	
			
				fmb = str(i+474)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = dark_seq_tint_bad_tile_count[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 


		if mintint_done and seqtint_done:
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#calculate dark current from min_tint and seq_tint in PP mode, bin0
			
			fmb = '480'
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						parameter_out = (dark_params_seq[0]-dark_params[0])/(test_conditions['tint_seq']-tint_min)*1000.0*2.0  #extra 2.0 factor since PP2 integration time is for ping+pong
					except:
						parameter_out = -10.0
						
			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1
			
			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
		
			
			
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#calculate dark current from min_tint and seq_tint in PP mode, bin1
			fmb = '481'
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						parameter_out = (dark_params_seq[2]-dark_params[2])/(test_conditions['tint_seq']-tint_min)*1000.0*2.0  #extra 2.0 factor since PP2 integration time is for ping+pong
					except:
						parameter_out = -10.0
						
			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1
			
			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 

			##########################################################
			# dark PP mode blinking pixel test
			##########################################################
			qsi.set_blk_row(test_conditions['tint_min_row'])
			tint_min = qsi.get_tint()

			########################################
			# go to PP mode
			########################################
			qsi.set_PP_mode()

			fmb = '490'
			t0 = time.time()
			t = trd[trd['failure_mode_bin'] == fmb]
			t = t.reset_index().to_dict()
			try:
				dark_blinking_done = qsi.is_yes(t['test_performed'][0])
			except:
				dark_blinking_done = False

			# if dark_blinking_done is false then skip all tests
			if dark_blinking_done:

				frame = qsi.capture(int(test_conditions['dark_blinking_frame_no']), 'cds')
				# calculate noise of each pixel
				blink_noise_bin0 = np.std(frame[:, 0, :, :], axis=0).flatten()
				# hack.  nickel D giving smaller frame than Nickel G
				if cfg.chip_type=='NickelD':
					blink_noise_bin1 = np.std(frame[:, 0, :, :], axis=0).flatten()
				else:
					blink_noise_bin1 = np.std(frame[:, 1, :, :], axis=0).flatten()


				blink_noise_tot_num = blink_noise_bin0.shape[0]

				blink_noise_median_bin0 = np.median(blink_noise_bin0)
				blink_noise_median_bin1 = np.median(blink_noise_bin1)
				blink_noise_IQR_bin0 = np.percentile(blink_noise_bin0, 75) - np.percentile(blink_noise_bin0, 25)
				blink_noise_IQR_bin1 = np.percentile(blink_noise_bin1, 75) - np.percentile(blink_noise_bin1, 25)

				# calculate # pixels with noise > 3*IQR + median

				blink_noise_percent_thr_35_bin0 = float(
					(blink_noise_bin0 > 3.5).sum()) / blink_noise_tot_num * 100.0
				blink_noise_percent_thr_35_bin1 = float(
					(blink_noise_bin1 > 3.5).sum()) / blink_noise_tot_num * 100.0
				blink_noise_percent_thr_50_bin0 = float(
					(blink_noise_bin0 > 5.0).sum()) / blink_noise_tot_num * 100.0
				blink_noise_percent_thr_50_bin1 = float(
					(blink_noise_bin1 > 5.0).sum()) / blink_noise_tot_num * 100.0

				print('number of bin1 pixels with >3.5DN dark temporal noise = ' + str(
					int(blink_noise_percent_thr_35_bin1 * blink_noise_tot_num / 100.0)))
				print('number of bin1 pixels with >5.0DN dark temporal noise = ' + str(
					int(blink_noise_percent_thr_50_bin1 * blink_noise_tot_num / 100.0)))
				print('number of bin0 pixels with >3.5DN dark temporal noise = ' + str(
					int(blink_noise_percent_thr_35_bin0 * blink_noise_tot_num / 100.0)))
				print('number of bin0 pixels with >5.0DN dark temporal noise = ' + str(
					int(blink_noise_percent_thr_50_bin0 * blink_noise_tot_num / 100.0)))
				if qsi.is_yes(t['save_image'][0]):  # do we want to save image(s)?
					test_str = setting['Image_stamp']
					props = dict(boxstyle='square', facecolor='wheat', alpha=0.5)
					# bin0 noise distribution
					di = pd.DataFrame(blink_noise_bin0)
					di.columns = ['noise']
					hist = di.hist(figsize=(12, 8), bins=500)
					p = plt.gca()
					title_text = 'Blinking Pixel Noise Dist. bin0, median = ' + str(
						round(blink_noise_median_bin0, 2)) + ', IQR = ' + str(round(blink_noise_IQR_bin0, 2))
					file_name = setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(
						setting['Wafer']) + '_P' + str(
						setting['Chip_position']) + '_blinking_pixel_dist_' + test_str + '_bin0.png'
					textstr = '>3.5DN percent=%.3f\n>5.0DN percent=%.3f\ntot_num=%.0f' % (
					blink_noise_percent_thr_35_bin0, blink_noise_percent_thr_50_bin0, blink_noise_tot_num)
					p.set_title(title_text, fontsize=12)
					p.set_xlabel('Temporal Noise (DN)')
					p.set_ylabel('# pixels')
					p.text(0.8, .9, textstr, transform=p.transAxes, fontsize=9, verticalalignment='top', bbox=props)
					plt.grid('on', 'major', 'y')
					p.set_yscale('log')
					plt.tight_layout()

					plt.savefig	(file_name)
					plt.close

					# # bin1 noise distribution
					# di = pd.DataFrame(blink_noise_bin1)
					# di.columns =['noise']
					# hist = di.hist(figsize=(12 ,8) ,bins=500)
					# p = plt.gca()
					# title_text = 'Blinking Pixel Noise Dist. bin1, median =  ' +str \
					# 	(round(blink_noise_median_bin1 ,2) ) +', IQR =  ' +str(round(blink_noise_IQR_bin1 ,2))
					# file_name = setting['Data_directory' ] +'images\\ ' +setting['Lot' ] +'_W ' +str \
					# 	(setting['Wafer'] ) +'_P ' +str \
					# 	(setting['Chip_position'] ) +'_blinking_pixel_dist_ ' +test_str +'_bin1.png'
					# textstr ='>10DN percent=%.3f\n>20DN percent=%.3f\ntot_num=%.0f' % (
					# blink_noise_percent_thr_10_bin1, blink_noise_percent_thr_20_bin1, blink_noise_tot_num)
					# p.set_title(title_text, fontsize=12)
					# p.set_xlabel('Temporal Noise (DN)')
					# p.set_ylabel('# pixels')
					# p.text(0.8, .9, textstr, transform=p.transAxes, fontsize=9, verticalalignment='top', bbox=props)
					# plt.grid('on', 'major', 'y')
					# p.set_yscale('log')
					# plt.tight_layout()
					#
					# plt.savefig	(file_name)
					# plt.close
				blinking_parameters = [blink_noise_median_bin0 ,blink_noise_median_bin1 ,blink_noise_IQR_bin0
									   ,blink_noise_IQR_bin1 ,blink_noise_percent_thr_35_bin0
									   ,blink_noise_percent_thr_35_bin1,
									   blink_noise_percent_thr_50_bin0 ,blink_noise_percent_thr_50_bin1
									   ,blink_noise_tot_num]
				# must save 9 parameters currently.  should fix
				# blinking_parameters = [blink_noise_median_bin0 ,blink_noise_IQR_bin0,
				# 						blink_noise_percent_thr_10_bin0,
				# 					    blink_noise_percent_thr_20_bin0,blink_noise_tot_num]
				parameter_out = True

			else:  # the blinking pixel test is in the TRD file but is not done so just add a line
				parameter_out = -1

			# assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data ,t ,setting ,fmb
																				   ,parameter_out ,hard_bin
																				   ,failure_mode_bin ,continue_test
																				   ,t1-t0)
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
					retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin ,retest_device  # testng is over for this chip

			# save dark blinking parameters
			if dark_blinking_done:
				for i in range(9):
					fmb = str( i +491)
					t0 = time.time()
					t = trd[trd['failure_mode_bin' ]==fmb]
					t = t.reset_index().to_dict()
					if len(t['failure_mode_bin'] ) >0:  # is this test in the TRD file?
						if qsi.is_yes(t['test_performed'][0]):  # the test is in the TRD file and is done
							try:
								parameter_out = blinking_parameters[i]
							except:
								parameter_out = -10.0

					else:  # the test is in the TRD file but is not done so just add a line
						parameter_out = -1

					# assess the test results based on TRD file limits etc.
					t1 = time.time()
					test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data ,t ,setting
																						   ,fmb ,parameter_out
																						   ,hard_bin
																						   ,failure_mode_bin
																						   ,continue_test ,t1-t0)
					if not continue_test:
						if qsi.is_yes(t['retest_on_fail']):
							retest_device = True
						return test_data, continue_test, hard_bin, failure_mode_bin ,retest_device  # testng is over for this chip


		
		########################################
		#go to PP mode for detailed dark noise dark current assessment of both bins
		########################################
		qsi.set_PP_mode()
		
		
		########################################
		#figure out blanking rows
		########################################
		qsi.set_blk_row(5)
		tint_min = qsi.get_tint()


		#define list of tints for dark current scan.
		tints = [tint_min, test_conditions['tint_seq'], test_conditions['tint_seq']*0.25*test_conditions['tint_mult'], test_conditions['tint_seq']*0.5*test_conditions['tint_mult'], test_conditions['tint_seq']*test_conditions['tint_mult']]
		#print('dark integration time scan tint values = '+str(tints))
		
		#see if first tint value is done..if not, then skip all tests
		t = trd[trd['failure_mode_bin']=='500']
		t = t.reset_index().to_dict()
		try:
			tintscan_done = qsi.is_yes(t['test_performed'][0])
		except:
			tintscan_done = False
			
		if tintscan_done:
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#save tint values for later debug purposes
			for i in range(len(tints)):	 
				fmb = str(i+500)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = tints[i]
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			
			#############################################################################################################################################################	 
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#scan integration times and calculated temporal noise and dark current using 100 frames
			
			fmb = '510'
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()
			temporal_noise_50th_bin0 = []
			temporal_noise_50th_bin1 = []
			temporal_noise_95th_bin0 = []
			temporal_noise_95th_bin1 = []
			signal_level_50th_bin0 = []
			signal_level_50th_bin1 = []
			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
				#if 1:
					tt=0
					for tint in tints:	#scan integration times
						qsi.set_tint(tint)
						b_check_chewie = False
						if b_check_chewie:
							qsi.dis()
							input('disconnect from NIM, press any key to reconnect and continue')
							qsi.con()
							time.sleep(1)
						try:
							frame = qsi.capture(int(test_conditions['tint_scan_frame_no']),'cds')
						except:
							b_good_image = False
							parameter_out = False
							break  # todo:  jump out of loop, go to end test fore this chip (does this work?)
						frame = np.broadcast_to(frame, (frame.shape[0], 2, frame.shape[2], frame.shape[3]))
						# signal_level_50th_bin0 = signal_level_50th_bin0 + [np.median(frame[5,0,:,:].flatten())]	 #just take median of 5th frame
						# signal_level_50th_bin1 = signal_level_50th_bin1 + [np.median(frame[5,1,:,:].flatten())]	 #just take median of 5th frame
						signal_level_50th_bin0 = signal_level_50th_bin0 + [np.mean(frame[5,0,:,:].flatten())]	 #just take median of 5th frame
						signal_level_50th_bin1 = signal_level_50th_bin1 + [np.mean(frame[5,1,:,:].flatten())]	 #just take median of 5th frame
						std0 = np.std(frame[:,0,:,:],axis=0).flatten()
						std1 = np.std(frame[:,1,:,:],axis=0).flatten()
						temporal_noise_50th_bin0 = temporal_noise_50th_bin0 + [np.median(std0)]
						temporal_noise_50th_bin1 = temporal_noise_50th_bin1 + [np.median(std1)]
						temporal_noise_95th_bin0 = temporal_noise_95th_bin0 + [np.percentile(std0,95)]
						temporal_noise_95th_bin1 = temporal_noise_95th_bin1 + [np.percentile(std1,95)]
						if tt==0:
							frame_first = frame	 #for difference image later on


						tt=tt+1
					frame_last = frame #for difference image later on

					parameter_out = True

			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1
			
			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if (not continue_test) or (not b_good_image):
				if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 

			dark_params_tint = [signal_level_50th_bin0, signal_level_50th_bin1, temporal_noise_50th_bin0,temporal_noise_50th_bin1, temporal_noise_95th_bin0, temporal_noise_95th_bin1]


			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#save tint values for later debug purposes
			for j in range(6):
				for i in range(len(tints)):
				
					fmb = str(i+520+j*10)
					t0 = time.time()
					t = trd[trd['failure_mode_bin']==fmb]
					t = t.reset_index().to_dict()

					if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
						if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
							try:
								parameter_out = dark_params_tint[j][i]
							except:
								parameter_out = -10.0
								
					else: #the test is in the TRD file but is not done so just add a line
						parameter_out = -1
					
					#assess the test results based on TRD file limits etc.
					t1 = time.time()
					test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
					if not continue_test:
						if qsi.is_yes(t['retest_on_fail']):
							retest_device = True
						return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			
			
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#find bin0/bin1 dark current in DN/sec
			DC_DN_per_msec = [] #for future calcs
			for i in range(2):

				fmb = str(i+580)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
						#if 1:
							test_str = setting['Image_stamp']
							file_name = setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_current_'+test_str+'_bin'+str(i)+'.png'
							fig_title = setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_current_'+test_str+'_bin'+str(i)
							fig_xlabel = 'tint (msec)'
							fig_ylabel = 'dark signal DN'
							dud, parameter_out = qsi.fit_line(tints,dark_params_tint[i][:],0.0,300.0,-1000.0,0.0,1000.0,10000.0,file_name,fig_title,fig_xlabel,fig_ylabel,t['save_image'][0])
							DC_DN_per_msec = DC_DN_per_msec + [parameter_out] #save for CGC calc below
							parameter_out = parameter_out*1000.0 #convert to DN/sec
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			
			
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			# save bin0/bin1 images of max-min tint
			for i in range(2):

				fmb = str(i + 582)
				t0 = time.time()
				t = trd[trd['failure_mode_bin'] == fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin']) > 0:  # is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]):  # the test is in the TRD file and is done
						if qsi.is_yes(t['save_image'][0]):  # do we want to save image(s)?
							test_str = setting['Image_stamp']
							fr = frame_last - frame_first
							fr = np.median(fr[:, :, :, :], axis=0)
							Image.fromarray(4 * fr[i, :, :]).save(
								setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(
									setting['Wafer']) + '_P' + str(
									setting['Chip_position']) + '_dark_diff_' + test_str + '_bin' + str(i) + '.tif')
						parameter_out = True

				else:  # the test is in the TRD file but is not done so just add a line
					parameter_out = False

				# assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data, t, setting, fmb,
																					   parameter_out, hard_bin,
																					   failure_mode_bin, continue_test,
																					   t1 - t0)
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin, retest_device  # testng is over for this chip

			# find dark signal white pixel count
			fmb = '584'
			t0 = time.time()
			t = trd[trd['failure_mode_bin'] == fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin']) > 0:  # is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]):  # the test is in the TRD file and is done
					try:
						dfr = fr[0,:,:]
						n_wp_75 = (dfr[np.abs(dfr-dfr.mean())>test_conditions['white_pix_thr']].size)/dfr.size
						parameter_out = n_wp_75
					except:
						parameter_out = 0

			else:  # the test is in the TRD file but is not done so just add a line
				parameter_out = False

			# assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data, t, setting, fmb,
																				   parameter_out, hard_bin,
																				   failure_mode_bin, continue_test,
																				   t1 - t0)
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
					retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin, retest_device  # testng is over for this chip

			############################################################################################################################################################
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#find bin0/bin1 read noise in DN, also calculate CGC for each bin
			CGC = []
			RN_electrons = []
			for i in range(2):

				fmb = str(i+590)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							test_str = setting['Image_stamp']
							file_name = setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_noise_'+test_str+'_bin'+str(i)+'.png'
							fig_title = setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_noise_'+test_str+'_bin'+str(i)
							fig_xlabel = 'tint (msec)'
							fig_ylabel = '(dark noise DN)^2'
							parameter_out,dud = qsi.fit_line(tints,np.array(dark_params_tint[i+2][:])**2,1.0,1.0,0.0,0.0,10.0,1000.0,file_name,fig_title,fig_xlabel,fig_ylabel,t['save_image'][0])
							parameter_out = np.sqrt(parameter_out)
							CGC = CGC + [DC_DN_per_msec[i]/dud]
							RN_electrons = RN_electrons + [parameter_out*DC_DN_per_msec[i]/dud]
							
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			

			
			
			
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#save bin0/bin1 images of temporal noise
			for i in range(4):

				fmb = str(i+592)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						if qsi.is_yes(t['save_image'][0]): #do we want to save image(s)?
							test_str = setting['Image_stamp']
							if i==0:
								fr = np.std(frame_first[:,0,:,:],axis=0)
								Image.fromarray(64*fr).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_min_tint_noise_'+test_str+'_bin0.tif') 
							elif i==1:
								fr = np.std(frame_first[:,1,:,:],axis=0)
								Image.fromarray(64*fr).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_min_tint_noise_'+test_str+'_bin1.tif') 
							elif i==2:
								fr = np.std(frame_last[:,0,:,:],axis=0)
								Image.fromarray(64*fr).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_max_tint_noise_'+test_str+'_bin0.tif') 
							elif i==3:
								fr = np.std(frame_last[:,1,:,:],axis=0)
								Image.fromarray(64*fr).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_max_tint_noise_'+test_str+'_bin1.tif') 

							
						parameter_out = True
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = False
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
						 
		
		
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#CGC in electrons/DN for bin0/bin1
			for i in range(2):

				fmb = str(i+596)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:	 
							parameter_out = CGC[i]							 
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#dark current in electrons/sec for bin0/bin1
			for i in range(2):

				fmb = str(i+598)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:	 
							parameter_out = DC_DN_per_msec[i] * CGC[i]	* 1000.0 #convert do e/sec					   
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
			
			
			############################################################################################################################################################	
			#############################################################################################################################################################		   
			#############################################################################################################################################################	
			#read noise in electrons
			for i in range(2):

				fmb = str(i+600)
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:	 
							parameter_out = RN_electrons[i]					   
						except:
							parameter_out = -10.0
							
				else: #the test is in the TRD file but is not done so just add a line
					parameter_out = -1
				
				#assess the test results based on TRD file limits etc.
				t1 = time.time()
				test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
				if not continue_test:
					if qsi.is_yes(t['retest_on_fail']):
						retest_device = True
					return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip 
					
			 
				
		return test_data, continue_test, hard_bin, failure_mode_bin,retest_device
		 
		
	   

