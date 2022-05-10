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
import re

import qsi_cfg as cfg
sys.path.append(cfg.UTILITY_FILE_PATH)
sys.path.append(cfg.MODULE_FILE_PATH)
import qsi_helpers as qsi
import nickel_efuse_lib as nickel_efuse
#import char_util as char
import qsi_NickelB_illum_tests_rev0






     
class qsi_init_001():
    name = 'qsi_init_001'

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
        


        ##########################################################
        #turn laser attenuation to max to put device in the dark
        ##########################################################
        if cfg.LASER_PRESENT:
            percentage_atten=test_conditions['dark_atten']
            qsi.set_mll_atten(percentage_atten) #percentage_atten 0 to 1.0
        
        
        
        
        ##########################################################
        #set blanking rows and PGA gain register
        ##########################################################
        qsi.set_gain_register(test_conditions['pga_gain_register'])  # 1 corresponds to 2X gain
        qsi.set_tint(test_conditions['tint_seq'])
        qsi.set_temperature(test_conditions['temperature_setpt'])
        
        ##########################################################
        #move MCLK to 0
        ##########################################################
        qsi.set_mclk_offset(0)

         
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################        
        fmb = '5' #write config 'failure mode bin'
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                parameter_out = qsi.set_config(cfg.CURRENT_CONFIG_PATH)
                #todo: seriously.  fix this.  and check youri todos.  cleanup, read b0/b1 static from config and set on STS here, close loop
                # for mclk sweep testing?  why seet static for mclk sweep?
                # qsi_NickelB_illum_tests_rev0._flask_set_b0_static_request(2.5)
                # qsi_NickelB_illum_tests_rev0._flask_set_b1_static_request(0.95)
                # for FT testing
                qsi_NickelB_illum_tests_rev0._flask_set_b0_static_request(0.0)
                qsi_NickelB_illum_tests_rev0._flask_set_b1_static_request(2.3) # (3.0)
                time.sleep(1)  #wait for the system voltages to stabilize
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
        fmb = '6' #sensor id
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                parameter_out = qsi.get_sensor_ID()  
                print('sensor ID = '+str(parameter_out))
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
        # Wait for voltages to settle
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################        
        print('waiting for '+str(test_conditions['Voltage_measure_wait_sec'])+' seconds for the voltages to settle')
        time.sleep(test_conditions['Voltage_measure_wait_sec'])
        
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        ############################################################################################################################################################# 
        # check voltages and currents after getting system running   
        #############################################################################################################################################################          
        ############################################################################################################################################################# 
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################   

        for i in range(10,44):  #power supply voltages
            # check out chewie before test result
            # if i==10:
            #     qsi.dis()
            #     input('check chewie, any key to continue ')
            #     qsi.con()
            fmb = str(i)
            t0 = time.time()
            t = trd[trd['failure_mode_bin']==fmb]
            t = t.reset_index().to_dict()

            if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                    try:
                        parameter_out = float(qsi.m_get(str(t['parameter_name'][0]),"V"))
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

        for i in range(60,81):  #power supply currents
        
            fmb = str(i)
            t0 = time.time()
            t = trd[trd['failure_mode_bin']==fmb]
            t = t.reset_index().to_dict()

            if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                    try:
                        parameter_out = float(qsi.m_get(str(t['parameter_name'][0][0:-2]),"I"))
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
        # Set VSUB = -3.0V, wait 15sec, then measure VSUB and VSUB_I
        
        #check if the lot and wafer is listed in photonics data to have VOD
        #check if the lot and wafer is listed in photonics data, check to make sure the lot/wafer are valid
        do_long_time_VOD = False
        df = pd.read_csv(cfg.UTILITY_FILE_PATH + cfg.PHOTONICS_FILE, low_memory=False).astype('str')
        try:
            if cfg.b_skip_photonics == True:
                self.photonics_data = df.iloc[-1:]
            else:
                self.photonics_data = df.loc[(df['lot'] == self.Lot.get()) & (df['wafer'] == str(int(self.Wafer.get())))]            # photonics_data = df.loc[(df['lot'] == setting['Lot']) & (df['wafer'] ==str(int(setting['Wafer'])) )]
            #VOD = self.photonics_data.values.tolist()[0][photonics_data.columns.get_loc("VOD")]
            #VOD = self.photonics_data.VOD.values[0]
            if (self.photonics_data.VOD == 'yes').any():
                do_long_time_VOD = True
            else:
                print('This wafer does not have VOD, not performing long wait VSUB current test')
        except:
            print('could not determine whether this wafer has VOD, skipping VSUB long time leakage test')
            
        

        if do_long_time_VOD:
            fmb = '81' #VSUB voltage after waiting
            t0 = time.time()
            t = trd[trd['failure_mode_bin']==fmb]
            t = t.reset_index().to_dict()

            if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done

                    #get original VSUB set voltage
                    orig_VSUB = qsi.get_chip_set_voltage('VSUB')
                    print('original VSUB setting = '+str(orig_VSUB))
                    print('original VSUB voltage = '+qsi.m_get("VSUB","V"))
                    print('original VSUB current = '+qsi.m_get(str(t['parameter_name'][0][0:-2]),"I"))
                    
                    #set VSUB to 0.0V as system may need this per testing
                    #qsi.set_chip_voltage('VSUB',0.0)
                    #time.sleep(1)
                    #print('new VSUB setting = '+str(0.0))
                    #print('VSUB voltage = '+qsi.m_get("VSUB","V"))
                    #print('VSUB current = '+qsi.m_get(str(t['parameter_name'][0][0:-2]),"I"))
                    
                    #set VSUB to -3.0V or whatever
                    qsi.set_chip_voltage('VSUB',test_conditions['VSUB_wait_volts'])
                    print('new VSUB setting = '+str(test_conditions['VSUB_wait_volts']))
                    #print('VSUB voltage immediately after setting = '+qsi.m_get("VSUB","V"))
                    #print('VSUB current immediately after setting = '+qsi.m_get(str(t['parameter_name'][0][0:-2]),"I"))
                    
                    
                    print('waiting ' + str(test_conditions['VSUB_wait_sec']) + ' seconds')
                    
                    time.sleep(test_conditions['VSUB_wait_sec'])
                    parameter_out = float(qsi.m_get("VSUB","V"))

                    print('new VSUB voltage after waiting = '+str(parameter_out))

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
            fmb = '82' #VSUB current after waiting
            t0 = time.time()
            t = trd[trd['failure_mode_bin']==fmb]
            t = t.reset_index().to_dict()

            if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
              

                    parameter_out = float(qsi.m_get("VSUB","I"))
                    print('new VSUB current after waiting = '+str(parameter_out))
                    
                    #set VSUB to origninal setting in configuration file
                    qsi.set_chip_voltage('VSUB',orig_VSUB)

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
            fmb = '88'  # write efuse new API
            t0 = time.time()
            t = trd[trd['failure_mode_bin'] == fmb]
            t = t.reset_index().to_dict()
            d_efuse_write = {}
            if len(t['failure_mode_bin']) > 0:  # is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]):  # the test is in the TRD file and is done
                    # construct d_efuse_write to be written
                    ret = re.search('X(?P<x>-?\d)Y(?P<y>-?\d)', str(setting['Chip_position']))
                    x,y = (int(ret.groupdict()['x']), int(ret.groupdict()['y']))
                    if cfg.b_half_wafer:
                        print('apply half wafer x,y mapping of wfrX = proberX -1 and wfrY = -proberY - 3)')
                        x = x-1
                        y = -y-3
                    d_efuse_write = {'lot': str(setting['Lot']), 'wafer':int(setting['Wafer']),
                                        'die_num':xy_to_die_num(x,y), 'used_counter':0}
                    # read efuse
                    d_efuse_read = qsi.efuse_read_dict()
                    print(f"existing efuse {d_efuse_read}")
                    if d_efuse_write != d_efuse_read:
                        qsi.efuse_write_dict(d_efuse_write) # (C api will take care of field mods)
                        print(f"write new efuse {d_efuse_write}")
                    # readback and confirm
                    d_efuse_read = qsi.efuse_read_dict()
                    if  d_efuse_write == d_efuse_read:
                        parameter_out = True
                        print(f" efuse successfully written and read back\n {d_efuse_read}")
                    else:
                        parameter_out = False
                        print(f" efuse write/readback failed, \n write {d_efuse_write} \n read {d_efuse_read}")
            else:  # the test is in the TRD file but is not done so just add a line
                parameter_out = -1

            # assess the test results based on TRD file limits etc.
            t1 = time.time()
            test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data, t, setting, fmb, parameter_out,
                                                                                   hard_bin, failure_mode_bin, continue_test,
                                                                                   t1 - t0)
            if not continue_test:
                if qsi.is_yes(t['retest_on_fail']):
                    retest_device = True
                return test_data, continue_test, hard_bin, failure_mode_bin, retest_device  # testng is over for this chip

            #############################################################################################################################################################
            #############################################################################################################################################################
            #############################################################################################################################################################
            fmb = '89'  # read efuse new API
            t0 = time.time()
            t = trd[trd['failure_mode_bin'] == fmb]
            t = t.reset_index().to_dict()

            if len(t['failure_mode_bin']) > 0:  # is this test in the TRD file?
                if qsi.is_yes(t['test_performed'][0]):  # the test is in the TRD file and is done
                    # readback and confirm
                    if d_efuse_write == {}:
                        # construct d_efuse_write to be written
                        ret = re.search('X(?P<x>-?\d)Y(?P<y>-?\d)', str(setting['Chip_position']))
                        x, y = (int(ret.groupdict()['x']), int(ret.groupdict()['y']))
                        if cfg.b_half_wafer:
                            print('apply half wafer x,y mapping of wfrX = proberX -1 and wfrY = -proberY - 3)')
                            x = x - 1
                            y = -y - 3
                        d_efuse_write = {'lot': str(setting['Lot']), 'wafer':int(setting['Wafer']),
                                            'die_num':xy_to_die_num(x,y), 'used_counter':0}
                    d_efuse_read = qsi.efuse_read_dict()
                    if d_efuse_write == d_efuse_read:
                        parameter_out = True
                        print(f" efuse sucessfully read and matches prober info\n {d_efuse_read}")
                    else:
                        parameter_out = False
                        print(f" efuse read failed, or failed to match prober info \n write {d_efuse_write} \n read {d_efuse_read}")
            else:  # the test is in the TRD file but is not done so just add a line
                parameter_out = -1

            # assess the test results based on TRD file limits etc.
            t1 = time.time()
            test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data, t, setting, fmb,
                                                                                   parameter_out,
                                                                                   hard_bin, failure_mode_bin,
                                                                                   continue_test,
                                                                                   t1 - t0)
            if not continue_test:
                if qsi.is_yes(t['retest_on_fail']):
                    retest_device = True
                return test_data, continue_test, hard_bin, failure_mode_bin, retest_device  # testng is over for this chip

        fmb = '90' #write efuse
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                if int(setting['Write_Efuse'])==0 or int(setting['Force_Efuse_Write'])==1:  #  Write_Efuse==0 means no previous write at wafer probe
                    old_efuse_text,bytes,last,lot,wafer,chip = qsi.read_efuse()

                    if last==0 or int(setting['Force_Efuse_Write'])==1:  #only write the efuse if nothing is there or there is a forced write for error correction
                        #length of string to be written
                        if last == 0:  # just write the full lot-wfr-chip string:
                            efuse_text = ':L' + str(setting['Lot']) + ':W' + str(setting['Wafer']) + ':C' + str(setting['Chip_position'])
                            qsi.write_efuse(efuse_text)
                        else:  #correction needed....find out what current lot-wfr-chip in efuse is, compare to values in setting dict and only change those that are different
                            
                            
                            #see if old lot/wafer/chip is different from those in setting dict
                            efuse_text = ''
                            if str(lot)!=str(setting['Lot']):
                                efuse_text = ':L'+str(setting['Lot'])

                            if str(wafer)!=str(setting['Wafer']):
                                efuse_text = efuse_text + ':W'+str(setting['Wafer'])
                                
                            if str(chip)!=str(setting['Chip_position']):
                                efuse_text = efuse_text + ':C'+str(setting['Chip_position'])
                            
                            if efuse_text != '':
                                qsi.write_efuse(efuse_text)
                                
                       
                        
                        #now see if data was written correctly
                        new_efuse_text,bytes,last,lot,wafer,chip = qsi.read_efuse()
                        if len(new_efuse_text) == len(old_efuse_text):
                            if new_efuse_text == efuse_text:
                                parameter_out = True
                            else:
                                parameter_out = False
                        else:
                            l = len(efuse_text)
                            if l>0:
                                if str(new_efuse_text[-l:]) == efuse_text:
                                    parameter_out = True
                                else:
                                    parameter_out = False
                            else: #nothing new written so just pass it along
                                parameter_out = True
                        
             
                    else:
                        parameter_out = True  #if efuse is not written then just pass the test
                    
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
        fmb = '91' #read efuse
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                #try:
                if 1:
                    efuse_text,bytes,last_byte,lot,wafer,chip = qsi.read_efuse()
                    setting['Efuse_Value']=efuse_text
                    parameter_out = True  #if efuse is not written then just pass the test
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
            return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip
            
        
        #############################################################################################################################################################    
        #############################################################################################################################################################          
        #############################################################################################################################################################         
        fmb = '121' #sensor temperature1
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                parameter_out, dud = qsi.get_chip_temperatures()
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
        fmb = '122' #sensor temperature1
        t0 = time.time()
        t = trd[trd['failure_mode_bin']==fmb]
        t = t.reset_index().to_dict()

        if len(t['failure_mode_bin'])>0: #is this test in the TRD file?
            if qsi.is_yes(t['test_performed'][0]): #the test is in the TRD file and is done
                dud, parameter_out = qsi.get_chip_temperatures()
            else: #the test is in the TRD file but is not done so just add a line
                parameter_out = -1
        
        #assess the test results based on TRD file limits etc.
        t1 = time.time()
        test_data, continue_test, hard_bin, failure_mode_bin = qsi.assess_test(test_data,t,setting,fmb,parameter_out,hard_bin,failure_mode_bin,continue_test,t1-t0)         
        if not continue_test:
            if qsi.is_yes(t['retest_on_fail']):
                    retest_device = True
            return test_data, continue_test, hard_bin, failure_mode_bin,retest_device #testng is over for this chip    
            
            
        
        #save setting values in qsi_prod_setup.csv file (save efuse value for later)
        df = pd.DataFrame.from_dict(setting, orient="index")
        df = df.reset_index()
        df.columns = ['condition','value']
        df.to_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")


        return test_data, continue_test, hard_bin, failure_mode_bin,retest_device

