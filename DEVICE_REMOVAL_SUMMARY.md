# 기기 삭제 기능 구현 요약

## 수정 일자
2025-08-28

## 수정 내용

### __init__.py 파일 수정

#### 추가된 import:
```python
from homeassistant.helpers.device_registry import DeviceEntry
```

#### 추가된 함수: async_remove_config_entry_device
Home Assistant의 표준적인 기기 삭제 기능을 구현하는 함수를 추가했습니다.

```python
async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
```

## 기능 설명

### 기기 삭제 프로세스
1. **권한 확인**: 삭제하려는 기기가 현재 통합(config_entry)에 속하는지 확인
2. **기기 식별**: DeviceEntry에서 기기 식별자 추출
3. **연관 기기 찾기**: 
   - 해당 기기와 연관된 모든 하위 엔티티 찾기
   - 예: "Light 1" 기기 삭제 시 light_1_1, light_1_2, light_1_3 모두 제거
4. **기기 제거**:
   - coordinator.devices에서 기기 정보 삭제
   - 발견된 기기 목록에서 제거
5. **삭제 승인**: True 반환으로 Home Assistant에 삭제 허용

### UI에서 사용 방법
1. Home Assistant의 설정 → 기기 및 서비스로 이동
2. Ezville Wallpad 통합 선택
3. 삭제하려는 기기 선택
4. 기기 상세 페이지에서 ⋮ (점 3개) 메뉴 클릭
5. **"기기 삭제"** 옵션이 활성화되어 있음
6. 클릭하여 기기 삭제

### 삭제 가능한 기기들
- Light 그룹 (예: Light 1, Light 2)
- Plug 그룹 (예: Plug 1, Plug 2)
- 단일 기기들 (Thermostat, Ventilation, Gas, Energy, Elevator, Doorbell)
- Unknown 기기
- CMD 센서들

### 주요 특징
- **그룹 단위 삭제**: Light 1을 삭제하면 Light 1-1, Light 1-2, Light 1-3도 함께 삭제
- **안전한 삭제**: 다른 통합의 기기는 삭제할 수 없음
- **메모리 정리**: coordinator와 client의 내부 상태에서도 제거

이 기능으로 더 이상 필요하지 않거나 잘못 감지된 기기들을 쉽게 정리할 수 있습니다.
