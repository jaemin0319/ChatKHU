# KHU AI Challenge 2026

말과 손짓으로 로봇팔 경로를 고치는 인터페이스 (ChatKHU 활용)

## 작업 규칙

- main 브랜치에는 직접 올리지 않습니다.
- 각자 자기 브랜치에서 작업하고, 합칠 때는 Pull Request를 올립니다.
- branch 이름은 무엇을 만들었는지 알 수 있는 이름으로 합니다.
- API 키, 개인정보는 절대 올리지 않습니다.

---

# 이 브랜치: `work/pinch-khu-demo`

`chatkhu/voice-mujoco-path-edit`(카메라 보정, 핀치, 쿠옹이 음성, MuJoCo)에서 이어 만든 시연 브랜치입니다. **설치부터 보정·실행·문제 해결까지는 [docs/PINCH_KHU_SETUP.md](docs/PINCH_KHU_SETUP.md)** 를 따라 하면 됩니다. 계획서: [docs/PINCH_KHU_INTEGRATION_PLAN.md](docs/PINCH_KHU_INTEGRATION_PLAN.md).

MuJoCo 시뮬레이터에 로봇팔의 경로가 그려지고, 사용자는 **말과 손으로** 경로를 고칩니다.

- **수정 모드:** "쿠옹아, 경로 수정할래"라고 하면 시뮬레이터가 **실제로** 수정 모드가 되고, 그 뒤에 쿠옹이가 "네. 손가락으로 경로를 수정해 주세요."라고 안내합니다. 손 입력은 수정 모드에서만 받습니다(음성 없이 E 키). 마우스는 언제나 됩니다.
- **손:** 검지를 펴서 0.4초 가리키면 경로 점을 고르고, 엄지와 검지로 집으면(핀치) 그 점을 잡아 **손이 3D로 움직인 만큼 1:1로** 옮깁니다(Astra 깊이). 깊이를 못 읽거나 RGB와 깊이 프레임의 시각이 어긋나면 **잡지 않고 이유를 알려 주며**, 드래그 중 깊이가 1초 넘게 끊기면 수정을 취소해 원래 경로로 돌립니다. 높이만 바꾸는 2D로 몰래 바뀌지 않습니다(깊이 없는 웹캠 모드는 화면에 "2D 높이 모드"로 따로 표시).
- **말:** "쿠옹아, 여기 위로 조금 올려줘" → **ChatKHU(Gemini Live)** 의 쿠옹이가 시뮬레이터에 명령을 보냅니다. "이전으로"는 손·마우스·말 수정을 같은 기록에서 되돌립니다.
- **카메라 화면:** Astra를 보정하면 실제 영상 위에 로봇 기준축, 시작점 A, 목표점 B, 경로가 겹쳐 그려집니다. 보정 결과가 통과했다는 것만으로 믿지 않고, 보정에 쓰지 않은 **ArUco 고정 표지**로 시작할 때와 실행 중에 정합을 다시 확인합니다(오른쪽 위 배지). 확인될 때만 3D 핀치를 씁니다.
- **검증과 자동 이동:** "이 경로로 할게 / 수정 완료" → 12항목 검증 → 실패면 빨간 점·이유와 함께 수정 모드로 돌아가고, 통과하면 **다시 묻지 않고** 그 검증된 경로로 시뮬레이터가 움직입니다. 그 사이 경로가 바뀌거나, 수정 모드를 켜거나, X, 음성 연결 끊김, 로봇 상태 변화가 있으면 예약이 취소됩니다. 버튼 S·V·Y는 지금처럼 수동입니다. 정지는 언제든 **X 키** 또는 "멈춰".
- **카메라 목표 (별도 단계):** G 키 또는 "쿠옹아, 이 물체로 목표 바꿔 줘" → 책상 위 물체의 윗면 중심 위로 목표를 바꾸고 새 경로를 만듭니다.
- 조금 · 보통 · 많이는 **2 · 5 · 8 cm**. **실제 로봇은 움직이지 않습니다.** 모든 동작은 시뮬레이터 안에서만 일어나며, 검증·좌표가 실물 로봇의 동작을 보증하지 않습니다.

## 한눈에 보기: 대화 흐름

### 1. 전체 흐름

수정 모드를 켜고 가는 길을 고친 뒤 "수정 완료"로 검증하고, 통과하면 바로 목표까지 갑니다(1단계). 도착하면 돌아오는 길을 고칠지 그대로 거꾸로 돌아올지 고릅니다(2단계). 움직이는 중에는 언제든 "멈춰"(또는 X)로 멈추고, 계속 갈지 돌아갈지 고를 수 있습니다.

![전체 흐름](docs/flow/flow1_overall.png)

### 2. 경로 수정 흐름 (위 그림의 ①)

![경로 수정 흐름](docs/flow/flow2_edit.png)

멈춘 뒤의 흐름: [docs/flow/flow3_stop.png](docs/flow/flow3_stop.png)

## 준비물

