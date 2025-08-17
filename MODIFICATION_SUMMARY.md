# EzVille Wallpad Home Assistant 통합 수정 요약

## 2025-08-17 주요 수정 사항 (업데이트 2)

### 7. 로그 출력 개선
- **모든 파일**:
  - Logger 이름을 짧게 변경하여 로그 가독성 향상
  - `custom_components.ezville_wallpad.rs485_client` → `custom_components.ezville_wallpad.rs485`
  - `paho-mqtt-client-` → `paho-mqtt`로 표시
  - 각 모듈별 logger 이름 단축화
- **rs485_client.py**:
  - `_communication_loop` → `_message_loop`로 메서드명 변경
  - Thread 이름을 "message_loop"로 설정하여 로그에서 간결하게 표시
  - MQTT 중복 패킷 처리 개선: 패킷 분할 후 중복 제거하여 성능 향상

### 8. MQTT 중복 패킷 제거 강화
- **rs485_client.py**:
  - `_process_mqtt_data`에서 패킷 분할 후 즉시 중복 제거
  - 동일한 패킷이 여러 번 수신되어도 한 번만 처리
  - 중복 제거 통계 로그 추가

## 2025-08-17 주요 수정 사항 (업데이트 1)

### 1. 영역(Area) 자동 지정 제거
- **climate.py, fan.py**: 초기 생성 시 자동 영역 지정 코드 제거
- 사용자가 필요시 수동으로 지정하도록 변경

### 2. Unknown 기기 처리 개선
- **rs485_client.py**: 
  - `_handle_unknown_device` 메서드 추가
  - 알려지지 않은 디바이스 패킷을 signature(첫 4바이트) 기반으로 처리
  - device_key: `unknown_{signature}` 형식 (예: unknown_f7602f81)
  - 디바이스 발견 시 콜백 호출하여 동적으로 센서 생성
- **coordinator.py**: 
  - unknown 디바이스 콜백 등록 추가
  - `_check_and_load_platform`에서 unknown 디바이스를 위한 센서 플랫폼 로드
- **sensor.py**: 
  - `EzvilleUnknownSensor` 클래스 추가
  - signature, device_id, command, raw_data 등을 속성으로 표시
  - 동적 센서 추가 로직 개선

### 3. 패킷 분석 상세 로그 개선
- **rs485_client.py**:
  - Light 패킷: 각 조명별 상태 파싱 및 로그
    ```
    => Light Room: 1, Num: 1, state: ON (key: light_1_1)
    => Light Room: 1, Num: 2, state: OFF (key: light_1_2)
    ```
  - Plug 패킷: 각 플러그별 상태 및 전력 사용량 파싱 및 로그
    ```
    => Plug Room: 3, Num: 1, state: ON, Power: 68.0W (key: plug_3_1, bytes: 00 68 00)
    => Plug Room: 3, Num: 2, state: OFF, Power: 0.0W (key: plug_3_2, bytes: 0B 00 00)
    ```
  - 상태 변경 시 어느 구성요소에 어떤 값으로 업데이트했는지 명시

### 4. MQTT 패킷 처리 개선
- **rs485_client.py**:
  - `_process_mqtt_data` 메서드에서 signature 기반 중복 제거
  - 새 패킷: "Created signature" 로그
  - 변경된 패킷: "Updated signature" 로그
  - 중복 패킷은 무시하여 성능 향상

### 5. 단일 기기 키 형식 통일
- **coordinator.py, rs485_client.py**:
  - 단일 기기(fan, gas, energy, elevator, doorbell): device_key = device_type
  - 다중 기기(light, plug, thermostat): device_key = device_type_room_num

### 6. 스레드 안전성 개선
- **모든 플랫폼 파일들**:
  - `_handle_coordinator_update`에서 `call_soon_threadsafe` 사용
  - RS485 통신 스레드에서 안전하게 HA 상태 업데이트

### 수정된 파일 목록

1. **custom_components/ezville_wallpad/rs485_client.py**
   - Logger 이름 변경: `rs485_client` → `rs485`
   - 메서드명 변경: `_communication_loop` → `_message_loop`
   - Thread 이름 설정: "message_loop"
   - MQTT 중복 패킷 제거 로직 강화
   - Unknown 디바이스 처리 로직 추가
   - 패킷 분석 상세 로그 개선
   - 각 구성요소별 상태 업데이트 로그

2. **custom_components/ezville_wallpad/coordinator.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.coordinator`
   - Unknown 디바이스 콜백 등록
   - 플랫폼 동적 로드 로직 개선
   - 초기 기기 생성 시 영역 정보 제거

3. **custom_components/ezville_wallpad/sensor.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.sensor`
   - EzvilleUnknownSensor 클래스 추가
   - 동적 센서 추가 로직 개선

4. **custom_components/ezville_wallpad/climate.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.climate`
   - 초기 영역 자동 지정 제거

5. **custom_components/ezville_wallpad/fan.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.fan`
   - 초기 영역 자동 지정 제거

6. **custom_components/ezville_wallpad/light.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.light`
   - 스레드 안전성 개선

7. **custom_components/ezville_wallpad/switch.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.switch`
   - 스레드 안전성 개선

