import spidev, time, statistics

CH = 2  # άλλαζε σε 0/1/2 ανάλογα το κανάλι
spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1000000

def read_ch(ch):
    r = spi.xfer2([1, (8+ch)<<4, 0])
    return ((r[1] & 3) << 8) + r[2]

vals=[]
for _ in range(50):
    vals.append(read_ch(CH))
    time.sleep(0.03)

spi.close()
print("CH", CH, "min", min(vals), "max", max(vals), "median", int(statistics.median(vals)), "avg", sum(vals)/len(vals))