#include <SoftwareSerial.h>

// elegoo Smart Car Shield v1.1 pin mapping
// AIN2/BIN2 are auto-inverted from AIN1/BIN1 via onboard Schmitt trigger
// Motor A = LEFT  (M1 + M4)
// Motor B = RIGHT (M2 + M3)

#define PWMA 5
#define AIN1 7
#define PWMB 6
#define BIN1 8
#define STBY 3

SoftwareSerial bt(2, 4);  // RX=2, TX=4

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
  Serial.println("READY");
}

void loop() {
  if (bt.available()) {
    String cmd = bt.readStringUntil('\n');
    cmd.trim();

    stopAll();

    if (cmd == "MA_FWD") {
      digitalWrite(AIN1, HIGH);
      analogWrite(PWMA, 255);

    } else if (cmd == "MA_REV") {
      digitalWrite(AIN1, LOW);
      analogWrite(PWMA, 255);

    } else if (cmd == "MB_FWD") {
      digitalWrite(BIN1, HIGH);
      analogWrite(PWMB, 255);

    } else if (cmd == "MB_REV") {
      digitalWrite(BIN1, LOW);
      analogWrite(PWMB, 255);
    }
  }
}
