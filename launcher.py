#!/usr/bin/env python
import sys
import cwiid
import logging
import time
import threading
from wiimote import Wiimote, WiimoteException
import RPi.GPIO as GPIO

import core
import rc
import Calibration
from lib_oled96 import ssd1306

import VL53L0X
from smbus import SMBus

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


class launcher:
    def __init__(self):
        self.reading_calibration = True

        # Initialise wiimote, will be created at beginning of loop.
        self.wiimote = None
        # Instantiate CORE / Chassis module and store in the launcher.
        self.core = core.Core(VL53L0X.tof_lib)

        GPIO.setwarnings(False)
        self.GPIO = GPIO

        self.challenge = None
        self.challenge_thread = None

        # Shutting down status
        self.shutting_down = False

        self.killed = False

        # WiiMote LED counter to indicate mode
        # NOTE: the int value will be shown as binary on the wiimote.
        self.MODE_NONE = 1
        self.MODE_RC = 2
        self.MODE_WALL = 3
        self.MODE_MAZE = 4
        self.MODE_CALIBRATION = 5

        self.mode = self.MODE_NONE

        # create oled object, nominating the correct I2C bus, default address
        self.oled = ssd1306(VL53L0X.i2cbus)

    def stop_threads(self):
        """ Single point of call to stop any RC or Challenge Threads """
        if self.challenge:
            if self.mode == self.MODE_CALIBRATION:
                # Write the config file when exiting the calibration module.
                self.challenge.write_config()

            self.challenge.stop()
            self.challenge = None
            self.challenge_thread = None
            logging.info("Stopping Challenge Thread")
        else:
            logging.info("No Challenge Thread")

        # Reset LED to NO MODE
        self.mode = self.MODE_NONE
        if self.wiimote and self.wiimote.wm:
            self.wiimote.wm.led = self.mode

        # Safety setting
        self.core.enable_motors(False)

        # Show state on OLED display
        self.show_mode()

    def show_message(self, title='', message=''):
        """ Show state on OLED display """
        # Clear Screen
        self.oled.cls()
        # Show the title
        self.oled.canvas.text((10, 10), title, fill=1)
        # Now show the message on the screen if required
        if message:
            self.oled.canvas.text((10, 30), message, fill=1)

        self.oled.display()

    def show_mode(self):
        """ Show state on OLED display """
        # Show appropriate mode
        mode_map = {
            self.MODE_NONE: '',
            self.MODE_RC: 'RC',
            self.MODE_WALL: 'Wall',
            self.MODE_MAZE: 'Maze',
            self.MODE_CALIBRATION: 'Calibration',
        }
        self.show_message(title='Mode: %s' % mode_map[self.mode])

    def show_motor_config(self, left):
        """ Show motor/aux config on OLED display """
        side_label = 'Left' if left else 'Right'
        title = '%s Motor:' % side_label
        servo = self.core.left_servo if left else self.core.right_servo

        self.display_config(title, servo)

    def show_aux_1_config(self, left):
        """ Show motor/aux config on OLED display """
        side_label = 'Left' if left else 'Right'
        title = '%s Aux 1:' % side_label
        servo = self.core.left_aux_1_servo if left else self.core.right_aux_1_servo

        self.display_config(title, servo)

    def display_config(self, title, servo):
        message = '%d / %d / %d' % (servo.servo_min, servo.servo_mid, servo.servo_max)

        self.show_message(title=title, message=message)

    def read_config(self):
        # Read the config file when starting up.
        if self.reading_calibration:
            calibration = Calibration.Calibration(self.core, self.wiimote, self)
            calibration.read_config()

    def start_rc_mode(self):
        # Kill any previous Challenge / RC mode
        self.stop_threads()

        # Set Wiimote LED to RC Mode index
        self.mode = self.MODE_RC
        if self.wiimote and self.wiimote.wm:
            self.wiimote.wm.led = self.mode

        # Inform user we are about to start RC mode
        logging.info("Entering into RC Mode")
        self.challenge = rc.rc(self.core, self.wiimote)

        # Create and start a new thread
        # running the remote control script
        logging.info("Starting RC Thread")
        self.challenge_thread = threading.Thread(
            target=self.challenge.run)
        self.challenge_thread.start()
        logging.info("RC Thread Running")

        # Show state on OLED display
        self.show_mode()

    def start_calibration_mode(self):
        # Kill any previous Challenge / RC mode
        self.stop_threads()

        # Set Wiimote LED to RC Mode index
        self.mode = self.MODE_CALIBRATION
        if self.wiimote and self.wiimote.wm:
            self.wiimote.wm.led = self.mode

        # Inform user we are about to start RC mode
        logging.info("Entering into Calibration Mode")
        self.challenge = Calibration.Calibration(self.core, self.wiimote, self)

        # Create and start a new thread
        # running the remote control script
        logging.info("Starting Calibration Thread")
        self.challenge_thread = threading.Thread(
            target=self.challenge.run)
        self.challenge_thread.start()
        logging.info("Calibration Thread Running")

        # Show state on OLED display
        self.show_mode()

    def run(self):
        """ Main Running loop controling bot mode and menu state """
        # Show state on OLED display
        self.show_message(title='Booting...')

        # Read config file FIRST
        self.read_config()

        self.show_message(title='Initialising Bluetooth...')

        # Never stop looking for wiimote.
        while not self.killed:
            # Show state on OLED display
            self.show_message(
                title='Waiting for WiiMote...',
                message='***Press 1+2 now ***'
            )

            self.wiimote = None
            try:
                self.wiimote = Wiimote()

            except WiimoteException:
                logging.error("Could not connect to wiimote. please try again")

            # Reset LED to NO MODE
            self.mode = self.MODE_NONE
            if self.wiimote and self.wiimote.wm:
                self.wiimote.wm.led = self.mode

            # Show state on OLED display
            self.show_mode()

            # Constantly check wiimote for button presses
            while self.wiimote:
                buttons_state = self.wiimote.get_buttons()
                classic_buttons_state = self.wiimote.get_classic_buttons()

                if buttons_state is not None:
                    if (buttons_state & cwiid.BTN_A):
                        self.start_rc_mode()

                    if (buttons_state & cwiid.BTN_HOME):
                        self.start_calibration_mode()

                    if (buttons_state & cwiid.BTN_B):
                        # Kill any previous Challenge / RC mode
                        self.stop_threads()

                    if (buttons_state & cwiid.BTN_HOME):
                        self.start_calibration_mode()

                    if (buttons_state & cwiid.BTN_UP):
                        logging.info("BUTTON_UP")
                    if (buttons_state & cwiid.BTN_DOWN):
                        logging.info("BUTTON_DOWN")
                    if (buttons_state & cwiid.BTN_LEFT):
                        logging.info("BUTTON_LEFT")
                    if (buttons_state & cwiid.BTN_RIGHT):
                        logging.info("BUTTON_RIGHT")

                if classic_buttons_state is not None:
                    if (classic_buttons_state & cwiid.CLASSIC_BTN_ZL or
                            classic_buttons_state & cwiid.CLASSIC_BTN_ZR):
                        # One of the Z buttons pressed, disable
                        # motors and set neutral.
                        self.core.enable_motors(False)
                    else:
                        # Neither Z buttons pressed,
                        # allow motors to move freely.
                        self.core.enable_motors(True)

                time.sleep(0.05)

                # Verify Wiimote is connected each loop. If not, set wiimote
                # to None and it "should" attempt to reconnect.
                if not self.wiimote.wm:
                    self.stop_threads()
                    self.wiimote = None


if __name__ == "__main__":
    launcher = launcher()
    try:
        launcher.run()
    except (Exception, KeyboardInterrupt) as e:
        # Stop any active threads before leaving
        launcher.wiimote = None
        launcher.stop_threads()  # This will set neutral for us.
        print("Stopping")
        print(str(e))
        # Show state on OLED display
        launcher.show_message(title='Exited Python Code')
