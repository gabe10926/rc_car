#include <SoftwareSerial.h>
#include <Wire.h>
#include <MPU6050.h>

// Elegoo Smart Car Shield v1.1
// Motor A = LEFT  (M1 + M4)
// Motor B = RIGHT (M2 + M3)
// AIN2/BIN2 auto-inverted via Schmitt trigger — do not use
// Bluetooth: RX=2, TX=4

#define PWMA 5
#define AIN1 7
#define PWMB 6
#define BIN1 8
#define STBY 3

#define IMU_SEND_INTERVAL 50

SoftwareSerial bt(2, 4);  // RX=2, TX=4

MPU6050 mpu;

unsigned long lastIMUSend = 0;

void stopAll() {
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
}

void setup() {
  Serial.begin(9600);
  bt.begin(9600);

  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(STBY, OUTPUT);
  digitalWrite(STBY, HIGH);
  stopAll();

  Wire.begin();
  mpu.initialize();

  Serial.println(mpu.testConnection() ? "MPU6050 OK" : "MPU6050 FAIL");
  Serial.println("READY");
}

void loop() {
  // receive drive commands
  if (bt.available()) {
    String data = bt.readStringUntil('\n');
    int x, y;

    if (sscanf(data.c_str(), "X:%d Y:%d", &x, &y) == 2) {
      int forward = -(y - 127);
      int turn    = -(x - 127);

      if (abs(forward) < 10) forward = 0;
      if (abs(turn)    < 10) turn    = 0;

      int leftSpeed  = constrain(forward + turn, -127, 127);
      int rightSpeed = constrain(forward - turn, -127, 127);

      int leftPWM  = map(abs(leftSpeed),  0, 127, 0, 255);
      int rightPWM = map(abs(rightSpeed), 0, 127, 0, 255);

      digitalWrite(AIN1, leftSpeed  >= 0 ? HIGH : LOW);
      digitalWrite(BIN1, rightSpeed >= 0 ? HIGH : LOW);

      analogWrite(PWMA, leftPWM);
      analogWrite(PWMB, rightPWM);
    }
  }

  // IMU telemetry DISABLED
  // unsigned long now = millis();
  // if (now - lastIMUSend >= IMU_SEND_INTERVAL) {
  //   lastIMUSend = now;
  //   int16_t ax, ay, az, gx, gy, gz;
  //   mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  //   float axf = ax / 16384.0;
  //   float ayf = ay / 16384.0;
  //   float azf = az / 16384.0;
  //   float gzf = gz / 131.0;
  //   bt.print("IMU:");
  //   bt.print(axf, 2); bt.print(",");
  //   bt.print(ayf, 2); bt.print(",");
  //   bt.print(azf, 2); bt.print(",");
  //   bt.println(gzf, 1);
  // }
}
