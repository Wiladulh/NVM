#pragma once
#include <Arduino.h>
#include <Keypad.h>

const byte NVM_ROWS=4, NVM_COLS=4;
char nvmKeys[NVM_ROWS][NVM_COLS]={
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte nvmRowPins[NVM_ROWS]={32,33,25,26};
byte nvmColPins[NVM_COLS]={13,14,16,17};
Keypad nvmKeypad=Keypad(makeKeymap(nvmKeys),nvmRowPins,nvmColPins,NVM_ROWS,NVM_COLS);
