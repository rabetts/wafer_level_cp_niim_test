#########################################################
#########################################################
#########################################################

#general items
HIDE_CONTROLS = False #show the extra controls used by test engineering
MIN_YIELD = 0.7 #if the yield for this tester file falls below this value then flag the operator to stop testing and check interposer
MIN_TOT_TESTED = 20	 #minimum number of chips tested to flag bad tester conditions if the yield is less than MIN_YIELD
STANDARD_FONT = 12 #the size of the GUI may need to be adjusted on different monitors.	This variable allows this.
IMAGE_SCALE = 2 #1 or 2 

# products, TRD, configuration files
PROGRAM_FILE = 'qsi_ft_TESTS_NickelB_rev0.py'
PHOTONICS_FILE = 'photonics_data.csv'
MODULE_FILES = ['qsi_NickelB_init_tests_rev0.py','qsi_NickelB_vref_tests_rev0.py','qsi_NickelB_dark_tests_rev0.py','qsi_NickelB_illum_tests_rev0.py',
				'qsi_NickelB_summarize_tests_rev0.py','qsi_NickelB_assembly_fails_rev0.py']


PROCESS_STEPS = ['Pre_Surface_Chem','Post_Surface_Chem','Other']

PRODUCTS = [
			'NickelB_512K-default-Electrode-XA',
			'NickelB_512K-default-Electrode-XB',
			'NickelB_512K-Todd-Electrode-XA',
			'NickelB_512K-Todd-Electrode-XB',
			'NickelB_2M-default-Electrode-XB',
			'NickelB_512K-default-Electrode-XB-osc',
			'NickelD_2M-default-Electrodes-XB',
			'NickelE_2M-default-Electrodes-XB',
			'NickelE',
			'NickelB_S42906_W9',
			'NickelB_2M-Tom-Electrodes-XB']

TRD_FILES = [
			'qsi_ft_TRD_NickelB_rev4_a.csv',
			'qsi_ft_TRD_NickelB_rev4_b.csv',
			'qsi_ft_TRD_NickelB_rev4_Todd_a.csv',
			'qsi_ft_TRD_NickelB_rev4_Todd_b.csv',
			'qsi_ft_TRD_NickelB_rev4_2M_b.csv',
			'qsi_ft_TRD_NickelB_rev4_osc_b.csv',
			'qsi_ft_TRD_NickelD_rev4_2M_b.csv',
			'qsi_ft_TRD_NickelE_rev4_2M_b.csv',
			'qsi_ft_TRD_NickelB_rev4_e.csv',
			'qsi_ft_TRD_NickelB_rev4_b.csv',
			'qsi_ft_TRD_NickelB_rev4_2M_Tom_b.csv']
			
			
TC_FILES = [
						'qsi_ft_TC_NickelB_rev4_a.csv',
						'qsi_ft_TC_NickelB_rev4_b.csv',
						'qsi_ft_TC_NickelB_rev4_Todd_a.csv',
						'qsi_ft_TC_NickelB_rev4_Todd_b.csv',
						'qsi_ft_TC_NickelB_rev4_2M_b.csv',
						'qsi_ft_TC_NickelB_rev4_osc_b.csv',
						'qsi_ft_TC_NickelD_rev4_2M_b.csv',
						'qsi_ft_TC_NickelE_rev4_2M_b.csv',
						'qsi_ft_TC_NickelB_rev4_e.csv',
						'qsi_ft_TC_NickelB_rev4_b.csv',
						'qsi_ft_TC_NickelB_rev4_2M_Tom_b.csv']
			
