# Ezville Wallpad Home Assistant Integration

[![GitHub Release](https://img.shields.io/github/release/pageskr/ha-ezville-wallpad.svg?style=flat-square)](https://github.com/pageskr/ha-ezville-wallpad/releases)
[![GitHub License](https://img.shields.io/github/license/pageskr/ha-ezville-wallpad.svg?style=flat-square)](https://github.com/pageskr/ha-ezville-wallpad/blob/main/LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%2341BDF5.svg?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

🏠 **이지빌(Ezville) 월패드**를 Home Assistant와 연동하는 **완전한 네이티브 통합**입니다. RS485 직렬 통신을 통해 조명, 플러그, 온도조절기, 환기팬, 가스밸브, 엘리베이터, 도어벨 등을 **웹 UI에서 직접 제어**할 수 있습니다.

![Ezville Wallpad](https://img.shields.io/badge/Ezville-Wallpad-blue?style=for-the-badge)
![Made in Korea](https://img.shields.io/badge/Made%20in-Korea-red?style=for-the-badge)

## ✨ 주요 특징

### 🎯 **완전한 Home Assistant 통합**
- ✅ **웹 UI 설정**: 복잡한 설정 파일 없이 브라우저에서 모든 설정
- ✅ **실시간 제어**: 월패드 상태 변화 즉시 반영 및 양방향 제어  
- ✅ **네이티브 엔티티**: MQTT 없이 직접 HA 엔티티로 등록
- ✅ **자동 감지**: 연결된 장치 자동 검색 및 등록
- ✅ **HACS 지원**: 원클릭 설치 및 자동 업데이트

### 🏠 **지원 장치 (총 8종)**
- 🏮 **조명**: 방별 조명 ON/OFF 제어
- 🔌 **스마트플러그**: ON/OFF 제어 + 실시간 전력 모니터링
- 🌡️ **온도조절기**: 난방/끄기, 목표온도 설정, 외출모드
- 💨 **환기팬**: 3단계 속도 조절 + 바이패스/난방 운전모드  
- ⛽ **가스밸브**: 상태 모니터링 + 원격 차단 기능
- 🛗 **엘리베이터**: 호출 버튼 + 운행 상태 확인
- 🔔 **도어벨**: 벨/통화/문열기/취소 + 방문자 알림
- ⚡ **에너지**: 전력/가스/수도 사용량 실시간 모니터링

### 🔧 **유연한 연결 방식**
- **🔗 시리얼 포트**: USB-to-RS485 컨버터 사용
- **🌐 TCP/IP 소켓**: 네트워크를 통한 원격 연결
- **📡 MQTT**: MQTT 브로커를 통한 연결 (실시간 이벤트 기반)

## 📸 스크린샷

| 웹 UI 설정 | 장치 제어 | 자동화 |
|-----------|----------|--------|
| ![Config](docs/images/config.png) | ![Devices](docs/images/devices.png) | ![Automation](docs/images/automation.png) |

## 📦 설치

### 🎯 HACS를 통한 설치 (권장)

1. **HACS** → **Integrations** → **우측 상단 ⋮** → **Custom repositories**
2. **Repository**: `https://github.com/pageskr/ha-ezville-wallpad`
3. **Category**: `Integration` 선택
4. **"ADD"** 클릭 후 **"Ezville Wallpad"** 검색하여 설치
5. **Home Assistant 재시작**

### 📁 수동 설치

```bash
# 저장소 클론
git clone https://github.com/pageskr/ha-ezville-wallpad.git

# 파일 복사
cp -r custom_components/ezville_wallpad /config/custom_components/

# Home Assistant 재시작
```

## ⚙️ 설정

### 1단계: 통합 추가

**설정** → **기기 및 서비스** → **통합 추가** → **"Ezville Wallpad"** 검색

### 2단계: 연결 방식 선택

#### 🔗 직렬 포트 연결
```
연결 방식: Serial
시리얼 포트: /dev/ttyUSB0
스캔 간격: 30초 (기본값)
최대 재시도: 10회 (기본값)
활성화 장치: 모든 장치 (기본값)
```

#### 🌐 소켓 연결  
```
연결 방식: Socket
호스트: 192.168.1.100
포트: 8899
스캔 간격: 30초 (기본값)
최대 재시도: 10회 (기본값)
활성화 장치: 모든 장치 (기본값)
```

#### 📡 MQTT 연결
```
연결 방식: MQTT
브로커 주소: 192.168.1.100
포트: 1883
사용자명/비밀번호: (선택사항)
수신 토픽: ezville/wallpad/recv
송신 토픽: ezville/wallpad/send
QoS: 0 (기본값, 0-2 선택가능)
활성화 장치: 모든 장치 (기본값)
```

**MQTT 모드 특징:**
- 실시간 이벤트 기반 업데이트 (폴링 없음)
- 동적 디바이스 발견 및 자동 추가
- 낮은 네트워크 부하
- 원격 접속 가능

### 3단계: 고급 설정 (옵션)

- **📊 패킷 덤프**: 디버깅을 위한 패킷 로깅 (1-300초)
- **📝 파일 로깅**: `/config/logs/ezville_wallpad.log`에 상세 로그 저장
- **🎛️ 장치 선택**: 필요한 장치 타입만 활성화

## 🏠 사용 방법

### 자동 생성되는 엔티티

설정 완료 후 다음 엔티티들이 자동으로 생성됩니다:

```yaml
# 조명
light.light_1_1  # 거실 조명 1
light.light_1_2  # 거실 조명 2

# 스마트플러그 
switch.plug_1_1        # 거실 플러그 1
sensor.plug_1_1_power  # 거실 플러그 1 전력

# 온도조절기
climate.thermostat_1   # 거실 온도조절기

# 환기팬
fan.ventilation_fan    # 욕실 환기팬

# 가스밸브
valve.gas_valve        # 주방 가스밸브

# 엘리베이터
button.call_elevator   # 엘리베이터 호출
sensor.elevator_status # 엘리베이터 상태

# 도어벨
button.doorbell_call   # 호출
button.doorbell_talk   # 통화  
button.doorbell_open   # 문열기
button.doorbell_cancel # 취소
binary_sensor.doorbell_ringing # 벨소리 울림중
binary_sensor.doorbell_ring    # 방문자 감지

# 에너지
sensor.energy_power   # 전력 사용량
sensor.energy_usage   # 전력 누적량
```

### 🤖 자동화 예제

#### 현관문 벨이 울리면 스마트폰 알림
```yaml
automation:
  - alias: "도어벨 푸시 알림"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell_ring
      to: "on"
    action:
      service: notify.mobile_app_your_phone
      data:
        title: "🔔 방문자"
        message: "현관문 벨이 울렸습니다!"
        data:
          actions:
            - action: "OPEN_DOOR"
              title: "문열기"
            - action: "TALK"
              title: "통화"

  - alias: "도어벨 문열기 액션"
    trigger:
      platform: event
      event_type: mobile_app_notification_action
      event_data:
        action: "OPEN_DOOR"
    action:
      service: button.press
      target:
        entity_id: button.doorbell_open
```

#### 외출 시 모든 조명 끄기 + 가스밸브 차단
```yaml
automation:
  - alias: "외출 시 안전 점검"
    trigger:
      platform: state
      entity_id: person.yourself
      to: "not_home"
      for: "00:05:00"
    action:
      - service: light.turn_off
        target:
          entity_id: all
      - service: valve.close_valve
        target:
          entity_id: valve.gas_valve
      - service: notify.mobile_app_your_phone
        data:
          message: "외출 모드: 조명 차단, 가스밸브 잠금 완료 ✅"
```

#### 에너지 사용량 모니터링
```yaml
automation:
  - alias: "전력 사용량 경고"
    trigger:
      platform: numeric_state
      entity_id: sensor.energy_power
      above: 3000  # 3kW 초과 시
    action:
      service: notify.mobile_app_your_phone
      data:
        title: "⚡ 전력 사용량 경고"
        message: "현재 전력 사용량: {{ states('sensor.energy_power') }}W"
```

## 🛠️ 고급 기능

### 🔧 서비스

통합은 다음 서비스들을 제공합니다:

```yaml
# 원시 명령 전송
service: ezville_wallpad.send_raw_command
data:
  device_id: "0x0E"
  command: "0x41"  
  data: "0x01"

# 패킷 덤프 (디버깅)
service: ezville_wallpad.dump_packets
data:
  duration: 30

# 연결 재시작
service: ezville_wallpad.restart_connection

# 장치 테스트
service: ezville_wallpad.test_device
data:
  device_type: "light"
```

### 📊 로깅 및 디버깅

#### 디버그 로깅 활성화
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.ezville_wallpad: debug
```

#### 파일 로그 확인
```bash
# 로그 파일 위치
tail -f /config/logs/ezville_wallpad.log

# 실시간 패킷 모니터링
grep "DUMP:" /config/logs/ezville_wallpad.log
```

## 🚨 문제 해결

### 연결 문제

<details>
<summary><strong>❌ "Failed to connect" 오류</strong></summary>

**원인**: USB 장치 인식 실패 또는 권한 문제

**해결방법**:
```bash
# 1. USB 장치 확인
ls -la /dev/ttyUSB*

# 2. 권한 설정
sudo chmod 666 /dev/ttyUSB0  

# 3. Docker 환경 (docker-compose.yml)
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```
</details>

<details>
<summary><strong>⏱️ 장치가 감지되지 않음</strong></summary>

**원인**: RS485 배선 문제 또는 통신 설정

**해결방법**:
1. **배선 확인**: A, B, GND 연결 상태
2. **극성 확인**: A ↔ B 선 바뀜 여부  
3. **패킷 덤프**: 통합 옵션에서 패킷 덤프 활성화
4. **통신 속도**: 9600 baud, 8N1 확인
</details>

<details>
<summary><strong>🐌 상태 업데이트 지연</strong></summary>

**해결방법**:
- 스캔 간격을 10-15초로 단축
- 다른 월패드 앱과 동시 사용 중단
- 네트워크 간섭 확인
</details>

### 성능 최적화

| 설정 | 권장값 | 설명 |
|------|--------|------|
| 스캔 간격 | 15-30초 | 너무 짧으면 통신 부하 증가 |
| 최대 재시도 | 5-10회 | 네트워크 불안정 시 증가 |
| 활성화 장치 | 필요한 것만 | 불필요한 장치는 비활성화 |
| 파일 로깅 | 디버깅 시에만 | 성능 영향 최소화 |

## 🏗️ 개발 정보

### 📁 프로젝트 구조
```
custom_components/ezville_wallpad/
├── __init__.py              # 통합 진입점
├── manifest.json            # 통합 메타데이터  
├── config_flow.py           # 설정 UI 로직
├── coordinator.py           # 데이터 동기화
├── rs485_client.py          # RS485 통신 핸들러
├── device.py               # 공통 장치 클래스
├── [platform].py           # 플랫폼별 엔티티 (light, switch 등)
├── translations/           # 다국어 지원
├── services.yaml           # 서비스 정의
└── strings.json            # UI 문자열
```

### 🔌 지원 플랫폼
- ✅ **light**: 조명 제어
- ✅ **switch**: 스마트플러그  
- ✅ **sensor**: 센서 (전력, 상태 등)
- ✅ **climate**: 온도조절기
- ✅ **fan**: 환기팬
- ✅ **valve**: 가스밸브
- ✅ **button**: 버튼 (엘리베이터, 도어벨)
- ✅ **binary_sensor**: 이진 센서 (도어벨 감지)

## 🤝 기여하기

이 프로젝트에 기여하고 싶다면:

1. **Fork** 이 저장소
2. **Feature 브랜치** 생성: `git checkout -b feature/amazing-feature`  
3. **변경사항 커밋**: `git commit -m 'Add amazing feature'`
4. **브랜치에 Push**: `git push origin feature/amazing-feature`
5. **Pull Request** 생성

### 개발 환경 설정
```bash
# 개발용 설치
git clone https://github.com/pageskr/ha-ezville-wallpad
cd ha-ezville-wallpad

# Home Assistant 개발 서버 실행  
hass -c config --skip-pip

# 코드 스타일 검사
black custom_components/
pylint custom_components/
```

## 📄 라이선스

이 프로젝트는 **MIT 라이선스** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 💝 후원

이 프로젝트가 도움이 되셨다면:
- ⭐ **GitHub 스타** 눌러주세요
- 🐛 **버그 리포트**나 💡 **기능 제안**을 남겨주세요  
- ☕ [**커피 한 잔** 후원](https://pages.kr/donate)

## 📞 지원

- **🐛 버그 리포트**: [GitHub Issues](https://github.com/pageskr/ha-ezville-wallpad/issues)
- **💬 질문 및 토론**: [GitHub Discussions](https://github.com/pageskr/ha-ezville-wallpad/discussions)
- **🇰🇷 한국어 커뮤니티**: [Home Assistant 한국 커뮤니티](https://cafe.naver.com/koreassistant)

## 📈 통계

![GitHub stars](https://img.shields.io/github/stars/pageskr/ha-ezville-wallpad?style=social)
![GitHub forks](https://img.shields.io/github/forks/pageskr/ha-ezville-wallpad?style=social)
![GitHub issues](https://img.shields.io/github/issues/pageskr/ha-ezville-wallpad)
![GitHub pull requests](https://img.shields.io/github/issues-pr/pageskr/ha-ezville-wallpad)

## 🔄 변경 이력

### v1.0.2 (2025-01-21)
- ✅ 도어벨 버튼 확장 (Call, Talk, Open, Cancel 4개 버튼)
- ✅ 도어벨 Ring 센서 추가 (방문자 감지)
- ✅ 도어벨 패킷 자동 감지 기능
  - 0x10, 0x90: Call 버튼 상태 업데이트
  - 0x13, 0x93: Ring 센서 ON (방문자 감지)
  - 0x11, 0x91: Cancel 이벤트 시 Ring 센서 OFF
  - 0x12, 0x92: Talk 버튼 상태 업데이트
  - 0x22, 0xA2: Open 버튼 상태 업데이트
- ✅ 버튼 및 센서에 패킷 정보 속성 추가
- ✅ 특정 도어벨 명령어 CMD 센서 생성 차단

### v1.0.1 (2025-08-17)
- ✅ MQTT QoS 설정 추가
- ✅ MQTT 모드에서 폴링 제거 (이벤트 기반)
- ✅ 동적 디바이스 자동 추가 기능
- ✅ deprecated 경고 수정
- ✅ 디버그 로그 강화

---

<p align="center">
<strong>Made with ❤️ by <a href="https://pages.kr">Pages in Korea</a></strong><br>
🏠 <em>스마트홈을 더 스마트하게</em>
</p>
