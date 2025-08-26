# Ezville Wallpad 수정 요약 - 2025-01-21

## 수정된 파일들
1. const.py
2. sensor.py
3. __init__.py

## 주요 수정 내용

### 1. 로그 레벨 처리 개선 (const.py, __init__.py)
- **문제**: 처음 등록하면 로그레벨이 debug로 작동
- **해결**: 
  - Home Assistant의 로그 레벨을 그대로 따르도록 수정
  - `log_debug`, `log_info`는 파일에만 기록 (_log_to_file_only 함수 사용)
  - `log_warning`, `log_error`는 HA 로그와 파일 모두에 기록
  - __init__.py에서 logger.propagate = False 설정으로 중복 로그 방지

### 2. 로그 중복 문제 해결 (__init__.py)
- **문제**: logs 폴더에 동일한 로그가 2개씩 기록
- **해결**:
  - 모든 서브모듈 로거에 대해 파일 핸들러 중복 제거
  - logger.propagate = False 설정으로 부모 로거로의 전파 방지
  - 각 로거별로 개별 설정 적용

### 3. CMD Sensor 개선 (sensor.py)
- **First detected, Last detected 제거**:
  - EzvilleCmdSensor 클래스에서 관련 속성 제거
  - extra_state_attributes에서 시간 관련 속성 제거

- **상태 변경 체크 개선**:
  - _handle_coordinator_update에서 이전 상태와 비교
  - CMD sensor는 'data' 필드만 비교하여 불필요한 업데이트 방지
  - 상태가 동일하면 업데이트 스킵

- **사용 불가 상태 방지**:
  - 상태 비교 로직 개선으로 잘못된 unavailable 상태 방지
  - coordinator에서도 CMD sensor 업데이트 시 data 필드만 비교

### 4. 로그 함수 일괄 적용 (const.py)
- log_debug, log_info, log_warning, log_error 함수가 한 곳에서 정의
- 모든 모듈에서 이 함수들을 import하여 사용
- 일관된 로그 처리 보장

## 테스트 필요 사항
1. Home Assistant 재시작 후 로그 레벨 확인
2. logs/ezville_wallpad.log 파일에 중복 로그가 없는지 확인
3. CMD sensor 상태 업데이트가 올바르게 작동하는지 확인
4. CMD sensor가 unavailable 상태가 되지 않는지 모니터링

## 추가 참고사항
- Home Assistant 로그에는 WARNING 이상만 표시
- 파일 로그에는 DEBUG 레벨부터 모든 로그 기록
- CMD sensor는 0x01 (상태 요청) 커맨드는 생성하지 않음
