#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

#include <math.h>

// ======================================================
// WiFi
// ======================================================

const char* ssid = "XXXX";
const char* password = "XXXX";

// ======================================================
// HiveMQ Cloud
// ======================================================

const char* mqtt_server = "XXXX";
const int mqtt_port = XXXX;

const char* mqtt_username = "XXXX";
const char* mqtt_password = "XXXX";

const char* mqtt_topic =
  "XXXX";

// ======================================================
// MQTT
// ======================================================

WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);

// ======================================================
// SENSOR PINS
// ======================================================

// BME280
#define I2C_SDA 21
#define I2C_SCL 22

// Analog
#define PIN_MQ135 34
#define PIN_LDR_AO 35
#define PIN_WIND 32

Adafruit_BME280 bme;


const unsigned long WIFI_RETRY_INTERVAL = 10000;


const unsigned long MQTT_RETRY_INTERVAL = 5000;


const unsigned long PUBLISH_INTERVAL = 10000;

unsigned long lastWiFiAttempt = 0;
unsigned long lastMQTTAttempt = 0;
unsigned long lastPublish = 0;

// ======================================================
// MQ-135
// ======================================================

const float MQ_VC = 5.0;


const float MQ_RL_MODULE = 1.0;


const float MQ_DIV_R1 = 10.0;
const float MQ_DIV_R2 = 10.0;

const float MQ_DIV_GAIN =
  (MQ_DIV_R1 + MQ_DIV_R2) /
  MQ_DIV_R2;

const float MQ_DIV_LOAD =
  MQ_DIV_R1 +
  MQ_DIV_R2;


const float MQ_RL_EFFECTIVE =
  (MQ_RL_MODULE * MQ_DIV_LOAD) /
  (MQ_RL_MODULE + MQ_DIV_LOAD);


const float MQ_R0 = 3.901;


const float MQ_PARA = 116.6020682;
const float MQ_PARB = 2.769034857;

// ======================================================
// LDR
// ======================================================

const float LDR_SUPPLY_VOLTAGE = 3.3;

const float LDR_FIXED_RESISTOR =
  10000.0;

const int LDR_DARK_RAW = 4080;

const float WIND_DIVIDER_GAIN = 3.0;


const float WIND_ZERO_VOLTAGE = 0.80;

const float WIND_MAX_VOLTAGE = 5.00;

const float WIND_MAX_SPEED = 30.0;

// ======================================================
// ANALOG STRUCT
// ======================================================

struct AnalogReading {
  float raw;
  float milliVolts;
};

// ======================================================
// ANALOG AVERAGE
// ======================================================

AnalogReading readAnalogAverage(
  int pin,
  int samples,
  int sampleDelayMs
) {

  uint32_t rawSum = 0;
  uint32_t mvSum = 0;

  for (int i = 0; i < samples; i++) {

    rawSum += analogRead(pin);

    mvSum += analogReadMilliVolts(pin);

    delay(sampleDelayMs);
  }

  AnalogReading reading;

  reading.raw =
    rawSum / (float)samples;

  reading.milliVolts =
    mvSum / (float)samples;

  return reading;
}

// ======================================================
// START WIFI
// ======================================================

