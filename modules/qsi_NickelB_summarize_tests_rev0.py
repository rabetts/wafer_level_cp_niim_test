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



class qsi_summarize_001():
    name = 'qsi_summarize_001'

    def __init__(self):
        hard_bin = 1

       
    def run(test_data,test_conditions,continue_test, hard_bin, failure_mode_bin,t_diff):

        
        
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
        i=0
        for key, value in test_conditions.items():
            fmb = str(9500+i)

            parameter_value = value
            parameter_name = key
            
            #append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_mode_bin,setting,test_duration,test_no,test_fmb)
            test_data = qsi.append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_mode_bin,setting,0,fmb,fmb,trd)    
            i=i+1
        
        
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################         
        fmb = '10000' #summarize test

        parameter_value = -1
        parameter_name = 'FT_summary'
        
        #append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_mode_bin,setting,test_duration,test_no,test_fmb)
        test_data = qsi.append_test_settings(test_data,parameter_name,parameter_value,hard_bin,failure_mode_bin,setting,t_diff,fmb,fmb,trd) 

        

            
       
       
       
       
        
        return test_data, continue_test, hard_bin, failure_mode_bin
         
        
       

