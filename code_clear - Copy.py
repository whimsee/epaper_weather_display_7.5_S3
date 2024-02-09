import board, busio, time, alarm, gc, wifi
import waveshare75


# E-ink pins
reset = board.D9
dc = board.D6
busy = board.D10
cs = board.D5
clk = board.SCK
mosi = board.MOSI
epd = waveshare75.EPD(reset, dc, busy, cs, clk, mosi)
#### ------- ###


## Setup ##
print(gc.mem_free())
fb_size = int(epd.width * epd.height >> 3)
frame_black = bytearray(fb_size)

epd.init()
epd.Clear_black()
time.sleep(2)
epd.sleep()
time.sleep(3)
