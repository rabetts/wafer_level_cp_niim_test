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



class qsi_assembly_fail_001():
    name = 'qsi_assembly_fail_001'

    def __init__(self):
        hard_bin = 1

       
    def run(test_data,test_conditions,continue_test, hard_bin, failure_mode_bin):

        
        
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
        pick_no = -1
        for i in range(int(setting['Number_assembly_fails'])):
            fmb = '2' #assembly fail
            t = trd[trd['failure_mode_bin']==fmb]
            t = t.reset_index().to_dict()
            setting['Chip_position']=pick_no-i

            if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                    parameter_out = False
                else: #the test is in the TRD file but is not done so just add a line
                    parameter_out = False
            
            #assess the test results based on TRD file limits etc.
            test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,0)         
            if not continue_test:
                return test_data, continue_test, hard_bin, failure_mode_bin #testng is over for this chip
                
        
            
            
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################
        fmb = '10000' #summarize test

        parameter_value = -1
        parameter_name = 'FT_summary'
        
        #append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_bin_mode,setting,test_duration,test_no,test_fmb)
        test_data = qsi.append_test_settings(test_data,parameter_name,parameter_value,hard_bin,'2',setting,0,fmb,fmb) 
            



            
        
        return test_data, continue_test, hard_bin, failure_mode_bin
         
        
       

