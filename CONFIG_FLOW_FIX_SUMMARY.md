# Config Flow 수정 요약

## 수정 일자
2025-08-28

## 수정 내용

### config_flow.py 파일 수정
Home Assistant 2025.12에서 제거될 예정인 deprecated 기능 경고를 해결했습니다.

#### 변경 사항:
1. **EzvilleWallpadOptionsFlowHandler 클래스의 __init__ 메서드**:
   - `self.config_entry = config_entry` → `self._config_entry = config_entry`로 변경
   - OptionsFlow의 __init__은 매개변수를 받지 않는다는 경고 해결

2. **모든 self.config_entry 참조 변경**:
   - `self.config_entry.data.get()` → `self._config_entry.data.get()`
   - `self.config_entry.options.get()` → `self._config_entry.options.get()`
   - 총 13개 위치에서 변경됨

## 해결된 문제
다음 deprecated 경고가 해결되었습니다:
```
WARNING (MainThread) [homeassistant.helpers.frame] Detected that custom integration 'ezville_wallpad' 
sets option flow config_entry explicitly, which is deprecated at 
custom_components/ezville_wallpad/config_flow.py, line 351: self.config_entry = config_entry. 
This will stop working in Home Assistant 2025.12
```

## 주요 변경 라인
- 350번 라인: `__init__` 메서드의 속성명 변경
- 360번 라인: connection_type 가져오기
- 370-399번 라인: MQTT 관련 옵션 기본값 설정
- 406-427번 라인: Serial/Socket 관련 옵션 기본값 설정

이제 Home Assistant 2025.12 이후에도 정상적으로 동작할 것입니다.
