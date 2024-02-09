import os
#import logging
import sys
import time

import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from bmplib import BitmapHeader, BitmapHeaderInfo

# Display resolution
EPD_WIDTH = 800
EPD_HEIGHT = 480

# epaper HAT commands
PANEL_SETTING                             = 0x00
POWER_SETTING                             = 0x01
POWER_OFF                                 = 0x02
POWER_ON                                  = 0x04
BOOSTER_SOFT_START                        = 0x06
DEEP_SLEEP                                = 0x07
DATA_TRANSMISSION_1                       = 0x10
DISPLAY_REFRESH                           = 0x12
DATA_TRANSMISSION_2                       = 0x13
DUAL_SPI_MODE                             = 0x15
LUT_VCOM                                  = 0x20
LUT_BW                                    = 0x21
LUT_BW2                                   = 0x22
LUT_WB                                    = 0x23
LUT_BB                                    = 0x24
PLL_CONTROL                               = 0x30
VCOM_DATA_INTERVAL                        = 0x50
TCON_SETTING                              = 0x60
RESOLUTION_SETTING                        = 0x61
GATE_SOURCE_START_SETTING                 = 0x65
GET_STATUS                                = 0x71
VCOM_DC                                   = 0x82

# Display orientation
ROTATE_0                                    = 0
ROTATE_90                                   = 1
ROTATE_180                                  = 2
ROTATE_270                                  = 3

