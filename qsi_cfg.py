#########################################################
#########################################################
#########################################################

#general items
HIDE_CONTROLS = False #show the extra controls used by test engineering
MIN_YIELD = 0.7 #if the yield for this tester file falls below this value then flag the operator to stop testing and check interposer
MIN_TOT_TESTED = 20	 #minimum number of chips tested to flag bad tester conditions if the yield is less than MIN_YIELD
STANDARD_FONT = 12 #the size of the GUI may need to be adjusted on different monitors.	This variable allows this.
#IMAGE_SCALE = 2 #1 or 2

# products, TRD, configuration files
PROGRAM_FILE = 'qsi_ft_TESTS_NickelB_rev0.py'
PHOTONICS_FILE = 'photonics_data.csv'
MODULE_FILES = ['qsi_NickelB_init_tests_rev0.py','qsi_NickelB_vref_tests_rev0.py','qsi_NickelB_dark_tests_rev0.py','qsi_NickelB_illum_tests_rev0.py',
				'qsi_NickelB_summarize_tests_rev0.py','qsi_NickelB_assembly_fails_rev0.py']


PROCESS_STEPS = ['Pre_Surface_Chem','Post_Surface_Chem','Other']

# change base_configuration_file also
#chip_type = 'NickelD'
chip_type = 'NickelG'
b_skip_photonics = True
flask_server_ip = '10.140.10.23'
if chip_type == 'NickelD':
	BASE_CONFIGURATION_FILES = ['q9001_prober_2048x1024_cont_65M_8M_20220218_near_solo.json',
								]

	TRD_FILES = [
				'qsi_ft_TRD_NickelB_rev13_cp.csv',
				'qsi_ft_TRD_NickelB_rev12_cp.csv',
				'qsi_ft_TRD_NickelB_rev10_cp.csv',
				'qsi_ft_TRD_NickelB_rev8_cp.csv',
				'qsi_ft_TRD_NickelB_rev7_cp.csv',
				'qsi_ft_TRD_NickelB_rev6_cp.csv',
				'qsi_ft_TRD_NickelB_rev6_va33_vd18_shorts_cp.csv',

	]
	TC_FILES = [
						'qsi_ft_TC_NickelB_rev4_f.csv',
				]
	# apparently PRODUCTS not used now
	PRODUCTS = ['q9001_prober_2048x1024_cont_65M_8M_20220218_near_solo.json',
				]
elif chip_type=='NickelG':
	OFF_CHIP_CDS_CONFIG_PATH = 'NickelG_dCDS_C3_GTX_4p4_TX_3p2_VDRAIN4p5_VDDP3p6_oscillating_4sp_chip_phase_1200_CP_2021-12-10_b.json'

	BASE_CONFIGURATION_FILES = \
		[  'NickelG_aCDS_2022-01-28_for_rel108.json',
		   'NickelG_aCDS_2022-03-06_prober_32x2048_for_rel108.json',
		 'NickelG_aCDS_C3_GTX_4p4_TX_3p2_VDRAIN4p5_VDDP3p6_oscillating_1p3x_61p49fps_cds_2021-12-10_b.json',
		]

	TRD_FILES = [
				'qsi_ft_TRD_NickelG_rev04_cp.csv',
				'qsi_ft_TRD_NickelG_rev03_cp.csv',  # run until 20220405
				]
	TC_FILES = [
						'qsi_ft_TC_NickelG_rev1.csv',
				]
	# apparently PRODUCTS not used now
	PRODUCTS = [	'NickelG_aCDS_2021_11_30.json',
						'NickelG_aCDS_C3_GTX_4p4_TX_3p2_VDRAIN4p5_VDDP3p6_oscillating_1p3x_61p49fps_cds_2021-12-10_b.json',
						]

# end of chip type dependent variables

b_half_wafer = False



vref_ROIS = [
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5],
			 [0, -1, 5, 0, -1, 5]]
			 
illum_ROIS = [
			 # [0, -1, 5, 0, -1, 5],
			  [0, -1, 1, 0, -1, 1],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5],
			  [0, -1, 5, 0, -1, 5]]



