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
# from smbus import SMBus  # Commented out as I don't believe its required.
from enum import Enum

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
# import OrderedDict

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


class Mode(Enum):
    # Enum class for robot mode/challenge.
    MODE_NONE = 1
    MODE_RC = 2
    MODE_WALL = 3
    MODE_MAZE = 4
    MODE_CALIBRATION = 5


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

        # Mode/Challenge Dictionary
        self.menu_list = OrderedDict((
            (Mode.MODE_NONE, ""),
            (Mode.MODE_RC, "RC"),
            (Mode.MODE_WALL, "Wall"),
            (Mode.MODE_MAZE, "Maze"),
            (Mode.MODE_CALIBRATION, "Calibration")
        ))
        self.current_mode = Mode.MODE_NONE
        self.menu_mode = Mode.MODE_NONE

        # create oled object, nominating the correct I2C bus, default address
        self.oled = ssd1306(VL53L0X.i2cbus)

    def stop_threads(self):
        """ Single point of call to stop any RC or Challenge Threads """
        if self.challenge:
            if (self.current_mode == Mode.MODE_CALIBRATION):
                # Write the config file when exiting the calibration module.
                self.challenge.write_config()

            self.challenge.stop()
            self.challenge = None
            self.challenge_thread = None
            logging.info("Stopping Challenge Thread")
        else:
            logging.info("No Challenge Thread")

        # Reset current mode index
        self.current_mode = Mode.MODE_NONE

        # Safety setting
        self.core.enable_motors(False)

        # Show state on OLED display
        self.show_menu()

    def show_message(self, message):
        """ Show state on OLED display """
        self.oled.cls()  # Clear Screen
        self.oled.canvas.text((10, 10), message, fill=1)
        # Now show the mesasge on the screen
        self.oled.display()

    def get_mode_name(self, mode):
        """ Return appropriate mode name """
        return self.menu_list[mode]

    def show_mode(self):
        """ Display current menu item. """
        # Clear Screen
        self.oled.cls()
        # Get current mode name and display it.
        mode_name = self.get_mode_name(self.current_mode)
        self.oled.canvas.text((10, 10), 'Mode: ' + mode_name, fill=1)
        # Now show the mesasge on the screen
        self.oled.display()

    def get_next_mode(self, mode):
        """ Find the previous menu item """
        mode_index = self.menu_list.keys().index(mode)
        next_index = mode_index + 1
        if next_index >= len(self.menu_list):
            next_index = 0  # Wrapped round to end
        return self.menu_list.keys()[next_index]

    def get_previous_mode(self, mode):
        """ Find the previous menu item """
        mode_index = self.menu_list.keys().index(mode)
        previous_index = mode_index - 1
        if previous_index < 0:
            previous_index = len(self.menu_list) - 1  # Wrapped round to end
        return self.menu_list.keys()[previous_index]

    def show_menu(self):
        """ Display menu. """
        # Clear Screen
        self.oled.cls()
        # Get next and previous list items
        previous_mode = self.get_previous_mode(self.menu_mode)
        next_mode = self.get_next_mode(self.menu_mode)

        # Get mode names and display them.
        current_mode_name = self.get_mode_name(self.current_mode)
        mode_name = self.get_mode_name(self.menu_mode)
        mode_name_up = self.get_mode_name(previous_mode)
        mode_name_down = self.get_mode_name(next_mode)

        # Show list items on LED screen
        self.oled.canvas.text((10, 0), 'TITO 2: ' + current_mode_name, fill=1)
        self.oled.canvas.line(
            (0, 9, self.oled.width - 1, 9),
            outline=1,
            fill=0)
        self.oled.canvas.text((10, 10), 'Mode: ' + mode_name_up, fill=1)
        self.oled.canvas.text((10, 30), 'Mode: ' + mode_name, fill=1)
        self.oled.canvas.text((10, 50), 'Mode: ' + mode_name_down, fill=1)

        # 2x triangles indicating menu direction
        self.oled.canvas.polygon(
            (1, 19, 5, 11, 9, 19, 1, 19),
            outline=1,
            fill=0)
        self.oled.canvas.polygon(
            (1, 59, 5, 51, 9, 59, 1, 59),
            outline=1,
            fill=0)

        # Now show the mesasge on the screen
        self.oled.display()

    def menu_item_pressed(self):
        """ Current menu item pressed. Do something """
        if self.menu_mode == Mode.MODE_NONE:
            self.stop_threads()
        elif self.menu_mode == Mode.MODE_RC:
            self.start_rc_mode()
        elif self.menu_mode == Mode.MODE_WALL:
            logging.info("Wall Mode")
        elif self.menu_mode == Mode.MODE_MAZE:
            logging.info("Maze Mode")
        elif self.menu_mode == Mode.MODE_CALIBRATION:
            self.start_calibration_mode()

    def show_motor_config(self, left):
        """ Show motor/aux config on OLED display """
        if left:
            title = "Left Motor:"
            message = str(self.core.left_servo.servo_min) + '/'\
                + str(self.core.left_servo.servo_mid) + '/'\
                + str(self.core.left_servo.servo_max)
        else:
            title = "Right Motor:"
            message = str(self.core.right_servo.servo_min) + '/'\
                + str(self.core.right_servo.servo_mid) + '/'\
                + str(self.core.right_servo.servo_max)

        self.oled.cls()  # Clear Screen
        self.oled.canvas.text((10, 10), title, fill=1)
        self.oled.canvas.text((10, 30), message, fill=1)
        # Now show the mesasge on the screen
        self.oled.display()

    def show_aux_1_config(self, left):
        """ Show motor/aux config on OLED display """
        if left:
            title = "Left Aux 1:"
            message = str(self.core.left_aux_1_servo.servo_min) + '/'\
                + str(self.core.left_aux_1_servo.servo_mid) + '/'\
                + str(self.core.left_aux_1_servo.servo_max)
        else:
            title = "Right Aux 1:"
            message = str(self.core.right_aux_1_servo.servo_min) + '/'\
                + str(self.core.right_aux_1_servo.servo_mid) + '/'\
                + str(self.core.right_aux_1_servo.servo_max)

        self.oled.cls()  # Clear Screen
        self.oled.canvas.text((10, 10), title, fill=1)
        self.oled.canvas.text((10, 30), message, fill=1)
        # Now show the mesasge on the screen
        self.oled.display()

    def read_config(self):
        # Read the config file when starting up.
        if self.reading_calibration:
            calibration = Calibration.Calibration(
                self.core,
                self.wiimote,
                self)
            calibration.read_config()

    def start_rc_mode(self):
        # Kill any previous Challenge / RC mode
        self.stop_threads()

        # Set Wiimote LED to RC Mode index
        self.current_mode = Mode.MODE_RC

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

    def start_calibration_mode(self):
        # Kill any previous Challenge / RC mode
        self.stop_threads()

        # Set Wiimote LED to RC Mode index
        self.current_mode = Mode.MODE_CALIBRATION

        # Inform user we are about to start RC mode
        logging.info("Entering into Calibration Mode")
        self.challenge = \
            Calibration.Calibration(self.core, self.wiimote, self)

        # Create and start a new thread
        # running the remote control script
        logging.info("Starting Calibration Thread")
        self.challenge_thread = threading.Thread(
            target=self.challenge.run)
        self.challenge_thread.start()
        logging.info("Calibration Thread Running")

    def run(self):
        """ Main Running loop controling bot mode and menu state """
        # Show state on OLED display
        self.show_message('Booting...')

        # Read config file FIRST
        self.read_config()

        self.show_message('Initialising Bluetooth...')

        # Never stop looking for wiimote.
        while not self.killed:
            # Show state on OLED display
            self.oled.cls()  # Clear screen
            self.oled.canvas.text((10, 10), 'Waiting for WiiMote...', fill=1)
            self.oled.canvas.text((10, 30), '***Press 1+2 now ***', fill=1)
            self.oled.display()

            self.wiimote = None
            try:
                self.wiimote = Wiimote()

            except WiimoteException:
                logging.error("Could not connect to wiimote. please try again")

            # Show state on OLED display
            self.show_menu()

            # Constantly check wiimote for button presses
            while self.wiimote:
                buttons_state = self.wiimote.get_buttons()
                classic_buttons_state = self.wiimote.get_classic_buttons()

                if buttons_state is not None:
                    if (buttons_state & cwiid.BTN_A):
                        self.menu_item_pressed()
                        self.show_menu()

                    if (buttons_state & cwiid.BTN_B):
                        # Kill any previous Challenge / RC mode
                        self.stop_threads()

                    if (buttons_state & cwiid.BTN_UP):
                        self.menu_mode = self.get_previous_mode(self.menu_mode)
                        self.show_menu()
                    if (buttons_state & cwiid.BTN_DOWN):
                        self.menu_mode = self.get_next_mode(self.menu_mode)
                        self.show_menu()

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
        launcher.show_message('Exited Python Code')
