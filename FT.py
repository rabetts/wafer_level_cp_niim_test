#Tom Thurston Quatum-Si inc. 2020
#API calls that run the vast majority of individual tests written by Dan Frier, Anthony Bellofiore, Mel Davey, Shannon Stewman + others?
#Large parts of this program use the structure/ideas of a python test program written by Andrew Betts
#Nickel python code based on characterization code written by Zhaoyu He

import json
import os
import time
import sys
import traceback
import tkinter as tk
import tkinter.font as font
import numpy as np
import pandas as pd
from tkinter import filedialog
from tkinter import ttk
from tkinter import messagebox
from tkinter import simpledialog
from collections import OrderedDict
import datetime as dt
import shutil
import matplotlib.pyplot as plt
from tkinter import Tk, Text, Scrollbar
from PIL import Image, ImageTk, ImageEnhance
# imports to support CP
import requests
import re

import qsi_cfg as cfg

sys.path.append(cfg.UTILITY_FILE_PATH)
sys.path.append(cfg.TRD_FILE_PATH)
sys.path.append(cfg.PROGRAM_FILE_PATH)

#########################################################
#########################################################
#########################################################
import qsi_ft_TESTS_NickelB_rev0 as qsi_tests
#########################################################
#########################################################
#########################################################

import qsi_helpers as qsi
import nickel_efuse_lib as nickel_efuse


