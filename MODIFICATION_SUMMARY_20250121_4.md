# Ezville Wallpad 수정 요약 - 2025-01-21 (원복)

## 수정 사항

### 1. async_create_task 문제 수정
- 잘못된 async_create_task 사용을 제거
- coordinator.py의 _on_device_discovered에서 직접 `self.async_set_updated_data(self.devices)` 호출
- _device_update_callback에서는 원래대로 `call_soon_threadsafe` 사용

### 2. 센서 업데이트 원복
- sensor.py, binary_sensor.py의 모든 `add_job`를 `call_soon_threadsafe`로 원복
- 이전에 정상 작동하던 방식으로 복원

### 3. CMD 센서 필터링은 유지
- button.py, binary_sensor.py의 `is_cmd_sensor` 체크는 그대로 유지
- CMD 센서가 별도 기기 그룹으로 생성되는 것은 방지

## 주요 변경 내용

```python
# 잘못된 수정 (제거됨)
async def update_data():
    self.async_set_updated_data(self.devices)
self.hass.async_create_task(update_data())

# 올바른 수정 (복원됨)
self.async_set_updated_data(self.devices)

# 스레드에서 호출 시
self.hass.loop.call_soon_threadsafe(
    lambda: self.async_set_updated_data(self.devices)
)
```

## 테스트 필요 사항
1. Home Assistant 재시작
2. 새로운 디바이스가 동적으로 추가되는지 확인
3. 센서 값이 정상적으로 업데이트되는지 확인
4. CMD 센서가 올바른 기기 그룹에 표시되는지 확인
