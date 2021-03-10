"""
Q9001 EFUSE API Example
"""

#from qsi_falcon import qsi_helpers as qsi
import nickel_lib as nickel

# Create the instrument object which attempts to connect to a nickel device, and then write the config
ni=nickel.instrument()
ni.config('./q9001_efuse_prog.json')

# Create a q9001 efuse api object
efuse=nickel.efuse()

#-----------------------------------------------------------------------------
# EFuse read/write access can be performed by an API with an "End User" scope,
# or an set of methods with "Direct Access" to the EFuse physical cells.
#
# 1. Primary EFuse access is via an End User set of methods.  These methods
#    wrap the lower level access methods (listed below), exposing the multiple
#    EFuse banks/cells as a single composite memory. This memory is accessed
#    a single array of bytes.  The read and write recipes are hard coded in
#    End User API methods.  If these parameters are not sufficient, either
#    update the parameters in the nickel_lib class (under revision control),
#    or learn and use the lower level "Direct Access" methods which do expose
#    EFuse programming parameters.
#
#    The End User can read and write from single bytes (i.e. characters) or
#    individual bits within a byte with the following methods:
#
#     Read Methods
#     ------------
#     rd_bit   -  Read a single bit in the composite EFuse memory map.
#     rd_byte  -  Read a single byte of the composite EFuse memory map.
#     rd_char  -  A convenience function for reading a single byte of the composite
#                 EFuse memory map and returning a character instead of an integer
#     rd_efuse  - Read the entire composite EFuse memory map as a byte integer list or char list
#
#     Write Methods
#     -------------
#     wr_bit    - Write a single bit in the composite EFuse memory map.
#     wr_byte   - Write a single byte in the composite EFuse memory map.
#     wr_char   - A convenience funtion for writing a single byte in the composite
#                 EFuse memory map from an ascii character parameter instead of
#                 an integer.
#
# 2. Secondary methods are "Direct Access" of the EFuse cells.  These methods
#    are used during characterization testing, but are also wrapped by the
#    higher level "End User" API.
#    The cells are read and written by accessing the Banks/Rows/Columns via
#    spi register access and FPGA pattern generator programmging.  This
#    access uses the following methods in the "efuse" class, but require
#    knowledge of the physical efuse programming parameters:
#
#    Direct EFuse Programming Methods
#    --------------------------------
#        rd_cell    - read a single cell (actually reads a row, but returns a single cell value)
#        rd_row     - read a row of cells into a 1D list
#        rd_bank    - read all rows in a bank into a 2D list
#        rd_banks   - read all banks into a 3D list
#        wr_cell    - burn a single cell
#        wr_row     - burn an entire row of cells (shortcut function for characterization)
#        wr_bank    - burn an entire bank of cells (shortcut function for characterization)
#        wr_banks   - burn all cells in all banks (shortcut function for characterization)
#        test_cell  - configure a single cell into test mode and test it
#
#    Low Level EFuse Recipe Support Functions
#    ----------------------------------------
#        set_vefuse  - Set the EFuse voltage level and ensure the supply is enabled
#        cfg_rd_ctrl - Configure the EFuse Control 1 register settings for a read operation.
#        cfg_wr_ctrl - Configure the EFuse Control 1 register settings for a write operation.
#        set_addr    - Configure the EFuse Control 0 registers for the targeted row byte(s).
#        get_data    - Get EFuse read data register contents for the bank/row
#        set_rd_pattern - Initialize the efuse pattern generator for read operations
#        set_wr_pattern - Initialize the efuse pattern generator for write operations
#        fire_oneshot   - Trigger the FPGA Oneshot pattern generator.
#-----------------------------------------------------------------------------

# Read the contents of all EFuse Banks as a single memory.  Value returned is a list of bytes
ret_type = 0 # 0 - return a list of bytes, 1 - return a list of characters
chip_efuse = efuse.rd_efuse(ret_type)
print("Q9001 EFuse contains " + str(len(chip_efuse)) + " bytes (" + str(len(chip_efuse) * 8) + " cells).")

print("Read the EFuse as a list of integers")
print(chip_efuse)
print()

print("Read the EFuse as a list of characters")
ret_type=1
chip_efuse = efuse.rd_efuse(ret_type)
print(chip_efuse)

# sample bit writes to a single byte.  Writing 'Q' to the first byte, but using bit access
efuse.wr_bit(1,0)
efuse.wr_bit(1,4)
efuse.wr_bit(1,6)

# sample byte writes with integer parameters. Writing '-Si' to bytes 1, 2, 3 using byte access
efuse.wr_byte(2,45)
efuse.wr_byte(3,83)
efuse.wr_byte(4,105)

# sample byte writes with character parameters. Writing '-Si' to bytes 1, 2, 3 using byte access

all_alphas = [' ', 'S','a','y','s',' ',':',' ','P','a','c','k',' ','m','y',' ','b','o','x',' ','w','i','t','h',' ','f','i','v','e',' ','d','o','z','e','n',' ','l','i','q','u','o','r',' ','j','u','g','s']

print()
print("Writing the EFuse with a list of characters, this takes a while")
byte_index = 5
for c in range(len(all_alphas)):
    efuse.wr_char(byte_index,all_alphas[c])
    byte_index = byte_index + 1

print()
print("Read the EFuse again...")
ret_type=1
chip_efuse = efuse.rd_efuse(ret_type)
print(''.join(chip_efuse))
