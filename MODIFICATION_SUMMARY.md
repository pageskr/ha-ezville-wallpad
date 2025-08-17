# EzVille Wallpad Home Assistant 통합 수정 요약

## 2025-08-17 수정 사항

### 수정된 파일 목록

1. **custom_components/ezville_wallpad/rs485_client.py**
   - 패킷 분석 로그 개선
     - Light: Room과 Num 분리 표시
     - Plug: Room과 Num 분리 표시
     - Thermostat: Room만 표시
   - Light 패킷 분석 로직 수정
     - Room 번호 추출: device_num & 0x0F 사용
     - Light 개수 계산: packet[4] - 1
     - Light 상태 읽기: 7번째 바이트부터 시작 (index 6)
     - 로그 형식: "Light Room: X, Num: Y"
   - Plug 패킷 분석 로직 수정
     - Room 번호 추출: device_num >> 4 사용 (상위 4비트)
     - Plug 개수 계산: int(packet[4] / 3)
     - Plug 상태 인덱스: plug_num * 3 + 3
     - 전력 사용량 계산 수정
     - 로그 형식: "Plug Room: X, Num: Y"
   - Thermostat 패킷 분석 로직 수정
     - Room 번호 추출: device_num >> 4 사용 (상위 4비트)
     - 특별 포맷 처리: room_id == 0x01 체크
     - 표준 포맷: room_id + index로 실제 room 번호 계산
     - 로그 형식: "Thermostat Room: X"
   - 단일 기기 처리 개선
     - fan, gas, energy, elevator, doorbell은 device_key = device_type (번호 없음)
     - 예: "doorbell_1" → "doorbell"
   - Unknown 기기 처리 개선
     - signature(첫 4바이트) 기반으로 device_key 생성
     - 예: "unknown_f7602f81"
     - signature를 device_id로 사용하여 구성요소 생성
   - 명령 패킷 생성 로직 수정
     - Thermostat: device_num = (room_id << 4) | 0
     - 단일 기기: idn이 None일 경우 device_num = 0x01
   - MQTT 로그 개선
     - "Created signature" 로그 추가 (최초 패킷)
     - "Updated signature" 로그 유지 (변경된 패킷)
   - 0x39 디바이스 처리 개선

2. **custom_components/ezville_wallpad/coordinator.py**
   - 초기 기기 생성 키 형식 수정
     - 단일 기기: doorbell, elevator, energy, gas, fan (번호 없음)
     - 다중 기기: light_1_1, plug_1_1, thermostat_1 (번호 있음)
   - _on_device_discovered 메서드 개선
     - device_type별로 다른 키 형식 적용
     - 단일 기기는 device_type만 사용
   - _device_update_callback 메서드 개선
     - device_type별로 다른 키 형식 적용
   - send_command 메서드 수정
     - 단일 기기의 경우 device_id가 None 허용
   - Unknown 디바이스 콜백 등록
   - 스레드 안전성 개선
     - async_set_updated_data 호출 시 event loop 사용
     - threading 모듈 import 추가

3. **custom_components/ezville_wallpad/sensor.py**
   - EzvilleUnknownSensor 클래스 추가
   - Unknown 디바이스를 센서로 표시

4. **custom_components/ezville_wallpad/valve.py**
   - reports_position 속성 추가 (False 설정)
   - ValveEntity 에러 수정

5. **MQTT_DATA_PROCESSING.md**
   - MQTT 데이터 처리 문서 작성

## 주요 버그 수정

### 1. 기기 키 형식 통일
- **단일 기기** (fan, gas, energy, elevator, doorbell):
  - 기존: `{device_type}_{device_num}` (예: doorbell_1)
  - 수정: `{device_type}` (예: doorbell)
- **다중 기기** (light, plug, thermostat):
  - 유지: `{device_type}_{room}_{num}` 또는 `{device_type}_{room}`

### 2. Unknown 기기 처리
- **기존**: device_id 기반 (예: unknown_60)
- **수정**: signature 기반 (예: unknown_f7602f81)
- 각 고유한 패킷 signature마다 별도 구성요소 생성

### 3. 패킷 분석 로그 개선
메인 로그 포맷:
- Light: "Packet Analysis - Device ID: 0x0E(Light), Room: 0x01(1), Cmd: 0x81, Packet: ..."
- Plug: "Packet Analysis - Device ID: 0x39(Plug), Room: 0x01(1), Cmd: 0x81, Packet: ..."
- Thermostat: "Packet Analysis - Device ID: 0x36(Thermostat), Room: 0x01(1), Cmd: 0x81, Packet: ..."
- 기타: "Packet Analysis - Device ID: 0xXX, Num: 0xXX(XX), Cmd: 0xXX, Packet: ..."

