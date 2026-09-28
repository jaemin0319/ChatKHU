# 설계: 왕복 3D 경로와 correction memory

## 모듈과 좌표계

실제 구현은 다섯 모듈이다. `core`는 numpy와 표준 라이브러리만 사용한다. `validation`은 core를, `storage`는 core와 validation의 직렬화 형식을, `editor`는 core와 validation을 사용한다. `viewer`가 입력·화면·저장을 조합하며 순환 import는 없다. `__init__`와 `__main__`는 연결만 담당한다.

위치와 변위는 robot-base 좌표계의 m, 시간은 s다. 경로 위치 배열은 `(N,3)`, xi와 시간은 `(N,)`, 손 위치와 correction 벡터는 `(3,)`다. 화면 선택은 가상 카메라의 영상 픽셀 좌표 `(2,)`로만 수행한다. 영상 좌상단이 원점이고 y는 아래로 증가한다.

가상 카메라의 forward는 position→look_at, right는 forward×up으로 정규화한다. 카메라 깊이는 광축 방향 거리다. 픽셀과 깊이를 pinhole 모델로 역투영해 base-frame 손 위치를 구한 다음 editor에 전달한다. 따라서 같은 10 px 이동도 깊이가 달라지면 실제 미터 이동량이 달라진다. 휠과 PgUp/PgDn은 카메라 깊이를 바꾸며, base Z축으로 직접 치환하지 않는다.

## 원본 경로와 대응 xi

직선 원본의 실행 진행률은 `s(u)=10u³−15u⁴+6u⁵`, `u=t/T`다. 시간 간격은 sample_dt이며 T가 간격의 정수배가 아니면 위로 반올림한다. bump 데모는 outbound에만 `16*bump_height*s²*(1−s)²`의 Z 높이를 더한다. return은 target→base 직선이며 독립 배열이다.

원본 폴리라인의 누적 호 길이를 정규화하여 xi를 최초 한 번 부여한다. outbound는 0→1, return은 1→0이다. xi는 시간 비율 u와 다르며, 수정된 경로의 길이를 이용해 다시 정의하지 않는다. both는 선택된 샘플의 xi를 다른 경로에 대응시킨다. 두 경로의 현재 3D 중심은 다르더라도 같은 손 변위를 사용한다.

기하 경로에는 correction 중심과 support 경계의 xi를 추가할 수 있다. 새 knot의 원본 위치·시간은 원본 xi로 보간한다. 이는 대응 좌표를 재정의하는 것이 아니며, 대응 중심이 원본 샘플 사이에 있어도 편집 후 중심의 단위 가중치를 정확하게 표현하기 위한 세분화다. 계산·검사는 샘플 인덱스를 맞춰 비교하지 않는다.

## 상태, 이력과 revision

- 원본: 최초 기하와 xi, correction 없음.
- 확정: committed_records를 원본에 적용한 결과.
- 편집: candidate_records를 적용한 결과.
- 드래그: 핀치 시작의 records/경로/손 위치/선택 xi를 고정하고 DragState.candidate_records를 적용한 결과.

상태 사이의 경로 배열, correction 배열과 메타데이터는 복사한다. 표시 경로 accessor도 새 배열을 반환한다. 드래그 갱신은 매번 `h−h0`의 총변위와 **핀치 시작 memory**로 candidate를 재구성한다. 이전 프레임에 총변위를 다시 더하지 않는다. both 기록은 같은 group_id의 두 record이며, undo/redo는 완료된 드래그 전체의 memory 스냅샷을 복원한다. reset도 하나의 스냅샷 트랜잭션이다. 저장 파일은 finish 이전에 바꾸지 않는다.

경로 또는 memory가 바뀌는 preview·해제·취소·undo·redo·reset은 revision을 증가시키고 기존 검사 결과를 무효화한다. 검사 결과는 정확히 그 revision에서만 표시·저장할 수 있다. 모드 변경은 경로를 바꾸지 않지만 드래그 중에는 금지한다. 검사 실패 candidate는 편집 상태에 남고 committed는 유지한다.

잘못된 손 좌표, shape, NaN/Inf, 깊이 누락은 마지막 유효 preview를 유지한다. 영상 영역 밖에서도 동결하며 창 안에서 해제하면 마지막 유효값을 기록한다. 창 밖 이탈 또는 닫기는 진행 중인 핀치를 취소한다. Esc도 같은 cancel_drag 명령이다. 전체 편집 취소는 committed로 돌아간다.

## 국소 가중치, 공간 gate와 끝점 보호

국소 영향 길이 L은 경로를 따라 잰 미터 거리다. 핀치 시작 직전 **현재 편집 폴리라인**의 호 길이를 구하고 중심으로부터 거리 r에 대해 다음 값을 만든다.

```text
w(r) = (1 + cos(pi*r/L))/2    0 <= r < L
w(r) = 0                    r >= L
```