BASE_CONFIGURATION_FILES = [
							'NickelB_512K_PP2_2020_09_28_default_electrodes_XylenA.json',
							'NickelB_512K_PP2_2020_09_28_default_electrodes_XylenB.json',
							'9001_NickelB_2048x256_pp2_2020_08_08_Todd_electrodes_XylenA.json',
							'9001_NickelB_2048x256_pp2_2020_08_08_Todd_electrodes_XylenB.json',
							'nickel_q9001_img_014_tom.json',
							'NickelB_512K_PP2_2020_10_01_default_electrodes_XylenB_osc.json',
							'NickelD_2M_PP2_2020_11_13_default_electrodes_singleBclock_XylenB.json',
							'NickelE_2M_PP2_2020_10_19_default_electrodes_XylenB_256rows.json',
							'NickelE_512K_PP2_2020_10_01_default_electrodes_XylenB_osc.json',
							'NickelB_512K_PP2_2020_10_29_Tom_electrodes_XylenB_S42906_W9.json',
							'NickelB_2M_PP2_2020_11_03_Tom_electrodes_XylenB.json'] 



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



#########################################################
#########################################################
#########################################################
#The items below can be used with all qsi_ft_TESTS files

#saved image types
IMAGE_TYPES = ["reset,bin0","reset,bin1","dark_min_tint,bin0","dark_min_tint,bin1","dark_seq_tint,bin0","dark_seq_tint,bin1",
				"dark_current,bin0","dark_current,bin1","dark_noise,bin0","dark_noise,bin1",
				"dark_diff,bin0","dark_diff,bin1","dark_min_tint_noise,bin0","dark_min_tint_noise,bin1",
				"dark_max_tint_noise,bin0","dark_max_tint_noise,bin1",
				"illum,bin0","illum,bin1","MCLK,scan","MCLK,chiplet0","MCLK,chiplet1","MCLK,chiplet2","MCLK,chiplet3"]
				
#parameters that can be viewed with FT program
SELECTED_PARAMETERS = ["beam_steer_THETA_Y","illum_median_laser_power_x_tint_x_rej","MCLK_rej_0p25nsec_bin1"]



PRODUCTION_TESTER = 'NI2004015' #tall helmet at my desk in 530
PRODUCTION_TESTER = 'NI2021003' #tall helmet at 351
PRODUCTION_TESTER = 'open' #tall helmet char machine at my home
PRODUCTION_TESTER = 'NI1949001' #tall helmet for Majelic
PRODUCTION_TESTER = 'NI1950010' #short helmet at 351


if PRODUCTION_TESTER == 'NI1950010': #short helmet machine in surface chem area
	#attenuator settings for Ni 10 Nickel machine
	LASER_PRESENT = True #is a mode locked laser present on this system
	atten_alignment = 1975 #this atten setting should be within equation range of Nickel machine...set to 15mW for now with min laser power setting of 10mW on the machine
	atten_0mW = 2800
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor
	
	dark_Y = 2300  #value of Y for dark tests (no shutter)
	align_theta_X = 2600  #value of theta_X for laser alignment
	align_theta_Y = 3300  #value of theta_Y for initial laser alignment

	DATA_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\configurations\\"  #this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\trd\\"
	TC_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\masks\\"
	INCLUDE_PATH = 'C:\\Users\\qsi\\Desktop\\1.104.0.0_2020_09_28\\'  #location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\current_config.json"  #this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\bin_images\\"	 #directory where images for bin of chip are saved.

	
if PRODUCTION_TESTER == 'NI2021003': #tall helmet machine in surface chem area
	LASER_PRESENT = True #is a mode locked laser present on this system
	#attenuator settings for Ni 3 Nickel machine
	atten_alignment = 2525
	atten_0mW = 3000
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor


	dark_Y = 2400  #value of Y for dark tests (no shutter)
	align_theta_X = 2600  #value of theta_X for laser alignment
	align_theta_Y = 3300  #value of theta_Y for initial laser alignment
	
	DATA_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\configurations\\"  #this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\trd\\"
	TC_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\masks\\"
	INCLUDE_PATH = 'C:\\Users\\Valued Customer\\Desktop\\1.104.0.0_2020_09_28\\'  #location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\utility\\current_config.json"  #this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\Valued Customer\\Desktop\\Production_FT\\bin_images\\"	 #directory where images for bin of chip are saved.

	

