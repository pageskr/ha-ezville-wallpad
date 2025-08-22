# Ezville Wallpad Command Sensor 수정 완료

## 수정 날짜: 2025-01-20

## 문제점
1. Command 패킷이 sensor 도메인이 아닌 light/switch/climate 등의 도메인에 생성되고 있었음
2. 센서 이름 형식이 요구사항과 맞지 않았음

## 해결 방법
모든 플랫폼(light, switch, climate, fan, valve, button)에서 command 센서를 건너뛰도록 수정
- device_id가 "cmd_"로 시작하면 해당 플랫폼에서 처리하지 않음
- sensor platform에서만 command 센서를 처리하도록 함

## 수정된 파일들

### 1. light.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in light platform", device_key)
    continue
```

### 2. switch.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀  
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in switch platform", device_key)
    continue
```

### 3. climate.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in climate platform", device_key)
    continue/return
```

### 4. fan.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in fan platform", device_key)
    continue
```

### 5. valve.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in valve platform", device_key)
    continue
```

### 6. button.py
```python
# Command 센서는 sensor platform에서 처리하도록 건너뜀
if isinstance(device_id, str) and device_id.startswith("cmd_"):
    _LOGGER.debug("Skipping command sensor %s in button platform", device_key)
    continue
```

### 7. coordinator.py (이전 수정)
- 모든 기기 타입에 대해 sensor platform을 로딩하도록 수정

## 결과

### Command 센서 이름 형식
- Light: "Light 1 1 Cmd 0x01" (sensor 도메인)
- Plug: "Plug 1 1 Cmd 0x01" (sensor 도메인)
- Thermostat: "Thermostat 1 Cmd 0x01" (sensor 도메인)
- Ventilation: "Ventilation Cmd 0x01" (sensor 도메인)
- 기타: "Doorbell Cmd 0x01", "Elevator Cmd 0x01" 등 (sensor 도메인)

### 동작 방식
1. rs485_client.py에서 command 패킷 감지 시 device_id를 "cmd_XX_XX" 형태로 생성
2. coordinator.py에서 device_type별로 적절한 플랫폼 로딩 (sensor 포함)
3. 각 플랫폼에서 cmd 센서는 건너뛰고, sensor platform에서만 처리
4. sensor.py의 EzvilleCommandSensor가 올바른 이름과 속성으로 센서 생성

## 테스트 방법
1. Home Assistant 재시작
2. 개발자 도구 > 상태에서 확인:
   - Command 센서가 모두 sensor 도메인에 생성되는지 확인
   - 센서 이름이 올바른 형식인지 확인
   - Unknown 기기가 정상 생성되는지 확인
