# 구현 및 검증 결과

검증일: 2026-09-29, Linux / Python 3.12.3.

## 구현

| 파일 | 구현 내용 |
|---|---|
| `core.py` | 설정 dataclass, 독립 왕복 원본, 고정 xi, cosine support, 선분 기반 등방·비등방 gate, 끝점 보호, norm 제한, correction 재수정·흡수·재현 |
| `editor.py` | 원본/확정/편집/드래그 상태, 세 모드, both 대응·그룹 이력, undo/redo/reset/cancel, 입력 동결, revision, 공통 명령 |
| `validation.py` | min-jerk 호 길이 시간 재배분, 일정 간격 실행 샘플, EE 속도·기하 검사, 위치별 결과, 미래 로봇 검사 프로토콜과 명시적 모의 검사 |
| `storage.py` | strict 설정·schema·단위·revision 검사, 원본/xi/correction 저장, 원자적 JSON 교체, 재구성 일치 확인 |
| `viewer.py` | 2D 가상 카메라 작업대, 픽셀 선택·역투영 손 입력, 깊이 조절, 높이 RGBA, 검은 비교선·대응점·영향·화살표·실패 표시, 한/영 UI, CLI |

요청한 다섯 구현 파일과 얇은 패키지 연결 파일, 설정 파일, 세 테스트 파일, 설치·설계 문서를 작성했다. ROS·로봇 제어·실제 센서/API 의존성은 추가하지 않았다.

## 실제 실행한 검증

가상환경을 생성하고 editable 설치를 수행했다. 검증 환경은 numpy 2.5.3, matplotlib 3.11.2, pytest 9.1.1이다. 셸에 기존 ROS `PYTHONPATH`가 설정되어 있어 처음의 일반 pytest는 외부 launch_testing 플러그인의 yaml 의존성으로 수집 전에 실패했다. 외부 경로를 제외한 아래 명령으로 프로젝트 자체를 검증했다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
env -u PYTHONPATH .venv/bin/python -m pip check
env -u PYTHONPATH .venv/bin/python -m pytest -q
```

- 전체 자동 테스트: **96 passed** (최초 전체 완료 실행 3.97 s).
- 가상환경 의존성 검사: **No broken requirements found**.
- 요청한 26개 항목을 포함해 경로 독립성, 이벤트 수 불변성, +8 cm 뒤 +3 cm, 남은 raw field 중복 방지, 모드/경로별 흡수, source-local/재사용 gate, 부드러운 경계·saturation을 검증했다.
- 서로 다른 원본 샘플 사이의 both 대응점도 기존 모양을 유지하며 같은 변위를 받는 것을 검증했다. 국소 support 바깥으로 보간 가중치가 새지 않는 것도 검사했다.
- 두 경로의 원자적 이력, redo 분기 제거, committed 격리, reset undo, 작은 실효 수정 거부, 이전 revision 무효화, 로봇 NOT_EVALUATED를 검증했다.
- 카메라 투영/역투영, 픽셀 선택 반경·동률, 깊이 배율, 공통 색상 정규화, 합성 마우스·키 이벤트, 창 이탈 취소, 검사 실패 화면 유지, 저장/로드 연결을 검증했다.
- 잘못된 schema·단위·설정·revision·실행 샘플을 거부하며, 교체 실패 시 기존 JSON을 보존하는 것을 검사했다.

CLI로 직선과 bump의 Agg 렌더링, 저장 JSON의 CLI 재로드를 실행했다.

```bash
env -u PYTHONPATH .venv/bin/python -m pac_path_editor \
  --config configs/demo.json --demo bump --headless \
  --screenshot artifacts/bump_initial.png
env -u PYTHONPATH .venv/bin/python -m pac_path_editor \
  --config configs/demo.json --headless \
  --screenshot artifacts/straight_initial.png
env -u PYTHONPATH .venv/bin/python -m pac_path_editor \
  --load artifacts/demo_session.json --headless \
  --screenshot artifacts/reloaded.png
```

별도 실행한 bump 중앙 both −6 cm 사례에서 두 record가 생성되었고, preview/해제/확정/JSON 재로드의 기하 배열이 bit-exact 일치했다. 재계산된 편도 시간은 각각 3.36 s, 시간 샘플의 최대 EE 속도는 outbound 0.343715015 m/s, return 0.345635539 m/s로 시험 한도 0.35 m/s 이하였다. JSON에는 여섯 로봇 검사 모두 NOT_EVALUATED가 저장되었다.

## GUI 확인 범위

- **실제 GUI 창 실행 확인**: 사용 가능한 X 디스플레이에서 TkAgg / FigureCanvasTkAgg로 창을 열고 GUI 이벤트 루프를 처리한 후 종료했다. 렌더링 크기는 1762×913이었다.
- Agg 초기 화면, both 드래그, 확정, 모의 실패, 재로드 화면을 생성했다. 한국어 폰트 표시와 검은 비교선·동일 이동·대응점·높이 색상을 이미지로 확인했다.
- 자동 테스트는 matplotlib callback에 합성 MouseEvent/KeyEvent를 전달한다. 이는 사람이 마우스·휠을 직접 조작한 사용자 검증과 다르다.
- **사람의 실제 마우스 조작·사용성 평가는 미확인**이다. README에 수동 데모 순서를 작성했다.

생성 이미지와 데모 JSON은 로컬 `artifacts/`에 있으며 생성물로서 Git 업로드에서 제외한다.

## 남은 한계

실제 로봇·카메라·음성·손 추적은 연결하지 않았으며 로봇의 정지 상태도 확인하지 않는다. 연속 자세 해석, 관절 한계, 특이점, 자기충돌, 관절 속도·가속도, 토크는 미검사다. UI나 저장 결과는 로봇 실행 승인을 뜻하지 않는다.

기하는 샘플 폴리라인이고 가중치도 저장된 cosine knot 사이의 선형 보간이다. 출발·도착의 호 길이 속도는 부드럽지만 모든 곡률·가속도를 보장하지 않는다. 흡수 시 주변 곡선이 재구성되는 효과는 DESIGN에 명시했다. 장비의 공간 gate·끝점 보호·속도 등 실제 운용 수치는 확정하지 않았다.

다른 원본에 correction을 재사용하는 계산은 제공하지만 UI에서 새로운 작업 경로로 전환하는 기능은 포함하지 않는다. 실행과 센서·로봇 검사기 연결은 후속 단계다.