- **컴퓨터:** Ubuntu 24.04, Python 3.12, OpenGL 그래픽. ROS 2가 깔려 있어도 됩니다(`env.sh`가 경로를 분리).
- **Orbbec Astra Pro** — 실제 영상 겹치기, 3D 핀치, 카메라 목표. 없으면 시뮬레이터 카메라 화면 + 마우스로 시연합니다.
- **A4 두 장, 펜, 테이프**(보정), **ArUco 표지 인쇄물 2장 이상, 줄자**(정합 확인).
- **마이크·스피커, ChatKHU API 키**(`BAZE_API_KEY`, 저장소 밖 파일) — 없으면 키보드 입력이나 `python -m voice.sim_dryrun`.

## 폴더 구성

- `voice/` — 쿠옹이(ChatKHU Gemini Live). `prompts/system_v6.md` 지시문, `tools.py` 함수 14개, `sim_link.py` 시뮬레이터 연결, `wake_word.py` 호출어·질문 창, `sim_dryrun.py` AI 없이 함수 시험, `env.sh` 환경.
- `mujoco_sim/` — MuJoCo 시뮬레이터. 경로 생성, 마우스·손 수정, 12항목 검증, 자동 이동 예약, 실행·멈춤, 카메라 영상 겹치기와 정합 감시(`pac_calib.py`), 손(`hand_input.py`, `hand_depth.py`), 카메라 목표(`vision_goal.py`).
- `pac_vision/` — Astra 보정(카메라 → base_ref), 정합, 깊이 읽기, 카메라 신원(`devices.py`), 고정 표지 확인(`markers.py`, `scripts/check_markers.py`).
- `6dof_description/` — 6축 로봇팔 모델과 그리퍼. `path 편집/` — 경로 편집 알고리즘(시뮬레이터가 그대로 씀).
- `docs/` — 재현 문서, 계획서, 흐름 그림.

## 빠른 시작 (자세한 내용은 docs/PINCH_KHU_SETUP.md)

```bash
mkdir -p ~/pinch_khu_ws && cd ~/pinch_khu_ws
git clone https://github.com/jaemin0319/26_project_manipulator.git && cd 26_project_manipulator
git switch work/pinch-khu-demo
# 시스템 패키지·Astra 드라이버·두 가상환경·API 키: docs/PINCH_KHU_SETUP.md 2~4절
```

카메라 없이 바로 보기(시뮬레이터 카메라 + 마우스 + 음성):

```bash
# 터미널 1
cd ~/pinch_khu_ws/26_project_manipulator/mujoco_sim && source scripts/env.sh
python -m pinch_sim.app --target-r 0.275 --target-deg 10 --voice-gateway
# 터미널 2
cd ~/pinch_khu_ws/26_project_manipulator && source voice/env.sh
python -m voice --sim                 # 키가 없으면: python -m voice.sim_dryrun
```

Astra로 전부(보정·고정 표지·로봇 위치는 그 문서 6절, **컴퓨터와 카메라 배치마다 각자 보정**):

```bash
python -m pinch_sim.app --calib ../pac_vision/config/cam2base.yaml --video auto --hand --depth --voice-gateway \
  --start 0,0,0.25 --goal 0,0.20
```

## 좌표 한 줄 요약

모든 입력 좌표는 보정 좌표계 base_ref(m, A4 대각선 교점 원점, +X 앞 = A4 화살표, +Y 왼쪽, +Z 위, 책상면 z = 0)입니다. 로봇 바닥 중심의 위치·방향은 `pac_vision/config/robot_pose.yaml` 또는 `--robot-pose X,Y,YAW`로 줍니다(보정 원점 = 로봇이라고 가정하지 않음). MuJoCo world는 로봇 바닥 원점, 로봇 앞 = +Y입니다: `p_world = R_z(90° − yaw) · (p_base − (x, y, 0))`.

## 확인한 것과 아직 확인하지 못한 것

[docs/PINCH_KHU_SETUP.md 13절](docs/PINCH_KHU_SETUP.md#13-확인-범위-2026-10-23-연구실-노트북) — 2026-10-23 연구실 노트북에서 자동 테스트(시뮬레이터 148, pac_vision 103, 경로 편집 110, 음성 13)와 카메라 없는 GUI·함수 흐름을 확인했고, 실제 Astra·마이크·ChatKHU 대화는 장치·키가 없어 **미확인**입니다.

## 문제 해결

[docs/PINCH_KHU_SETUP.md 10절](docs/PINCH_KHU_SETUP.md#10-문제-해결). 자주 보는 것:

- 시뮬레이터가 보정을 거부함 → 출력의 `CALIBRATION:` 줄(실패한 보정, 바뀐 정합 설정, 다른 카메라·USB 포트).
- 핀치가 안 잡힘 → 커서 옆 문구(수정 모드 아님 / 정합 미검증 / 깊이 없음 / 시각 어긋남).
- `시뮬레이터 소켓이 없습니다` → 시뮬레이터를 `--voice-gateway`로 먼저 켭니다.
- `PortAudio library not found` → `sudo apt install libportaudio2`.
- 음수 인수는 `--robot-pose=-0.15,0,0`처럼 `=`로 붙입니다.
