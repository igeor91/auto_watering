#!/usr/bin/env python3
from time import sleep
from gpiozero import OutputDevice

RELAY_PIN = 19

# Δοκίμασε πρώτα active_high=False (συνήθως relay active-low)
relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)

print("OFF 2s")
relay.off()
sleep(2)

print("ON 3s")
relay.on()
sleep(3)

print("OFF")
relay.off()
sleep(1)

print("Done")
