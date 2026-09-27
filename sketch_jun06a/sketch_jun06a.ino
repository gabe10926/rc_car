#include <SoftwareSerial.h>

#define PWMA 5
#define AIN1 8
#define AIN2 9

#define PWMB 6
#define BIN1 10
#define BIN2 11

#define STBY 3

SoftwareSerial bt(7, 12);  // RX, TX

void setup() {
  Serial.begin(9600);
  bt.begin(9600);

  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);

  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);

  pinMode(STBY, OUTPUT);
  digitalWrite(STBY, HIGH);

  Serial.println("READY");
}

void drive(int x, int y) {
  // convert joystick to -255 -> 255
  int forward = map(y, 0, 255, 255, 255);
  int turn    = map(x, 0, 255, 255, -255);

  // deadzone
  if (abs(forward) < 20) forward = 0;
  if (abs(turn) < 20) turn = 0;

  // differential drive mixing
  int leftSpeed  = forward + turn;
  int rightSpeed = forward - turn;

  // limit values
  leftSpeed  = constrain(leftSpeed, -255, 255);
  rightSpeed = constrain(rightSpeed, -255, 255);
  // left motor
  if (leftSpeed > 0) {
    digitalWrite(AIN1, HIGH);
    digitalWrite(AIN2, LOW);
  } else if (leftSpeed < 0) {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, HIGH);
  } else {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, LOW);
  }

  // right motor
  if (rightSpeed > 0) {
    digitalWrite(BIN1, HIGH);
    digitalWrite(BIN2, LOW);
  } else if (rightSpeed < 0) {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, HIGH);
  } else {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, LOW);
  }

  // speed control
  analogWrite(PWMA, abs(leftSpeed));
  analogWrite(PWMB, abs(rightSpeed));

  // debug
  Serial.print("L:");
  Serial.print(leftSpeed);
  Serial.print(" R:");
  Serial.println(rightSpeed);
}

void loop() {
  if (bt.available()) {
    String data = bt.readStringUntil('\n');

    int x, y;
    if (sscanf(data.c_str(), "X:%d Y:%d", &x, &y) == 2) {
      drive(x, y);
    }
  }
}
