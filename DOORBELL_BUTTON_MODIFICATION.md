# Doorbell Button and Ring Sensor Modification Summary

## 수정 일시
2025-01-21

## 수정 내용

### 1. button.py 파일 수정
- Doorbell 기기 그룹에 4개의 버튼 생성
  - Call 버튼: 0x10, 0x90 명령어 감지 (수정됨)
  - Talk 버튼: 0x12, 0x92 명령어 감지
  - Open 버튼: 0x22, 0xA2 명령어 감지
  - Cancel 버튼: 0x11, 0x91 명령어 감지

- 각 버튼의 패킷 감지 시 상태 업데이트
  - last_pressed: 이벤트 발생 시간 (ISO format)
  - device_id: 디바이스 ID
  - device_num: 디바이스 번호
  - command: 명령어
  - raw_data: 원시 패킷 데이터

### 2. binary_sensor.py 파일 수정
- 기존 Ringing 센서 유지
- 새로운 Ring 센서 추가
  - 0x13, 0x93 명령어 감지 시: Ring 센서 ON
  - 0x11, 0x91 명령어 감지 시: Ring 센서 OFF (Cancel 이벤트)
  - 센서 속성에 패킷 정보 저장:
    - last_ring: 마지막 ring 시간
    - last_cancel: 마지막 cancel 시간
    - device_id, device_num, command, raw_data

### 3. rs485_client.py 파일 수정
- _handle_device_cmd_packet 메서드 수정
  - Doorbell의 특정 명령어들이 CMD sensor로 생성되지 않도록 필터링
  - 필터링된 명령어: 0x10, 0x90, 0x13, 0x93, 0x12, 0x92, 0x22, 0xA2, 0x11, 0x91
  - 해당 명령어는 CMD sensor 생성 대신 버튼과 센서에 직접 전달

### 4. const.py 파일 수정
- doorbell 디바이스의 명령어 정의
  - ring 명령어 복원: {"id": 0x40, "cmd": 0x93, "ack": 0xC3}
  - call 명령어 유지: {"id": 0x40, "cmd": 0x10, "ack": 0xC0}

## 동작 설명

1. **버튼 클릭 시**
   - Call: doorbell/call 명령 전송
   - Talk: doorbell/talk 명령 전송
   - Open: doorbell/open 명령 전송
   - Cancel: doorbell/cancel 명령 전송

2. **패킷 수신 시**
   - 0x10, 0x90: Call 버튼의 last_pressed 업데이트
   - 0x12, 0x92: Talk 버튼의 last_pressed 업데이트
   - 0x22, 0xA2: Open 버튼의 last_pressed 업데이트
   - 0x11, 0x91: Cancel 버튼의 last_pressed 업데이트 + Ring 센서 OFF
   - 0x13, 0x93: Ring 센서 ON

3. **Ring 센서 동작**
   - 0x13 또는 0x93 패킷 수신 시 Ring 센서가 ON 상태로 변경
   - 0x11 또는 0x91 패킷 수신 시 Ring 센서가 OFF 상태로 변경 (이전 상태 무관)
   - 센서 속성에 마지막 패킷 정보 저장

## 테스트 시나리오

1. Home Assistant 재시작
2. Doorbell 엔티티 확인
   - 4개 버튼 (Call, Talk, Open, Cancel)
   - 2개 센서 (Ringing, Ring)
3. 각 버튼 클릭 테스트
4. 외부 패킷 수신 테스트
   - 0x13/0x93 패킷: Ring 센서 ON 확인
   - 0x11/0x91 패킷: Ring 센서 OFF 확인
   - Developer Tools > States에서 속성 확인
