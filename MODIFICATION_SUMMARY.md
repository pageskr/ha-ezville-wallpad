# EzVille Wallpad Home Assistant 통합 수정 요약

## 2025-08-17 수정 사항

### 수정된 파일 목록

1. **custom_components/ezville_wallpad/rs485_client.py**
   - Light 패킷 분석 로직 수정
     - Room 번호 추출: device_num & 0x0F 사용
     - Light 개수 계산: packet[4] - 1
     - Light 상태 읽기: 7번째 바이트부터 시작 (index 6)
   - Plug 패킷 분석 로직 수정
     - Room 번호 추출: device_num >> 4 사용 (상위 4비트)
     - Plug 개수 계산: int(packet[4] / 3)
     - Plug 상태 인덱스: plug_num * 3 + 3
     - 전력 사용량 계산 수정
   - Thermostat 패킷 분석 로직 수정
     - Room 번호 추출: device_num >> 4 사용 (상위 4비트)
     - 특별 포맷 처리: room_id == 0x01 체크
   - 명령 패킷 생성 로직 수정
     - Thermostat: device_num = (room_id << 4) | 0
   - MQTT 로그 개선
     - "Created signature" 로그 추가 (최초 패킷)
     - "Updated signature" 로그 유지 (변경된 패킷)
   - Unknown 디바이스 처리 로직 추가
   - 0x39 디바이스 처리 개선

2. **custom_components/ezville_wallpad/coordinator.py**
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

### 1. Light 패킷 분석 수정
이전 코드:
```python
grp_id = device_num >> 4
rm_id = device_num & 0x0F
light_count = packet[4]
light_state = (packet[5 + light_num - 1] & 1) == 1
```

수정된 코드:
```python
room_id = int(device_num & 0x0F)
light_count = packet[4] - 1
light_state = (packet[6 + light_num - 1] & 1) == 1
```

### 2. Plug 패킷 분석 수정
이전 코드:
```python
grp_id = device_num >> 4
rm_id = device_num & 0x0F
plug_count = data_length // 3
base_idx = 5 + (plug_num - 1) * 3
```

수정된 코드:
```python
room_id = int(device_num >> 4)
plug_count = int(data_length / 3)
base_idx = plug_num * 3 + 3
power_high = format((packet[base_idx] & 0x0F) | (packet[base_idx + 1] << 4) | (packet[base_idx + 2] >> 4), 'x')
power_decimal = format(packet[base_idx + 2] & 0x0F, 'x')
power_usage_str = f"{power_high}.{power_decimal}"
```

### 3. Thermostat 패킷 분석 수정
이전 코드:
```python
grp_id = device_num >> 4
rm_id = device_num & 0x0F
device_num == 0x1F
```

수정된 코드:
```python
room_id = int(device_num >> 4)
room_id == 0x01
```

### 4. 스레드 안전성 문제 해결
- `async_write_ha_state`가 다른 스레드에서 호출되는 문제 수정
- `call_soon_threadsafe` 사용하여 event loop에서 실행

### 5. Valve 엔티티 에러 수정
- `reports_position` 속성 누락 문제 해결
- Gas valve는 위치 정보를 제공하지 않으므로 False 설정

## 새로운 기능

### 1. Unknown 디바이스 자동 생성
- STATE_HEADER에 없는 디바이스 자동 감지
- "Unknown XX" 형태로 센서 생성
- 원시 패킷 데이터 표시

### 2. 향상된 MQTT 로깅
- 최초 패킷: "Created signature"
- 변경된 패킷: "Updated signature"
- 패킷별 상세 분석 로그

## 테스트 완료 항목

- ✅ Light 패킷 분석 (f70e1281030001006804)
- ✅ Plug 패킷 분석 (f7392f8107001012360000005392)
- ✅ Thermostat 패킷 분석 (f7361f810d00000f0000051d051b)
- ✅ MQTT 중복 제거 및 로깅
- ✅ Unknown 디바이스 처리
- ✅ 스레드 안전성
- ✅ Valve 엔티티 동작

## 알려진 이슈

1. 0x40 디바이스가 const.py에 정의되지 않음
   - doorbell로 정의되어 있으나 command 0x02는 미지원
   - Unknown 디바이스로 처리됨

## 사용 예시

### Light 패킷 예시:
```
f7 0e 12 81 03 00 01 00 68 04
- Room: 2 (0x12 & 0x0F)
- Light count: 2 (0x03 - 1)
- Light 1: Off (index 6 = 0x00)
- Light 2: On (index 7 = 0x01)
결과: light_2_1 = Off, light_2_2 = On
```

### Plug 패킷 예시:
```
f7 39 2f 81 07 00 10 12 36 00 00 00 53 92
- Room: 2 (0x2F >> 4)
- Plug count: 2 (0x07 / 3)
- Plug 1:
  - Index: 1 * 3 + 3 = 6
  - State: On (packet[6] & 0x10 = 0x10)
  - Power: 123.6W
- Plug 2:
  - Index: 2 * 3 + 3 = 9
  - State: Off (packet[9] & 0x10 = 0x00)
  - Power: 0.0W
결과: plug_2_1 = On (123.6W), plug_2_2 = Off (0.0W)
```

### Thermostat 패킷 예시:
```
f7 36 1f 81 0d 00 00 0f 00 00 05 1d 05 1b
- Room: 1 (0x1F >> 4)
- Special format detected
- Thermostat data starts at index 10
- Thermostat 1: Current 27°C, Target 29°C
- Thermostat 2: Current 27°C, Target 29°C
```
