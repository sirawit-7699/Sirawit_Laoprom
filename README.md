## 🎥 วิดีโอสาธิตการใช้งานเว็บไซต์
[![วิดีโอแนะนำการใช้งานเว็บไซต์]([https://www.youtube.com/watch?v=VIDEO_ID](https://youtu.be/d3gfSq6hbmk))
คลิกที่ Link เพื่อรับชมวิดีโอบน YouTube
# IoT Weather Station

โครงงานสถานีตรวจวัดสภาพอากาศด้วยเทคโนโลยี Internet of Things (IoT)  
พัฒนาขึ้นเพื่อเก็บข้อมูลสภาพอากาศจากเซนเซอร์ภายในพื้นที่จริง ส่งข้อมูลผ่าน MQTT และนำข้อมูลมาประมวลผลเพื่อแสดงผลผ่านเว็บแอปพลิเคชัน รวมถึงเปรียบเทียบกับข้อมูลจากกรมอุตุนิยมวิทยา (TMD)

---

## Objectives

1. เพื่อสร้างสถานีตรวจวัดสภาพอากาศด้วยเทคโนโลยี IoT
2. เพื่อพัฒนาเว็บแอปพลิเคชันสำหรับแสดงผลข้อมูลสภาพอากาศ
3. เพื่อเปรียบเทียบข้อมูลสภาพอากาศที่ตรวจวัดได้จริงในพื้นที่กับข้อมูลจากกรมอุตุนิยมวิทยา

---

## System Overview

การทำงานหลักของระบบมีลำดับดังนี้

```text
Weather Sensors
      |
      v
    ESP32
      |
      | MQTT
      v
HiveMQ Cloud
      |
      v
   Node-RED
      |
      | Hourly Average
      v
MongoDB Local / MongoDB Atlas
      |
      v
Flask Web Application
      |
      +---- Sensor Dashboard
      +---- Sensor History
      +---- TMD Forecast
      +---- Sensor vs TMD Comparison
```

ข้อมูลจากเซนเซอร์จะถูกส่งจาก ESP32 ไปยัง MQTT Broker จากนั้น Node-RED จะรับและสะสมข้อมูล เพื่อนำมาคำนวณค่าเฉลี่ยรายชั่วโมงก่อนบันทึกลงฐานข้อมูล MongoDB

ข้อมูลจากกรมอุตุนิยมวิทยาจะถูกดึงและจัดเก็บแยกจากข้อมูลเซนเซอร์ เพื่อนำมาใช้ในการเปรียบเทียบภายในเว็บแอปพลิเคชัน

---

## Hardware

อุปกรณ์หลักที่ใช้ในโครงงาน

| Device | Function |
|---|---|
| ESP32 | ไมโครคอนโทรลเลอร์หลักและเชื่อมต่อ Wi-Fi |
| BME280 | วัดอุณหภูมิ ความชื้น และความกดอากาศ |
| MQ-135 | ประมาณค่าความเข้มข้นของก๊าซ CO₂ |
| LDR | ประมาณค่าความเข้มแสง |
| Wind Speed Sensor | ตรวจวัดความเร็วลม |
| Solar Panel | แหล่งพลังงานสำหรับระบบ |
| 12V Battery | จัดเก็บพลังงานสำหรับใช้งานช่วงไม่มีแสงแดด |

> **Note:** ค่า CO₂ จาก MQ-135 และค่า Lux จาก LDR เป็นค่าประมาณจากการคำนวณและการปรับเทียบ ไม่ใช่ค่าจากเครื่องมือวัดมาตรฐานโดยตรง

---

## Sensor Pin Configuration

| Sensor | ESP32 Pin |
|---|---|
| BME280 SDA | GPIO 21 |
| BME280 SCL | GPIO 22 |
| MQ-135 Analog Output | GPIO 34 |
| LDR Analog Output | GPIO 35 |
| Wind Sensor Analog Output | GPIO 32 |

---

## Technologies

### Hardware / Embedded

- ESP32
- Arduino IDE
- C/C++
- BME280
- MQ-135
- LDR
- Wind Speed Sensor

### Communication

- Wi-Fi
- MQTT
- HiveMQ Cloud

### Backend / Processing

- Node-RED
- Python
- Flask

### Database

- MongoDB Local
- MongoDB Atlas

### Frontend

- HTML
- CSS
- JavaScript

### External Data

- Thai Meteorological Department (TMD)

---

## Repository Structure

```text
iot-weather-station/
│
├── esp32/
│   └── weatherstation.ino
│
├── node-red/
│   └── Node-Red.json
│
├── web/
│   ├── app.py
│   ├── requirements.txt
│   ├── tmd_collector.py
│   │
│   ├── static/
│   │   ├── weather.css
│   │   └── weather.js
│   │
│   └── templates/
│       ├── _filter.html
│       ├── _pagination.html
│       ├── base.html
│       ├── compare.html
│       ├── history.html
│       ├── index.html
│       ├── records.html
│       └── tmd.html
│
├── .env.example
├── .gitignore
└── README.md
```

---

## ESP32

ไฟล์โปรแกรมหลักอยู่ที่

```text
esp32/weatherstation.ino
```

ESP32 ทำหน้าที่

- อ่านข้อมูลจากเซนเซอร์
- เชื่อมต่อ Wi-Fi
- คำนวณค่าที่จำเป็นจาก Analog Sensor
- สร้างข้อมูลในรูปแบบ JSON
- ส่งข้อมูลไปยัง HiveMQ Cloud ผ่าน MQTT

ตัวอย่างข้อมูลที่ส่งผ่าน MQTT

```json
{
  "temperature": 30.5,
  "humidity": 65.2,
  "pressure": 992.4,
  "mq135": 520.3,
  "ldr_raw": 1200,
  "lux": 850.5,
  "wind_speed": 2.350
}
```

---

## Node-RED

Node-RED ทำหน้าที่รับข้อมูลจาก MQTT และประมวลผลข้อมูลก่อนจัดเก็บใน MongoDB

Flow หลัก

```text
Weather MQTT
     |
     v
    JSON
     |
     v
Collect Hourly Data
     |
     v
Store samples temporarily
```

เมื่อครบช่วงเวลาที่กำหนด

```text
Every 1 Hour
     |
     v
Calculate Hourly Average
     |
     v
Prepare MongoDB
     |
     +---- MongoDB Local
     |
     +---- MongoDB Atlas
```

ค่าที่นำมาหาค่าเฉลี่ยรายชั่วโมงประกอบด้วย

- Temperature
- Humidity
- Pressure
- Estimated CO₂
- Lux
- Wind Speed

จากนั้นระบบจะจัดเก็บข้อมูลหนึ่งรายการต่อหนึ่งชั่วโมงเพื่อใช้ในการแสดงผลและเปรียบเทียบกับข้อมูลจาก TMD

---

## MongoDB

ฐานข้อมูลหลัก

```text
weather_db
```

Collection สำหรับข้อมูลจากสถานีตรวจวัด

```text
test_sensor
```

ตัวอย่างข้อมูล

```json
{
  "station_id": "station01",
  "timestamp": "2026-09-27T16:00:00",
  "temperature": 32.14,
  "humidity": 56.27,
  "pressure": 988.07,
  "ppm": 529.46,
  "lux": 2934.68,
  "wind_speed": 1.62
}
```

ระบบรองรับการบันทึกข้อมูลไปยัง

- MongoDB Local
- MongoDB Atlas

---

## TMD Weather Data

ไฟล์

```text
web/tmd_collector.py
```

ใช้สำหรับดึงข้อมูลสภาพอากาศจากกรมอุตุนิยมวิทยา และจัดเก็บข้อมูลเพื่อนำมาใช้เปรียบเทียบกับค่าที่ตรวจวัดจากสถานี

ข้อมูลหลักที่นำมาเปรียบเทียบ ได้แก่

- Temperature
- Humidity
- Atmospheric Pressure
- Wind Speed

---

## Web Application

เว็บแอปพลิเคชันพัฒนาด้วย Flask

ไฟล์หลัก

```text
web/app.py
```

หน้าเว็บประกอบด้วย

### Dashboard

แสดงข้อมูลสภาพอากาศจากสถานีตรวจวัด

### Sensor History

แสดงข้อมูลย้อนหลังจากเซนเซอร์

### TMD Forecast

แสดงข้อมูลจากกรมอุตุนิยมวิทยา

### Sensor vs TMD Comparison

เปรียบเทียบข้อมูลจากสถานีตรวจวัดกับข้อมูลกรมอุตุนิยมวิทยาในช่วงเวลาเดียวกัน

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/sirawit-7699/iot-weather-station.git
cd iot-weather-station
```

---

### 2. Install Python Dependencies

```bash
pip install -r web/requirements.txt
```

---

### 3. Configure Environment Variables

สร้างไฟล์ `.env` จาก `.env.example`

ตัวอย่าง

```env
MONGODB_URI=YOUR_MONGODB_CONNECTION_STRING
```

> ห้ามอัปโหลดข้อมูล Username/Password จริงขึ้น GitHub

---

### 4. Configure ESP32

แก้ไขข้อมูลการเชื่อมต่อภายในเครื่องของผู้ใช้งาน เช่น

```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

const char* mqtt_server = "YOUR_HIVEMQ_SERVER";
const char* mqtt_username = "YOUR_MQTT_USERNAME";
const char* mqtt_password = "YOUR_MQTT_PASSWORD";
```

จากนั้น Upload โปรแกรมเข้าสู่ ESP32 ด้วย Arduino IDE

---

### 5. Import Node-RED Flow

เปิด Node-RED และเลือก

```text
Menu
→ Import
→ Clipboard / File
```

จากนั้น Import

```text
node-red/Node-Red.json
```

แล้วกำหนดค่าการเชื่อมต่อ

- HiveMQ Cloud
- MongoDB Local
- MongoDB Atlas

ให้ตรงกับระบบที่ใช้งาน

---

### 6. Run TMD Collector

```bash
python web/tmd_collector.py
```

---

### 7. Run Flask Web Application

```bash
python web/app.py
```

จากนั้นเปิดเว็บเบราว์เซอร์ไปยัง Address ที่ Flask แสดงใน Terminal

---

## Data Processing

ระบบไม่ได้บันทึกทุกข้อมูลจาก ESP32 ลง MongoDB โดยตรง

Node-RED จะสะสมข้อมูลจาก MQTT และคำนวณค่าเฉลี่ยรายชั่วโมง

ตัวอย่าง

```text
Sensor samples during 13:00 - 13:59
              |
              v
      Hourly Average
              |
              v
Timestamp = 13:00
              |
              v
          MongoDB
```

วิธีนี้ช่วยลดจำนวนข้อมูลในฐานข้อมูล และทำให้ข้อมูลมีช่วงเวลาเหมาะสมสำหรับการเปรียบเทียบกับข้อมูลสภาพอากาศรายชั่วโมงของกรมอุตุนิยมวิทยา

---

## Security

Repository นี้ไม่จัดเก็บข้อมูลสำคัญ เช่น

- Wi-Fi Password
- MQTT Password
- MongoDB Username / Password
- MongoDB Connection URI ที่มี Credential

ค่าดังกล่าวจะต้องกำหนดโดยผู้ใช้งานก่อนใช้งานระบบ

---

## Project Status

ระบบสามารถ

- ตรวจวัดข้อมูลจากเซนเซอร์
- ส่งข้อมูลผ่าน MQTT
- ประมวลผลข้อมูลด้วย Node-RED
- คำนวณค่าเฉลี่ยรายชั่วโมง
- บันทึกข้อมูลลง MongoDB
- ดึงข้อมูลจากกรมอุตุนิยมวิทยา
- แสดงข้อมูลผ่านเว็บแอปพลิเคชัน
- แสดงข้อมูลย้อนหลัง
- เปรียบเทียบข้อมูล Sensor กับข้อมูล TMD

---

## Author

Final Year Project  
IoT Weather Station