if PRODUCTION_TESTER == 'NI2004015': #tall helmet at my desk in 530
	LASER_PRESENT = True #is a mode locked laser present on this system
	#attenuator settings 
	atten_alignment = 2275
	atten_0mW = 2600
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor


	dark_Y = 2400  #value of Y for dark tests (no shutter)
	align_theta_X = 2600  #value of theta_X for laser alignment
	align_theta_Y = 3300  #value of theta_Y for initial laser alignment
	
	DATA_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\configurations\\"	#this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\trd\\"
	TC_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\masks\\"
	INCLUDE_PATH = 'C:\\Users\\tthur\\Desktop\\1.104.0.0_2020_09_28\\'	#location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\utility\\current_config.json"	#this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\tthur\\Desktop\\Production_FT\\bin_images\\"  #directory where images for bin of chip are saved.
	
if PRODUCTION_TESTER == 'open': #tall helmet char machine at my home
	LASER_PRESENT = False #is a mode locked laser present on this system
	#attenuator settings for open chassis machine at my home
	atten_alignment = 0
	atten_0mW = 0
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor


	dark_Y = 0	#value of Y for dark tests (no shutter)
	align_theta_X = 0  #value of theta_X for laser alignment
	align_theta_Y = 0  #value of theta_Y for initial laser alignment
	
	LASER_PRESENT = False
	DATA_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\configurations\\"	#this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\trd\\"
	TC_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\masks\\"
	INCLUDE_PATH = 'C:\\Users\\tthurston\\Desktop\\1.104.0.0_2020_09_28\\'	#location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\utility\\current_config.json"	#this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\tthurston\\Desktop\\Production_FT\\bin_images\\"  #directory where images for bin of chip are saved.

	
if PRODUCTION_TESTER == 'NI1949001': #Majelac tester w/o laser
	LASER_PRESENT = False #is a mode locked laser present on this system
	#attenuator settings for open chassis machine for Majelic
	atten_alignment = 0
	atten_0mW = 0
	min_measurement_power = 11.0  #if the power goes below this value during illuminated image tests then the laser will be realigned.
	align_measurement_power = 13.5 #target laser power to calibrate attenuator motor


	dark_Y = 0	#value of Y for dark tests (no shutter)
	align_theta_X = 0  #value of theta_X for laser alignment
	align_theta_Y = 0  #value of theta_Y for initial laser alignment
	STANDARD_FONT = 12 #the size of the GUI may need to be adjusted on different monitors.	This variable allows this.

	
	LASER_PRESENT = False
	DATA_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Chip_data\\"
	UTILITY_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\"
	CONFIGURATION_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\configurations\\"	#this is the rev controlled configuration repository....no modifications done to this file
	PROGRAM_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\programs\\"
	TRD_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\trd\\"
	TC_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\test_conditions\\"
	MODULE_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\modules\\"
	MASK_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\masks\\"
	INCLUDE_PATH = 'C:\\Users\\qsi\\Desktop\\1.104.0.0_2020_09_28\\'	#location API files
	DEFAULT_REG_FILE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\spi_reg_map.csv"
	CURRENT_CONFIG_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\utility\\current_config.json"	#this is a temp config file that is modified during tests
	BIN_IMAGE_PATH = "C:\\Users\\qsi\\Desktop\\Production_FT\\bin_images\\"	 #directory where images for bin of chip are saved.




#column names for data stored in tester csv files.
TEST_DATA_COLUMNS = ['TIMESTAMP','test_time','test_duration','lot','wafer','chip','tester','product','process_step','chip_hard_bin','chip_failure_mode_bin','trd_hard_bin','trd_failure_mode_bin',
								'test_no','test_type','parameter_name','parameter_value','parameter_unit','test_performed','information_only',
								'stop_on_fail','low_limit','high_limit','save_image','engineering_mode','write_efuse','trd_file','program_file_rev','cmos_configuration_file','Data_file_full_path']
								





