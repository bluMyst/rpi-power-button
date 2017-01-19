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

# Used to interact with the blink() thread.
# Set to None to keep a solid LED.
blink_delay = None

def blink(pin, stop_event):
    new_pin_state = False

    event_timeout = blink_delay or 0.5

    while True:
        # TODO: Use events to tell this thread if blink_delay was changed.
        event_timeout = blink_delay or 0.5

        if stop_event.wait(timeout=event_timeout):
            return

        if blink_delay is None:
            new_pin_state = True
        else:
            new_pin_state = not gpio.input(pin)

        gpio.output(pin, new_pin_state)

stop_blinking = threading.Event()

# blinker is a daemon so it won't keep the program alive after a kill signal or
# KeyboardInterrupt.
blinker = threading.Thread(daemon=True, target=(lambda: blink(LED, stop_blinking)))
blinker.start()

while True:
    # This stops signals like KeyboardInterrupt from working when it blocks.

    while gpio.wait_for_edge(BUTTON, gpio.RISING, timeout=500) is None:
        pass

    blink_delay = 0.2
    time.sleep(1)

    # Wait for 500 ms 10 times for a total of 5 seconds.
    for _ in range(10):
        if gpio.wait_for_edge(BUTTON, gpio.RISING, timeout=500) is not None:
            stop_blinking.set()
            blinker.join()
            os.system("poweroff")
            exit(0)

    blink_delay = None
