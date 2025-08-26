# Ezville Wallpad 수정 요약 - 2025-01-21 (추가5)

## 수정된 파일들
1. climate.py
2. fan.py
3. valve.py

## 주요 수정 내용

### CMD 센서 필터링 추가
모든 플랫폼에서 CMD 센서가 일반 디바이스로 생성되지 않도록 `is_cmd_sensor` 체크 추가

#### climate.py
- 메인 루프와 async_add_thermostats 함수에 CMD 센서 체크 추가
- log_info 함수 import 추가

#### fan.py
- 메인 루프에 CMD 센서 체크 추가

#### valve.py
- 메인 루프에 CMD 센서 체크 추가
- log_info 함수 import 추가

#### light.py, switch.py
- 이미 CMD 센서 체크가 구현되어 있음

## 수정 패턴
```python
# 모든 플랫폼에 동일하게 적용
for device_key, device_info in coordinator.devices.items():
    # Skip CMD sensors
    if device_info.get("is_cmd_sensor", False):
        continue
    if device_info["device_type"] == "해당_타입":
        # 엔티티 생성
```

## 테스트 필요 사항
1. 각 디바이스 타입(thermostat, fan, gas)의 CMD 센서가 별도 기기로 생성되지 않는지 확인
2. CMD 센서가 원래 디바이스 그룹 내에만 표시되는지 확인
3. 정상적인 디바이스는 올바르게 생성되는지 확인
