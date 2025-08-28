# 엘리베이터 Calling 센서 추가 요약

## 수정 일자
2025-08-28

## 수정 내용

### 1. sensor.py 수정

#### 추가된 내용:
1. **엘리베이터 센서 지원 추가**:
   - `async_add_sensors` 함수에 엘리베이터 calling 센서 추가 로직 구현
   - 엘리베이터 기기 타입을 센서 생성 대상 목록에 추가 (`["plug", "energy", "thermostat", "elevator", "unknown"]`)

2. **EzvilleElevatorCallingSensor 클래스 신규 추가**:
   - 엘리베이터 호출 상태를 추적하는 센서 엔티티
   - 상태값 판단 로직:
     - `status == 0`: "off"
     - `(status << 4) == 0x20`: "on"
     - `(status << 4) == 0x40`: "cut"
     - 기타: status 값을 문자열로 표시
   - 속성(Attributes):
     - `device_id`: 기기 ID
     - `device_num`: 기기 번호
     - `raw_data`: 원시 패킷 데이터
     - `floor`: 현재 층수

### 2. rs485_client.py 수정

#### 엘리베이터 패킷 파싱 개선:
- 엘리베이터 상태 파싱 시 추가 정보 포함:
  - `device_id`: 패킷의 device ID (0x형식)
  - `device_num`: 패킷의 device number (0x형식)
  - `raw_packet`: 전체 원시 패킷 데이터

## 기능 설명

### Elevator Calling 센서
- **엔티티 이름**: "Elevator Calling"
- **상태 값**:
  - `off`: 엘리베이터가 호출되지 않음
  - `on`: 엘리베이터가 호출됨
  - `cut`: 엘리베이터 호출이 차단됨
  - 숫자: 기타 상태 코드
- **속성**:
  - Device ID: 엘리베이터 기기 식별자
  - Device Num: 엘리베이터 번호
  - Raw Data: 분석된 패킷의 원시 데이터
  - Floor: 현재 엘리베이터가 위치한 층수

## 동작 방식
1. 엘리베이터 기기가 발견되면 자동으로 "Elevator Calling" 센서가 생성됨
2. 엘리베이터 상태 패킷이 수신될 때마다 센서 상태가 업데이트됨
3. 패킷의 6번째 바이트 상위 4비트를 분석하여 호출 상태를 판단
4. 패킷의 6번째 바이트 하위 4비트는 현재 층수 정보로 사용

이 수정으로 Home Assistant에서 엘리베이터 호출 상태를 모니터링하고 자동화에 활용할 수 있습니다.