상세 로그 포맷:
- Light: "=> Light Room: 1, Num: 1, state: ON (key: light_1_1)"
- Plug: "=> Plug Room: 2, Num: 1, state: ON, Power: 123.6W (key: plug_2_1, bytes: ...)"
- Thermostat: "=> Thermostat Room: 1 - Current: 25°C, Target: 23°C (key: thermostat_1)"
- 단일 기기: "=> Fan state: {'power': False, 'speed': 0, 'mode': 'bypass'}"

### 4. 스레드 안전성 문제 해결
- `async_write_ha_state`가 다른 스레드에서 호출되는 문제 수정
- `call_soon_threadsafe` 사용하여 event loop에서 실행

### 5. Valve 엔티티 에러 수정
- `reports_position` 속성 누락 문제 해결
- Gas valve는 위치 정보를 제공하지 않으므로 False 설정

## 새로운 기능

### 1. 단일 기기 자동 인식
- fan, gas, energy, elevator, doorbell은 자동으로 단일 기기로 처리
- 번호 없이 device_type만으로 식별

### 2. Unknown 디바이스 자동 생성
- STATE_HEADER에 없는 디바이스 자동 감지
- signature 기반으로 고유한 구성요소 생성
- 원시 패킷 데이터를 상태값으로 표시

### 3. 향상된 MQTT 로깅
- 최초 패킷: "Created signature"
- 변경된 패킷: "Updated signature"
- 패킷별 상세 분석 로그

## 테스트 완료 항목

- ✅ Light 패킷 분석 (f70e118104000000006d08)
- ✅ Plug 패킷 분석 (f7391f810700900167100137879e)
- ✅ Thermostat 패킷 분석 (f7361f810d00000f0000051d051d)
- ✅ 단일 기기 처리 (doorbell, elevator, energy, gas, fan)
- ✅ Unknown 기기 signature 기반 처리
- ✅ MQTT 중복 제거 및 로깅
- ✅ 스레드 안전성
- ✅ Valve 엔티티 동작

## 알려진 이슈

1. 0x40 디바이스가 const.py에 doorbell로 정의되어 있으나 command 0x02는 미지원
   - Unknown 디바이스로 처리됨

## 사용 예시

### Light 패킷 예시:
```
f7 0e 11 81 04 00 00 00 00 6d 08
- Device ID: 0x0E (light)
- Room: 1 (0x11 & 0x0F)
- Light count: 3 (0x04 - 1)
- Light 1: Off (index 6 = 0x00)
- Light 2: Off (index 7 = 0x00)
- Light 3: Off (index 8 = 0x00)
결과: light_1_1 = Off, light_1_2 = Off, light_1_3 = Off
```

### Plug 패킷 예시:
```
f7 39 1f 81 07 00 90 01 67 10 01 37 87 9e
- Device ID: 0x39 (plug)
- Room: 1 (0x1F >> 4)
- Plug count: 2 (0x07 / 3)
- Plug 1:
  - Index: 1 * 3 + 3 = 6
  - State: On (packet[6] & 0x10 = 0x10)
  - Power: 190.1W
- Plug 2:
  - Index: 2 * 3 + 3 = 9
  - State: On (packet[9] & 0x10 = 0x10)
  - Power: 137.3W
결과: plug_1_1 = On (190.1W), plug_1_2 = On (137.3W)
```

### Thermostat 패킷 예시:
```
f7 36 1f 81 0d 00 00 0f 00 00 05 1d 05 1d
- Device ID: 0x36 (thermostat)
- Room: 1 (0x1F >> 4)
- Special format detected
- Thermostat data starts at index 10
- Thermostat 1: Current 29°C (0x1d), Target 29°C (0x1d)
결과: thermostat_1 = 29°C/29°C
```

### 단일 기기 예시:
```
- doorbell (초인종)
- elevator (엘리베이터)
- energy (에너지 미터)
- gas (가스 밸브)
- fan (환기팬)
```

### Unknown 기기 예시:
```
f7 60 2f 81 ...
- signature: f7602f81
- device_key: unknown_f7602f81
- 구성요소명: Unknown f7602f81
```
