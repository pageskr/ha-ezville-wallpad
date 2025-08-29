# Doorbell Button and Ring Sensor Modification Summary

## 수정 일시
2025-01-21 (v2)

## 수정 내용

### 1. rs485_client.py 수정
- doorbell 명령 패킷 처리 개선
  - 임시 state를 생성하여 콜백 호출 후 즉시 삭제
  - coordinator.devices에 등록되지 않도록 처리
  - 버튼/센서 이벤트가 발생한 시점에만 업데이트

### 2. coordinator.py 수정
- doorbell_cmd 타입의 임시 이벤트 처리 추가
  - 이벤트를 devices에 저장하지 않고 직접 엔티티에 전달
  - 매초마다 갱신되는 문제 해결

### 3. button.py 전면 개선
- EzvilleDoorbellButtonBase 기본 클래스 생성
- 버튼 클릭 시 last_pressed 시간 업데이트
- 외부 패킷 수신 시 last_pressed 시간 업데이트
- extra_state_attributes로 패킷 정보 표시
- 임시 이벤트 콜백 등록 방식 개선

### 4. binary_sensor.py 개선
- Ring 센서의 패킷 처리 방식 개선
- 임시 이벤트 콜백 등록
- coordinator 업데이트와 패킷 이벤트 분리

## 동작 방식

1. **패킷 수신 흐름**
   - doorbell 관련 패킷 수신 → rs485_client에서 임시 state 생성
   - coordinator의 doorbell_cmd 콜백 호출
   - 등록된 엔티티에만 이벤트 전달
   - 임시 state 즉시 삭제 (devices에 저장 안됨)

2. **버튼 동작**
   - 버튼 클릭: 명령 전송 + last_pressed 업데이트
   - 패킷 수신: 해당 명령어 감지 시 last_pressed 업데이트
   - extra_state_attributes에 패킷 정보 표시

3. **Ring 센서 동작**
   - 0x13, 0x93: 센서 ON + last_ring 시간 기록
   - 0x11, 0x91: 센서 OFF + last_cancel 시간 기록
   - 패킷 정보를 속성에 저장

## 문제 해결

- ✅ doorbell 이벤트 후 매초마다 갱신되는 문제 해결
- ✅ 버튼의 last_pressed 시간이 업데이트되지 않는 문제 해결
- ✅ CMD sensor가 생성되지 않도록 처리
- ✅ 이벤트 발생 시점에만 업데이트

## 테스트 방법

1. Home Assistant 재시작
2. Developer Tools > States에서 doorbell 엔티티 확인
3. 버튼 클릭 → last_pressed 시간 확인
4. 외부 패킷 수신 → last_pressed 시간 업데이트 확인
5. 이벤트 후 갱신 주기 확인 (매초 갱신되지 않아야 함)