#########################################################
#########################################################
#########################################################
#The items below can be used with all qsi_ft_TESTS files

#saved image types
IMAGE_TYPES = ["reset,bin0","dark_min_tint,bin0", "dark_seq_tint,bin0",
			   "dark_current,bin0", "dark_noise,bin0",
			   "dark_diff,bin0", "dark_min_tint_noise,bin0",
			   "dark_max_tint_noise,bin0",]
# IMAGE_TYPES = ["reset,bin0", "reset,bin1", "dark_min_tint,bin0", "dark_min_tint,bin1", "dark_seq_tint,bin0",
# 			   "dark_seq_tint,bin1",
# 			   "dark_current,bin0", "dark_current,bin1", "dark_noise,bin0", "dark_noise,bin1",
# 			   "dark_diff,bin0", "dark_diff,bin1", "dark_min_tint_noise,bin0", "dark_min_tint_noise,bin1",
# 			   "dark_max_tint_noise,bin0", "dark_max_tint_noise,bin1",
# 			   "illum,bin0", "illum,bin1", "MCLK,scan", "MCLK,chiplet0", "MCLK,chiplet1", "MCLK,chiplet2",
# 			   "MCLK,chiplet3"]

#parameters that can be viewed with FT program
SELECTED_PARAMETERS = ["beam_steer_THETA_Y","illum_median_laser_power_x_tint_x_rej","MCLK_rej_0p25nsec_bin1"]



# PRODUCTION_TESTER = 'NI2004015' #tall helmet at my desk
# PRODUCTION_TESTER = 'NI2021003' #tall helmet at 351
# PRODUCTION_TESTER = 'NI1949001' #tall helmet for Majelic
# PRODUCTION_TESTER = 'NI1950010' #short helmet at 351
PRODUCTION_TESTER = 'open' #tall helmet char machine at my home
#PRODUCTION_TESTER = 'NI1949001' #tall helmet for Majelic
#PRODUCTION_TESTER = 'NI1950010' #short helmet at 351



if PRODUCTION_TESTER == 'open':
	LASER_PRESENT = False  #is a mode locked laser  present on this system
	#attenuator settings for open chassis machine at my home
	atten_alignment = 0
	atten_0mW = 0
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor


	dark_Y = 0	#value of Y for dark tests (no shutter)
	align_theta_X = 0  #value of theta_X for laser alignment
	align_theta_Y = 0  #value of theta_Y for initial laser alignment
	
	DATA_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\configurations\\"	#this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\trd\\"
	TC_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\masks\\"
#	INCLUDE_PATH =  'C:\\Users\\qsi\\Dropbox (Quantum-SI)\\Q-Si Software\\Falcon 64\chewie\\1.105.0.0\\'	#location API files
	INCLUDE_PATH =  'C:\\Users\\qsi\\Dropbox (Quantum-SI)\\Q-Si Software\\Falcon 64\chewie\\Beta\\'	#location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\utility\\current_config.json"	#this is a temp config file that is modified during tests
	CURRENT_CONFIG_PATH_OFF_CHIP_CDS = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\utility\\current_config_off_chip_cds.json"	#this is a temp config file that is modified during tests
	FULL_FRAME_CONFIG_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\configurations\\q9001_prober_2048x1024_cont_65M_8M.json"	#this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT_mod_cp\\bin_images\\"  #directory where images for bin of chip are saved.


#column names for data stored in tester csv files.
TEST_DATA_COLUMNS = ['TIMESTAMP','test_time','test_duration','lot','wafer','chip','tester','product','process_step','chip_hard_bin','chip_failure_mode_bin','trd_hard_bin','trd_failure_mode_bin',
								'test_no','test_type','parameter_name','parameter_value','parameter_unit','test_performed','information_only',
								'stop_on_fail','low_limit','high_limit','save_image','engineering_mode','write_efuse','trd_file','program_file_rev','cmos_configuration_file','Data_file_full_path']
								





