"""경로 수정 흐름도 (좌표를 직접 정해 그리는 SVG). 실행: python3 flow2_edit_svg.py → flow2_edit.svg"""
from pathlib import Path

W, H = 1800, 1460
FONT = "Noto Sans CJK KR"
STYLE = {
    "main":  ("#E8F1FB", "#2B5797"),
    "voice": ("#EEEBFB", "#5B4BB7"),
    "pinch": ("#E6F4EE", "#2E7D5B"),
    "dec":   ("#FFFFFF", "#888888"),
    "pill":  ("#F2F0EA", "#9A968C"),
    "note":  ("#F7F6F2", "#BDBAB0"),
}
out = []


def box(cx, cy, w, h, lines, kind="main", dashed=False, size=17, bold=True, r=14, width=1.6):
    fill, stroke = STYLE[kind]
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<rect x="{cx - w/2}" y="{cy - h/2}" width="{w}" height="{h}" rx="{r}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash}/>')
    lh = size * 1.35
    y0 = cy - lh * (len(lines) - 1) / 2 + size * 0.35
    weight = "700" if bold else "400"
    for i, t in enumerate(lines):
        out.append(f'<text x="{cx}" y="{y0 + i*lh}" font-size="{size}" font-weight="{weight}" '
                   f'text-anchor="middle" font-family="{FONT}" fill="#1a1a1a">{t}</text>')


def pill(cx, cy, text, w=None):
    w = w or (len(text) * 15 + 34)
    box(cx, cy, w, 36, [text], "pill", size=15, r=18, width=1.2)


