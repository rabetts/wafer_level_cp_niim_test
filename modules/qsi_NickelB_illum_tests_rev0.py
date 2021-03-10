#from qsi_falcon import qsi_helpers as qsi
import numpy as np
import pandas as pd
import os
import sys
import json
from collections import OrderedDict
from scipy.io import savemat
from PIL import Image
import time
import shutil
import threading

import qsi_cfg as cfg
sys.path.append(cfg.UTILITY_FILE_PATH)
sys.path.append(cfg.MODULE_FILE_PATH)
import qsi_helpers as qsi
#import debug.qsi_nickel_macros as macros
#import char_util as char
import requests



# for an mclk sweep img stream, calc median pixel rej_ratio (within laser spot ROI)
# rej_ratio = value at 90percentile pixel_response / value 1ns after 90percentile pixel_response
# currently assumes mclk_sweep starts high ,drops low, then optinoally back high (after half way)
def calc_mclk_sweep_rr(imgs):
	d_imgs = {}
	#imgs = imgs_p[:,y_roi[0]:y_roi[1],x_roi[0]:x_roi[1]]
	for mclk_idx in np.arange(imgs.shape[0]):
		d_imgs[mclk_idx] = imgs[mclk_idx]

	dd1 = {(y, x): imgs[:, y, x] for y in np.arange(imgs.shape[1]) for x in np.arange(imgs.shape[2])}
	df1 = pd.DataFrame(dd1, index=np.arange(imgs.shape[0]))
	df1.index.name = 'mclk'
	df1.columns.names = (['y', 'x'])

	#y_idx = pd.IndexSlice
	#x_idx = pd.IndexSlice
	#df_rr = df1.loc[:, (y_idx[y_roi[0]:y_roi[1]], x_idx[x_roi[0],x_roi[1]])].apply(find_pix_rr, axis=0)  # for each pixel
	df_rr = df1.apply(find_pix_rr, axis=0)  # for each pixel
	print(f"collect response median = {df_rr.loc['resp_collect'].median()}")
	print(f"reject response median = {df_rr.loc['resp_reject'].median()}")
	print(f"reject response std dev = {df_rr.loc['resp_reject'].std()}")

	return df_rr.loc['rr'].median()

def find_pix_rr(ds):
	collect_plateau = 0
	rej_floor = 125  # mclk index
	# breakpoint()
	ds1 = ds.iloc[collect_plateau:rej_floor]
	p90 = ds1[0:30].mean() * 0.9
	p10 = ds1[0:30].mean() * 0.1
	try:
		# breakpoint()
		t_90 = ds1[ds1 > p90].index[-1]
		t_10 = ds1[ds1 > p10].index[-1]
		# find time in sweep 1ns after t_collect' point
		mclk_idx_per_1ns = 13
		t_rej = t_90 + mclk_idx_per_1ns
		resp_p90 = ds1.loc[t_90]
		resp_p10 = ds1.loc[t_10]
		resp_rej = ds.loc[t_rej]
		d_ret = {'resp_collect': resp_p90, 'resp_reject': resp_rej, 'resp_p10': resp_p10, 't_90': t_90,
				 't_10': t_10}
		d_ret['rr'] = resp_p90 / np.abs(resp_rej)  # hack to deal with temporal noise negative values
		mclk_per_index = 25
		ps_per_mclk = 3.1
		d_ret['fall_rate'] = (resp_p90 - resp_p10) / (t_10 - t_90) * mclk_idx_per_1ns
	except:
		d_ret = {'rr': -99, 'resp_collect':-99, 'resp_reject':-99}
	return (pd.Series(d_ret))