class EPD:
    def __init__(self, reset, dc, busy, cs, clk, mosi):
        self.reset_pin = DigitalInOut(reset)
        self.reset_pin.direction = Direction.OUTPUT
        
        self.dc_pin = DigitalInOut(dc)
        self.dc_pin.direction = Direction.OUTPUT
        
        self.busy_pin = DigitalInOut(busy)
        self.busy_pin.direction = Direction.INPUT

        self.cs_pin = DigitalInOut(cs)
        self.cs_pin.direction = Direction.OUTPUT
        #self.cs_pin.pull = Pull.UP
                
        self.spi = busio.SPI(clk, mosi)
        self.spi.try_lock()
        self.spi.configure(baudrate=8000000)
        self.spi.unlock()
        
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.rotate = ROTATE_0
        
    VOLTAGE_FRAME = [
       0x6,0x3F,0x3F,0x11,0x24,0x7,0x17
    ]

    LUT_VCOM = [
	0x0,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0xF,	0x1,	0xF,	0x1,	0x2,	
	0x0,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0	
    ]

    LUT_WW = [
	0x10,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x84,	0xF,	0x1,	0xF,	0x1,	0x2,	
	0x20,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0	
    ]

    LUT_BW = [
	0x10,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x84,	0xF,	0x1,	0xF,	0x1,	0x2,	
	0x20,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0
    ]

    LUT_WB = [
	0x80,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x84,	0xF,	0x1,	0xF,	0x1,	0x2,	
	0x40,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0
    ]

    LUT_BB = [
	0x80,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x84,	0xF,	0x1,	0xF,	0x1,	0x2,	
	0x40,	0xF,	0xF,	0x0,	0x0,	0x1,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0,	
	0x0,	0x0,	0x0,	0x0,	0x0,	0x0
    ]   
        

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000)

    def reset(self): # Hardware reset
        self.reset_pin.value = True
        self.delay_ms(200)
        self.reset_pin.value = False
        self.delay_ms(2)
        self.reset_pin.value = True
        self.delay_ms(200)

    def _spi_transfer(self, data):
        self.cs_pin.value = False
        self.spi.try_lock()
        self.spi.write(bytes([data]))
        self.spi.unlock()
        self.cs_pin.value = True
        
    def send_command(self, command):
        self.dc_pin.value = False
        self._spi_transfer(command)

    def send_data(self, data):
        self.dc_pin.value = True
        self._spi_transfer(data)

    def ReadBusy(self):
        while(self.busy_pin.value == True):      # 0: idle, 1: busy
            self.delay_ms(5)
            
    def TurnOnDisplay(self):       # Showtime
        self.send_command(DISPLAY_REFRESH)
        self.delay_ms(100)    
        self.ReadBusy()

    def init(self):
        self.reset()

        self.send_command(POWER_SETTING)  
        self.send_data(0x17)  # 1-0=11: internal power
        self.send_data(self.VOLTAGE_FRAME[6])  # VGH&VGL
        self.send_data(self.VOLTAGE_FRAME[1])  # VSH
        self.send_data(self.VOLTAGE_FRAME[2])  #  VSL
        self.send_data(self.VOLTAGE_FRAME[3])  #  VSHR

        self.send_command(VCOM_DC)  
        self.send_data(self.VOLTAGE_FRAME[4])  # VCOM

        self.send_command(BOOSTER_SOFT_START)  
        self.send_data(0x27)
        self.send_data(0x27)
        self.send_data(0x2F)
        self.send_data(0x17)

        self.send_command(PLL_CONTROL)   # OSC Setting
        self.send_data(self.VOLTAGE_FRAME[0])  # 2-0=100: N=4  ; 5-3=111: M=7  ;  3C=50Hz     3A=100HZ

        self.send_command(POWER_ON) #POWER ON
        self.delay_ms(100)
        self.ReadBusy()

        self.send_command(PANEL_SETTING)
        self.send_data(0x3F)   #KW-3f   KWR-2F BWROTP 0f BWOTP 1f

        self.send_command(RESOLUTION_SETTING)        # tres
        self.send_data(0x03) #source 800
        self.send_data(0x20)
        self.send_data(0x01) #gate 480
        self.send_data(0xE0)

        self.send_command(DUAL_SPI_MODE)
        self.send_data(0x00)

        self.send_command(VCOM_DATA_INTERVAL)
        self.send_data(0x10)
        self.send_data(0x00)

        self.send_command(TCON_SETTING)
        self.send_data(0x22)

        self.send_command(GATE_SOURCE_START_SETTING) 
        self.send_data(0x00)
        self.send_data(0x00)   # 800*480
        self.send_data(0x00)
        self.send_data(0x00)
        
        self.send_command(LUT_VCOM) #VCOM
        for count in range(42):
            self.send_data(self.LUT_VCOM[count])

        self.send_command(LUT_BW) #LUTBW
        for count in range(42):
            self.send_data(self.LUT_WW[count])

        self.send_command(LUT_BW2) #LUTBW
        for count in range(42):
            self.send_data(self.LUT_BW[count])

        self.send_command(LUT_WB) #LUTWB
        for count in range(42):
            self.send_data(self.LUT_WB[count])

        self.send_command(LUT_BB) #LUTBB
        for count in range(42):
            self.send_data(self.LUT_BB[count])

        return 0

    def module_exit(self):
        #logger.debug("spi end")
        self.spi.deinit()
        self.reset_pin.value = False
        self.dc_pin.value = False
        
        self.reset_pin.deinit()
        self.dc_pin.deinit()
        self.busy_pin.deinit()
        self.cs_pin.deinit()

        #logger.debug("close 5V, Module enters 0 power consumption ...")
    
    def sleep(self):
        # self.send_command(0x22) #POWER OFF
        # self.send_data(0xC3)
        # self.send_command(0x20)

        self.send_command(POWER_OFF)  # Enter deep sleep
        self.ReadBusy()
        
        self.send_command(DEEP_SLEEP)
        self.send_data(0xA5)
        
        self.delay_ms(2000)
        self.module_exit()

    def Clear(self):                  # Fill frame buffer, write to RAM, update screen
        if self.width & 0x7 == 0:
            linewidth = int(self.width >> 3)
        else:
            linewidth = int(self.width >> 3) + 1
        # logger.debug(linewidth)
        
        self.send_command(DATA_TRANSMISSION_1)
        for j in range(0, self.height):
            for i in range(0, linewidth):
                self.send_data(0xFF)
        
        self.send_command(DATA_TRANSMISSION_2)
        for j in range(0, self.height):
            for i in range(0, linewidth):
                self.send_data(0x00)
                
        self.TurnOnDisplay()
        
    def Clear_black(self):                  # Fill frame buffer, write to RAM, update screen
        if self.width & 0x7 == 0:
            linewidth = int(self.width >> 3)
        else:
            linewidth = int(self.width >> 3) + 1
        # logger.debug(linewidth)
        
        self.send_command(DATA_TRANSMISSION_1)
        for j in range(0, self.height):
            for i in range(0, linewidth):
                self.send_data(0x00)
        
        self.send_command(DATA_TRANSMISSION_2)
        for j in range(0, self.height):
            for i in range(0, linewidth):
                self.send_data(0xFF)
                
        self.TurnOnDisplay()
    
    def clear_frame(self, frame_buffer_black): # Empties frame buffer. No update. Slower. Just reassign bytearray.
        for i in range(int(self.width * self.height >> 3)):
            frame_buffer_black[i] = 0x00

    def display_frame(self, frame_buffer_black):  # Writes buffer into ram and updates screen (unused)
        self.send_command(DATA_TRANSMISSION_2)
        self.delay_ms(2)
        for i in range(0, self.width * self.height >> 3):
            temp = 0x00
            for bit in range(0, 4):
                if (frame_buffer_black[i] & (0x80 >> bit) != 0):
                    temp |= 0xC0 >> (bit * 2)
            self.send_data(temp)
            temp = 0x00
            for bit in range(4, 8):
                if (frame_buffer_black[i] & (0x80 >> bit) != 0):
                    temp |= 0xC0 >> ((bit - 4) * 2)
            self.send_data(temp)
        self.delay_ms(2)
        self.TurnOnDisplay()

    def display(self, image):                     # Writes buffer into ram and updates screen
        if self.width & 0x7 == 0:
            linewidth = int(self.width >> 3)
        else:
            linewidth = int(self.width >> 3) + 1

        self.send_command(DATA_TRANSMISSION_2)
        for j in range(0, int(self.height)):
            for i in range(0, int(self.width >> 3)):
                self.send_data(image[i + j * linewidth])   
        self.TurnOnDisplay()
        
    def display2(self, image):                     # Writes buffer into ram and updates screen
        self.send_command(DATA_TRANSMISSION_2)
        for j in range(0, 48000):
            self.send_data(image[j])   
        self.TurnOnDisplay()

