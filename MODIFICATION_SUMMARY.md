# EzVille Wallpad MQTT 데이터 처리 기능 수정 요약

## 수정된 파일 목록

1. **ezville_wallpad.py**
   - MQTT 데이터 수신을 위한 콜백 함수 추가 (`on_mqtt_data_message`)
   - 패킷 파싱 및 중복 제거 로직 구현
   - 알 수 없는 기기 자동 감지 및 등록 기능 추가
   - 가상 연결 객체를 통한 기존 패킷 처리 로직 재사용
   - 로그 레벨 설정 기능 추가

2. **config.json**
   - `mqtt_data_topic` 옵션 추가
   - 로그 레벨 설정 옵션 추가

3. **options_standalone.json**
   - `mqtt_data_topic` 옵션 추가
   - 로그 레벨 설정 옵션 추가

4. **MQTT_DATA_PROCESSING.md** (신규)
   - MQTT 데이터 처리 기능 상세 문서화

5. **info.md**
   - MQTT 데이터 연결 방식 추가

## 주요 기능 개선사항

### 1. MQTT 패킷 처리
- F7로 시작하는 패킷 자동 분리
- 시그니처 기반 중복 패킷 필터링
- 변경된 값만 처리하여 성능 최적화

### 2. 알 수 없는 기기 지원
- 등록되지 않은 기기 자동 감지
- "Unknown Device XX" 형태로 엔티티 생성
- 원시 패킷 데이터를 상태값으로 표시

### 3. 기존 코드 재사용
- EzVilleSocket 클래스를 MQTT 모드로 확장
- 기존 패킷 처리 로직을 그대로 활용
- 코드 중복 최소화

### 4. 디버깅 지원
- 로그 레벨 설정 가능 (DEBUG/INFO/WARNING/ERROR)
- 패킷 처리 과정 상세 로깅
- 중복 패킷 통계 정보

## 사용 방법

1. `config.json` 또는 `options_standalone.json`에서 MQTT 설정:
   ```json
   "mqtt": {
     "mqtt_data_topic": "ezville/raw/data"
   }
   ```

2. MQTT 브로커에 원시 데이터 전송

3. 자동으로 기기 감지 및 Home Assistant 엔티티 생성

## 테스트 완료 항목

- ✅ F7 패킷 분리 로직
- ✅ 중복 패킷 필터링
- ✅ 알 수 없는 기기 처리
- ✅ 기존 기기 상태 업데이트
- ✅ MQTT Discovery 통합
- ✅ 로깅 시스템

## 향후 개선 가능 사항

1. 웹 UI를 통한 MQTT 데이터 토픽 설정
2. 실시간 패킷 모니터링 대시보드
3. 패킷 분석 통계 기능
4. 커스텀 패킷 파서 플러그인 지원
