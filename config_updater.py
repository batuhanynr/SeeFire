import re

with open("/Users/bemres/Desktop/CSE/CENG Project/gitfor/SeeFire/config.py", "r") as f:
    text = f.read()

text = re.sub(r'DHT22_PIN = 4\n', '', text)
text = re.sub(r'MPU6050_ADDR = 0x68\n', '', text)
text = re.sub(r'"DHT22_PIN": DHT22_PIN,\s*', '', text)
text = re.sub(r'MQ2_CS_PIN = 5', 'MQ2_CS_PIN = 5\nMQ2_ADC_CH = 0', text)

with open("/Users/bemres/Desktop/CSE/CENG Project/gitfor/SeeFire/config.py", "w") as f:
    f.write(text)
