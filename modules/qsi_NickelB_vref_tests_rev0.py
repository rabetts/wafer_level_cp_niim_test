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





     
class qsi_vref_001():
    name = 'qsi_vref_001'

    def __init__(self):
        hard_bin = 1

       
    def run(self,test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,retest_device):
        
        
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
        

        
       
   
     
      
        
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################         
        if 0:
            qsi.dis()
            input('disconnect from NIM, press any key to reconnect and continue')
            qsi.con()
            time.sleep(1)
        fmb = '311' #set VREFSH_T/B
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()
        vref_params = []
        vref_done = qsi.is_yes(t['test_performed'][0])

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                try:
                #if 1:
                    adcBit = 10
                    Ntb = 1 #number of time bins
                    target = test_conditions['vref_target'] #DN good for PGA spi setting = 1
                    ROI = cfg.vref_ROIS[int(setting['Product_number'])]
                    
                    if qsi.set_rst_level(ROI, Ntb, target,adcBit) == False:
                        parameter_out = False
                    
                    else:
                    
                        qsi.set_CROP_RAW()
                        frame = qsi.capture(1,'crop')
                        #frame = frame[:, :, :, 0:int(frame.shape[-1] // 16 * 15)]

                        qsi.set_CDS_SINGLE_BIN()
                        
                        if qsi.is_yes(t['save_image'][0]): #do we want to save image(s)?
                            test_str = setting['Image_stamp']
                            Image.fromarray(0.25 * frame[0,0,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_reset_'+test_str+'_bin0.tif') 
                            #Image.fromarray(0.25 * frame[0,1,:,:]).save(setting['Data_directory']+'images\\'+setting['Lot']+'_W'+str(setting['Wafer'])+'_P'+str(setting['Chip_position'])+'_reset_'+test_str+'_bin1.tif')
                        
                        #calculate a bunch of parameters from the frame
                        f = frame[0,0,:,:].flatten()
                        #g = frame[0,1,:,:].flatten()
                        #vref_params = [int(qsi.get_Vrefsh()), np.percentile(f,5),np.percentile(f,50),np.percentile(f,95),np.std(f), np.percentile(g,5),np.percentile(g,50),np.percentile(g,95),np.std(g)]
                        vref_params = [int(qsi.get_Vrefsh()), np.percentile(f,5),np.percentile(f,50),np.percentile(f,95),np.std(f)]

                        
                        #calculate parameters over tiles
                        no_col = frame.shape[3]
                        no_row = frame.shape[2]
                        
                        #there are 32 tiles in column direction, 2 tiles in row direction, 64 tiles in all
                        col_step = int(no_col/32)
                        row_step = int(no_row/2)
                       
                        tile_mean_bin0 = []
                        tile_noise_bin0 = []
                        #tile_mean_bin1 = []
                        #tile_noise_bin1 = []
                        no_bad_tiles_signal_bin0 = 0
                        #no_bad_tiles_signal_bin1 = 0
                        no_bad_tiles_noise_bin0 = 0
                        #no_bad_tiles_noise_bin1 = 0
                        for i in range(32):
                            for j in range(2):
                                tile_f = frame[0,0,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
                                #tile_g = frame[0,1,j*row_step:(j+1)*row_step,i*col_step:(i+1)*col_step].flatten()
                                
                                sig_bin0 = np.mean(tile_f)
                                #sig_bin1 = np.mean(tile_g)
                                noise_bin0 = np.std(tile_f)
                                #noise_bin1 = np.std(tile_g)
                                
                                tile_mean_bin0  = tile_mean_bin0  + [sig_bin0 ]
                                #tile_mean_bin1  = tile_mean_bin1  + [sig_bin1]
                                
                                tile_noise_bin0  = tile_noise_bin0  + [noise_bin0]
                                #tile_noise_bin1  = tile_noise_bin1  + [noise_bin1]
                                
                                if sig_bin0 < test_conditions['vref_tile_min_signal_limit'] or sig_bin0 > test_conditions['vref_tile_max_signal_limit']:
                                    no_bad_tiles_signal_bin0 = no_bad_tiles_signal_bin0 + 1
                                    
                                #if sig_bin1 < test_conditions['vref_tile_min_signal_limit'] or sig_bin1 > test_conditions['vref_tile_max_signal_limit']:
                                #    no_bad_tiles_signal_bin1 = no_bad_tiles_signal_bin1 + 1
                                    
                                if noise_bin0 < test_conditions['vref_tile_min_noise_limit'] or noise_bin0 > test_conditions['vref_tile_max_noise_limit']:
                                    no_bad_tiles_noise_bin0 = no_bad_tiles_noise_bin0 + 1
                                    
                                #if noise_bin1 < test_conditions['vref_tile_min_noise_limit'] or noise_bin1 > test_conditions['vref_tile_max_noise_limit']:
                                #    no_bad_tiles_noise_bin1 = no_bad_tiles_noise_bin1 + 1
                                    

                    
                        tile_max_signal_bin0 = np.max(tile_mean_bin0)
                        tile_min_signal_bin0 = np.min(tile_mean_bin0)
                        tile_max_noise_bin0 = np.max(tile_noise_bin0)
                        tile_min_noise_bin0 = np.min(tile_noise_bin0)
                        #
                        # tile_max_signal_bin1 = np.max(tile_mean_bin1)
                        # tile_min_signal_bin1 = np.min(tile_mean_bin1)
                        # tile_max_noise_bin1 = np.max(tile_noise_bin1)
                        # tile_min_noise_bin1 = np.min(tile_noise_bin1)
                        
                        #vref_tile_params = [tile_max_signal_bin0,tile_min_signal_bin0,tile_max_noise_bin0,tile_min_noise_bin0,
                        #                    tile_max_signal_bin1,tile_min_signal_bin1,tile_max_noise_bin1,tile_min_noise_bin1]
                        vref_tile_params = [tile_max_signal_bin0,tile_min_signal_bin0,tile_max_noise_bin0,tile_min_noise_bin0,]

                       #vref_bad_tile_count = [no_bad_tiles_signal_bin0,no_bad_tiles_signal_bin1,no_bad_tiles_noise_bin0,no_bad_tiles_noise_bin1]
                        vref_bad_tile_count = [no_bad_tiles_signal_bin0,no_bad_tiles_noise_bin0]

                        parameter_out = True
                except:
                    parameter_out = False

                        
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
        if vref_done:
            for i in range(len(vref_params)):  #parmeters from vref setting
            
                fmb = str(i+312)
                t0 = time.time()
                t = trd[trd['failure_mode_bin']==fmb]
                t = t.reset_index().to_dict()

                if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                    if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                        try:
                            parameter_out = vref_params[i]
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
        # save min/max tile parameters for vref
        if vref_done:
            for i in range(len(vref_tile_params)):  
            
                fmb = str(i+330)
                t0 = time.time()
                t = trd[trd['failure_mode_bin']==fmb]
                t = t.reset_index().to_dict()

                if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                    if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                        try:
                            parameter_out = vref_tile_params[i]
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
        # count # of bad tiles by each criteria (signal/noise
        if vref_done:
            for i in range(len(vref_bad_tile_count)):  
            
                fmb = str(i+340)
                t0 = time.time()
                t = trd[trd['failure_mode_bin']==fmb]
                t = t.reset_index().to_dict()

                if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                    if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                        try:
                            parameter_out = vref_bad_tile_count[i]
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
         
        
       

