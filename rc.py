import core
import time


class rc:
    def __init__(self, core_module, wm):
        """Class Constructor"""
        self.killed = False
        self.core_module = core_module
        self.wiimote = wm
        self.ticks = 0

        # Store Max joystick values for left/right
        self.l_max_x = -1
        self.l_min_x = -1
        self.l_max_y = -1
        self.l_min_y = -1
        self.r_max_x = -1
        self.r_min_x = -1
        self.r_max_y = -1
        self.r_min_y = -1

    def stop(self):
        """Simple method to stop the RC loop"""
        self.killed = True

    def run(self):
        """ Main Challenge method. Has to exist and is the
            start point for the threaded challenge. """

        # Loop indefinitely, or until this thread is flagged as stopped.
        while self.wiimote and not self.killed:
            # While in RC mode, get joystick states and pass speeds to motors.
            try:
                l_joystick_state = \
                    self.wiimote.get_classic_joystick_state(True)
                r_joystick_state = \
                    self.wiimote.get_classic_joystick_state(False)
            except:
                print("Failed to get Joystick")

            # Get raw joystick values. Using it to calibrate min/max range
            l_joystick_raw_pos = l_joystick_state['state']['raw']
            l_joystick_y, l_joystick_x = l_joystick_raw_pos
            # min/max [X]
            if self.l_max_x == -1:
                self.l_max_x = l_joystick_x
            else:
                self.l_max_x = max(self.l_max_x, l_joystick_x)
            if self.l_min_x == -1:
                self.l_min_x = l_joystick_x
            else:
                self.l_min_x = max(self.l_min_x, l_joystick_x)
            # min/max [Y]
            if self.l_max_y == -1:
                self.l_max_y = l_joystick_x
            else:
                self.l_max_y = max(self.l_max_y, l_joystick_x)
            if self.l_min_y == -1:
                self.l_min_y = l_joystick_x
            else:
                self.l_min_y = max(self.l_min_y, l_joystick_x)

            r_joystick_raw_pos = r_joystick_state['state']['raw']
            r_joystick_y, r_joystick_x = r_joystick_raw_pos
            # min/max [X]
            if self.r_max_x == -1:
                self.r_max_x = r_joystick_x
            else:
                self.r_max_x = max(self.r_max_x, r_joystick_x)
            if self.r_min_x == -1:
                self.r_min_x = r_joystick_x
            else:
                self.r_min_x = max(self.r_min_x, r_joystick_x)
            # min/max [Y]
            if self.r_max_y == -1:
                self.r_max_y = r_joystick_x
            else:
                self.r_max_y = max(self.r_max_y, r_joystick_x)
            if self.r_min_y == -1:
                self.r_min_y = r_joystick_x
            else:
                self.r_min_y = max(self.r_min_y, r_joystick_x)

            print("Left raw X[{},{}] Y[{},{}]".format(
                self.r_min_x,
                self.r_max_x,
                self.r_min_y,
                self.r_max_y)
            )
            print("Right raw X[{},{}] Y[{},{}]".format(
                self.r_min_x,
                self.r_max_x,
                self.r_min_y,
                self.r_max_y)
            )

            # Annotate joystick states to screen
            # if l_joystick_state:
            #     print("l_joystick_state: {}".format(l_joystick_state))
            # if r_joystick_state:
            #     print("r_joystick_state: {}".format(r_joystick_state))

            # Grab normalised x,y / steering,throttle
            # from left and right joysticks.
            l_joystick_pos = l_joystick_state['state']['normalised']
            l_throttle, l_steering = l_joystick_pos
            r_joystick_pos = r_joystick_state['state']['normalised']
            r_throttle, r_steering = r_joystick_pos

            self.core_module.throttle(self.l_throttle, self.r_throttle)
            # print ("Motors %f, %f" % (self.l_throttle, self.r_throttle))

            # Sleep between loops to allow other stuff to
            # happen and not over burden Pi and Arduino.
            time.sleep(0.5)


if __name__ == "__main__":
    core = core.Core()
    rc = rc(core)
    try:
        rc.run_auto()
    except (KeyboardInterrupt) as e:
        # except (Exception, KeyboardInterrupt) as e:
        # Stop any active threads before leaving
        rc.stop()
        core.set_neutral()
        print("Quitting")
