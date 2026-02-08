from gpiozero import LED
from time import sleep

led = LED(17)  # BCM GPIO17 (physical 11)
for _ in range(5):
    led.on(); sleep(0.5)
    led.off(); sleep(0.5)
print("ok")