class qsi_illum_001():
	name = 'qsi_illum_001'

	def __init__(self):
		hard_bin = 1

	   
	def run(self,test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,retest_device):
		#if not cfg.LASER_PRESENT:
		#	return test_data, continue_test, hard_bin, failure_mode_bin,retest_device
		
		
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
		#turn laser on and set motors to initial positions
		##########################################################		 
		qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, test_conditions['align_atten'])	 
		
		#check laser power
		time.sleep(1)
		power = qsi.get_laser_power()
		print('laser power = '+str(round(power,1))+'mW')
		if power > 25.0:
			print('laser power = '+str(round(power,1))+'mW. Too high, setting laser atten to 0 and exiting.')
			percentage_atten=test_conditions['dark_atten']
			qsi.set_mll_atten(percentage_atten) #percentage_atten 0 to 1.0
			time.sleep(1)
			power = qsi.get_laser_power()
			print('new laser power = '+str(round(power,1))+'mW')
			sys.exit()
			
			
			
		
		qsi.set_motor(qsi.lib.MOTOR_THETA_X, test_conditions['align_theta_X'])	
		qsi.set_motor(qsi.lib.MOTOR_THETA_Y, test_conditions['align_theta_Y'])
		
		qsi.get_motor_info(qsi.lib.MOTOR_ATTENUATOR)
		
		##########################################################
		#move MCLK back to 0
		##########################################################
		qsi.set_mclk_offset(0)
		mclk_align = 0	#mclk may be adjusted during laser alignment for chips with no optical filter
		
		
		
		
		
		#############################################################################################################################################################	 
		#############################################################################################################################################################		   
		#############################################################################################################################################################		  

		fmb = '611' #align laser
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()

		if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
			if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
				#try:
				if 1:
					qsi.set_SB_mode()
					qsi.set_tint(test_conditions['tint_align'])
					aligned, mclk_align = qsi.align_laser(test_conditions,setting)
					if aligned:
						qsi.set_PP_mode()
						parameter_out = True
						
					else:
						#print('Aligning laser with long scan....')
						#parameter_out = qsi.coarse_mll_alignment()
						qsi.set_PP_mode()
						parameter_out = False
						
					
					if parameter_out:
						motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_X)
						#print('MOTOR_X = '+str(current_offset))
						setting['MOTOR_X']=current_offset
						motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_Y)
						#print('MOTOR_Y = '+str(current_offset))
						setting['MOTOR_Y']=current_offset
						motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_THETA_X)
						#print('MOTOR_THETA_X = '+str(current_offset))
						setting['MOTOR_THETA_X']=current_offset
						motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_THETA_Y)
						#print('MOTOR_THETA_Y = '+str(current_offset))
						setting['MOTOR_THETA_Y']=current_offset
					   
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
		#get beam steering motor positions after aligning chip 
		#define MOTOR_X				1
		#define MOTOR_Y				2
		#define MOTOR_THETA_X		3
		#define MOTOR_THETA_Y		4
		#define MOTOR_ATTENUATOR	5
		#define MOTOR_WAVE_CAVITY	6	// OLD incorrect name; use MOTOR_ICW instead
		#define MOTOR_ICW			6
		#define MOTOR_ROLL			7
		#define MOTOR_UNUSED_7		8

		
		#for i in range(7):	#beam steering motor posistion
		for i in range(0):  # beam steering motor posistion
			fmb = str(i+612)
			
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()
			
			########################################################################################################################
			#the low and high limits for beam steering parameters depend on the tester....need to modify these values in the dict here
			########################################################################################################################
			
			motors = [['X',612],['Y',613],['THETA_X',614],['THETA_Y',615]]
			for m in motors:
				if int(m[1])==int(fmb):
					t['low_limit'][0]=int(test_conditions['beam_steer_'+m[0]+'_min'])+int(t['low_limit'][0])
					t['high_limit'][0]=int(test_conditions['beam_steer_'+m[0]+'_max'])-int(t['high_limit'][0])
					
			
			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						motor_ind = i+1
						motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(motor_ind)
						parameter_out = int(current_offset)
					except:
						parameter_out = -10
						
			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1

			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
					retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip	 

	   
		#only do next test if there is an optical filter present
		#if setting['filter']!='none':
		
		##########################################################
		#set tint to sequencing value
		##########################################################
		#qsi.set_tint(test_conditions['tint_seq'])	#turned off 2020-09-30 since tint is now adjusted in this scan anyway
		
		
		#############################################################################################################################################################	   
		#############################################################################################################################################################			   
		#############################################################################################################################################################	 
		illuminated_photon_metric = 0.0 #this will be used later...define it just in case this test fails
		fmb = '620' # set laser power so median pixel with aperture is target value
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()

		if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
			if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
				#print('adjusting tint, mclk, laser power for illuminated images')
				print('adjusting mclk, laser power for illuminated power metric')
				#try:
				if 1:
					target = float(test_conditions['illum_median_signal'])
				
					
					#set tint to sequencing value for MCLK scan
					qsi.set_tint(test_conditions['tint_seq'])
					#print('setting tint to sequencing value = '+str(test_conditions['tint_seq'])+' msec')
					
					#set power to a value above the minimum readout for the Nickel instrument
					qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, cfg.atten_alignment) #earlier cfg.atten_1mW...now higher pwer so we minimize tint/mclk to get to this
					time.sleep(1)
					power = qsi.get_laser_power()
					if power < cfg.min_measurement_power: #laser power is getting too low...realign laser
						print('laser power = '+str(round(qsi.get_laser_power(),1))+', which is too low.  re-align laser')
						print('starting internal laser alignment, this should take ~10-20 seconds')
						qsi.align_mll()
						print('setting laser power to '+str(cfg.align_measurement_power)+'mW to calibrate for illuminated scans')
						cfg.atten_alignment = qsi.set_mll_power_get_atten(cfg.align_measurement_power)
						
						#set power to a value above the minimum readout for the Nickel instrument (again!)
						qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, cfg.atten_alignment) #earlier cfg.atten_1mW...now higher pwer so we minimize tint/mclk to get to this
						time.sleep(1)
						power = qsi.get_laser_power()
						print('new laser power = '+str(round(power,1))+'mW')
						#disable gets removed on restart
						qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds 
						print('laser ready')
						qsi.set_config(cfg.CURRENT_CONFIG_PATH ) #write the config to the chip again
					 
					signal, signal_0, signal_1, signal_2, signal_3	= qsi.get_current_signal(setting,test_conditions)
					print('current signal = '+str(round(signal,1)))

					#adjust laser power if signal is too low
					if signal < target:
						parameter_out, signal, signal_0, signal_1, signal_2, signal_3 = qsi.set_laser_power(target,setting,test_conditions)
					
					else: #signal is too high...adjust mclk
						signal, mclk_align = qsi.adjust_mclk(target,setting,test_conditions)
						signal, signal_0, signal_1, signal_2, signal_3	= qsi.get_current_signal(setting,test_conditions)
					
						
					
					sig_par = []
					sig_par = sig_par + [signal]
					power = qsi.get_laser_power()
					sig_par = sig_par + [power]
					tint = qsi.get_tint()
					sig_par = sig_par + [tint]
					sig_par = sig_par + [tint*power*target/signal]
					sig_par = sig_par + [signal_0]
					sig_par = sig_par + [signal_1]
					sig_par = sig_par + [signal_2]
					sig_par = sig_par + [signal_3]
					
					chiplet_sig = [signal_0,signal_1,signal_2,signal_3]
					percent_diff = (np.max(chiplet_sig)-np.min(chiplet_sig))/np.max(chiplet_sig)*100.0
					sig_par = sig_par + [percent_diff]
					sig_par = sig_par + [mclk_align]
					
					

					print('illuminated laser power = '+str(round(power,1))+' mW')
					print('illuminated tint = '+str(round(tint,1))+' msec')
					illuminated_photon_metric = tint*power*target/signal
					print('illuminated photon metric = '+str(round(illuminated_photon_metric,1))+' mW x msec')
					print('illuminated MCLK = '+str(mclk_align))
					parameter_out = True #hack to keep test going for parts where illuminated power goes to 0
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
		#laser power and median signal for illuminated image
		
		for i in range(4):	
			fmb = str(i+621)
			
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					parameter_out = sig_par[i]
						
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
		#chiplet median signals
		
		for i in range(5):	
			fmb = str(round(i+1601,1))
			
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					parameter_out = sig_par[i+4]
						
			else: #the test is in the TRD file but is not done so just add a line
				parameter_out = -1

			#assess the test results based on TRD file limits etc.
			t1 = time.time()
			test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)			
			if not continue_test:
				if qsi.is_yes(t['retest_on_fail']):
					retest_device = True
				return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip	 



		

		fmb = '629' #MCLK scan forGSL laser
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()


		if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
			if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
				test_str = setting['Image_stamp']

				ROI = cfg.illum_ROIS[int(setting['Product_number'])]
				mclk_points = int(test_conditions['MCLK points'])
				mclk_step = int(test_conditions['MCLK step'])
				mclk_offset = np.arange(int(test_conditions['MCLK start'] * mclk_step),
										int(test_conditions['MCLK start']) + mclk_points * mclk_step, mclk_step)
				# loop for 2 b1 dc levels
				b1_common = 1.25
				num_frs = 625
				for idx in range(1):
					if idx==0:
						b1 = b1_common
					# run 2nd  loop if new b1_tune found
					elif b1_tune != b1_common:
						b1 = b1_tune
					else:
						break
				# for b0 in np.arange(0.75, 1.51, 0.25):
				# 	for b1 in np.arange(0.75,1.51,0.25):
				#for b0,b1 in [(1.0,1.0), (1.25,1.25)]:
				#for b0,b1 in [(1.1,1.2),(1.2,1.2),(1.3,1.3)]:
				for b0,b1 in [(1.25,1.25),]:
				#for b0 in np.arange(1.0, 1.61, 0.2):
				#	for b1 in np.arange(1.0, 1.61, 0.2):

						#set b1 dc_level thru STS
						set_vmod_led((b1-0.5)) # tmp fix, drop b1 by 0.5V so next set will trigger STS to restore
						set_vmod_led((b1)) # tmp fix, use STS smu ch to set b1 dc bias
						#for n_blk_rows in [0, 2504]: # prev 461 also
						#for n_blk_rows in [4, 316]:  # prev 461 also
						for n_blk_rows in [4,316]:  # prev 461 also
							# qsi.set_config("C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\configurations\\q9001_prober_outer_102x1024_with_2btm_rows_cont_65M_8M_S50194_picoquant_off.json")  # write the config w/ pq off
							qsi.set_blk_row(n_blk_rows)
							#set b0 dc_level
							qsi.v_set('B0_L_H_DAC', str(b0))
							print(f"b0 dc level set to {qsi.v_get('B0_L_H_DAC')} from v_set {b0} ")
							qsi.picoquant_enable(enable = False)
							#qsi.gsl_enable(enable=0, vlaser=18.0, vbias=0.5)
							# todo: hack
							wait_for_picoquant_sync()
							#time.sleep(4)
							# grab dark frame, assume 4d, so average frames
							b_check_chewie= False
							if b_check_chewie:
								qsi.dis()
								input('disconnect from NIM, press any key to reconnect and continue')
								qsi.con()
								time.sleep(1)
							dark_frame = qsi.capture(num_frs, 'cds')
							np.save(
								setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(setting['Wafer']) + '_P' + str(
								setting['Chip_position']) + '_' + str(n_blk_rows) + f'_mclk_dark_b0_{b0}V_b1_{b1}V_dc50_frs{num_frs}_sr_ns_' + test_str, dark_frame.mean(0).mean(0))
							# todo:F tmp
							np.save(
								setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(setting['Wafer']) + '_P' + str(
								setting['Chip_position']) + '_' + str(n_blk_rows) + f'_mclk_dark_b0_{b0}V_b1_{b1}V_dc50_all_frames_frs{num_frs}_sr_ns_' + test_str, dark_frame)

							row_num = dark_frame.shape[2]
							col_num = dark_frame.shape[3]
							# store per pixel dark frame
							dark_frame = np.mean(dark_frame, axis=0)
							dud = dark_frame
							dud = dud[:, ROI[0]:ROI[1]:ROI[2], ROI[3]:ROI[4]:ROI[5]]
							dark = np.median(dud)
							# turn on laser
							#qsi.gsl_clock_init(pulse2=170)  # defaults to pulse1=0, pulse2=150
							#qsi.gsl_enable(enable=1, vlaser=18.0, vbias=0.5)
							time.sleep(1)
							#qsi.gsl_info()
							# qsi.gsl_enable(enable=0, vlaser=18.0, vbias=0.4)
							# time.sleep(1)
							# qsi.gsl_info()
							# qsi.gsl_enable(enable=1, vlaser=18.0, vbias=0.4)
							# time.sleep(1)
							# qsi.gsl_info()
							# qsi.set_config("C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\configurations\\q9001_prober_outer_102x1024_with_2btm_rows_cont_65M_8M_S50194_picoquant_on.json")  # write the config w/ pq on
							qsi.picoquant_enable(enable = True)
							wait_for_picoquant_sync()
							#time.sleep(4)
							# sweep for vt, 1st pass only
							if (True & (n_blk_rows == 4) & (idx==0)):
								num_vt_frames = 25
								vt_start = 1.1
								vt_stop = 1.5
								vt_step = 0.1
								frm_sequence = np.zeros([int(np.round((vt_stop-vt_start)/vt_step)), *(dark_frame.shape)])
								y_roi = (17,18)
								x_roi = (575,625)
								qsi.set_mclk_offset(0)  # solid collect region
								b1_dc_lvls = np.arange(vt_start, vt_stop, vt_step)
								for idx,b1_dc in enumerate(b1_dc_lvls):
									set_vmod_led((b1_dc))  # tmp fix, use STS smu ch to set b1 dc bias
									time.sleep(2)
									frames = qsi.capture(num_vt_frames, 'cds')
									frames_roi = frames[:,0,y_roi[0]:y_roi[1],x_roi[0]:x_roi[1]]
									print(f'b1 dc = {b1_dc} gives mean response {frames_roi.mean()} and wtd dev {frames_roi.std()}')
									frm_sequence[idx] = frames.mean(axis=0)
								np.save(setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(
										setting['Wafer']) + '_P' + str(setting['Chip_position']) + '_' + \
										f'_b1_vt_search_{vt_start}_{vt_stop}_step_{vt_step}_' + test_str, frm_sequence)
								diffs = np.diff(frm_sequence[:,0,y_roi[0]:y_roi[1],x_roi[0]:x_roi[1]].mean(1).mean(1))
								# find first b1 dc_lvl where increment small, take as good operating point
								try:
									b1_tune = np.round(np.max([b1_dc_lvls[np.argwhere(diffs<2)[0][0]],b1_common]),1)
								except:
									b1_tune = b1_common
								# restore b1 dc bias
								set_vmod_led((b1))  # tmp fix, use STS smu ch to set b1 dc bias
							else:
								b1_tune = b1_common
							# sweep mclks, saving frames
							frm_sequence_l = np.zeros([mclk_points, *dark_frame.shape])
							print('running MCLK scan...')
							for i in range(mclk_points):
								qsi.set_mclk_offset(mclk_offset[i])
								time.sleep(0.15)

								# assume 4d , avg 1st 2 dims to get single frame
								# do variable fr averaging depending on mclk window, high for falling  edge only
								num_mclk_frames = 169 if ((i>25) and (i<75)) else 2
								b_check_chewie = False
								if ((i==0) & (b_check_chewie)):
									qsi.dis()
									input('disconnect from NIM, press any key to reconnect and continue')
									qsi.con()
									time.sleep(1)
								capture_frame = qsi.capture(num_mclk_frames,'cds')
								if ((isinstance(capture_frame, int)) or (dark_frame is None)):
									print('Bad capture, Move to next die')
									parameter_out = False
									# assess the test results based on TRD file limits etc.
									t1 = time.time()
									test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data, t, setting,
																										   fmb, parameter_out,
																										   hard_bin,
																										   failure_mode_bin,
																										   continue_test, t1 - t0)
									if not continue_test:
										if qsi.is_yes(t['retest_on_fail']):
											retest_device = True
										return test_data, continue_test, hard_bin, failure_mode_bin, retest_device  # testng is over for this chip

								# np.save(
								# 	setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(
								# 	setting['Wafer']) + '_P' + str(
								# 	setting['Chip_position']) + '_' + str(n_blk_rows) + '_mclk_' + str(mclk_offset[i]) + '_' + test_str, capture_frame.mean(0).mean(0))
								dud = capture_frame[:,:,:,:].mean(axis=0) - dark_frame[:,:,:]
								#select pixels in ROI for all chiplets
								dud_all = dud[:,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
								#only take pixels with apertures above them
								#dud0 = np.multiply(dud_all[0],aper).flatten()
								#dud0 = dud0[dud0 !=0.0]
								#frm_sequence_l[i,0] = np.median(dud0)
								frm_sequence_l[i] = dud
								# lost mclk setting in this save, better to pickle dict?

							# save sweep frames and turn off laser
							np.save(
								setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(
								setting['Wafer']) + '_P' + str(
								setting['Chip_position']) + '_' + str(n_blk_rows) +f'_mclk_sweep_b0_{b0}V_b1_{b1}V_dc50_frs{num_mclk_frames}_sr_ns_' + test_str, frm_sequence_l)
							# display rej ratio for this mclk sequence
							y_roi = (99,101)
							y_roi = (17,18)
							x_roi = (575,625)
							rr_roi = calc_mclk_sweep_rr(frm_sequence_l[:, 0, y_roi[0]:y_roi[1], x_roi[0]:x_roi[1]])
							print(f'rej ratio for blanking rows {n_blk_rows} {y_roi[0]}:{y_roi[1]}, {x_roi[0]}:{x_roi[1]} = {rr_roi}')
					# todo: tmp - check dark frame after mclk sweep, compare to pre
					#time.sleep(2)  # would sync work here?
					# qsi.set_config(cfg.FULL_FRAME_CONFIG_PATH)  # write the config to the chip again
					# n_blk_rows = 500
					# qsi.set_blk_row(n_blk_rows)
					# #time.sleep(1)
					# # load new config
					# # capture illum and save
					# qsi.picoquant_enable(enable=True)
					# wait_for_picoquant_sync()
					# illum_frame = qsi.capture(5, 'cds')
					# np.save( setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(setting['Wafer']) + '_P' + str(
					# 		setting['Chip_position']) + '_' + str(n_blk_rows) + 'full_frame_' + test_str,
					# 		illum_frame.mean(0).mean(0))
					# print(f'image mean = {illum_frame.mean()}')
					# qsi.picoquant_enable(enable=False)
					# wait_for_picoquant_sync()
					# # capture dark and save
					# dark_frame = qsi.capture(5, 'cds')
					# np.save( setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(setting['Wafer']) + '_P' + str(
					# 		setting['Chip_position']) + '_' + str(n_blk_rows) + 'full_frame_dark_' + test_str,
					# 		dark_frame.mean(0).mean(0))
					# b1_tune = 1.5  # hack
					# np.save(
					# 	setting['Data_directory'] + 'images\\' + setting['Lot'] + '_W' + str(setting['Wafer']) + '_P' + str(
					# 		setting['Chip_position']) + '_' + str(n_blk_rows) + '_mclk_dark_post_sweep_all_frames' + test_str,
					# 	dark_frame)
					# todo: remove?  not useful with picoquant?
					#qsi.gsl_enable(enable=0, vlaser=18.0, vbias=0.5)
			##########################################################
			#teardown from mclk test
			##########################################################
			qsi.picoquant_enable(enable=False)
			wait_for_picoquant_sync()
			qsi.set_mclk_offset(0)
			set_vmod_led((0)) # drop to 0V for move to next die



		#############################################################################################################################################################
		#############################################################################################################################################################			   
		#############################################################################################################################################################	 
		# rej_align = 0.0 #this paramter will be used later, define it
		# fmb = '630' #MCLK scan
		# t0 = time.time()
		# t = trd[trd['failure_mode_bin']==fmb]
		# t = t.reset_index().to_dict()
		#
		#
		# if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
		# 	if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
		#
		# 		#for MCLK we will only use pixels with apertures over them
		# 		ROI = cfg.illum_ROIS[int(setting['Product_number'])]
		# 		aper = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]).astype('float')
		#
		# 		#convert all nonzero elements in aper array to 1.0
		# 		aper = np.where(aper > 0.0, 1.0, 0.0)
		#
		# 		#try:
		# 		if 1:
		# 			#turn off laser
		# 			motor_ind, current_offset_attenuator, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_ATTENUATOR)
		# 			qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, cfg.atten_0mW)
		#
		# 			#move Y motor off from peak position by -400 steps (or +400 steps if necessary)
		# 			motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_Y)
		# 			if current_offset > 500+min_step:
		# 				qsi.set_motor(qsi.lib.MOTOR_Y, current_offset - 400)
		# 			else:
		# 				qsi.set_motor(qsi.lib.MOTOR_Y, current_offset + 400)
		#
		# 			dark_frame = qsi.capture(10,'cds')
		# 			row_num = dark_frame.shape[2]
		# 			col_num = dark_frame.shape[3]
		# 			dark_frame = np.mean(dark_frame,axis=0)
		# 			dud = dark_frame
		# 			dud = dud[:,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		# 			dud1 = np.multiply(dud[1],aper).flatten()
		# 			dud1 = dud1[dud1 !=0.0]
		# 			dark = np.median(dud1)
		#
		# 			#move MOTOR_ATTENUATOR back so chip is illuminated
		# 			qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, current_offset_attenuator)
		#
		# 			#move MOTOR_Y back so chip is illuminated
		# 			qsi.set_motor(qsi.lib.MOTOR_Y, current_offset)
		#
		# 			#move MCLK to initial position for scan
		# 			qsi.set_mclk_offset(test_conditions['MCLK start'])
		#
		#
		# 			#now check if signal is too low or too high....this will happen if MCLK was adjusted above knee for laser alignment of no-filter chips or from changing tint
		# 			#if setting['filter']=='none':
		# 			capture_frame = qsi.capture(10,'cds')
		# 			dud = np.mean(capture_frame[:,:,:,:],axis=0) - dark_frame[:,:,:]
		# 			dud = dud[:,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		# 			dud1 = np.multiply(dud[1],aper).flatten()
		# 			dud1 = dud1[dud1 !=0.0]
		# 			signal = np.median(dud1)
		#
		# 			print('MCLK collection initial signal = '+str(round(signal,1)))
		# 			if signal > test_conditions['illum_median_signal']:
		# 				print('moving MOTOR_Y off peak to reduce signal')
		# 				target = test_conditions['illum_median_signal']
		# 				motor_range = 200
		# 				step = 1
		# 				qsi.adjust_MOTOR_Y_off_peak(target,dark,motor_range,step,setting,test_conditions)
		# 			else: #the signal is below the target...most likely because tint was adjusted down from alignmsent value of tint
		# 				target = test_conditions['illum_median_signal']
		# 				#get MOTOR_ATTENUATOR info
		# 				motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(qsi.lib.MOTOR_ATTENUATOR)
		# 				qsi.raise_laser_power(target,current_offset,min_step,10,dark,ROI,aper,50)
		#
		# 			#now adjust X as it may have been off during laser alignment if MCLK is above the knee (left right asymetry problem)
		# 			#only use bin0 for this
		# 			print('adjusting X under collection conditions')
		# 			d_frame = dark_frame[0,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		#
		# 			#only take pixels with apertures above them
		# 			d_frame = np.multiply(d_frame,aper).flatten()
		# 			d_frame = d_frame[d_frame !=0.0]
		# 			d_frame = np.mean(d_frame)
		#
		# 			motor_range = 100
		# 			motor_scan_step = 10
		# 			motor = qsi.lib.MOTOR_X
		# 			motor_ind, current_offset, coil_sleep,coil_max_current, min_step, max_step, deg_step = qsi.get_motor_info(motor)
		# 			print('old X position = '+str(round(current_offset,0)))
		# 			#set the motor_range to be +/- motor_range from the current position
		# 			if current_offset - motor_range > min_step:
		# 				lower = current_offset - motor_range
		# 			else:
		# 				lower = min_step
		# 			if current_offset + motor_range < max_step:
		# 				upper = current_offset + motor_range
		# 			else:
		# 				upper = max_step
		# 			min, max, max_motor_step = qsi.scan_laser_alignment_motor(motor,lower,upper,motor_scan_step,d_frame,ROI,aper,50.0)
		# 			print('scan X: min signal = '+str(round(min,1))+', max signal = '+str(round(max,1))+', max signal motor position = '+str(max_motor_step))
		# 			qsi.set_motor(motor,max_motor_step)
		#
		# 			#capture illuminated frame for later figs
		# 			illum_frame = qsi.capture(10,'cds')
		# 			illum_frame = np.mean(illum_frame,axis=0)
		#
		# 			#set up ROIs for chiplets
		# 			ROI_chiplet_data = [[int(row_num/2),ROI[1],ROI[2],ROI[3],int(col_num/2),ROI[5]],
		# 							[int(row_num/2),ROI[1],ROI[2],int(col_num/2),ROI[4],ROI[5]],
		# 							[ROI[0],int(row_num/2),ROI[2],int(col_num/2),ROI[4],ROI[5]],
		# 							[ROI[0],int(row_num/2),ROI[2],ROI[3],int(col_num/2),ROI[5]]]
		# 			aper_chiplet = []
		# 			for j in range(len(ROI_chiplet_data)):
		# 				aper_dud = np.array(pd.read_csv(cfg.MASK_FILE_PATH + setting['aperture_file'],header=None).values[ROI_chiplet_data[j][0]:ROI_chiplet_data[j][1]:ROI_chiplet_data[j][2],ROI_chiplet_data[j][3]:ROI_chiplet_data[j][4]:ROI_chiplet_data[j][5]]).astype('float')
		#
		# 				#convert all nonzero elements in aper array to 1.0
		# 				aper_chiplet = aper_chiplet + [np.where(aper_dud > 0.0, 1.0, 0.0)]
		#
		# 			mclk_points = int(test_conditions['MCLK points'])
		# 			mclk_step = int(test_conditions['MCLK step'])
		# 			mclk_offset = np.arange(int(test_conditions['MCLK start']),int(test_conditions['MCLK start']) +	 mclk_points * mclk_step, mclk_step)
		# 			frm_sequence_l = np.zeros([mclk_points, 2])
		# 			chiplet_data = [np.zeros([mclk_points, 2]),np.zeros([mclk_points, 2]),np.zeros([mclk_points, 2]),np.zeros([mclk_points, 2])]
		#
		# 			print('running MCLK scan...')
		# 			for i in range(mclk_points):
		# 				qsi.set_mclk_offset(mclk_offset[i])
		# 				capture_frame = qsi.capture(1,'cds')
		#
		# 				dud = np.mean(capture_frame[:,:,:,:],axis=0) - dark_frame[:,:,:]
		#
		# 				#select pixels in ROI for all chiplets
		# 				dud_all = dud[:,ROI[0]:ROI[1]:ROI[2],ROI[3]:ROI[4]:ROI[5]]
		#
		# 				#only take pixels with apertures above them
		# 				dud0 = np.multiply(dud_all[0],aper).flatten()
		# 				dud1 = np.multiply(dud_all[1],aper).flatten()
		# 				dud0 = dud0[dud0 !=0.0]
		# 				dud1 = dud1[dud1 !=0.0]
		#
		# 				frm_sequence_l[i,0] = np.median(dud0)
		# 				frm_sequence_l[i,1] = np.median(dud1)
		#
		#
		# 				for j in range(len(ROI_chiplet_data)):
		# 					#select pixels in ROI for all chiplets
		# 					dud_all = dud[:,ROI_chiplet_data[j][0]:ROI_chiplet_data[j][1]:ROI_chiplet_data[j][2],ROI_chiplet_data[j][3]:ROI_chiplet_data[j][4]:ROI_chiplet_data[j][5]]
		#
		# 					#only take pixels with apertures above them
		# 					dud0 = np.multiply(dud_all[0],aper_chiplet[j]).flatten()
		# 					dud1 = np.multiply(dud_all[1],aper_chiplet[j]).flatten()
		# 					dud0 = dud0[dud0 !=0.0]
		# 					dud1 = dud1[dud1 !=0.0]
		#
		# 					chiplet_data[j][i,0] = np.median(dud0)
		# 					chiplet_data[j][i,1] = np.median(dud1)
		# 					j= j+1
		#
		#
		# 			#now fit the MCLK scans for the entire array
		# 			#fit one exponential convolved with gaussian resolution function
		# 			mclk_beg = test_conditions['mclk_beg'] #beginning MCLK setting for bin1 fit to MCLK scan
		# 			mclk_end = test_conditions['mclk_end']	#ending MCLK setting for bin1 fit to MCLK scan
		# 			knee = test_conditions['knee']	#initial guess for MCLK bin1 knee position
		# 			amp = test_conditions['amp']  #initial	guess for MCLK bin1 amplitude
		# 			tau = test_conditions['tau']  #initial guess for MCLK bin1 exponential tau
		# 			bgnd = test_conditions['bgnd'] #initial guess for MCLK bin1 backgrounf
		# 			res = test_conditions['res']  #intial guess for MCLK bin1 resolution function width
		#
		# 			test_str = setting['Image_stamp']
		# 			file_name = setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_MCLK_'+test_str+'.png'
		# 			fig_title = setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_MCLK_'+test_str
		#
		# 			knee0,knee1,rejection_bin0_1nsec,rejection_bin1_1nsec,rejection_bin0_0p5nsec,rejection_bin1_0p5nsec,rejection_bin0_0p25nsec,
		# 			rejection_bin1_0p25nsec,amp0,amp1,bgnd0,bgnd1,tau0,tau1,res0,res1,MCLK_diff,rej_align,collection_metric_bin0,collection_metric_bin1
		# 			= qsi.fit_mclk(
		# 					frm_sequence_l[:,0],frm_sequence_l[:,1],test_conditions['MCLK step'],mclk_beg,mclk_end,knee,amp,bgnd,tau,
		# 					res,file_name,fig_title,t['save_image'][0],test_conditions,0,mclk_align)
		#
		#
		# 			MCLK_params = [knee0,knee1,rejection_bin0_1nsec,rejection_bin1_1nsec,rejection_bin0_0p5nsec,rejection_bin1_0p5nsec,rejection_bin0_0p25nsec,rejection_bin1_0p25nsec,amp0,amp1,bgnd0,bgnd1,tau0,tau1,res0,res1,MCLK_diff,collection_metric_bin0,collection_metric_bin1]
		#
		# 			print('collection_metric_bin0 = '+str(round(collection_metric_bin0,2)))
		# 			print('collection_metric_bin1 = '+str(round(collection_metric_bin1,2)))
		# 			#now fit chiplets
		#
		# 			knees = []
		# 			MCLK_params_chiplets = []
		# 			for j in range(len(ROI_chiplet_data)):
		# 				mclk_beg = test_conditions['mclk_beg'] #beginning MCLK setting for bin1 fit to MCLK scan
		# 				mclk_end = test_conditions['mclk_end']	#ending MCLK setting for bin1 fit to MCLK scan
		# 				knee = test_conditions['knee']	#initial guess for MCLK bin1 knee position
		# 				amp = test_conditions['amp']  #initial	guess for MCLK bin1 amplitude
		# 				tau = test_conditions['tau']  #initial guess for MCLK bin1 exponential tau
		# 				bgnd = test_conditions['bgnd'] #initial guess for MCLK bin1 backgrounf
		# 				res = test_conditions['res']  #intial guess for MCLK bin1 resolution function width
		#
		# 				test_str = setting['Image_stamp']
		# 				file_name = setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_MCLK_'+test_str+'_chiplet'+str(j)+'.png'
		# 				fig_title = setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_MCLK_'+test_str+' chiplet'+str(j)
		# 				frm_sequence_l[:,0] = chiplet_data[j][:,0]
		# 				frm_sequence_l[:,1] = chiplet_data[j][:,1]
		#
		# 				knee0,knee1,rejection_bin0_1nsec,rejection_bin1_1nsec,rejection_bin0_0p5nsec,rejection_bin1_0p5nsec,rejection_bin0_0p25nsec,rejection_bin1_0p25nsec,amp0,amp1,bgnd0,bgnd1,tau0,tau1,res0,res1,MCLK_diff,rej_align_dud,collection_metric_bin0,collection_metric_bin1 = qsi.fit_mclk(frm_sequence_l[:,0],frm_sequence_l[:,1],
		# 																						  test_conditions['MCLK step'],mclk_beg,mclk_end,knee,amp,bgnd,tau,res,file_name,fig_title,t['save_image'][0],test_conditions,0,mclk_align)
		#
		#
		# 				MCLK_params_chiplets = MCLK_params_chiplets + [[knee0,knee1,rejection_bin0_1nsec,rejection_bin1_1nsec,rejection_bin0_0p5nsec,rejection_bin1_0p5nsec,rejection_bin0_0p25nsec,rejection_bin1_0p25nsec,amp0,amp1,bgnd0,bgnd1,tau0,tau1,res0,res1,MCLK_diff,collection_metric_bin0,collection_metric_bin1]]
		#
		# 				knees = knees + [knee1]
		#
		# 				print('chiplet'+str(j)+' collection_metric_bin0 = '+str(round(collection_metric_bin0,2)))
		# 				print('chiplet'+str(j)+' collection_metric_bin1 = '+str(round(collection_metric_bin1,2)))
		# 			parameter_out = True
		# 		#except:
		# 			#parameter_out = False
		# 			#MCLK_params = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
		# 			#MCLK_params_chiplets = []
		# 			#for kk in range(4):
		# 				#MCLK_params_chiplets = MCLK_params_chiplets + [[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]
		#
		# 	else: #the test is in the TRD file but is not done so just add a line
		# 		parameter_out = -1
		# 		MCLK_params = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
		# 		MCLK_params_chiplets = []
		# 		for kk in range(4):
		# 			MCLK_params_chiplets = MCLK_params_chiplets + [[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]
		#
		# #assess the test results based on TRD file limits etc.
		# t1 = time.time()
		# test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)
		# if not continue_test:
		# 	if qsi.is_yes(t['retest_on_fail']):
		# 			retest_device = True
		# 	return test_data, continue_test, hard_bin, failure_mode_bin,retest_device  #testng is over for this chip
		#
		
		#############################################################################################################################################################	   
		#############################################################################################################################################################			   
		#############################################################################################################################################################	 
		fmb = '625' #save illuminated and dark frames
		t0 = time.time()
		t = trd[trd['failure_mode_bin']==fmb]
		t = t.reset_index().to_dict()

		if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
			if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
				#try:
				if 1:
					#frame = qsi.capture(1,'cds')  
					if qsi.is_yes(t['save_image'][0]): #do we want to save image(s)?
						test_str = setting['Image_stamp']
						#np.save(setting['Data_directory']+'images\\'+setting['Lot']+'_'+str(setting['Wafer'])+'_'+str(setting['Chip_position'])+'_dark_'+test_str+'.npy',frame)
						#illum_frame[bin,row,col]
						if illum_frame.shape[0]==1:
							#Image.fromarray(1 * frame[0,0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin0.tif') 
							Image.fromarray(1 * illum_frame[0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin0.tif') 
							Image.fromarray(1 * dark_frame[0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_'+test_str+'_bin0.tif') 

						if illum_frame.shape[0]==2:
							#Image.fromarray(1 * frame[0,0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin0.tif') 
							#Image.fromarray(1 * frame[0,1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin1.tif') 
							Image.fromarray(1 * illum_frame[0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin0.tif') 
							Image.fromarray(1 * illum_frame[1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_illum_'+test_str+'_bin1.tif') 
							Image.fromarray(1 * dark_frame[0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_'+test_str+'_bin0.tif') 
							Image.fromarray(1 * dark_frame[1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_dark_'+test_str+'_bin1.tif') 
						
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
		#save MCLK scan parameters for entire array
		#for i in range(19):
		for i in range(0):

			fmb = str(i+640)
			if i>16:	
				fmb = str(i-17+740)
			
			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						parameter_out = MCLK_params[i]
					except:
						parameter_out = -10
						
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
		#save MCLK scan parameters for chiplets
		#for j in range(4):
		for j in range(0):
			for i in range(19):
				fmb = str(i+657+j*17)
				if i>16:
					fmb = str(i-17+742+j*2)
				
				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = MCLK_params_chiplets[j][i]
						except:
							parameter_out = -10
							
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
		#save MCLK max knee difference among chiplets
		if 0:
			fmb = '725'

			t0 = time.time()
			t = trd[trd['failure_mode_bin']==fmb]
			t = t.reset_index().to_dict()

			if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
				if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
					try:
						parameter_out = np.max(knees)-np.min(knees)
					except:
						parameter_out = -10

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
			#save illum_median_laser_power_x_tint_x_rej etc
			if illuminated_photon_metric > 0.0 and rej_align > 0.0:
				print('rej_align = '+str(round(rej_align,1)))
				illuminated_photon_metric_rej = illuminated_photon_metric/rej_align
				print('illum_median_laser_power_x_tint_x_rej = '+str(round(illuminated_photon_metric_rej,3)))
			else:
				illuminated_photon_metric_rej = -10.0
				print('rej_align = '+str(round(rej_align,1)))
				print('can not calculate illum_median_laser_power_x_tint_x_rej')

			illum_par = [mclk_align, rej_align,illuminated_photon_metric_rej]
			for j in range(3):
				fmb = str(j+730)

				t0 = time.time()
				t = trd[trd['failure_mode_bin']==fmb]
				t = t.reset_index().to_dict()

				if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
					if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
						try:
							parameter_out = illum_par[j]
						except:
							parameter_out = -10

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
			#move MCLK back to 0
			##########################################################
			qsi.set_mclk_offset(0)

			##########################################################
			#set laser power back to 0
			##########################################################
			qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, cfg.atten_0mW)
			time.sleep(1)
			power = qsi.get_laser_power()
			print('laser power after illuminated tests = '+str(round(power,1))+'mW')

		##########################################################
		# move MCLK back to 0
		##########################################################
		qsi.set_mclk_offset(0)

		#save setting values in qsi_prod_setup.csv file (save for next chip since it will hopefully have similar MOTOR_X, MOTOR_Y, etc values
		df = pd.DataFrame.from_dict(setting, orient="index")
		df = df.reset_index()
		df.columns = ['condition','value']
		df.to_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
		
		return test_data, continue_test, hard_bin, failure_mode_bin,retest_device

def wait_for_picoquant_sync():
		tries = 0
		max_tries = 40
		while not qsi.picoquant_clock_locked():
			time.sleep(0.1)
			tries += 1
			if tries > max_tries:
				print('picoquant failed to sync')
				return 0
		return 1


def _flask_get_led_v_mod_real():
	r = requests.get('http://10.52.11.36:5000/get_v_mod_led_real')
	vmod = float(eval(r.text)['v'])
	return (vmod)


def _flask_set_led_v_mod_request(v_mod_request):
	r = requests.get(f'http://10.52.11.36:5000/set_v_mod_led_request/{v_mod_request}')
	return (r.text)


def _flask_get_i_led():
	r = requests.get('http://10.52.11.36:5000/get_i_led')
	i = float(eval(r.text)['i'])
	return (i)


def set_vmod_led(vmod_led):
	_flask_set_led_v_mod_request(vmod_led)
	while True:
		time.sleep(1)
		if np.isclose(_flask_get_led_v_mod_real(), vmod_led, rtol=0.002):
			print(f'LED Vmod is set to {vmod_led}')
			break