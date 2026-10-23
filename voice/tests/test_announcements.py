"""시뮬레이터 이벤트 → 쿠옹이가 말할 문장, 수정 모드 안내 (AI 없이)."""
from voice import tools
from voice.sim_link import (ASK_ARRIVED, BACK_TO_EDIT, MOVE_START, PASSED_MOVE, PASSED_WAIT, _announcement,
                            edit_guide)


def ev(kind, state='GENERATED', actor='sim', data=None, **status):
    return {'kind': kind, 'state': state, 'actor': actor, 'data': data or {}, 'status': status}


def test_passed_runs_without_a_question():
    assert _announcement(ev('validation', 'PASSED', auto_run={'request_id': 'r'})) == ''
    assert _announcement(ev('execution_start', 'EXECUTING', actor='voice')) == PASSED_MOVE
    assert '?' not in PASSED_MOVE
    assert _announcement(ev('validation', 'PASSED')) == PASSED_WAIT            # 버튼 V로 검증: Y를 안내
    assert _announcement(ev('execution_start', 'EXECUTING', actor='key')) == MOVE_START


def test_failure_says_why_where_and_back_to_editing():
    t = _announcement(ev('validation', 'FAILED', phase='outbound',
                         report={'failed_kinds': ['collision'], 'fail_at_pct': 63.0}))
    assert '책상이나 로봇 자신과 부딪혀요' in t and '가는 길의 약 60% 지점' in t and '수정 모드' in t


def test_arrival_back_to_edit_and_cancelled_booking():
    t = _announcement(ev('execution_end', 'DONE', last_exec={'phase': 'outbound', 'kind': 'outbound'}))
    assert t == ASK_ARRIVED
    assert _announcement(ev('back_to_edit')) == BACK_TO_EDIT and not BACK_TO_EDIT.endswith('?')
    assert _announcement(ev('auto_run_cancelled', data={'reason': 'validation failed'})) == ''
    assert _announcement(ev('auto_run_cancelled', data={'reason': 'edit mode on'})) == ''
    assert '자동 이동 예약이 취소' in _announcement(ev('auto_run_cancelled', data={'reason': 'voice link lost'}))


def test_calibration_and_hand_refusals_are_spoken():
    assert '다시 보정' in _announcement(ev('calib', data={'calib': 'moved'}))
    assert _announcement(ev('calib', data={'calib': 'verified'})) == ''
    assert '경로 수정할래' in _announcement(ev('hand_refused', data={'reason': 'not_edit_mode'}))
    assert '취소' in _announcement(ev('hand_refused', data={'reason': 'depth_lost'}))


def test_edit_guide_matches_what_the_user_can_use():
    assert edit_guide({'hand': '3d', 'calib': 'verified'}).startswith('네. 손가락으로 경로를 수정해 주세요.')
    t = edit_guide({'hand': '3d', 'calib': 'moved'})
    assert '3D 수정은 쓸 수 없어요' in t and '마우스' in t
    assert '높이만' in edit_guide({'hand': '2d'})
    assert '클릭' in edit_guide({})
    for g in (edit_guide({'hand': '3d', 'calib': 'verified'}), edit_guide({})):
        assert '수정 완료' in g and '이전으로' in g                         # 지금 할 수 있는 말도 알려 준다


def test_declarations_offer_start_edit_and_no_second_approval():
    names = {d['name'] for d in tools.DECLARATIONS}
    assert 'start_edit' in names and 'finish_edit' in names
    assert not names & {'approve_move', 'keep_editing'}
    finish = next(d for d in tools.DECLARATIONS if d['name'] == 'finish_edit')
    assert '이 경로로 할게' in finish['description']