void startWiFi() {

  Serial.print("Connecting WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);

  WiFi.persistent(false);

  WiFi.setAutoReconnect(true);

  WiFi.setSleep(false);

  WiFi.begin(
    ssid,
    password
  );
}

// ======================================================
// MQTT CONNECT
// ======================================================

void connectMQTT() {

  if (
    WiFi.status() != WL_CONNECTED ||
    mqttClient.connected()
  ) {
    return;
  }

  uint64_t chipId =
    ESP.getEfuseMac();

  char clientId[40];

  snprintf(
    clientId,
    sizeof(clientId),
    "ESP32-Weather-%04X%08X",
    (uint16_t)(chipId >> 32),
    (uint32_t)chipId
  );

  Serial.print(
    "Connecting HiveMQ Cloud... "
  );

  bool connected =
    mqttClient.connect(
      clientId,
      mqtt_username,
      mqtt_password
    );

  if (connected) {

    Serial.println("CONNECTED!");

  } else {

    Serial.print(
      "FAILED! MQTT state = "
    );

    Serial.println(
      mqttClient.state()
    );
  }
}

// ======================================================
// SETUP
// ======================================================

void setup() {

  Serial.begin(115200);

  delay(1500);

  Serial.println();
  Serial.println(
    "================================"
  );
  Serial.println(
    "ESP32 Weather Station"
  );
  Serial.println(
    "================================"
  );

  // ====================================================
  // WiFi Event
  // ====================================================

  WiFi.onEvent(

    [](WiFiEvent_t event,
       WiFiEventInfo_t info) {

      Serial.printf(
        "\n[WiFi event] disconnected, reason=%u\n",
        info.wifi_sta_disconnected.reason
      );

    },

    ARDUINO_EVENT_WIFI_STA_DISCONNECTED
  );

  startWiFi();

  // ====================================================
  // TLS
  // ====================================================

  wifiClient.setInsecure();

  // ====================================================
  // MQTT
  // ====================================================

  mqttClient.setServer(
    mqtt_server,
    mqtt_port
  );

  mqttClient.setKeepAlive(30);

  mqttClient.setSocketTimeout(5);

  mqttClient.setBufferSize(512);

  // ====================================================
  // I2C
  // ====================================================

  Wire.begin(
    I2C_SDA,
    I2C_SCL
  );

  // ====================================================
  // BME280
  // ====================================================

  bool bmeOK = false;

  if (
    bme.begin(
      0x76,
      &Wire
    )
  ) {

    Serial.println(
      "BME280 found at 0x76"
    );

    bmeOK = true;

  } else if (
    bme.begin(
      0x77,
      &Wire
    )
  ) {

    Serial.println(
      "BME280 found at 0x77"
    );

    bmeOK = true;
  }

  if (!bmeOK) {

    Serial.println(
      "ERROR: BME280 not found!"
    );

    while (1) {
      delay(1000);
    }
  }

  // ====================================================
  // MQ135
  // ====================================================

  pinMode(
    PIN_MQ135,
    INPUT
  );

  analogSetPinAttenuation(
    PIN_MQ135,
    ADC_11db
  );

  // ====================================================
  // LDR
  // ====================================================

  pinMode(
    PIN_LDR_AO,
    INPUT
  );

  analogSetPinAttenuation(
    PIN_LDR_AO,
    ADC_11db
  );

  // ====================================================
  // WIND
  // ====================================================

  pinMode(
    PIN_WIND,
    INPUT
  );

  analogSetPinAttenuation(
    PIN_WIND,
    ADC_11db
  );

  // ====================================================
  // INFO
  // ====================================================

  Serial.println(
    "Sensors initialized"
  );

  Serial.print(
    "MQ135 R0 = "
  );

  Serial.print(
    MQ_R0,
    3
  );

  Serial.println(
    " kOhm"
  );

  Serial.print(
    "Wind Zero Voltage = "
  );

  Serial.print(
    WIND_ZERO_VOLTAGE,
    2
  );

  Serial.println(
    " V"
  );

  Serial.println(
    "Wind Dead Zone = DISABLED"
  );

  Serial.println(
    "MQTT Publish = every 10 seconds"
  );

  Serial.println(
    "System ready!"
  );


  lastPublish = millis();
}

// ======================================================
// PUBLISH WEATHER
// ======================================================

void publishWeatherData() {

  // ====================================================
  // BME280
  // ====================================================

  float temperature =
    bme.readTemperature();

  float humidity =
    bme.readHumidity();

  float pressure =
    bme.readPressure() /
    100.0F;

  if (
    isnan(temperature) ||
    isnan(humidity) ||
    isnan(pressure)
  ) {

    Serial.println(
      "BME280 read error!"
    );

    return;
  }

  // ====================================================
  // MQ135
  // ====================================================

  AnalogReading mqReading =
    readAnalogAverage(
      PIN_MQ135,
      20,
      5
    );

  int mq135_raw =
    (int)round(
      mqReading.raw
    );

  float mqAdcVoltage =
    mqReading.milliVolts /
    1000.0;

  float mqVoltage =
    mqAdcVoltage *
    MQ_DIV_GAIN;

  float mqRs = -1.0;
  float mqRatio = -1.0;
  float co2_ppm = 0.0;

  bool mqValid = false;

  if (
    mqVoltage > 0.01 &&
    mqVoltage < MQ_VC
  ) {

    mqRs =
      MQ_RL_EFFECTIVE *
      (
        (MQ_VC / mqVoltage)
        - 1.0
      );

    if (mqRs > 0) {

      mqRatio =
        mqRs /
        MQ_R0;

      if (mqRatio > 0) {

        co2_ppm =
          MQ_PARA *
          pow(
            mqRatio,
            -MQ_PARB
          );

        if (
          !isnan(co2_ppm) &&
          !isinf(co2_ppm) &&
          co2_ppm >= 0
        ) {

          mqValid = true;
        }
      }
    }
  }

  // ====================================================
  // LDR
  // ====================================================

  AnalogReading ldrReading =
    readAnalogAverage(
      PIN_LDR_AO,
      20,
      3
    );

  int ldr_raw =
    (int)round(
      ldrReading.raw
    );

  float ldrVoltage =
    ldr_raw *
    (
      LDR_SUPPLY_VOLTAGE /
      4095.0
    );

  float lux = 0.0;

  if (
    ldr_raw >=
    LDR_DARK_RAW
  ) {

    lux = 0.0;

  } else {

    ldrVoltage =
      constrain(
        ldrVoltage,
        0.01,
        3.29
      );

    float ldrResistance =
      LDR_FIXED_RESISTOR *
      ldrVoltage /
      (
        LDR_SUPPLY_VOLTAGE -
        ldrVoltage
      );

    if (
      ldrResistance > 0
    ) {

      lux =
        pow(
          (
            500000.0 /
            ldrResistance
          ),
          1.4
        );
    }

    if (
      isnan(lux) ||
      isinf(lux) ||
      lux < 0
    ) {

      lux = 0.0;
    }
  }

  // ====================================================
  // WIND
  // ====================================================

  AnalogReading windReading =
    readAnalogAverage(
      PIN_WIND,
      20,
      5
    );

  int wind_raw =
    (int)round(
      windReading.raw
    );

  // Voltage ที่ GPIO32
  float windAdcVoltage =
    windReading.milliVolts /
    1000.0;

  // ย้อน divider x3
  float windSensorVoltage =
    windAdcVoltage *
    WIND_DIVIDER_GAIN;

  float wind_speed = 0.0;


  if (
    windSensorVoltage <=
    WIND_ZERO_VOLTAGE
  ) {

    wind_speed = 0.0;

  } else {

    wind_speed =
      (
        (
          windSensorVoltage -
          WIND_ZERO_VOLTAGE
        )
        /
        (
          WIND_MAX_VOLTAGE -
          WIND_ZERO_VOLTAGE
        )
      )
      *
      WIND_MAX_SPEED;
  }

  wind_speed =
    constrain(
      wind_speed,
      0.0,
      WIND_MAX_SPEED
    );

  // ====================================================
  // JSON
  // ====================================================

  String json;

  json.reserve(300);

  json = "{";

  json +=
    "\"temperature\":";

  json +=
    String(
      temperature,
      1
    );

  json +=
    ",\"humidity\":";

  json +=
    String(
      humidity,
      1
    );

  json +=
    ",\"pressure\":";

  json +=
    String(
      pressure,
      1
    );

  // MQ135 = Estimated CO2
  json +=
    ",\"mq135\":";

  if (mqValid) {

    json +=
      String(
        co2_ppm,
        1
      );

  } else {

    json += "null";
  }

  // LDR raw
  json +=
    ",\"ldr_raw\":";

  json +=
    String(
      ldr_raw
    );

  // Lux
  json +=
    ",\"lux\":";

  json +=
    String(
      lux,
      1
    );

  // Wind
  json +=
    ",\"wind_speed\":";

  json +=
    String(
      wind_speed,
      3
    );

  json += "}";

  // ====================================================
  // MQTT PUBLISH
  // ====================================================

  bool success =
    mqttClient.publish(
      mqtt_topic,
      json.c_str()
    );

  // ====================================================
  // SERIAL
  // ====================================================

  Serial.println();

  Serial.println(
    "========================================"
  );

  // BME
  Serial.print(
    "Temperature: "
  );
  Serial.print(
    temperature,
    2
  );
  Serial.println(" C");

  Serial.print(
    "Humidity: "
  );
  Serial.print(
    humidity,
    2
  );
  Serial.println(" %");

  Serial.print(
    "Pressure: "
  );
  Serial.print(
    pressure,
    2
  );
  Serial.println(" hPa");

  // MQ135
  Serial.println();
  Serial.println(
    "--- MQ-135 ---"
  );

  Serial.print(
    "RAW: "
  );
  Serial.println(
    mq135_raw
  );

  Serial.print(
    "ADC Voltage: "
  );
  Serial.print(
    mqAdcVoltage,
    3
  );
  Serial.println(" V");

  Serial.print(
    "AO Voltage: "
  );
  Serial.print(
    mqVoltage,
    3
  );
  Serial.println(" V");

  if (mqValid) {

    Serial.print(
      "Estimated CO2: "
    );

    Serial.print(
      co2_ppm,
      1
    );

    Serial.println(
      " ppm"
    );

  } else {

    Serial.println(
      "MQ135 reading invalid"
    );
  }

  // LDR
  Serial.println();
  Serial.println(
    "--- LDR ---"
  );

  Serial.print(
    "RAW: "
  );
  Serial.println(
    ldr_raw
  );

  Serial.print(
    "Voltage: "
  );
  Serial.print(
    ldrVoltage,
    3
  );
  Serial.println(
    " V"
  );

  Serial.print(
    "Estimated Lux: "
  );
  Serial.print(
    lux,
    1
  );
  Serial.println(
    " lux"
  );

  // WIND
  Serial.println();
  Serial.println(
    "--- WIND ---"
  );

  Serial.print(
    "RAW: "
  );
  Serial.println(
    wind_raw
  );

  Serial.print(
    "ADC Voltage: "
  );
  Serial.print(
    windAdcVoltage,
    3
  );
  Serial.println(
    " V"
  );

  Serial.print(
    "Sensor Voltage: "
  );
  Serial.print(
    windSensorVoltage,
    3
  );
  Serial.println(
    " V"
  );

  Serial.print(
    "Zero Voltage: "
  );
  Serial.print(
    WIND_ZERO_VOLTAGE,
    2
  );
  Serial.println(
    " V"
  );

  Serial.print(
    "Wind Speed: "
  );
  Serial.print(
    wind_speed,
    3
  );
  Serial.println(
    " m/s"
  );

  // MQTT
  Serial.println();

  if (success) {

    Serial.println(
      "MQTT PUBLISH SUCCESS"
    );

    Serial.print(
      "Data: "
    );

    Serial.println(
      json
    );

  } else {

    Serial.println(
      "MQTT PUBLISH FAILED"
    );
  }

  Serial.println(
    "========================================"
  );
}

// ======================================================
// LOOP
// ======================================================

void loop() {

  unsigned long now =
    millis();

  // ====================================================
  // WIFI
  // ====================================================

  if (
    WiFi.status() !=
    WL_CONNECTED
  ) {


    if (
      lastWiFiAttempt == 0 ||
      now - lastWiFiAttempt >=
      WIFI_RETRY_INTERVAL
    ) {

      lastWiFiAttempt =
        now;

      Serial.println(
        "WiFi disconnected. Waiting for auto reconnect..."
      );
    }

    return;
  }

  // ====================================================
  // MQTT
  // ====================================================

  if (
    !mqttClient.connected()
  ) {

    if (
      lastMQTTAttempt == 0 ||
      now - lastMQTTAttempt >=
      MQTT_RETRY_INTERVAL
    ) {

      lastMQTTAttempt =
        now;

      connectMQTT();
    }

    return;
  }

  mqttClient.loop();


  if (
    now - lastPublish >=
    PUBLISH_INTERVAL
  ) {

    lastPublish =
      now;

    publishWeatherData();
  }
}