8. **custom_components/ezville_wallpad/valve.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.valve`
   - 스레드 안전성 개선

9. **custom_components/ezville_wallpad/button.py**
   - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.button`
   - 스레드 안전성 개선

10. **custom_components/ezville_wallpad/binary_sensor.py**
    - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.binary_sensor`
    - 스레드 안전성 개선

11. **custom_components/ezville_wallpad/__init__.py**
    - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad`

12. **custom_components/ezville_wallpad/config_flow.py**
    - Logger 이름 변경: `__name__` → `custom_components.ezville_wallpad.config_flow`

## 주요 기능 개선 사항

### 1. 동적 디바이스 추가
- 사전 정의되지 않은 디바이스도 자동으로 센서로 추가
- MQTT 패킷 수신 시 실시간으로 새 디바이스 생성

### 2. 상세한 디버깅 정보
- 각 패킷의 파싱 결과를 구성요소별로 상세히 로그
- 상태 변경 시 어떤 엔티티가 어떤 값으로 업데이트되었는지 명시

### 3. 성능 최적화
- MQTT 중복 패킷 필터링으로 불필요한 처리 방지
- signature 기반 빠른 패킷 식별

### 4. 사용자 경험 개선
- 영역 자동 지정 제거로 사용자가 원하는 대로 구성 가능
- Unknown 디바이스도 센서로 표시하여 데이터 확인 가능

## 테스트 완료 항목

- ✅ Light 다중 구성요소 파싱 및 로그
- ✅ Plug 다중 구성요소 파싱 및 로그
- ✅ Thermostat 특수 포맷 처리
- ✅ Unknown 디바이스 자동 생성
- ✅ MQTT signature 기반 중복 제거
- ✅ 동적 플랫폼 로드
- ✅ 스레드 안전한 상태 업데이트

## 알려진 이슈 및 해결

1. **이슈**: 초기 생성된 기기의 상태가 MQTT 패킷으로 업데이트되지 않음
   - **해결**: 디바이스 콜백에서 상태 업데이트 시 엔티티 콜백 호출

2. **이슈**: Unknown 디바이스가 동적으로 추가되지 않음
   - **해결**: `_handle_unknown_device` 메서드 추가 및 discovery 콜백 호출

3. **이슈**: 다중 구성요소 디바이스의 개별 상태가 로그에 표시되지 않음
   - **해결**: Light/Plug 파싱 시 각 구성요소별 상세 로그 추가

## 사용 예시

### 개선된 로그 출력 예시:
```
2025-08-17 23:04:42.504 INFO (paho-mqtt) [custom_components.ezville_wallpad.rs485] MQTT message received on ew11a/recv: 128 bytes
2025-08-17 23:04:42.510 INFO (message_loop) [custom_components.ezville_wallpad.rs485] Converted hex message: f7 39 1f 81 07 00 90 02 69 10 01 71 cc 20
```

### MQTT 중복 제거 로그:
```
2025-08-17 22:17:24.615 DEBUG (message_loop) [custom_components.ezville_wallpad.rs485] MQTT: Received 13 packets from data
2025-08-17 22:17:24.615 DEBUG (message_loop) [custom_components.ezville_wallpad.rs485] MQTT: Processing 2 unique packets (removed 11 duplicates)
```

### Light 패킷 상세 로그:
```
2025-08-17 19:12:20.777 INFO Packet Analysis - Device ID: 0x0E(Light), Room: 0x02(2), Cmd: 0x81, Packet: f70e1281030000006904
2025-08-17 19:12:20.777 INFO => State packet for device type: light
2025-08-17 19:12:20.777 INFO => Light state: Room 2 (device_num=0x12)
2025-08-17 19:12:20.777 INFO => Light count in room: 2
2025-08-17 19:12:20.777 INFO => Light Room: 2, Num: 1, state: OFF (key: light_2_1)
2025-08-17 19:12:20.777 INFO => Light Room: 2, Num: 2, state: OFF (key: light_2_2)
```

### Plug 패킷 상세 로그:
```
2025-08-17 19:20:19.625 INFO Packet Analysis - Device ID: 0x39(Plug), Room: 0x03(3), Cmd: 0x81, Packet: f7393f8107001004680000000b7e
2025-08-17 19:20:19.625 INFO => State packet for device type: plug
2025-08-17 19:20:19.625 INFO => Plug state: Room 3 (device_num=0x3F)
2025-08-17 19:20:19.625 INFO => Data length: 7, Plug count: 2
2025-08-17 19:20:19.625 INFO => Plug Room: 3, Num: 1, state: ON, Power: 68.0W (key: plug_3_1, bytes: 10 04 68)
2025-08-17 19:20:19.625 INFO => Plug Room: 3, Num: 2, state: OFF, Power: 0.0W (key: plug_3_2, bytes: 00 00 00)
```

### Unknown 디바이스 로그:
```
2025-08-17 19:20:19.625 INFO Created signature f7393f81: 07 00 10 04 68 00 00 00 0b 7e
2025-08-17 19:20:19.625 INFO => NEW UNKNOWN DEVICE discovered: unknown_f7393f81 (signature: f7393f81)
```
