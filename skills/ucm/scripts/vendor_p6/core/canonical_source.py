"""Canonical Source of Truth Generator & Cross-Reconciliation Module v5.2.
UCM Architecture Remediation Release v1.0.7-beta (Round 2 Acceptance Remediation).
"""
import json, math

def generate_canonical_timeline(p):
    """Derive canonical timeline table strictly from screenplay JSON."""
    scenes = p.get('screenplay_body', {}).get('scenes', [])
    rows = []
    t = 0.0
    for s in scenes:
        sid = s.get('scene_id', 'S')
        for b in s.get('beats', []):
            bid = b.get('beat_id')
            st = float(b.get('start_sec', 0.0))
            en = float(b.get('end_sec', 0.0))
            dur = en - st
            dialogue = b.get('dialogue', [])
            words = sum(len(d.get('text', '').split()) for d in dialogue)
            wps = float(b.get('estimated_dialogue_wps', 1.5))
            spoken_time = round(words / wps, 2) if wps > 0 else 0.0
            pause_time = round(max(0.0, dur - spoken_time), 2)
            action = b.get('action_text', '')
            rows.append({
                'scene_id': sid,
                'beat_id': bid,
                'start_sec': st,
                'end_sec': en,
                'duration_sec': dur,
                'word_count': words,
                'estimated_wps': wps,
                'spoken_sec': spoken_time,
                'pause_sec': pause_time,
                'action_text': action
            })
            t = en
    return rows

def generate_canonical_dialogue(p):
    """Derive canonical dialogue line by line strictly from screenplay JSON."""
    lines = []
    scenes = p.get('screenplay_body', {}).get('scenes', [])
    for s in scenes:
        for b in s.get('beats', []):
            bid = b.get('beat_id')
            for d in b.get('dialogue', []):
                spk = d.get('speaker')
                txt = d.get('text', '')
                lines.append({
                    'beat_id': bid,
                    'speaker': spk,
                    'text': txt,
                    'words': len(txt.split())
                })
    return lines

def generate_canonical_prop_ledger(p):
    """Derive prop state lifecycle history strictly from screenplay JSON (DEFECT-01 Fix)."""
    try:
        from core.validator import PropStateMachine
    except ImportError:
        try:
            from .validator import PropStateMachine
        except ImportError:
            import validator as _val
            PropStateMachine = _val.PropStateMachine

    initial_props = p.get('initial_props', {})
    initial_containers = p.get('initial_containers', {})
    registry = p.get('prop_registry', [])
    sm = PropStateMachine(initial_props, initial_containers, registry)
    ledger = {
        pid: {
            'initial_holder': loc,
            'history': [],
            'terminal_holder': None,
            'terminal_grasped_by': None,
            'terminal_surface': None,
            'terminal_attached_to': None,
            'terminal_contact': None
        }
        for pid, loc in initial_props.items()
    }
    if registry:
        for r in registry:
            pid = r['prop_id']
            if pid not in ledger:
                ledger[pid] = {
                    'initial_holder': r.get('initial_location', 'UNREGISTERED'),
                    'history': [],
                    'terminal_holder': None,
                    'terminal_grasped_by': None,
                    'terminal_surface': None,
                    'terminal_attached_to': None,
                    'terminal_contact': None
                }

    scenes = p.get('screenplay_body', {}).get('scenes', [])
    for s in scenes:
        sid = s.get('scene_id')
        for b in s.get('beats', []):
            bid = b.get('beat_id')
            action = b.get('action_text', '')
            for n, e in enumerate(b.get('prop_events', [])):
                pid = e.get('prop_id')
                error = sm.step(e, sid, bid, n, action)
                if error:
                    raise ValueError(f'INVALID_PROP_EVENT: {error[0]} at {error[1]}')
                if pid:
                    if pid not in ledger:
                        ledger[pid] = {
                            'initial_holder': 'LATE_INTRODUCED',
                            'history': [],
                            'terminal_holder': None,
                            'terminal_grasped_by': None,
                            'terminal_surface': None,
                            'terminal_attached_to': None,
                            'terminal_contact': None
                        }
                    ledger[pid]['history'].append({
                        'beat_id': bid,
                        'event_type': e.get('event_type'),
                        'actor': e.get('actor'),
                        'target': e.get('target_recipient'),
                        'surface': e.get('surface_id'),
                        'container': e.get('container_id'),
                        'current_holder': sm.props.get(pid),
                        'grasped_by': sm.grasped_by.get(pid),
                        'attached_to': sm.attached.get(pid),
                        'contact_state': sm.contact.get(pid, 'NONE')
                    })

    for pid in ledger:
        ledger[pid]['terminal_holder'] = sm.props.get(pid)
        ledger[pid]['terminal_grasped_by'] = sm.grasped_by.get(pid)
        ledger[pid]['terminal_surface'] = sm.surfaces.get(pid)
        ledger[pid]['terminal_attached_to'] = sm.attached.get(pid)
        ledger[pid]['terminal_contact'] = sm.contact.get(pid, 'NONE')
    return ledger

