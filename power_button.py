#!/usr/bin/python3

import RPi.GPIO as gpio
import signal
import threading
import time
import os

# Press the button twice in a row and it'll shut everything down for you.

# BE ABSOLUTELY SURE THAT YOU'RE USING:
# GPIO 3: LED
# GPIO 4: Button
# Otherwise shit will probably explode or something idfk.
LED = 3
BUTTON = 4

# Use GPIO numbers and not pin numbers because they're different for some
# fucking reason.
gpio.setmode(gpio.BCM)

# We need to use a pulldown resistor on the button because electronics is
# bullshit.
gpio.setup(BUTTON, gpio.IN, gpio.PUD_DOWN)
gpio.setup(LED, gpio.OUT)


# Be 100% sure to clean up before exiting.
def cleanup(sig, stack_frame):
    print("Cleaning up... ", end='')
    gpio.cleanup()
    print("done!")
    exit(0)

for sig in [signal.SIGTERM, signal.SIGINT]:
    signal.signal(sig, cleanup)

class Blinker(object):
    # How often should we check for self.solid to stop being False? Only
    # applies if it's true. In milliseconds.
    SOLID_CHECK_FREQ = 500

    def __init__(self, pin, interrupt=None):
        """ Blinks an LED in its own thread.

        pin: The pin number of the LED.

        interrupt: An event that tells the blinker class to stop its sleep to
            handle something. Either exit the program or change blinking
            patterns.
        """
        self.pin = pin

        self.interrupt = interrupt or threading.Event()

        # If interrupt is set and so is this, we know we're supposed to kill
        # the thread.
        self.kill_thread = False

        self.blink_thread = threading.Thread(daemon=True, target=self.blink)

    def set_led(self, value):
        """ This is here so you can monkey-patch it for debugging. """
        gpio.output(self.pin, value)

    def get_led(self):
        """ Ditto. """
        return gpio.input(self.pin)

    def set_pattern(self, blink_delay=None):
        """ Set the blinking pattern.

        blink_delay: Wait this many milliseconds between blinks. If this is
            None, keep the light solid instead of blinking it.
        """
        if blink_delay == None:
            self.solid = True
            self.blink_delay = self.SOLID_CHECK_FREQ
        else:
            self.solid = False
            self.blink_delay = blink_delay

        self.interrupt.set()

    def start_blinking(self, *args, **kwargs):
        """ Start a thread that'll blink the LED for you.

        See set_pattern for arg info.
        """
        self.set_pattern(*args, **kwargs)
        self.blink_thread.start()

    def stop_blinking(self):
        """ Signal blink_thread to stop. Blocks until it's done. """
        self.kill_thread = True
        self.interrupt.set()
        self.blink_thread.join()

    def blink(self):
        while True:
            if self.interrupt.wait(self.blink_delay):
                self.interrupt.clear()

                if self.kill_thread:
                    self.kill_thread = False
                    self.set_led(gpio.LOW)
                    return

            if self.solid:
                self.set_led(gpio.HIGH)
            else:
                self.set_led(not self.get_led())

class ButtonHandler(object):
    # The blinking patterns to use in safe and unsafe mode.
    # See Blinker.set_pattern
    SAFE_BLINK = None
    UNSAFE_BLINK = 500

    def __init__(self, button_pin):
        self.button_pin = button_pin
        self.blinker = Blinker(self.button_pin)
        self.blinker.start_blinking()

        # The power switch has two modes: In safe mode, the LED is solid and
        # everything is good. A press of the button brings us to unsafe mode.
        # In unsafe mode, the LED blinks and a button press will power off the
        # system. Basically, the second button press is like an "are you sure"?
        self._safe_mode = True

    def start_monitoring(self):
        gpio.add_event_detect(self.button_pin, gpio.RISING, self.handle_button)

    def stop_monitoring(self):
        """ CAUTION: This removes all listeners on the button_pin. """
        gpio.remove_event_detect(self.button_pin)

    @property
    def safe_mode(self):
        return self._safe_mode

    @safe_mode.setter
    def safe_mode(self, value):
        value = bool(value)

        if self._safe_mode != value:
            self._safe_mode = value
            self.blinker.set_pattern(
                self.SAFE_BLINK if self.safe_mode else self.UNSAFE_BLINK)

    def handle_button(self):
        if not self.safe_mode:
            self.blinker.stop_blinking()
            os.system("poweroff")
            exit(0)
        else:
            def threaded_stuff():
                self.safe_mode = False
                time.sleep(5)
                self.safe_mode = True
            threading.Thread(daemon=True, target=threaded_stuff).start()

bh = ButtonHandler()
bh.start_monitoring()

while True:
    input()