class FinalTest(object):
	def __init__(self):
	
		
				

		self.root = tk.Tk()
		self.root.title("Final Test - Quantum-Si, Inc.")
		# define font
		myFont = font.Font(family='Helvetica', size=cfg.STANDARD_FONT, weight='bold')
		self.root.option_add("*Font", myFont)

		# flag for wafer level CP run control
		self.b_cp = False

		#connect the NIckel machine
		ret = qsi.char_initialize()
		if not ret:
			print('machine not initialized')
			print('please exit ipython and try again')
			sys.exit()
		

		# a counter for how many times the 'start' button is pushed in this session
		self.num_iteration = 0
		
		
		qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds
		self.root.withdraw()
		
		if cfg.LASER_PRESENT: #only check laser status if there is one!
			if qsi.get_laser_status() != 2: #laser is not on
				#self.root.withdraw()
				start_laser = simpledialog.askstring(title = 'Laser Start' , prompt =  "Laser not on!!	Start? yes or no", initialvalue='yes', parent=self.root)
				if start_laser == 'yes':
					start_laser = simpledialog.askstring(title = 'Laser Start' , prompt =  "Is a chip in the socket and the lid closed?", initialvalue='yes', parent=self.root)
					if start_laser == 'yes':
						print('\n\nTurning on Laser and TEC')
						qsi.set_laser_tec("pump_on_tec_on")
						time.sleep(3)
						power = qsi.get_laser_power()
						print('laser power = '+str(round(power,1))+'mW')
					start_aln = simpledialog.askstring(title = 'Laser Alignment?' , prompt =  "Would you like to align the laser?", initialvalue='yes', parent=self.root)
					if start_aln == 'yes':
						print('\n\nAligning laser, this should take ~10-20 seconds')
						qsi.align_mll()
						
					
				#disable gets removed on cold start
				qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds	 
				
		if not self.b_cp:
			print('setting laser power to '+str(cfg.align_measurement_power)+'mW to calibrate for illuminated scans')
			cfg.atten_alignment = qsi.set_mll_power_get_atten(cfg.align_measurement_power)

			#put laser power back to 0mW for dark tests
			qsi.set_motor(qsi.lib.MOTOR_ATTENUATOR, cfg.atten_0mW)
			print('laser power calibrated')

		self.root.update()
		self.root.deiconify()

		#load up current lot/wfr/part/data_file settings
		try:
			dd = pd.read_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
			self.prod_setup = dict(zip(dd['condition'].to_list(),dd['value'].to_list()))
		except:
			self.prod_setup = OrderedDict()
			self.prod_setup['Lot'] = 'XXXXXX'
			self.prod_setup['Wafer'] = 'XX'
			self.prod_setup['Chip_position'] = 'XXX'
			self.prod_setup['Data_file'] = 'LXXXXX_WXX_2020_03_26.csv'
			self.prod_setup['Date_stamp']='2020-05-05 12:27:46'
			self.prod_setup['Product_number'] = 0

		
		#initialize a matplotlib plot since it interacts with TKinter stuff
		fig2 = plt.figure(figsize=(12,6))
		fig2.canvas.set_window_title('FT')
		axes1=fig2.add_subplot(111)
		axes1.scatter([0,1,1], [2,3,4],c='r',marker='o')
		plt.grid(b=True, which='major', color='b', linestyle='-')
		plt.tight_layout()
		plt.close 
		
		#set machine time for alarms code
		qsi.set_device_tod()


		#add to prod_setup parameters values found in qsi_current.csv
		#these are parameters that can be changed by the operator or engineer
		row = 0
		tk.Label(self.root, text = 'Lot').grid(row=row, column=0, sticky='W', padx=30)
		self.Lot = tk.Entry(self.root, width = 40)
		self.Lot.grid(row=row, column=1, sticky='W')
		self.Lot.insert(20, self.prod_setup['Lot'])
		self.Lot.config(state='normal')
		
		row += 1
		tk.Label(self.root, text = 'Wafer').grid(row=row, column=0, sticky='W', padx=30)
		self.Wafer = tk.Entry(self.root, width = 40)
		self.Wafer.grid(row=row, column=1, sticky='W')
		self.Wafer.insert(20, self.prod_setup['Wafer'])
		self.Wafer.config(state='normal')

		row += 1
		tk.Label(self.root, text = 'Chip_position').grid(row=row, column=0, sticky='W', padx=30)
		self.Chip_position = tk.Entry(self.root, width = 40)
		self.Chip_position.grid(row=row, column=1, sticky='W')
		self.Chip_position.insert(20, self.prod_setup['Chip_position'])
		self.Chip_position.config(state='readonly')


		row +=1
		tk.Label(self.root, text = 'PRODUCTION_TESTER').grid(row=row, column=0, sticky='W', padx=30)
		self.PRODUCTION_TESTER = tk.Entry(self.root, width = 40)
		self.PRODUCTION_TESTER.grid(row=row, column=1, sticky='W')
		self.PRODUCTION_TESTER.insert(20, cfg.PRODUCTION_TESTER)
		self.PRODUCTION_TESTER.config(state='readonly')

		row +=1
		#combo box for selecting product
		tk.Label(self.root, text = 'PRODUCT:').grid(row=row, column=0, sticky='W', padx=30)
		self.Product = ttk.Combobox(self.root, values = cfg.PRODUCTS, width=38)
		self.Product.grid(row = row , column=1, sticky='W')
		self.Product.current(self.prod_setup['Product_number'])
		

		row +=1
		tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')  
		row +=1		   
		tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')


		row +=1 
		tk.Label(self.root, text = 'Press start button after chip is inserted into clamp').grid(row=row , column=0, sticky='W', padx=30)

		# The big start button
		row += 1
		self.start_button = tk.Button(self.root, text='Start', state='disabled', command=self.run_test, width=32)
		self.start_button.grid(row=row, column=0, sticky='W', padx=30)
		self.start_button['state'] = 'normal'

		# The big CP start button.  flask control loop with STS and get ocr lot/wfr/x/y from prober
		row += 1
		self.start_button = tk.Button(self.root, text='Start_CP', state='disabled', command=self.run_cp_test, width=32)
		self.start_button.grid(row=row, column=0, sticky='W', padx=30)
		self.start_button['state'] = 'normal'

		#Save current state button
		self.save_current_button = tk.Button(self.root, text='Save current state', state='disabled', command = self.save_current_state, width=32)
		self.save_current_button.grid(row = row , column=1, sticky='W', padx=30)
		self.save_current_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.save_current_button.grid_forget()
		
		row +=1		   
		tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')
		row +=1
		if not cfg.HIDE_CONTROLS:
			tk.Label(self.root, text = 'Assembly Failures?').grid(row=row , column=1, sticky='W', padx=30)

		row +=1
		self.delete_last_button = tk.Button(self.root, text='Delete Last Record', state='disabled', command = self.delete_last, width=32)
		self.delete_last_button.grid(row = row , column=0, sticky='W', padx=30)
		self.delete_last_button['state'] = 'normal'

			
		#combo box for adding assembly fails
		self.Assembly_failure = ttk.Combobox(self.root, values = ["No","Yes"], width=34)
		self.Assembly_failure.grid(row = row , column=1, sticky='W', padx=30)
		self.Assembly_failure.current(0)
		if cfg.HIDE_CONTROLS:
			self.Assembly_failure.grid_forget()
			  
		
		
		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')
			row +=1
			tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')
			row +=1
			tk.Label(self.root, text = 'TRD_FILE').grid(row=row, column=0, sticky='W', padx=30)
		self.TRD_FILE = tk.Entry(self.root, width = 40)
		self.TRD_FILE.grid(row=row, column=1, sticky='W')
		self.TRD_FILE.insert(20, cfg.TRD_FILES[int(self.prod_setup['Product_number'])])
		self.TRD_FILE.config(state='readonly')
		if cfg.HIDE_CONTROLS:
			self.TRD_FILE.grid_forget()
		

		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = 'PROGRAM_FILE').grid(row=row, column=0, sticky='W', padx=30)
		self.PROGRAM_FILE = tk.Entry(self.root, width = 40)
		self.PROGRAM_FILE.grid(row=row, column=1, sticky='W')
		self.PROGRAM_FILE.insert(20, cfg.PROGRAM_FILE)
		self.PROGRAM_FILE.config(state='readonly')
		if cfg.HIDE_CONTROLS:
			self.PROGRAM_FILE.grid_forget()

		#combo box for selecting engineering or production mode
		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = 'ENGINEERING MODE?').grid(row=row, column=0, sticky='W', padx=30)
		self.ENGINEERING = ttk.Combobox(self.root, values = ["No","Yes"], width=38)
		self.ENGINEERING.grid(row = row , column=1, sticky='W')
		self.ENGINEERING.current(int(self.prod_setup['Engineering_Mode']))
		if cfg.HIDE_CONTROLS:
			self.ENGINEERING.grid_forget()
		
		if not cfg.HIDE_CONTROLS:
			row +=1 #Prober has written Efuse?
			tk.Label(self.root, text = 'READ EFUSE (from prober)?').grid(row=row, column=0, sticky='W', padx=30)
		self.PROBER_EFUSE = ttk.Combobox(self.root, values = ["No","Yes"], width=38)
		self.PROBER_EFUSE.grid(row = row , column=1, sticky='W')
		self.PROBER_EFUSE.current(int(self.prod_setup['Write_Efuse']))	#Write_Efuse == 0 means the efuse has not been written at wafer probe
		if cfg.HIDE_CONTROLS:
			self.PROBER_EFUSE.grid_forget()
			
		if not cfg.HIDE_CONTROLS:
			row +=1 #force efuse write at FT? Normally if the Efuse has been written the code will not write it again (allows fast retest w/o clogging efuse)
			tk.Label(self.root, text = 'FORCE EFUSE WRITE?').grid(row=row, column=0, sticky='W', padx=30)
		self.FORCE_EFUSE_WRITE = ttk.Combobox(self.root, values = ["No","Yes"], width=38)
		self.FORCE_EFUSE_WRITE.grid(row = row , column=1, sticky='W')
		self.FORCE_EFUSE_WRITE.current(int(self.prod_setup['Force_Efuse_Write']))
		if cfg.HIDE_CONTROLS:
			self.FORCE_EFUSE_WRITE.grid_forget()
			
		#combo box for selecting process step
		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = 'PROCESS STEP:').grid(row=row, column=0, sticky='W', padx=30)
		self.Process_step = ttk.Combobox(self.root, values = cfg.PROCESS_STEPS, width=38)
		self.Process_step.grid(row = row , column=1, sticky='W')
		self.Process_step.current(self.prod_setup['Process_step'])
		if cfg.HIDE_CONTROLS:
			self.Process_step.grid_forget()
			
		#combo box for auto or current file
		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = 'FILE_MODE:').grid(row=row, column=0, sticky='W', padx=30)
		self.FILE_MODE = ttk.Combobox(self.root, values = ['auto','manual'], width=38)
		self.FILE_MODE.grid(row = row , column=1, sticky='W')
		self.FILE_MODE.current(0)
		if cfg.HIDE_CONTROLS:
			self.FILE_MODE.grid_forget()

		#engineering data file name
		if not cfg.HIDE_CONTROLS:
			row += 1
			tk.Label(self.root, text = 'ENGINEERING DATA FILE').grid(row=row, column=0, sticky='W', padx=30)
		self.Data_file = tk.Entry(self.root, width = 40)
		self.Data_file.grid(row=row, column=1, sticky='W')
		self.Data_file.insert(20, self.prod_setup['Data_file_eng'])
		self.Data_file.config(state='normal')
		if cfg.HIDE_CONTROLS:
			self.Data_file.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = 'TIMESTAMP').grid(row=row, column=0, sticky='W', padx=30)
		self.record_timestamp = tk.Entry(self.root, width = 40)
		self.record_timestamp.grid(row=row, column=1, sticky='W')
		self.record_timestamp.insert(20, self.prod_setup['Date_stamp'])
		self.record_timestamp.config(state='normal')
		if cfg.HIDE_CONTROLS:
			self.record_timestamp.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1
			tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')
			row +=1
			tk.Label(self.root, text = '	').grid(row = row , column=3, sticky='E')  
			row +=1 
		self.show_records_button = tk.Button(self.root, text='Show Record Summary', state='disabled', command = self.show_records, width=32)
		self.show_records_button.grid(row = row , column=0, sticky='W', padx=30)
		self.show_records_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.show_records_button.grid_forget()

		self.calc_yield_button = tk.Button(self.root, text='Calculate Current Yield', state='disabled', command = self.calc_yield, width=32)
		self.calc_yield_button.grid(row = row , column=1, sticky='W', padx=30)
		self.calc_yield_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.calc_yield_button.grid_forget()
			
			

		if not cfg.HIDE_CONTROLS:
			row +=1 
		
		self.show_selected_parameter_button = tk.Button(self.root, text='Show parameter', state='disabled', command = self.show_selected_parameter, width=32)
		self.show_selected_parameter_button.grid(row = row , column=0, sticky='W', padx=30)
		self.show_selected_parameter_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.show_selected_parameter_button.grid_forget()
			
		self.selected_parameter = ttk.Combobox(self.root, values = cfg.SELECTED_PARAMETERS, width=38)
		self.selected_parameter.grid(row = row , column=1, sticky='W')
		self.selected_parameter.current(0)
		if cfg.HIDE_CONTROLS:
			self.selected_parameter.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1 
		self.change_lot_wfr_part_selected_button = tk.Button(self.root, text='Change Lot/Wfr/Part by TIMESTAMP', state='disabled', command = self.change_selected, width=32)
		self.change_lot_wfr_part_selected_button.grid(row = row , column=0, sticky='W', padx=30)
		self.change_lot_wfr_part_selected_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.change_lot_wfr_part_selected_button.grid_forget()

		self.show_records_by_TIMESTAMP = tk.Button(self.root, text='Show Records with chosen TIMESTAMP', state='disabled', command = self.show_records_timestamp, width=32)
		self.show_records_by_TIMESTAMP.grid(row = row , column=1, sticky='W', padx=30)
		self.show_records_by_TIMESTAMP['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.show_records_by_TIMESTAMP.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1 
		self.show_image_button = tk.Button(self.root, text='Show image by TIMESTAMP', state='disabled', command = self.show_image, width=32)
		self.show_image_button.grid(row = row , column=0, sticky='W', padx=30)
		self.show_image_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.show_image_button.grid_forget()

		#combo box for type of image
		self.Image_type = ttk.Combobox(self.root, values = cfg.IMAGE_TYPES, width=34)
		self.Image_type.grid(row = row , column=1, sticky='W', padx=30)
		self.Image_type.current(0)
		if cfg.HIDE_CONTROLS:
			self.Image_type.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1 
		self.change_all_lot_wfr_button = tk.Button(self.root, text='Change Lot/Wafer of all Records', state='disabled', command = self.change_all, width=32)
		self.change_all_lot_wfr_button.grid(row = row , column=0, sticky='W', padx=30)
		self.change_all_lot_wfr_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.change_all_lot_wfr_button.grid_forget()

		self.change_data_file_button = tk.Button(self.root, text='Change Datafile (manual)', state='disabled', command = self.change_data_file, width=32)
		self.change_data_file_button.grid(row = row , column=1, sticky='W', padx=30)
		self.change_data_file_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.change_data_file_button.grid_forget()
		
		if not cfg.HIDE_CONTROLS:
			row +=1	  
		self.write_efuse_button = tk.Button(self.root, text='Write Efuse', state='disabled', command = self.write_efuse, width=32)
		self.write_efuse_button.grid(row = row , column=0, sticky='W', padx=30)
		self.write_efuse_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.write_efuse_button.grid_forget()

		#efuse write data
		self.efuse_write_data = tk.Entry(self.root, width = 40)
		self.efuse_write_data.grid(row=row, column=1, sticky='W')
		self.efuse_write_data.insert(20, ":LS42787:W12:C74")
		self.efuse_write_data.config(state='normal')
		if cfg.HIDE_CONTROLS:
			self.efuse_write_data.grid_forget()

		if not cfg.HIDE_CONTROLS:
			row +=1
		self.read_efuse_button = tk.Button(self.root, text='Read Efuse', state='disabled', command = self.read_efuse, width=32)
		self.read_efuse_button.grid(row = row , column=0, sticky='W', padx=30)
		self.read_efuse_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.read_efuse_button.grid_forget()
		
		self.display_alarms_button = tk.Button(self.root, text='Display Alarms', state='disabled', command = self.display_alarms, width=32)
		self.display_alarms_button.grid(row = row , column=1, sticky='W', padx=30)
		self.display_alarms_button['state'] = 'normal'
		if cfg.HIDE_CONTROLS:
			self.display_alarms_button.grid_forget()

		if cfg.LASER_PRESENT:
		
			row +=1	  
			self.laser_on_button = tk.Button(self.root, text='Laser On', state='disabled', command = self.laser_on, width=32)
			self.laser_on_button.grid(row = row , column=0, sticky='W', padx=30)
			self.laser_on_button['state'] = 'normal'
			if cfg.HIDE_CONTROLS:
				self.laser_on_button.grid_forget()
			
			self.laser_off_button = tk.Button(self.root, text='Laser Off', state='disabled', command = self.laser_off, width=32)
			self.laser_off_button.grid(row = row , column=1, sticky='W', padx=30)
			self.laser_off_button['state'] = 'normal'
			if cfg.HIDE_CONTROLS:
				self.laser_off_button.grid_forget()
			
			row +=1 
			self.align_laser_button = tk.Button(self.root, text='Align Laser', state='disabled', command = self.align_laser, width=32)
			self.align_laser_button.grid(row = row , column=0, sticky='W', padx=30)
			self.align_laser_button['state'] = 'normal'
			if cfg.HIDE_CONTROLS:
				self.align_laser_button.grid_forget()
			
			self.delete_selected_button = tk.Button(self.root, text='Delete Record by TIMESTAMP', state='disabled', command = self.delete_selected, width=32)
			self.delete_selected_button.grid(row = row , column=1, sticky='W', padx=30)
			self.delete_selected_button['state'] = 'normal'
			if cfg.HIDE_CONTROLS:
				self.delete_selected_button.grid_forget()
		
		else:
			row +=1
			self.delete_selected_button = tk.Button(self.root, text='Delete Record by TIMESTAMP', state='disabled', command = self.delete_selected, width=32)
			self.delete_selected_button.grid(row = row , column=0, sticky='W', padx=30)
			self.delete_selected_button['state'] = 'normal'
			if cfg.HIDE_CONTROLS:
				self.delete_selected_button.grid_forget()
				
		row +=1
		row +=1 
		tk.Label(self.root, text = '	').grid(row = row, column=3, sticky='E')

		if self.ENGINEERING.current()==0:
			import warnings
			warnings.filterwarnings("ignore")  
	 

	def save_current_state(self):
		#save prod_setup values in qsi_prod_setup.csv file (for passing data to modules)
		
		#text boxes
		self.prod_setup['Lot'] = self.Lot.get()
		self.prod_setup['Wafer'] = self.Wafer.get()
		self.prod_setup['Chip_position']   = self.Chip_position.get()
		self.prod_setup['Data_file_eng'] = self.Data_file.get()
		self.prod_setup['Date_stamp'] = self.record_timestamp.get()
		
		
		
		
		#combo boxes
		self.prod_setup['Process_step']= self.Process_step.current()
		self.prod_setup['Engineering_Mode'] = self.ENGINEERING.current()
		self.prod_setup['Write_Efuse'] = self.PROBER_EFUSE.current()
		self.prod_setup['Force_Efuse_Write'] = self.FORCE_EFUSE_WRITE.current()
		self.prod_setup['Product_number'] = self.Product.current()
		self.prod_setup['File_mode'] = self.FILE_MODE.current()
		
		self.TRD_FILE.config(state='normal')
		self.TRD_FILE.delete(0, 'end')
		self.TRD_FILE.insert(20, cfg.TRD_FILES[int(self.prod_setup['Product_number'])])
		self.TRD_FILE.config(state='readonly')

		#set Efuse_Value to be 0 at the beginning
		self.prod_setup['Efuse_Value'] = '0'
		
		df = pd.DataFrame.from_dict(self.prod_setup, orient="index")
		df = df.reset_index()
		df.columns = ['condition','value']
		df.to_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
		
		print('New setup successfully saved.')
		
	def read_efuse(self):

		efuse_text,bytes,last_byte,lot,wafer,chip = qsi.read_efuse()
		print()
		print('efuse = ' + efuse_text)
		print('efuse size = '+str(bytes)+' bytes')
		print('last used byte = '+str(last_byte))
		print('lot = '+lot)
		print('wafer = '+wafer)
		print('chip = '+chip)
		
	def write_efuse(self):
		efuse_text = self.efuse_write_data.get()
		qsi.write_efuse(efuse_text)
	   

	def display_alarms(self):
		#qsi.display_alarms()
		if qsi.test_for_alarms()==0:
			print('loss of lock')

	def laser_on(self):
		print('\n\nTurning on Laser and TEC')
		qsi.set_laser_tec("pump_on_tec_on")
		time.sleep(3)
		power = qsi.get_laser_power()
		print('laser power = '+str(round(power,1))+'mW')
		
		
	def laser_off(self):
		print('\n\nTurning off Laser and TEC')
		qsi.set_laser_tec("pump_off_tec_off")
		time.sleep(3)
		power = qsi.get_laser_power()
		print('laser power = '+str(round(power,1))+'mW')
		
	def align_laser(self):
		print('\n\nstarting laser alignment, this should take ~10-20 seconds')
		qsi.align_mll()
		print('setting laser power to '+str(cfg.align_measurement_power)+'mW to calibrate for illuminated scans')
		cfg.atten_alignment = qsi.set_mll_power_get_atten(cfg.align_measurement_power)	
		power = qsi.get_laser_power()
		print('laser power = '+str(round(power,1))+'mW')
		#disable gets removed on restart
		qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds 
		print('laser ready')
		
	def show_image(self):

		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, nothing to view.') 
			return
			
		#read out the selected TIMESTAMP value
		selected_timestamp = self.record_timestamp.get()
		results= results[results['TIMESTAMP']==selected_timestamp]
		res = results.sort_values(by=['test_no'],ascending=[True],inplace=False)
	   
		if res.shape[0]<1:
			print('no records with this TIMESTAMP')
			return
		
		r = results.reset_index().to_dict() 
		rr = r['Data_file_full_path'][0].split('\\')[0:-1]
		data_path ='\\'.join([str(i) for i in rr]) + '\\images\\'
		
		
		lot = r['lot'][0]
		wafer = r['wafer'][0]
		chip = r['chip'][0]
		i_type = cfg.IMAGE_TYPES[self.Image_type.current()].split(',')	 
		ff =  r['TIMESTAMP'][0].split(' ')

		fff = ff[1].split(':')
		file_name = lot + '_W' + str(wafer) + '_P' + str(chip) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
		if i_type[0]=='MCLK':
			if i_type[1]=='scan':
				file_name = file_name + '.png'
			else:
				file_name = file_name + '_' + i_type[1] + '.png'
		elif i_type[0]=='dark_current' or i_type[0]=='dark_noise':
			file_name = file_name + '_' + i_type[1] +  '.png'
		else:
			file_name = file_name + '_' + i_type[1] + '.tif'
			
		file_name = data_path + file_name
		if os.path.isfile(file_name):  #there is a file with this path
			pop_up_image = tk.Toplevel() 
	   
			try:
				load = Image.open(file_name)
				if i_type[0]=='MCLK'  or i_type[0]=='dark_current' or i_type[0]=='dark_noise':
					load = load.resize((int(2048/cfg.IMAGE_SCALE), int(1024/cfg.IMAGE_SCALE)), Image.ANTIALIAS)
				else:
					load = load.resize((int(2048/cfg.IMAGE_SCALE), int(256/cfg.IMAGE_SCALE)), Image.ANTIALIAS) ## The (250, 250) is (height, width)
				render = ImageTk.PhotoImage(load)
				img = tk.Label(pop_up_image, image=render)
				img.image = render
				img.place(x=0, y=0)

				#pop_up_image.wm_title("Tkinter window")
				if i_type[0]=='MCLK' or i_type[0]=='dark_current' or i_type[0]=='dark_noise':
					if cfg.IMAGE_SCALE == 1:
						pop_up_image.geometry("2048x1024")	
					else:
						pop_up_image.geometry("1024x512")
				else:
					if cfg.IMAGE_SCALE == 1:
						pop_up_image.geometry("2048x256")
					else:
						pop_up_image.geometry("1025x128")
				pop_up_image.mainloop()
			except:
				print('\n\nCould not open image file of this type for this TIMESTAMP.')
		else:
			print('\n\nThere is no image file')
		
	
	
	def show_records_timestamp(self):  
		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, nothing to see.') 
			return
			
		#read out the selected TIMESTAMP value
		selected_timestamp = self.record_timestamp.get()
		results= results[results['TIMESTAMP']==selected_timestamp]
		res = results.sort_values(by=['test_no'],ascending=[True],inplace=False)
		res = res.reset_index()
		
		res = res[['TIMESTAMP','lot','wafer','chip','test_no','chip_hard_bin','chip_failure_mode_bin','parameter_name','parameter_value']]
		if res.shape[0]<1:
			print('no records with this TIMESTAMP')
			return


		pd.set_option('display.max_rows', None)
		print('\n\n\n\n')
		print(res)
		

	def show_records(self):	   
		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, nothing to see.') 
			return
		
		res = results.sort_values(by=['test_time'],ascending=[True],inplace=False)
		res = res[res['trd_failure_mode_bin']==10000] #get the summary records for each test
		res = res.reset_index()
		res = res[['TIMESTAMP','lot','wafer','chip','chip_hard_bin','chip_failure_mode_bin']]
		pd.set_option('display.max_rows', None)
		print('\n\n\n\n')
		print(res)
		

	def show_selected_parameter(self):
		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, no yield to calculate.') 
			return 0, 0, 0
		
		dg = results.sort_values(by=['test_time'],ascending=[True],inplace=False)
		
		par_name = cfg.SELECTED_PARAMETERS[self.selected_parameter.current()]
		dg = dg[dg['parameter_name']==par_name] #get the parameter records
		dg = dg.reset_index()

		dh = dg[['lot','wafer','chip','test_time']]
		dh = dh.groupby(['lot','wafer','chip'],sort=True).max()
		di = dg.join(dh.set_index('test_time'),on='test_time',how='inner')


		di = di[['TIMESTAMP','lot','wafer','chip','parameter_name','parameter_value','chip_hard_bin']]
		pd.set_option('display.max_rows', None)

		print('\n\n\n\n')
		print(di)
		
		median_par = np.median(di['parameter_value'])
		max_par = np.max(di['parameter_value'])
		min_par = np.min(di['parameter_value'])
		
		print('\n\n')
		print('median '+par_name+' = '+str(round(median_par,2)))
		print('max '+par_name+' = '+str(round(max_par,2)))
		print('min '+par_name+' = '+str(round(min_par,2)))
		
	def calc_yield(self,show_info=True):	
		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, no yield to calculate.') 
			return 0, 0, 0
		
		dg = results.sort_values(by=['test_time'],ascending=[True],inplace=False)
		dg = dg[dg['trd_failure_mode_bin']==10000] #get the summary records for each test
		dg = dg.reset_index()

		dh = dg[['lot','wafer','chip','test_time']]
		dh = dh.groupby(['lot','wafer','chip'],sort=True).max()
		di = dg.join(dh.set_index('test_time'),on='test_time',how='inner')


		di = di[['TIMESTAMP','lot','wafer','chip','chip_hard_bin','chip_failure_mode_bin']]
		pd.set_option('display.max_rows', None)
		if show_info:
			print('\n\n\n\n')
			print(di)
		
		#calculate yield
		tot_tested=di.shape[0]
		dj = di[di['chip_hard_bin']==1]
		tot_passed=dj.shape[0]		 
		
		if show_info:
			print('\n')
			print('total chips tested = '+str(tot_tested))
			print('passing chips = '+str(tot_passed))
			print('yield = '+str(round(float(tot_passed)/float(tot_tested),2)))
		
		return tot_tested, tot_passed, round(float(tot_passed)/float(tot_tested),2)
		
	def delete_last(self):
		
		
		#see if there is already a csv file for this testing session		
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			print('No tester data file, nothing to delete.') 
			return


		#get TIMESTAMP of last record
		res = results.sort_values(by=['test_time','test_no'],ascending=[False,False],inplace=False)
	   
		if res.shape[0]<1:
			print('no records with this TIMESTAMP')
			return
		
		r = res.reset_index().to_dict() 
		rr = r['Data_file_full_path'][0].split('\\')[0:-1]
		data_path ='\\'.join([str(i) for i in rr]) + '\\images\\'
		
		
		lot = r['lot'][0]
		wafer = r['wafer'][0]
		chip = r['chip'][0]
		bin = r['chip_hard_bin'][0]
		last_timestamp = r['TIMESTAMP'][0]
		ff =  r['TIMESTAMP'][0].split(' ')
		fff = ff[1].split(':')
		
		do_it	= simpledialog.askstring(title = 'Delete' , prompt =  "Do you really want to delete "+str(last_timestamp)+"\nlot = "+lot+", wafer = "+str(wafer)+", chip = "+str(chip)+", bin ="+str(bin)+"?", initialvalue='yes', parent=self.root)
		if do_it is not None and do_it == 'yes':
			
			#remove all of the images associated with this TIMESTAMPs
			for i in range(len(cfg.IMAGE_TYPES)):
				i_type = cfg.IMAGE_TYPES[i].split(',')	
				file_name = lot + '_W' + str(wafer) + '_P' + str(chip) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
				if i_type[0]=='MCLK':
					file_name = file_name + '.png'
				else:
					file_name = file_name + '_' + i_type[1] + '.tif'
					
				file_name = data_path + file_name
				#print(file_name)
				if os.path.isfile(file_name):  #there is a file with this path
					os.remove(file_name)
					
		
			#remove data from results dataframe now
			results= results[results['TIMESTAMP']!=last_timestamp]
			if results.empty:
				print('\n\nOnly one record in this tester file.	 Deleting tester csv file.')
				#shutil.rmtree(self.prod_setup['Data_directory'])
				os.remove(self.prod_setup['Data_file_full_path'])
			else:
				print('\n\nRemoving last record with TIMESTAMP = '+str(last_timestamp))
				results= results[results['TIMESTAMP']!=last_timestamp]
				results.sort_values(by=['test_time','test_no'],ascending=[True,True],inplace=True)
				results.to_csv(self.prod_setup['Data_file_full_path'],index=False)
				
				#update last record box
				results.sort_values(by=['test_time','test_no'],ascending=[False,False],inplace=True)
				r = results.reset_index().to_dict()		 
				self.prod_setup['Date_stamp'] = r['TIMESTAMP'][0]
				self.record_timestamp.delete(0, 'end')
				self.record_timestamp.insert(20, self.prod_setup['Date_stamp'])
			
			#remove all images associated with this time stamp
			
			
		else:
			return



	def delete_selected(self):
		do_it	= simpledialog.askstring(title = 'Input' , prompt =	 "Do you really want to delete?", initialvalue='yes', parent=self.root)
		if do_it is not None and do_it == 'yes':
		
			#see if there is already a csv file for this testing session		
			try:
				results=pd.read_csv(self.prod_setup['Data_file_full_path'])
			except:
				print('No tester data file, nothing to delete.') 
				return
				
				
			#remove all of the images associated with this TIMESTAMPs
			res = results[results['TIMESTAMP']==self.record_timestamp.get()]
			if res.shape[0]==0:
				print('no record with this TIMESTAMP')
				return
			else:
				r = res.reset_index().to_dict() 
				rr = r['Data_file_full_path'][0].split('\\')[0:-1]
				data_path ='\\'.join([str(i) for i in rr]) + '\\images\\'
				
				
				lot = r['lot'][0]
				wafer = r['wafer'][0]
				chip = r['chip'][0]
				last_timestamp = r['TIMESTAMP'][0]
				ff =  r['TIMESTAMP'][0].split(' ')
				fff = ff[1].split(':')
				
				for i in range(len(cfg.IMAGE_TYPES)):
					i_type = cfg.IMAGE_TYPES[i].split(',')	
					file_name = lot + '_W' + str(wafer) + '_P' + str(chip) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
					if i_type[0]=='MCLK':
						file_name = file_name + '.png'
					else:
						file_name = file_name + '_' + i_type[1] + '.tif'
						
					file_name = data_path + file_name
					#print(file_name)
					if os.path.isfile(file_name):  #there is a file with this path
						os.remove(file_name)
			
			#read out the selected TIMESTAMP value
			selected_timestamp = self.record_timestamp.get()
			no_rec_1 = results.shape[0]
			results= results[results['TIMESTAMP']!=selected_timestamp]
			no_rec_2 = results.shape[0]
			
			if no_rec_1 == no_rec_2:
				print('\n\nno record with this TIMESTAMP')
				return
				
			 
			
				
			if results.empty:
				print('\n\nOnly one record in this tester file.	 Deleting tester csv file.')
				#shutil.rmtree(self.prod_setup['Data_directory'])
				os.remove(self.prod_setup['Data_file_full_path'])
			else:
				print('\n\nRemoving record with TIMESTAMP = '+str(selected_timestamp))
				results= results[results['TIMESTAMP']!=selected_timestamp]
				results.sort_values(by=['test_time','test_no'],ascending=[True,True],inplace=True)
				results.to_csv(self.prod_setup['Data_file_full_path'],index=False)
		else:
			return
			
			
			
	 
	def change_data_file(self):

		old_Data_file = self.prod_setup['Data_file']
		old_Data_directory = self.prod_setup['Data_directory']

		
		#get data file directory etc
		new_Data_file = filedialog.askopenfilename(title="Choose file",initialdir = old_Data_directory,defaultextension='csv')
	   

		new_parts = new_Data_file.split('/')
		if new_parts[-1][-3:] != 'csv':
			print('please select a csv file')
			return
			

		self.prod_setup['Data_file'] = new_parts[-1][0:-4]
		self.prod_setup['Data_file_full_path'] = str("\\".join([str(i) for i in new_parts]))
		self.prod_setup['Data_directory'] = str("\\".join([str(i) for i in new_parts[0:-1]]))+"\\"
		self.prod_setup['Data_summary_file_full_path'] = self.prod_setup['Data_file_full_path'][0:-4] + '_summary.csv'
		
		#print(self.prod_setup['Data_file'])
		#print(self.prod_setup['Data_file_full_path'])
		#print(self.prod_setup['Data_directory'])
		#print(self.prod_setup['Data_summary_file_full_path'])


		#see if there is already a csv file for this new file	 
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
			
			#get TIMESTAMP of last record for the new datafile
			res = results.sort_values(by=['test_time','test_no'],ascending=[False,False],inplace=False)
			r = res.reset_index().to_dict() 
			
			last_timestamp = r['TIMESTAMP'][0]
			self.record_timestamp.delete(0, 'end')
			self.record_timestamp.insert(20,  last_timestamp )
			self.prod_setup['Date_stamp']=last_timestamp
			
			self.Lot.delete(0, 'end')
			self.Lot.insert(20, r['Lot'][0] )
			self.prod_setup['Lot'] = r['Lot'][0]
			
			self.Wafer.delete(0, 'end')
			self.Wafer.insert(20, r['Wafer'][0] )
			self.prod_setup['Wafer'] = r['Wafer'][0]
			
			
			self.Chip_position.delete(0, 'end')
			self.Chip_position.insert(20, r['Chip_position'][0] )
			self.prod_setup['Chip_position'] = r['Chip_position'][0]
			
			self.prod_setup['Data_file'] = r['Data_file'][0]

			
		except:
			print('Not a tester data file, new file will be created on next test.') 
			return
		
		if results.shape[0]>1:
			self.FILE_MODE.current(1)  #set FILE_MODE to manual


	def change_all(self):
		do_it	= simpledialog.askstring(title = 'Input' , prompt =	 "Do you really want to change this record?", initialvalue='yes', parent=self.root)
		if do_it is not None and do_it == 'yes':
		
			#see if there is already a csv file for this testing session		
			try:
				results=pd.read_csv(self.prod_setup['Data_file_full_path'])
			except:
				print('No tester data file, nothing to change.') 
				return
				
			
			if results.shape[0]<1:
				print('no records in tester file')
				return
				
			r = results[results['test_no']==10000]
			r = r.reset_index().to_dict() 
			old_lot = r['lot'][0]
			old_wafer = r['wafer'][0]

			
			#get new part number etc.
			new_lot = simpledialog.askstring(title = 'Input' , prompt =	 "New Lot No.?", initialvalue=old_lot, parent=self.root)
			if new_lot is None:
				new_lot = old_lot
			
			new_wafer = simpledialog.askstring(title = 'Input' , prompt =  "New Wafer No.?", initialvalue=old_wafer , parent=self.root)
			if new_wafer  is None:
				new_wafer  = old_wafer 
			
			data_path = self.prod_setup['Data_directory']+'images\\'
			
			#change file names of images
		   
			for j in range(len(r['TIMESTAMP'])):
				ts = r['TIMESTAMP'][j]
				ff =  ts.split(' ')
				fff = ff[1].split(':')
				old_chip = r['chip'][j]
				old_lot = r['lot'][j]
				old_wafer = r['wafer'][j]
				for i in range(len(cfg.IMAGE_TYPES)):
					i_type = cfg.IMAGE_TYPES[i].split(',')	
					file_name = old_lot + '_W' + str(old_wafer) + '_P' + str(old_chip) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
					new_file_name = new_lot + '_W' + str(new_wafer) + '_P' + str(old_chip) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
					if i_type[0]=='MCLK':
						file_name = file_name + '.png'
						new_file_name = new_file_name + '.png'
					else:
						file_name = file_name + '_' + i_type[1] + '.tif'
						new_file_name = new_file_name + '_' + i_type[1] + '.tif'
					
					file_name = data_path + file_name
					new_file_name = data_path + new_file_name

					if os.path.isfile(file_name):  #there is a file with this path
						shutil.move(file_name, new_file_name)
				
			
			results['lot'] =  new_lot
			results['wafer'] =	new_wafer

			

			print('\n\nChanging all lot and wafer of all records to lot='+new_lot+', wafer='+str(new_wafer))
			results.sort_values(by=['test_time','test_no'],ascending=[True,True],inplace=True)
			results.to_csv(self.prod_setup['Data_file_full_path'],index=False)
			
			self.prod_setup['Lot']	 = new_lot
			self.Lot.delete(0, 'end')
			self.Lot.insert(20, self.prod_setup['Lot'])
			
			self.prod_setup['Wafer']   = new_wafer
			self.Wafer.delete(0, 'end')
			self.Wafer.insert(20, self.prod_setup['Wafer'])
			
			
			
			
		else:
			return
			
			
			
			
		
	def change_selected(self):
		do_it	= simpledialog.askstring(title = 'Input' , prompt =	 "Do you really want to change this record?", initialvalue='yes', parent=self.root)
		if do_it is not None and do_it == 'yes':
		
			#see if there is already a csv file for this testing session		
			try:
				results=pd.read_csv(self.prod_setup['Data_file_full_path'])
			except:
				print('No tester data file, nothing to change.') 
				return
				  
			
			#read out the selected TIMESTAMP value
			self.record_timestamp
			selected_timestamp = self.record_timestamp.get()
			
			#find the lot/wafer/part_no of the selected record
			r= results[results['TIMESTAMP']==selected_timestamp]
			if r.shape[0]<1:
				print('no record with that TIMESTAMP')
				return
				
			r = r.reset_index().to_dict()
			
			old_lot = r['lot'][0]
			old_wafer = r['wafer'][0]
			old_part = r['chip'][0]
			
			rr = r['Data_file_full_path'][0].split('\\')[0:-1]
			data_path ='\\'.join([str(i) for i in rr]) + '\\images\\'
			
			#get new part number etc.
			new_lot = simpledialog.askstring(title = 'Input' , prompt =	 "New Lot No.?", initialvalue=old_lot, parent=self.root)
			if new_lot is None:
				new_lot = old_lot
			
			new_wafer = simpledialog.askstring(title = 'Input' , prompt =  "New Wafer No.?", initialvalue=old_wafer , parent=self.root)
			if new_wafer  is None:
				new_wafer  = old_wafer 
				
			new_part = simpledialog.askstring(title = 'Input' , prompt =  "New Part No.?", initialvalue=old_part, parent=self.root)
			if new_part is None:
				new_part = old_part
			
			results.loc[results.TIMESTAMP == selected_timestamp, 'lot'] =  new_lot
			results.loc[results.TIMESTAMP == selected_timestamp, 'wafer'] =	 new_wafer
			results.loc[results.TIMESTAMP == selected_timestamp, 'chip'] =	new_part
			
			
			
			#change file names of the images associated with this TIMESTAMPs
			ff =  selected_timestamp.split(' ')
			fff = ff[1].split(':')
			
			
			for i in range(len(cfg.IMAGE_TYPES)):
				i_type = cfg.IMAGE_TYPES[i].split(',')	
				file_name = old_lot + '_W' + str(old_wafer) + '_P' + str(old_part) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
				new_file_name = new_lot + '_W' + str(new_wafer) + '_P' + str(new_part) + '_' + i_type[0] + '_' + ff[0] + '-' + qsi.dateit(fff[0]) + '-' + qsi.dateit(fff[1]) + '-' + qsi.dateit(fff[2]) 
				if i_type[0]=='MCLK':
					file_name = file_name + '.png'
					new_file_name = new_file_name + '.png'
				else:
					file_name = file_name + '_' + i_type[1] + '.tif'
					new_file_name = new_file_name + '_' + i_type[1] + '.tif'
				
				file_name = data_path + file_name
				new_file_name = data_path + new_file_name

				if os.path.isfile(file_name):  #there is a file with this path
					shutil.move(file_name, new_file_name)


			print('\n\nChanging record with TIMESTAMP = '+str(selected_timestamp))
			results.sort_values(by=['test_time','test_no'],ascending=[True,True],inplace=True)
			results.to_csv(self.prod_setup['Data_file_full_path'],index=False)
		else:
			return

	# extract methods functions for run_test_cp
	# get lot/wfr/x/y from flask servere
	def get_lwxy_from_sts(self):
		die_id = requests.get("http://10.52.11.36:5000/get_die_id").text
		mtch = re.search('(?P<lot>\w*)-(?P<wafer>\d+)__(?P<chip_position>X-?\d+Y-?\d+)', die_id)
		if mtch:
			mtch = mtch.groupdict()
			# update button values, not direct overwrite
			lot, wafer, chip_position = (mtch['lot'], mtch['wafer'], mtch['chip_position'])

			self.prod_setup['Chip_position'] = chip_position
			self.Chip_position.config(state='normal')
			self.Chip_position.delete(0, 'end')
			self.Chip_position.insert(20, self.prod_setup['Chip_position'])
			self.Chip_position.config(state='readonly')

			self.prod_setup['Lot'] = lot
			self.Lot.config(state='normal')
			self.Lot.delete(0, 'end')
			self.Lot.insert(20, self.prod_setup['Lot'])

			self.prod_setup['Wafer'] = wafer
			self.Wafer.config(state='normal')
			self.Wafer.delete(0, 'end')
			self.Wafer.insert(20, self.prod_setup['Wafer'])

	# poll flask server for 'controller' state... wait if 'sts', start testing if 'nim'
	def wait_for_start_from_sts(self):
		i = 0
		r = requests.get('http://10.52.11.36:5000/get_controller')
		while r.text != 'nim':
			if i % 1000 == 0:
				print(r.text)
			time.sleep(1)
			# print(f"sleep for 1sec")
			if r.text == 'stop':
				return 'stop'
			elif i > 100:
				print('timeout')
				return 'timeout'
			r = requests.get('http://10.52.11.36:5000/get_controller')
		print('starting NIM testing')
		return 'start'

	# signal STS that NMI done testing current die, and trigger move to next die
	def send_finished_to_sts(self):
		requests.get(f'http://10.52.11.36:5000/nim_finished/{self.hard_bin}')

	def run_cp_test(self):
		'''
		query flask for lot/wfr/x/y, set FinalTest lot/wfr/chip_position
		query STS flask server for 'start_NIM
		run FinalTest.run_test
		set flask server 'NIM_done' so STS moves to next die
		How end testing?  for now, relay on STS num_die_to_test setting

		Returns:

		'''

		self.b_cp = True
		self.get_lwxy_from_sts()
		ctlr_state = self.wait_for_start_from_sts()
		# loop for multi die, as controlled by STS program
		while ctlr_state != 'stop':
			self.run_test()
			self.send_finished_to_sts()
			ctlr_state = self.wait_for_start_from_sts()
			self.get_lwxy_from_sts()
		print('cp control loop ended by STS')


	def run_test(self):

		
		self.num_iteration +=1
		
		#see if the TRD file is valid
		try:
			self.prod_setup['Product_number'] = self.Product.current()
			t_orig = pd.read_csv(cfg.TRD_FILE_PATH + cfg.TRD_FILES[int(self.prod_setup['Product_number'])], low_memory=False).astype('str')
			self.trd = OrderedDict()
			self.trd = t_orig.to_dict()
		except:
			messagebox.showinfo('Error!', 'Invalid TRD file, consult engineering')
			return

		if self.trd['program_file_rev'][0] != cfg.PROGRAM_FILE:
			messagebox.showinfo('Error!', 'Invalid program file, consult engineering')
			return
			
			
			
		#input new part number with dialog box or assembly failure number
		#enter number of assembly failures
		if self.Assembly_failure.current()==1: 
			no_assembly_fails = simpledialog.askstring(title = 'Input' , prompt =  "# Assembly Fails?", initialvalue=0, parent=self.root)
			if no_assembly_fails is not None and int(no_assembly_fails)>0:
				self.prod_setup['Chip_position']   = 'AF'
				self.Chip_position.config(state='normal')
				self.Chip_position.delete(0, 'end')
				self.Chip_position.insert(20, self.prod_setup['Chip_position'])
				self.Chip_position.config(state='readonly')
				self.prod_setup['Number_assembly_fails']=no_assembly_fails
			else:
				return
		else:
		
			if self.PROBER_EFUSE.current()==1:	#this chip has an efuse written at wafer probe or whatever
				efuse_text,bytes,last_byte,lot,wafer,chip = qsi.read_efuse()
				print()
				print('Will use lot/wafer/chip from efuse')
				print('efuse = ' + efuse_text)
				print('efuse size = '+str(bytes)+' bytes')
				print('last used byte = '+str(last_byte))
				print('lot = '+lot)
				print('wafer = '+wafer)
				print('chip = '+chip)
			
				if last_byte>0 and chip!='' and lot!='' and wafer!='':	#the efuse has been written
					self.prod_setup['Number_assembly_fails']=0
					
					self.prod_setup['Chip_position']   = chip
					self.Chip_position.config(state='normal')
					self.Chip_position.delete(0, 'end')
					self.Chip_position.insert(20, self.prod_setup['Chip_position'])
					self.Chip_position.config(state='readonly')
					
					self.prod_setup['Lot'] = lot
					self.Lot.config(state='normal')
					self.Lot.delete(0, 'end')
					self.Lot.insert(20, self.prod_setup['Lot'])
					
					self.prod_setup['Wafer'] = wafer
					self.Wafer.config(state='normal')
					self.Wafer.delete(0, 'end')
					self.Wafer.insert(20, self.prod_setup['Wafer'])
					
				else:  #can't read efuse so manual input
					print('Could not read the efuse for lot/wafer/chip!')
					new_lot = simpledialog.askstring(title = 'Input' , prompt =	 "Lot?", initialvalue=self.prod_setup['Lot'], parent=self.root)
					if new_lot is not None:
						self.prod_setup['Lot']	 = new_lot
						self.Lot.config(state='normal')
						self.Lot.delete(0, 'end')
						self.Lot.insert(20, self.prod_setup['Lot'])
						self.prod_setup['Number_assembly_fails']=0
					else:
						return
						
					new_wafer = simpledialog.askstring(title = 'Input' , prompt =  "Wafer?", initialvalue=self.prod_setup['Wafer'], parent=self.root)
					if new_wafer is not None:
						self.prod_setup['Wafer'] = new_wafer
						self.Wafer.config(state='normal')
						self.Wafer.delete(0, 'end')
						self.Wafer.insert(20, self.prod_setup['Wafer'])
						self.prod_setup['Number_assembly_fails']=0
					else:
						return
						
					new_part = simpledialog.askstring(title = 'Input' , prompt =  "New Part No.?", initialvalue=self.prod_setup['Chip_position'], parent=self.root)
					if new_part is not None:
						self.prod_setup['Chip_position']   = new_part
						self.Chip_position.config(state='normal')
						self.Chip_position.delete(0, 'end')
						self.Chip_position.insert(20, self.prod_setup['Chip_position'])
						self.Chip_position.config(state='readonly')
						self.prod_setup['Number_assembly_fails']=0
					else:
						return
			elif self.b_cp==True:
				print('Lot, Wafer, Chip_position set by prober')
				#TODO: why required?
				self.prod_setup['Number_assembly_fails'] = 0


			else:  #inputchip number
				new_part = simpledialog.askstring(title = 'Input' , prompt =  "New Part No.?", initialvalue=self.prod_setup['Chip_position'], parent=self.root)
				if new_part is not None:
					self.prod_setup['Chip_position']   = new_part
					self.Chip_position.config(state='normal')
					self.Chip_position.delete(0, 'end')
					self.Chip_position.insert(20, self.prod_setup['Chip_position'])
					self.Chip_position.config(state='readonly')
					self.prod_setup['Number_assembly_fails']=0
				else:
					return
			
		#check if the lot and wafer is listed in photonics data, check to make sure the lot/wafer are valid
		df = pd.read_csv(cfg.UTILITY_FILE_PATH + cfg.PHOTONICS_FILE, low_memory=False).astype('str')
		try:
			self.photonics_data = df.loc[(df['lot'] == self.Lot.get()) & (df['wafer'] == str(int(self.Wafer.get())) )]
			self.prod_setup['aperture_file'] = self.photonics_data.values.tolist()[0][self.photonics_data.columns.get_loc("aperture_file")] 
			self.prod_setup['filter'] = self.photonics_data.values.tolist()[0][self.photonics_data.columns.get_loc("filter")]
		except:
			messagebox.showinfo('Error!', 'Invalid Lot and/or Wafer: Try Again!')
			return
			

		#set Process step with combo box
		self.prod_setup['Process_step']= self.Process_step.current()
		
		#set Engineering mode with combo box
		self.prod_setup['Engineering_Mode'] = self.ENGINEERING.current()
		
		#set Read_Efuse with combo box
		self.prod_setup['Write_Efuse'] = self.PROBER_EFUSE.current()
		
		#set Force_Efuse_Write with combo box
		self.prod_setup['Force_Efuse_Write'] = self.FORCE_EFUSE_WRITE.current()
			
		#set Product with combo box
		self.prod_setup['Product_number'] = self.Product.current()
		
		#set Efuse_Value to be 0 at the beginning
		self.prod_setup['Efuse_Value'] = '0'

			
			
		  
		#lot/wfr are updated too....just no dialog box since they are not changed so ofter	
		self.prod_setup['Lot'] = self.Lot.get()
		self.prod_setup['Wafer'] = self.Wafer.get()
		
		#date string and time that will serve as keys for when this block of tests were done on this chip
		f_string, f_time, i_time = qsi.get_date_time()	
		self.prod_setup['Date_stamp']=f_string
		self.prod_setup['Time_stamp']=f_time
		self.prod_setup['Image_stamp']=i_time
		self.record_timestamp.delete(0, 'end')
		self.record_timestamp.insert(20, self.prod_setup['Date_stamp'])
	 
		print('\n\n\n')
		print('Chip Test '+str(self.num_iteration)+' Begun', 'Lot='+str(self.prod_setup['Lot'])+', Wafer='+str(self.prod_setup['Wafer'])+', Part='+str(self.prod_setup['Chip_position']))
		print('aperture file = ' + self.prod_setup['aperture_file']) 
		print('filter = ' + self.prod_setup['filter']) 
		
		#display alarms and test for mode lock
		#qsi.display_alarms()
		if cfg.LASER_PRESENT:
			kk = 0
			while qsi.test_for_alarms()==0 and kk<4:
				print('Loss of laser lock.	Turning laser back on and aligning (this will take ~20 seconds).')
				print('Turning on Laser and TEC')
				qsi.set_laser_tec("pump_on_tec_on")
				time.sleep(1)
				print('aligning laser')
				qsi.align_mll()
				print('setting laser power to '+str(cfg.align_measurement_power)+'mW to calibrate for illuminated scans')
				cfg.atten_alignment = qsi.set_mll_power_get_atten(cfg.align_measurement_power)
				print('laser ready')

				#disable gets removed on restart
				qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds 
				kk = kk + 1
			
			if kk>=3:
				messagebox.showinfo('Error!', 'Laser not turning on!')
				return
			
		
			#display current power
			power = qsi.get_laser_power()
			print('laser power = '+str(round(power,1))+'mW')
			#disable gets removed on restart
			qsi.disable_laser_lib_shutoff(1000000) #disable the laser shutoff when the lid is open for 1000000 seconds 
			print('laser ready')


		  
		#make sure the datafile path is mounted
		if not os.path.exists(cfg.DATA_FILE_PATH):
			try:
				os.mkdir(cfg.DATA_FILE_PATH)
			except:
				print (cfg.DATA_FILE_PATH + " not mounted")
				print ("Please contact engineering to fix the problem")
				sys.exit()	
				 
		#determine whether to use old or new data file:
		if self.FILE_MODE.current() ==	0: #auto file generation mode	 

			#create new data file if desired for enginneering mode
			if self.ENGINEERING.current()==1:
				self.prod_setup['Data_file_eng'] = self.Data_file.get()
		  
				now	 = dt.datetime.now()
				f_string = str(str(now.year) + "_" + "_".join([str(i) for i in [qsi.dateit(now.month),qsi.dateit(now.day)]]))
				m_string = str(now.year) + "_" + str(qsi.dateit(now.month))
				res_path = cfg.DATA_FILE_PATH+m_string
				if not os.path.exists(res_path):
					try:
						os.mkdir(res_path)
					except:
						print (res_path + " directory not available")
						print ("Please make sure engineering data path is mounted.")
						sys.exit()	
						
				#self.data_path = res_path + '\\'  + f_string + '_' + cfg.PRODUCTION_TESTER + '_' + cfg.PRODUCTS[self.prod_setup['Product_number']]	 + '\\'	   
				self.data_path = res_path + '\\'  + f_string + '_' + cfg.PRODUCTION_TESTER	 + '\\'	 
				if not os.path.exists(self.data_path):
					try:
						os.mkdir(self.data_path)
						os.mkdir(self.data_path + 'images\\')  #for image files that are saved
					except:
						print (self.data_path + " not available")
						print ("Please make sure engineering data path is mounted.")
						sys.exit()	
	 
				self.prod_setup['Data_directory'] = self.data_path
				self.prod_setup['Data_file']=self.prod_setup['Data_file_eng']
				self.prod_setup['Data_file_full_path'] = self.data_path + self.prod_setup['Data_file_eng'] +'.csv'
				self.prod_setup['Data_summary_file_full_path'] = self.data_path + self.prod_setup['Data_file_eng']+'_summary.csv'
		   
			#this is production mode....see if a new data file for this day/tester/product needs to be created. 
			else:  
				now	 = dt.datetime.now()
				f_string = str(str(now.year) + "_" + "_".join([str(i) for i in [qsi.dateit(now.month),qsi.dateit(now.day)]]))
				m_string = str(now.year) + "_" + str(qsi.dateit(now.month))
				res_path = cfg.DATA_FILE_PATH+m_string
				if not os.path.exists(res_path):
					try:
						os.mkdir(res_path)
					except:
						print (res_path + "data directory not available")
						print ("Please contact engineering to fix the problem")
						sys.exit()	
						
				self.data_path = res_path + '\\'  + f_string + '_' + cfg.PRODUCTION_TESTER	+ '\\'		 
				if not os.path.exists(self.data_path):
					try:
						os.mkdir(self.data_path)
						os.mkdir(self.data_path + 'images\\')  #for image files that are saved
					except:
						print (self.data_path + " not available")
						print ("Please contact engineering to fix the problem")
						sys.exit() #use the datafile and datapath currently held in self.prod_setup
			
				self.prod_setup['Data_directory'] = self.data_path
				self.prod_setup['Data_file']= f_string + '_production_FT_'+ cfg.PRODUCTION_TESTER 
				self.prod_setup['Data_file_full_path'] = self.data_path + self.prod_setup['Data_file'] +'.csv'
				self.prod_setup['Data_summary_file_full_path'] = self.data_path + self.prod_setup['Data_file']+'_summary.csv'
	   

	   
	   
		#copy TRD, config, qsi_tests.py qsi_helper.py files to data directory if this is a new directory
		qsi.copy_conditional(cfg.TRD_FILE_PATH + cfg.TRD_FILES[int(self.prod_setup['Product_number'])],self.prod_setup['Data_directory'])
		qsi.copy_conditional(cfg.PROGRAM_FILE_PATH + cfg.PROGRAM_FILE,self.prod_setup['Data_directory'])
		qsi.copy_conditional(cfg.UTILITY_FILE_PATH + 'qsi_helpers.py',self.prod_setup['Data_directory'])
		qsi.copy_conditional(cfg.CONFIGURATION_FILE_PATH + cfg.BASE_CONFIGURATION_FILES[self.prod_setup['Product_number']],self.prod_setup['Data_directory'])
		for f in cfg.MODULE_FILES:
			qsi.copy_conditional(cfg.MODULE_FILE_PATH + f,self.prod_setup['Data_directory'])
			


		
		#copy configuration file in TRD to current_config.json in utility folder (used in qsi_helpers.py)
		shutil.copy(cfg.CONFIGURATION_FILE_PATH + cfg.BASE_CONFIGURATION_FILES[self.prod_setup['Product_number']], cfg.CURRENT_CONFIG_PATH)
		
		#see if there is already a csv file for this data_file		  
		try:
			results=pd.read_csv(self.prod_setup['Data_file_full_path'])
		except:
			results=pd.DataFrame([])
			print('No tester data file, will save new one.')			 
		
		
		#save prod_setup values in qsi_prod_setup.csv file (for passing data to modules)
		df = pd.DataFrame.from_dict(self.prod_setup, orient="index")
		df = df.reset_index()
		df.columns = ['condition','value']
		df.to_csv(cfg.UTILITY_FILE_PATH + "qsi_current.csv")
		
		
		#start up power and sleep to get it stabilized
		#qsi.chip_power_enable_disable(1) #enable the chip power (in case it was turned off by a chip with shorts previously)
		#wait_time = cfg.power_stabilization_wait_sec
		#print('waiting '+str(wait_time)+' seconds for power supplies to stabilize')
		#time.sleep(wait_time)	#wait for the power to stabilize
		
		#take test data
		if self.prod_setup['Number_assembly_fails'] == 0:
			results,hard_bin, failure_mode_bin,retest_device = qsi_tests.run_all(results)
		else:
			results,hard_bin, failure_mode_bin,retest_device = qsi_tests.run_assembly_fail(results)
		
		#disable power to chip ASAP in case there were shorts (protect the tester)
		#qsi.chip_power_enable_disable(0) 
		
		#save test data to csv
		results = results[cfg.TEST_DATA_COLUMNS]					   
		results.to_csv(self.prod_setup['Data_file_full_path'],index=False)


	   
		
		

		#messagebox.showinfo('Chip Test '+str(self.num_iteration)+' Done', 'Lot='+str(self.prod_setup['Lot'])+', Wafer='+str(self.prod_setup['Wafer'])+', Part='+str(self.prod_setup['Chip_position'])+
						   # ', hard_bin='+str(hard_bin)+', fail_bin='+str(failure_mode_bin))
		
		tot_tested, tot_passed, yield_no = self.calc_yield(show_info=False)

		# if tot_tested > cfg.MIN_TOT_TESTED:
		# 	if yield_no < cfg.MIN_YIELD:
		# 		messagebox.showinfo('Tester may need repair!  Check with Engineering!', 'The yield for today is < '+str(round(100.0*cfg.MIN_YIELD,1))+'%!')

		if retest_device:
			messagebox.showinfo('This failure mode may be related to chip/interposer contact.  Please re-seat the chip in the clamp and try testing again!')
			 
		
		self.hard_bin = hard_bin
		if hard_bin==1:
			print('Chip Test '+str(self.num_iteration)+' Done', 'Lot='+str(self.prod_setup['Lot'])+', Wafer='+str(self.prod_setup['Wafer'])+', Part='+str(self.prod_setup['Chip_position']))
			print('Chip Passed')
			print('hard_bin='+str(hard_bin))
			print('\ntotal chips tested today = '+str(tot_tested)+', yield = '+str(round(100.0*yield_no,1))+'%')
			
			
			file_name = cfg.BIN_IMAGE_PATH + 'Bin1.png'
			if os.path.isfile(file_name):  #there is a file with this path
				pop_up_image = tk.Toplevel() 
		   
				try:
					load = Image.open(file_name)
					load = load.resize((1373, 691), Image.ANTIALIAS) ## The (1373, 691) is (height, width)
					render = ImageTk.PhotoImage(load)
					img = tk.Label(pop_up_image, image=render)
					img.image = render
					img.place(x=0, y=0)
					pop_up_image.geometry("1373x691")
					pop_up_image.attributes('-topmost','true')
					pop_up_image.grab_set()
					#pop_up_image.mainloop()
					# non blocking.
					pop_up_image.update_idletasks()
					pop_up_image.update()
					time.sleep(3)
					pop_up_image.destroy()
				except:
					print('unable to show bin image!')
					messagebox.showinfo('Test Done!', 'Chip Passed! \nBin=1')
			
		else:
			#dd = t_orig[t_orig['failure_mode_bin']==failure_mode_bin]
			#dd = dd.reset_index().to_dict()
			print('Chip Test '+str(self.num_iteration)+' Done', 'Lot='+str(self.prod_setup['Lot'])+', Wafer='+str(self.prod_setup['Wafer'])+', Part='+str(self.prod_setup['Chip_position']))
			print('Chip Failed')
			#print('hard_bin='+str(hard_bin)+', fail_mode_bin='+str(failure_mode_bin)+', parameter='+str(dd['parameter_name'][0]))
			
			
			#find the failure mode parameter value for the most recent test
			results['test_time'] = results['test_time'].astype(float)
			res = results.sort_values(by=['test_time'],ascending=[False],inplace=False)
			r = res.reset_index().to_dict()		 
			last_timestamp = r['TIMESTAMP'][0]		
			res = res[res['trd_failure_mode_bin']==failure_mode_bin]
			res = res[res['TIMESTAMP']==last_timestamp]
			res = res.reset_index().to_dict()	  
			failure_mode_bin_parameter_value = res['parameter_value'][0]
			
			
			#print('parameter_value='+str(failure_mode_bin_parameter_value)+',	  low_limit='+str(dd['low_limit'][0])+', high_limit='+str(dd['high_limit'][0]))
			print('hard_bin='+str(hard_bin)+', fail_mode_bin='+str(failure_mode_bin)+', parameter='+str(res['parameter_name'][0]))
			print('parameter_value='+str(failure_mode_bin_parameter_value)+',	  low_limit='+str(res['low_limit'][0])+', high_limit='+str(res['high_limit'][0])) #modify 2020-10-22
			
			print('\ntotal chips tested today = '+str(tot_tested)+', yield = '+str(round(100.0*yield_no,1))+'%')
			file_name = cfg.BIN_IMAGE_PATH + 'Bin'+str(hard_bin)+'.png'
			if os.path.isfile(file_name):  #there is a file with this path
				pop_up_image = tk.Toplevel() 
		   
				try:
					load = Image.open(file_name)
					load = load.resize((1373, 691), Image.ANTIALIAS) ## The (1373, 691) is (height, width)
					render = ImageTk.PhotoImage(load)
					img = tk.Label(pop_up_image, image=render)
					img.image = render
					img.place(x=0, y=0)
					pop_up_image.geometry("1387x724")
					pop_up_image.attributes('-topmost','true')
					pop_up_image.grab_set()
					#pop_up_image.mainloop()
					# non blocking.
					pop_up_image.update_idletasks()
					pop_up_image.update()
					time.sleep(3)
					pop_up_image.destroy()

				except:
					print('unable to show bin image!')
					messagebox.showinfo('Test Done!', 'Chip Failed! \nBin='+str(hard_bin))

		return(hard_bin)




		

		

			
d = FinalTest()
d.root.mainloop()