def reconcile_canonical_source(p):
    """Cross-reconcile narrative prose, dialogue packet, timeline intervals, and prop ledger."""
    discrepancies = []
    cfg = p.get('approved_configuration', {})
    target_dur = float(cfg.get('target_duration_sec', -1))
    scenes = p.get('screenplay_body', {}).get('scenes', [])

    # 1. Timeline integrity
    tl = generate_canonical_timeline(p)
    if not tl:
        discrepancies.append('No timeline beats generated')
    else:
        if tl[0]['start_sec'] != 0.0:
            discrepancies.append(f'Timeline does not start at 0.0s (starts at {tl[0]["start_sec"]})')
        for i in range(1, len(tl)):
            if not math.isclose(tl[i]['start_sec'], tl[i-1]['end_sec'], abs_tol=1e-7):
                discrepancies.append(f'Timeline gap/overlap between {tl[i-1]["beat_id"]} and {tl[i]["beat_id"]}')
        if target_dur > 0 and not math.isclose(tl[-1]['end_sec'], target_dur, abs_tol=1e-7):
            discrepancies.append(f'Timeline total duration {tl[-1]["end_sec"]}s != approved target {target_dur}s')

    # 2. Dialogue packet reconciliation
    dialogue_lines = generate_canonical_dialogue(p)
    packet = p.get('canonical_dialogue_packet')
    if packet is not None:
        extracted = [{'speaker': d['speaker'], 'text': d['text']} for d in dialogue_lines]
        if packet != extracted:
            discrepancies.append('Canonical dialogue packet does not match dialogue extracted from beats')

    # 3. Prop locators reconciliation
    for s in scenes:
        for b in s.get('beats', []):
            act = b.get('action_text', '')
            for n, e in enumerate(b.get('prop_events', [])):
                loc = e.get('text_locator') or {}
                st, en, q = loc.get('start_char'), loc.get('end_char'), loc.get('quoted_text')
                if not (isinstance(st, int) and isinstance(en, int) and isinstance(q, str) and q and 0 <= st < en <= len(act) and act[st:en] == q):
                    discrepancies.append(f'Grounded locator mismatch in {b.get("beat_id")}/event{n}: quoted "{q}" does not match slice')

    # 4. DEFECT-04 Fix: Check for complete absence of prop events when physical prose is present
    total_events = sum(len(b.get('prop_events', [])) for s in scenes for b in s.get('beats', []))
    PHYSICAL_VERBS = ('تمسك', 'يمسك', 'يضع', 'تضع', 'سحب', 'تسحب', 'تدفع', 'يدفع', 'تفتح', 'يفتح', 'تغلق', 'يغلق', 'hold', 'push', 'open', 'close', 'take', 'slide')
    has_physical_prose = any(any(v in b.get('action_text', '') for v in PHYSICAL_VERBS) for s in scenes for b in s.get('beats', []))
    if has_physical_prose and total_events == 0:
        discrepancies.append('ZERO_PROPEVENTS_DECLARED_WITH_PHYSICAL_PROSE: Physical interactions exist in prose but zero prop events were extracted')
    elif total_events > 0:
        for scene in scenes:
            for beat in scene.get('beats', []):
                action = beat.get('action_text', '')
                if not beat.get('prop_events') and any(v in action for v in PHYSICAL_VERBS):
                    discrepancies.append(f'PARTIAL_PROPEVENTS_SUSPECTED: Physical prose in {beat.get("beat_id")} but zero events in that beat; manual extraction audit required')

    return discrepancies