# setup wafermap to die_num mapping
# given row num, lookup info on left most die (col num, die_num)
if cfg.chip_type == 'NickelD':
    d_left_die_nickel ={-6:(-1,1),
                  -5:(-2,5),
                  -4:(-3,11),
                  -3:(-3,19),
                  -2:(-4,28),
                  -1:(-4,38),
                   0:(-4,48),
                   1:(-4,58),
                   2:(-3,68),
                   3:(-3,77),
                   4:(-2,85),
                   5:(-1,91),
                          }
elif cfg.chip_type == 'NickelG':
    # d_left_die_nickel = {
    #
    d_left_die_nickel = {
                  -6:(-1,1),
                  -5:(-3,4),
                  -4:(-4,11),
                  -3:(-5,20),
                  -2:(-5,31),
                  -1:(-5,42),
                   0:(-5,53),
                   1:(-5,64),
                   2:(-5,75),
                   3:(-4,86),
                   4:(-3,95),
                   5:(-1,102),
                  }
    #               -6:(-1,1,1),
    #               -5:(-3,3,4),
    #               -4:(-4,4,11),
    #               -3:(-5,5,20),
    #               -2:(-5,5,31),
    #               -1:(-5,5,42),
    #                0:(-5,5,53),
    #                1:(-5,5,64),
    #                2:(-5,5,75),
    #                3:(-4,4,86),
    #                4:(-3,3,95),
    #                5:(-1,1,102),
    #               }
def xy_to_die_num(x,y):
    ldie_col, ldie_num = d_left_die_nickel[y]
    return ldie_num+(x-ldie_col)