중심 xi, 현재 기하 knot, support 경계의 xi에서 cosine을 샘플링하여 weight_xi/weight_values에 저장한다. 중심 값은 1이며 support 경계는 명시적인 0 knot로 추가하므로 샘플 사이 보간이 영향 범위 밖으로 새지 않는다. 그 사이 가중치는 선형 보간한 이산 field다. 새 프레임이나 JSON 재로드 시 수정된 호 길이로 가중치를 다시 계산하지 않는다. 새로운 드래그만 새로운 시작 경로의 호 길이를 사용한다. 연속 미분 가능한 곡선 대신 샘플 폴리라인을 사용한다는 근사 한계는 남는다.

공간 gate는 L과 별개이며 다른 원본 경로로 correction을 재사용할 때의 계수 gamma다. 등방은 XYZ/R0, 비등방은 `(X/Rxy,Y/Rxy,Z/Rz)`로 공간을 정규화한다. center와 새 원본의 **모든 선분** 사이 최소거리를 정규화한 rho로 구한다. rho<alpha면 1, alpha~1에서는 cosine으로 감소하고 1 이상이면 0이다. 점만 검색하지 않아 샘플 밀도의 영향을 줄인다.

새 입력이 원본에서 멀어진 현재 경로 위에 있을 때 일반 재사용 gate를 적용하면 손을 움직여도 사라질 수 있다. 이를 피하기 위해 record에 원본 path_id·points·xi의 SHA-256 fingerprint를 저장한다. 동일한 원본에 속한 correction은 gamma=1을 유지하며 JSON 재로드도 동일하다. **다른 원본**으로 재사용할 때만 거리 gate를 적용한다. 원본 fingerprint는 실행 시간에 의존하지 않는다. 이 분기는 새 제스처의 의미를 보존하기 위한 명시적인 source-local 규칙이다.

끝점 가중치는 원본 호 길이에서 가장 가까운 끝점까지의 거리 `d=min(xi,1−xi)*original_length`를 사용한다. `a=clip(d/endpoint_protection,0,1)`, `b=a²(3−2a)`이다. b는 끝점에서 0이고 보호 구간 끝에서 1이며 두 경계의 미분도 0이다. 수정된 끝점 좌표만 사후 덮어쓰는 방식은 사용하지 않는다.

```text
A(xi) = sum(gamma_i * w_i(xi) * delta_i)  # unsaturated raw field, metres
S(v)  = v * min(1, total_offset_limit / norm(v))
p(xi) = p_original(xi) + b(xi) * S(A(xi))
```

개별 손 입력에는 drag_limit으로 별도 norm saturation을 적용한다. 축별 clipping은 하지 않는다. 따라서 요청 방향은 보존되며, 모든 correction이 겹쳐도 최종 원본 대비 변위 norm은 total_offset_limit 이하이다.

## 재수정과 흡수 계산

같은 applies_to **그리고** 같은 path_id인 record 중, 새 현재 중심이 기존 record 중심의 공간 gate support 내부에 있으면 흡수한다. applies_to는 사용자 모드이고 path_id는 실제 적용 대상이다. both와 outbound-only는 합쳐지지 않는다. 그룹 전체를 무조건 삭제하지 않으며 경로별 흡수 후에도 undo 스냅샷은 두 경로를 원자적으로 되돌린다.

저장 delta는 손 변위 자체가 아니라 **남은 raw field를 보정하는 잔차 계수**다. `F_all`과 `F_keep`을 서로 다른 처리 단계의 양으로 단순 차감하면 포화·gate·끝점에서 오류가 난다. 구현은 중심의 동일 xi에서 다음과 같이 정의한다.

```text
A_all  = 기존 모든 record의 unsaturated raw 합
K      = 흡수하지 않고 남긴 record의 unsaturated raw 합
U      = 현재 보이는 중심 offset / b
D      = norm_saturation(h - h0, drag_limit)
U_goal = S(S(U) + D)
delta_new = U_goal - K
```

기존 기하 knot에서는 `U=S(A_all)`이다. both의 다른 경로 중심이 기존 knot 사이에 있으면 **현재 표시 폴리라인의 실제 보간 위치**에서 U를 계산한다. 이렇게 해야 원래 보이던 중심에 변위를 더한다는 의미가 유지된다. b가 수치 허용오차 이하이면 나눗셈을 피하고 A_all을 기준으로 계산한다. 끝점의 실제 변위는 계속 0이다.

새 record는 같은 원본에 대한 gamma=1과 중심 w=1을 갖는다. 따라서 재구성한 중심 raw 합은 `K + delta_new = U_goal`이고, `S(U_goal)=U_goal`이다. 최종 중심은 `p_original + b*U_goal`이다. b=1이고 포화되지 않으면 정확히 현재 중심+D이며, 끝점 보호 구간에서는 b만큼 입력이 줄어든다. 보간 중심에서 b의 비선형성으로 U가 한도를 넘는 드문 경우에도 먼저 S(U)를 적용해 최종 한도를 유지한다.

