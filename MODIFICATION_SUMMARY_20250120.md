# Ezville Wallpad 통합 수정 사항 요약
날짜: 2025-01-20

## 수정 요청 사항 및 적용 내용

### 1. Unknown 기기 처리 개선
- **요청**: 사전 정의되지 않은 패킷이 발생하면 unknown 기기 아래에 "unknown {signature}" 구성요소가 추가되어 상태값에 패킷이 업데이트 되어야 함
- **적용 내용**:
  - `rs485_client.py`에서 `_handle_unknown_device()` 함수 구현
  - 패킷의 앞 8자리를 signature로 사용하여 "unknown_f7300301" 형태의 device_key 생성
  - 상태값에 전체 패킷 문자열 저장
  - `sensor.py`의 `EzvilleUnknownSensor`에 최초/마지막 탐지 시간 속성 추가

### 2. Thermostat 모드 제한
- **요청**: climate 기기의 thermostat 구성요소에서 난방/꺼짐 2개 모드만 지원
- **적용 내용**:
  - `climate.py`에서 HVAC 모드를 OFF, HEAT 2개로 제한
  - mode 값이 1이면 heat, 그 외는 off로 처리
  - `async_turn_on()` 메서드에서 AUTO 대신 HEAT 모드로 변경

### 3. 로깅 설정 개선
- **요청**: "파일 로깅 활성화" 체크 해제 시 특정 로그가 기록되지 않도록 함
- **적용 내용**:
  - `log_info()`, `log_debug()` 등 로깅 함수에서 LOGGING_ENABLED 체크
  - "Unknown packet" 로그 레벨을 WARNING에서 INFO로 변경
  - MQTT 관련 디버그 로그에서 (paho-mqtt-client-) 대신 (paho-mqtt)로 표시되도록 스레드 이름 설정

### 4. 선택적 디바이스 로깅
- **요청**: "로깅할 장치 타입" 선택한 기기에 대해서만 콜백 호출 및 로그 기록
- **적용 내용**:
  - `coordinator.py`의 `_device_update_callback()`에서 log_device_types 옵션 체크
  - 선택된 device_type만 DEBUG 로그 출력
  - `rs485_client.py`의 콜백 관련 로그도 log_debug() 함수 사용

## 주요 파일 변경 사항

### 1. `rs485_client.py`
- `_handle_unknown_device()` 함수 추가
- 패킷 signature 기반 unknown device 생성 및 상태 업데이트
- 로깅 함수 사용으로 선택적 로깅 구현
- 스레드 이름을 "paho-mqtt"로 설정

### 2. `coordinator.py`
- `_device_update_callback()`에서 log_device_types 옵션 체크
- 선택된 device type에 대해서만 DEBUG 로그 출력

### 3. `sensor.py`
- `EzvilleUnknownSensor`에 타임스탬프 속성 추가
- first_detected, last_detected 시간 추적

### 4. `climate.py`
- HVAC 모드를 OFF, HEAT 2개로 제한
- hvac_mode 프로퍼티에서 mode 값 매핑 단순화
- async_set_hvac_mode()에서 heat/off 문자열로 명령 전송

### 5. `__init__.py`
- LOGGING_DEVICE_TYPES 전역 변수를 log_device_types 옵션에서 읽도록 수정

## 테스트 시나리오
1. Unknown 패킷 수신 시 unknown_f7300301 형태의 센서 생성 확인
2. Thermostat에서 난방/꺼짐 모드만 표시되는지 확인
3. 파일 로깅 비활성화 시 로그가 기록되지 않는지 확인
4. 선택한 장치 타입에 대해서만 디버그 로그가 출력되는지 확인
