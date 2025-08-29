# CMD Sensor Optimization Summary

## 수정 일시
2025-01-21 (v3)

## 수정 내용

### 1. rs485_client.py 수정
- 모든 CMD 패킷을 임시 이벤트로 처리
  - coordinator.devices에 저장하지 않음
  - 패킷 발생 시점에만 콜백 호출
  - 임시 state 생성 후 즉시 삭제
- doorbell 버튼/센서 커맨드는 별도 처리 유지

### 2. coordinator.py 수정  
- 모든 _cmd 타입의 임시 이벤트 처리
  - device_id가 _temp로 끝나는 경우 직접 엔티티 콜백 호출
  - devices에 저장하지 않음
  - 매초 갱신 방지

### 3. sensor.py의 EzvilleCmdSensor 클래스 전면 개선
- last_seen 시간 표시 (센서 값)
- 패킷 수신 시점에만 업데이트
- extra_state_attributes에 패킷 정보 저장
  - device_id, device_num, command
  - raw_data, packet_length
  - full_data (전체 패킷 데이터)
- 임시 이벤트 콜백 등록 방식 구현

## 동작 방식

1. **CMD 패킷 수신 흐름**
   - CMD 패킷 수신 → rs485_client에서 임시 state 생성
   - coordinator의 _cmd 타입 콜백 호출
   - 등록된 CMD sensor 엔티티에만 이벤트 전달
   - 임시 state 즉시 삭제

2. **CMD Sensor 동작**
   - 평상시: last_seen 시간 표시 (없으면 "Never")
   - 패킷 수신: last_seen 업데이트 + 패킷 정보 저장
   - coordinator.devices를 참조하지 않음
   - 매초 갱신되지 않음

## 문제 해결

- ✅ 모든 CMD sensor가 매초마다 갱신되는 문제 해결
- ✅ CMD sensor에 last_seen 시간 표시
- ✅ 패킷 발생 시점에만 업데이트
- ✅ coordinator.devices 부하 감소

## 테스트 방법

1. Home Assistant 재시작
2. Developer Tools > States에서 CMD sensor 확인
3. CMD 패킷 발생 시 last_seen 시간 업데이트 확인
4. 패킷 발생 후 센서가 매초 갱신되지 않는지 확인
5. extra_state_attributes에서 패킷 정보 확인