# For Drawing

    def set_pixel(self, frame_buffer, x, y):
        if (x < 0 or x >= self.width or y < 0 or y >= self.height):
            return
        if (self.rotate == ROTATE_0):
            self.set_absolute_pixel(frame_buffer, x, y)
        elif (self.rotate == ROTATE_90):
            point_temp = x
            x = EPD_WIDTH - y
            y = point_temp
            self.set_absolute_pixel(frame_buffer, x, y)
        elif (self.rotate == ROTATE_180):
            x = EPD_WIDTH - x
            y = EPD_HEIGHT- y
            self.set_absolute_pixel(frame_buffer, x, y)
        elif (self.rotate == ROTATE_270):
            point_temp = x
            x = y
            y = EPD_HEIGHT - point_temp
            self.set_absolute_pixel(frame_buffer, x, y)

    def set_absolute_pixel(self, frame_buffer, x, y):
        # To avoid display orientation effects
        # use EPD_WIDTH instead of self.width
        # use EPD_HEIGHT instead of self.height
        if (x < 0 or x >= EPD_WIDTH or y < 0 or y >= EPD_HEIGHT):
            return
        frame_buffer[int((x + y * EPD_WIDTH) >> 3)] |= 0x80 >> (x & 0x7)
        
    def draw_char_at(self, frame_buffer, x, y, char, font):
        char_offset = (ord(char) - ord(' ')) * font.height * (int(font.width >> 3) + (1 if font.width & 0x7 else 0))
        offset = 0
        
        for j in range(font.height):
            for i in range(font.width):
                if font.data[char_offset+offset] & (0x80 >> (i & 0x7)):
                    # Previously self.set_pixel(frame_buffer, x + i, y + j) but reoriented
                    # Possible orientations (frame_buffer, y + j, x + i), (frame_buffer, y + j, x - i), (frame_buffer, y + j, x + i)
                    self.set_pixel(frame_buffer, x + i, y + j)
                if i & 0x7 == 7:
                    offset += 1
            if font.width & 0x7 != 0:
                offset += 1

    def display_string_at(self, frame_buffer, x, y, text, font):
        refcolumn = x
        
        # Send the string character by character on EPD
        for index in range(len(text)):
            # print(text[index]) -- Debug for each letter to be displayed
            # Display one character on EPD
            self.draw_char_at(frame_buffer, refcolumn, y, text[index], font)
            # Decrement the column position by 16
            refcolumn += font.width

    def draw_line(self, frame_buffer, x0, y0, x1, y1):
        # Bresenham algorithm
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while((x0 != x1) and (y0 != y1)):
            self.set_pixel(frame_buffer, x0, y0)
            if (2 * err >= dy):
                err += dy
                x0 += sx
            if (2 * err <= dx):
                err += dx
                y0 += sy

    def draw_horizontal_line(self, frame_buffer, x, y, width):
        for i in range(x, x + width):
            self.set_pixel(frame_buffer, i, y)

    def draw_vertical_line(self, frame_buffer, x, y, height):
        for i in range(y, y + height):
            self.set_pixel(frame_buffer, x, i)

    def draw_rectangle(self, frame_buffer, x0, y0, x1, y1):
        min_x = x0 if x1 > x0 else x1
        max_x = x1 if x1 > x0 else x0
        min_y = y0 if y1 > y0 else y1
        max_y = y1 if y1 > y0 else y0
        self.draw_horizontal_line(frame_buffer, min_x, min_y, max_x - min_x + 1)
        self.draw_horizontal_line(frame_buffer, min_x, max_y, max_x - min_x + 1)
        self.draw_vertical_line(frame_buffer, min_x, min_y, max_y - min_y + 1)
        self.draw_vertical_line(frame_buffer, max_x, min_y, max_y - min_y + 1)

    def draw_filled_rectangle(self, frame_buffer, x0, y0, x1, y1):
        min_x = x0 if x1 > x0 else x1
        max_x = x1 if x1 > x0 else x0
        min_y = y0 if y1 > y0 else y1
        max_y = y1 if y1 > y0 else y0
        for i in range(min_x, max_x + 1):
            self.draw_vertical_line(frame_buffer, i, min_y, max_y - min_y + 1)

    def draw_circle(self, frame_buffer, x, y, radius):
        # Bresenham algorithm
        x_pos = -radius
        y_pos = 0
        err = 2 - 2 * radius
        if (x >= self.width or y >= self.height):
            return
        while True:
            self.set_pixel(frame_buffer, x - x_pos, y + y_pos)
            self.set_pixel(frame_buffer, x + x_pos, y + y_pos)
            self.set_pixel(frame_buffer, x + x_pos, y - y_pos)
            self.set_pixel(frame_buffer, x - x_pos, y - y_pos)
            e2 = err
            if (e2 <= y_pos):
                y_pos += 1
                err += y_pos * 2 + 1
                if(-x_pos == y_pos and e2 <= x_pos):
                    e2 = 0
            if (e2 > x_pos):
                x_pos += 1
                err += x_pos * 2 + 1
            if x_pos > 0:
                break

    def draw_filled_circle(self, frame_buffer, x, y, radius):
        # Bresenham algorithm
        x_pos = -radius
        y_pos = 0
        err = 2 - 2 * radius
        if (x >= self.width or y >= self.height):
            return
        while True:
            self.set_pixel(frame_buffer, x - x_pos, y + y_pos)
            self.set_pixel(frame_buffer, x + x_pos, y + y_pos)
            self.set_pixel(frame_buffer, x + x_pos, y - y_pos)
            self.set_pixel(frame_buffer, x - x_pos, y - y_pos)
            self.draw_horizontal_line(frame_buffer, x + x_pos, y + y_pos, 2 * (-x_pos) + 1)
            self.draw_horizontal_line(frame_buffer, x + x_pos, y - y_pos, 2 * (-x_pos) + 1)
            e2 = err
            if (e2 <= y_pos):
                y_pos += 1
                err += y_pos * 2 + 1
                if(-x_pos == y_pos and e2 <= x_pos):
                    e2 = 0
            if (e2 > x_pos):
                x_pos  += 1
                err += x_pos * 2 + 1
            if x_pos > 0:
                break
            
    def draw_bmp(self, frame_buffer, image_path):
        self.draw_bmp_at(frame_buffer, 0, 0, image_path)


    def draw_bmp_at(self, frame_buffer, x, y, image_path):
        if x >= self.width or y >= self.height:
            return

        try:
            with open(image_path, 'rb') as bmp_file:
                header = BitmapHeader(bmp_file.read(BitmapHeader.SIZE_IN_BYTES))
                header_info = BitmapHeaderInfo(bmp_file.read(BitmapHeaderInfo.SIZE_IN_BYTES))
                data_end = header.file_size - 2

                if header_info.width > self.width:
                    widthClipped = self.width
                elif x < 0:
                    widthClipped = header_info.width + x
                else:
                    widthClipped = header_info.width

                if header_info.height > self.height:
                    heightClipped = self.height
                elif y < 0:
                    heightClipped = header_info.height + y
                else:
                    heightClipped = header_info.height

                heightClipped = max(0, min(self.height-y, heightClipped))
                y_offset = max(0, -y)

                if heightClipped <= 0 or widthClipped <= 0:
                    return

                width_in_bytes = int(self.width >> 3)
                if header_info.width_in_bytes > width_in_bytes:
                    rowBytesClipped = width_in_bytes
                else:
                    rowBytesClipped = header_info.width_in_bytes

                for row in range(y_offset, heightClipped):
                    absolute_row = row + y
                    # seek to beginning of line
                    bmp_file.seek(data_end - (row + 1) * header_info.line_width)

                    line = bytearray(bmp_file.read(rowBytesClipped))
                    if header_info.last_byte_padding > 0:
                        mask = 0xFF<<header_info.last_byte_padding & 0xFF
                        line[-1] &= mask

                    for byte_index in range(len(line)):
                        byte = line[byte_index]
                        for i in range(8):
                            if byte & (0x80 >> i):
                                self.set_pixel(frame_buffer, byte_index*8 + i + x, absolute_row)

        except OSError as e:
            print('error: {}'.format(e))