남은 K는 끝점 감쇠 전·포화 전의 raw 값으로 차감한다. 저장 delta 자체를 무조건 drag_limit이나 total_offset_limit로 clipping하지 않는다. 예를 들어 남은 raw K가 +0.40 m이고 총한도가 0.10 m일 때, 현재 보이는 +0.10 m에서 −0.03 m를 요청하면 새 잔차는 `+0.07−0.40=−0.33 m`이어야 한다. 이를 −0.10으로 자르면 화면상 변화가 없어지는 오류가 난다. 테스트는 이 반례와 +8 cm→+3 cm=+11 cm, 감쇠 gate, 끝점, 중첩을 별도로 검증한다.

흡수는 기존 국소 profile을 새 profile로 교체하므로 중심 밖의 곡선도 바뀔 수 있다. 특히 중심 입력이 작아도 주변 실효 변화는 클 수 있다. 최소 수정량은 요청 norm이 아니라 **드래그 직전/직후 대응점 최대 이동량**으로 평가한다. 두 폴리라인의 xi knot 합집합에서 비교하면 각 선형 구간에서 변위 norm의 최댓값이 구간 끝에 있으므로 배열 길이에 영향을 받지 않는다.

## 미리보기·저장 재현

build_drag_candidate가 흡수와 새 record 추가까지 완료한 실제 memory를 반환한다. preview·마우스 해제·finish·로드 모두 같은 apply_corrections를 사용한다. 저장 JSON에는 최초 원본, xi, 시간, correction 중심·잔차·모드·path_id·group·fingerprint·frozen profile, 모든 설정, revision, 검사 결과와 실행 샘플을 담는다. 수정 결과를 다시 원본으로 취급하지 않아 이중 적용하지 않는다.

storage는 schema/단위/좌표계/설정/xi/shape/유한값/중복 ID를 검사한다. 통과 결과라도 revision이 다르거나 실제 memory에서 재구성한 실행 샘플과 다르면 저장·로드를 거절한다. 동일 디렉터리 임시 파일에 기록하고 flush/fsync 후 os.replace한다. 쓰기 실패 시 기존 파일은 보존된다. UI에서 파일 저장에 실패하면 통과한 메모리 상태를 유지하고 F로 재시도한다.

## 시간 배분과 검사

기하 knot의 시간 배열은 대응 메타데이터다. finish는 별도의 실행 배열을 만든다. 현재 길이를 ell이라고 하면 min-jerk 호 길이 진행의 최대 속도는 `1.875*ell/T`이다. 기본 시간은 초기 시간과 입력 기하 시간보다 짧아지지 않으며, `T >= 1.875*ell*speed_safety/max_ee_speed`를 만족하도록 늘린 후 sample_dt 정수배로 올림한다. `never_shorten=false`이면 이 최소 시간 정책을 해제할 수 있다.

실행 위치와 xi는 동일한 호 길이 보간 계수를 사용한다. 실행 시간 단조성·일정 간격과 실제 샘플간 `norm(dp)/dt` 속도를 다시 검사한다. min-jerk는 호 길이 출발/도착을 부드럽게 하지만 폴리라인 코너의 곡률·관절 가속도까지 보장하지 않는다. 첫 검사 후의 길어진 실행 시간은 결과에 저장되며 기본 편집 기하 기준시간 자체를 매번 덮어쓰지는 않는다.

검사는 PASS/FAIL/NOT_EVALUATED를 구분하며 종류·path_id·문제 xi 또는 구간·사용자 설명·개발 수치·revision을 가진다. 경로 shape/NaN/Inf, 끝점, 총변형, xi, 시간, EE 속도, 마지막 드래그의 실효 변화가 검사 대상이다. 연속 IK·관절 범위·특이점·자기충돌·관절 속도/가속도·토크는 기본 NOT_EVALUATED다. 기하 PASS는 로봇 실행 허가를 뜻하지 않는다.

## 입력과 로봇 검사기 확장

향후 음성 계층은 Editor.execute_command의 start_edit/set_edit_mode/finish_edit/cancel_edit/undo/redo/reset을 호출한다. 핀치 검출은 화면 픽셀 pick_point를 호출하고, 깊이 센서·보정 계층이 base-frame 손 위치를 만들어 begin_drag/update_drag/end_drag에 전달한다. 실제 손과 경로의 3D 거리는 선택 조건에 추가하지 않는다.

RobotValidator 프로토콜의 validate는 실행 PathData와 Config를 받아 CheckResult 목록을 반환한다. 하드웨어 실행 명령은 이 인터페이스에 없다. MockRobotValidator는 명시적인 MOCK 실패만 주입하는 화면 테스트용이며 실제 검증과 구분한다. 실제 로봇 실행, 로봇 정지 확인, 음성 API, MediaPipe, 깊이 카메라 연결, 기구학·동역학 모델은 별도의 다음 단계다.
