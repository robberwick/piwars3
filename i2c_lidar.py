#!/usr/bin/python

import time
import VL53L0X
import RPIO

# Turn off all VL53L0X devices
def xshut(gpios):
    """ Turn off all VL53L0X devices.

        Takes a list of GPIO pins the devices' XSHUT ports are connected to,
        and brings each one to 0 volts (low) """
    for x in gpios:
        RPIO.setup(x, RPIO.OUT, initial = 0)

# Turn on a specific device
def create(gpio, addr):
    """ Turn on a specific device (by GPIO pin which its XSHUT port is connected
        to), create a VL53L0X object for it, and start it in constant ranging
        mode.

        Unresets the chip by making the GPIO a high-impedence input, so that the
        pull-up resister on the LIDAR board can bring XSHUT high.

        Don't set the address to 0x29 if there are any more devices to do. Chaos
        will ensue. """
    RPIO.setup(gpio, RPIO.IN)        # Unreset the pin
    time.sleep(0.002)                # Wait for chip to wake

    # Create a VL53L0X object
    tof = VL53L0X.VL53L0X(address = addr)
    tof.start_ranging(VL53L0X.VL53L0X_LONG_RANGE_MODE)

    return tof