def hop_line(pts, hop_x, r=11, color="#777777"):
    """점선 꺾은선. 마지막 수평 구간이 x = hop_x 세로선을 지날 때 작은 반원으로 넘는다 (이어진 선이 아님을 표시)."""
    *head, (x1, y1), (x2, y2) = pts
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(head + [(x1, y1)]))
    d += f" L{hop_x + r},{y2} A{r},{r} 0 0 0 {hop_x - r},{y2} L{x2},{y2}"
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" stroke-dasharray="7 5" marker-end="url(#ah)"/>')


def line(pts, arrow=True, dashed=False, color="#777777"):
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    mk = ' marker-end="url(#ah)"' if arrow else ""
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{dash}{mk}/>')


# ---------------------------------------------------------------- 위: 고치는 방법
CX = 900
box(CX, 60, 300, 52, ["① 고치는 방법 선택"], "dec", dashed=True)
VX, PX = 560, 1240                      # 말(왼쪽) / 핀치(오른쪽) 기둥
line([(CX - 60, 86), (CX - 60, 120), (VX, 120), (VX, 140)], arrow=False)
line([(CX + 60, 86), (CX + 60, 120), (PX, 120), (PX, 140)], arrow=False)
pill(VX, 158, "점 클릭 + 말로")
pill(PX, 158, "핀치로")
line([(VX, 176), (VX, 214)])
line([(PX, 176), (PX, 214)])

# 말로 고치기 (왼쪽)
box(VX, 245, 420, 60, ["사용자: 화면에서 경로 위 점을 클릭", "→ 노란 동그라미로 표시"], "voice")
line([(VX, 275), (VX, 310)])
box(VX, 340, 420, 60, ["② 사용자: 점을 보고 말함", "예: 쿠옹아, 여기 위로 조금 올려줘"], "voice")
line([(VX, 370), (VX, 410)])
box(VX, 440, 300, 60, ["쿠옹이: 정보가 충분한가?", "(왼쪽 아래 ※ 참고)"], "dec", dashed=True)
# 부족 → 되묻기 (왼쪽으로 수평), 고르면 다시 확인
line([(VX - 150, 430), (330, 430)], arrow=False)
pill(285, 430, "부족", 70)
line([(250, 430), (237, 430)])
box(141, 440, 190, 100, ["쿠옹이가 되물음", "예: 위로 넘어갈까요,", "옆으로 돌아갈까요?"], "voice", size=15)
line([(141, 390), (141, 355), (VX - 212, 355)], dashed=True)   # 되물은 뒤 사용자가 다시 말함 → ②
# 충분 → 말한 거리만큼 옮길 수 있나? → 고침 / 못 옮김
line([(VX, 470), (VX, 484)], arrow=False)
pill(VX, 500, "충분", 70)
line([(VX, 518), (VX, 536)])
box(VX, 560, 300, 46, ["말한 거리만큼 옮길 수 있나?"], "dec", dashed=True, size=15)
line([(VX, 583), (VX, 593)], arrow=False)
pill(VX, 607, "가능", 70)
line([(VX, 625), (VX, 640)])
box(VX, 670, 420, 60, ["쿠옹이: 여기를 위로 2센티 올렸어요.", "(수정 전 경로를 회색으로 겹쳐 표시)"], "voice", size=16)
line([(VX - 150, 560), (378, 560)], arrow=False)
pill(330, 560, "불가능", 92)
line([(284, 560), (165, 560), (165, 606)])
box(165, 650, 260, 84, ["쿠옹이: 너무 많이 이동해서", "더이상 수정할 수 없어요.", "(경로는 그대로)"], "voice", size=15)
line([(35, 650), (22, 650)], arrow=False, dashed=True)       # 왼쪽 버스로 ②에 복귀

# 핀치로 고치기 (오른쪽)
box(PX, 245, 380, 60, ["사용자: 경로를 핀치로 집어 옮김", "(손을 놓는 순간 반영)"], "pinch")
line([(PX, 275), (PX, 640)])
box(PX, 670, 420, 60, ["쿠옹이: 경로를 수정했어요.", "(수정 전 경로를 회색으로 겹쳐 표시)"], "pinch", size=16)

# 두 갈래 → ③
line([(VX, 700), (VX, 708), (CX - 40, 708), (CX - 40, 718)])
line([(PX, 700), (PX, 708), (CX + 40, 708), (CX + 40, 718)])

# ---------------------------------------------------------------- ③ 다음 말과 줄기
box(CX, 755, 300, 74, ["③ 다음 말", "(입력이 올 때까지 기다림)"], "dec", dashed=True)
line([(CX, 792), (CX, 1210)], arrow=False)          # 가운데 줄기
ROWS = (870, 1000, 1130)
LX_P, LX_B = 640, 290                               # 왼쪽 말 / 결과
RX_P, RX_B = 1160, 1510                             # 오른쪽 말 / 결과
branches = [
    (ROWS[0], "L", "조금만 더 · 좀 더 · 아직 모자라", ["직전 수정을 한 단계 크게 다시", "조금 2 → 보통 5 → 많이 8 cm", "(많이에서는: 이미 가장 많이 옮겼어요)"]),
    (ROWS[0], "R", "너무 갔어 · 좀 덜 · 과해", ["직전 수정을 한 단계 작게 다시", "많이 8 → 보통 5 → 조금 2 cm", "(조금에서는: 이미 가장 조금 옮겼어요)"]),
    (ROWS[1], "L", "아 별로다, 이전으로", ["쿠옹이: 직전 수정을 되돌렸어요."]),
    (ROWS[1], "R", "아니, 아직 하지 마 · 그대로 둬", ["쿠옹이: 네, 그대로 둘게요.", "(아무것도 움직이지 않음)"]),
    (ROWS[2], "L", "처음부터 다시 · 초기화", ["쿠옹이: 처음 경로로 되돌렸어요.", "(지금까지 한 수정을 모두 취소)"]),
]
for y, side, said, result in branches:
    bh = 30 + 24 * len(result)
    if side == "L":
        line([(CX, y), (LX_P + 142, y)])
        pill(LX_P, y, said, 280)
        line([(LX_P - 140, y), (LX_B + 200, y)])
        box(LX_B, y, 400, bh, result, size=15)
        line([(LX_B - 200, y), (22, y), (22, 300), (330, 300), (330, 325), (VX - 212, 325)], dashed=True)   # 왼쪽 버스로 ②에 복귀
    else:
        line([(CX, y), (RX_P - 142, y)])
        pill(RX_P, y, said, 280)
        line([(RX_P + 140, y), (RX_B - 200, y)])
        box(RX_B, y, 400, bh, result, size=15)
        hop_line([(RX_B + 200, y), (1760, y), (1760, 325), (VX + 212, 325)], hop_x=PX)   # 오른쪽 버스로 ②에 복귀 (핀치 선은 다리로 넘음)
out.append(f'<text x="30" y="292" font-size="14" font-family="{FONT}" fill="#777">다시 ②로</text>')
out.append(f'<text x="1752" y="317" font-size="14" font-family="{FONT}" fill="#777" text-anchor="end">다시 ②로</text>')

# 다른 점 고치기 → ①
line([(CX + 150, 740), (1078, 740)])
pill(1160, 740, "다른 점 고치기", 160)
line([(1240, 740), (1790, 740), (1790, 60), (CX + 152, 60)], color="#2E7D5B")

# 수정 완료 → ④ (가운데 아래로 곧게)
line([(CX, 1210), (CX, 1245)])
pill(CX, 1265, "수정 완료 · 됐어", 180)
line([(CX, 1283), (CX, 1340)])
box(CX, 1375, 360, 66, ["④ 수정 끝 → 검증 시작", "(전체 흐름 ②로 이어짐)"], "main", width=2.6)

# ※ 조건 (오른쪽 위 빈 곳)
fill, stroke = STYLE["note"]
out.append(f'<rect x="60" y="1300" width="360" height="140" rx="14" fill="{fill}" stroke="{stroke}"/>')
for i, (t, b) in enumerate([("※ 정보가 충분한 조건", True), ("· 어디: 클릭한 점 (또는 시작·가운데·끝)", False),
                            ("· 방향: 위·아래·왼쪽·오른쪽·내 쪽·저쪽", False), ("· 거리: 조금 2 · 보통 5 · 많이 8 cm", False),
                            ("   (말 안 하면 조금)", False)]):
    out.append(f'<text x="80" y="{1330 + i*24}" font-size="{16 if b else 14}" font-weight="{700 if b else 400}" '
               f'font-family="{FONT}" fill="#1a1a1a">{t}</text>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
       '<path d="M0,0 L10,5 L0,10 z" fill="#777777"/></marker></defs>'
       f'<rect width="{W}" height="{H}" fill="white"/>' + "".join(out) + "</svg>")
Path(__file__).with_name("flow2_edit.svg").write_text(svg, encoding="utf-8")
print("flow2_edit.svg")
