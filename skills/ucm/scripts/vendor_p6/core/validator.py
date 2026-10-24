"""Conservative P6 checker and Prop State Machine v5.2.
Only measurable facts can auto-pass. Creative judgments block for review.
UCM Architecture Remediation Release v1.0.7-beta (Round 2 Acceptance Remediation).
"""
import json, hashlib, math, re
from pathlib import Path

CRITERIA = [f'H{i:02d}' for i in range(1, 11)]
GEN_BINS = {4, 6, 8, 10}

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def load(x):
    return json.loads(Path(x).read_text(encoding='utf-8'))

def record(c, status, code, description, extra=None):
    return {'criterion': c, 'status': status, 'code': code, 'message': description, 'evidence': extra or []}

def beats_of(p):
    return [(s.get('scene_id', 'S'), b) for s in p.get('screenplay_body', {}).get('scenes', []) for b in s.get('beats', [])]

def nearly(a, b):
    return math.isclose(a, b, abs_tol=1e-7)

def numeric(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

NEGATIVE_CONTAINER = r'(?:يحاول|حاول|تحاول|ليمنع|استعصى|لم يستطع|لم تنفتح|لكن لم|لم يفتح|فشل|failed|could not|unable to)'
CONTAINER_OPEN_VERBS = [
    'تفتح', 'يفتح', 'فتحت', 'فتح', 'فك سحاب', 'تفك سحاب', 'يفك سحاب',
    'open', 'opens', 'opened', 'unzip', 'unzips', 'unzipped'
]
PHYSICAL_NOUNS = [
    'ورقة', 'ورق', 'سجل', 'دفتر', 'إذن', 'كارت', 'محضر', 'قلم', 'حقيبة',
    'شنطة', 'حافظة', 'ملف', 'ختم', 'مفتاح', 'كوب', 'مستند', 'خراطيم', 'محابس'
]
HANDLING_VERBS = [
    'تمسك', 'يمسك', 'تفتح', 'يفتح', 'تسحب', 'يسحب', 'تضع', 'يضع',
    'تدفع', 'يدفع', 'تغلق', 'يغلق', 'توقع', 'يوقع', 'تسلم', 'يسلم', 'ترفق', 'يرفق'
]

class PropStateMachine:
    """Full lifecycle prop state machine with per-actor custody, grasp, surface, and container states."""
    def __init__(self, initial_props=None, initial_containers=None, prop_registry=None):
        self.props = dict(initial_props or {})
        self.containers = dict(initial_containers or {})
        self.grasped_by = {}      # prop_id -> actor_id or None
        self.surfaces = {}        # prop_id -> surface_id
        self.hands = {}           # (actor, hand) -> prop_id
        self.attached = {}        # prop_id -> target_prop_id
        self.registry = {p['prop_id']: p for p in prop_registry} if prop_registry else None
        self.initial_containers_declared_open = {c for c, st in self.containers.items() if st == 'OPEN'}

        for pid, loc in list(self.props.items()):
            if loc in self.containers:
                self.grasped_by[pid] = None
            elif loc in ('DESK', 'TABLE', 'SURFACE', 'WORLD'):
                self.grasped_by[pid] = None
                self.surfaces[pid] = loc
            else:
                self.grasped_by[pid] = loc  # Initial holder character is grasping it

    @property
    def contact(self):
        """Dynamic compatibility mapping for contact state ('GRASPED' or 'NONE')."""
        return {pid: ('GRASPED' if self.grasped_by.get(pid) else 'NONE') for pid in self.props}

    def step(self, e, sid, bid, n, action_text):
        label = f'{sid}/{bid}/event{n}'
        loc = e.get('text_locator') or {}
        st, en, q = loc.get('start_char'), loc.get('end_char'), loc.get('quoted_text')

        # Verifiable text locator check
        if not (isinstance(st, int) and isinstance(en, int) and isinstance(q, str) and q and 0 <= st < en <= len(action_text) and action_text[st:en] == q):
            return ('LOCATOR_NOT_GROUNDED', label)

        typ = e.get('event_type')
        pid = e.get('prop_id')
        cid = e.get('container_id')
        sid_surf = e.get('surface_id', 'DESK')
        a = e.get('actor')
        dest = e.get('target_recipient')
        hand = e.get('hand')

        # Registry check
        if self.registry is not None and pid and pid not in self.registry:
            return ('UNREGISTERED_PROP', f'{label}: {pid}')

        # Strict Per-Actor Custody Lock:
        # If prop is currently grasped by Actor X, Actor Y (Y != X) CANNOT act upon it
        # unless it is a mutual handoff where X is transferring to Y.
        current_grasper = self.grasped_by.get(pid)
        if current_grasper and current_grasper != a and typ not in ('INITIALIZE', 'TRANSFER_HANDOFF', 'DIRECT_HANDOFF'):
            return ('CUSTODY_CONFLICT_HELD_BY_ANOTHER_ACTOR', f'{label}: Actor {a} cannot act on {pid} held exclusively by {current_grasper}')

        if typ == 'INITIALIZE':
            if pid in self.props:
                return ('DOUBLE_INITIALIZE', label)
            self.props[pid] = cid or a or sid_surf or 'WORLD'
            if cid:
                self.grasped_by[pid] = None
            elif a:
                self.grasped_by[pid] = a
            return None

        if typ in ('OPEN_CONTAINER', 'CONTAINER_STATE_CHANGE'):
            target_c = cid or pid
            near = action_text[max(0, st - 35):min(len(action_text), en + 35)]
            if re.search(NEGATIVE_CONTAINER, near, re.I):
                return ('NEGATED_OPENING', label)
            self.containers[target_c] = 'OPEN'
            return None

        if typ == 'CLOSE_CONTAINER':
            target_c = cid or pid
            self.containers[target_c] = 'CLOSED'
            return None

        if typ in ('RETRIEVE_FROM_CONTAINER', 'ACQUIRE_PROP'):
            if cid:
                if self.containers.get(cid, 'CLOSED') != 'OPEN':
                    return ('CLOSED_CONTAINER', label)
                if self.props.get(pid) != cid:
                    return ('NOT_IN_CONTAINER', label)
                self.props[pid] = a
                self.grasped_by[pid] = a
                return None
            elif sid_surf:
                if self.props.get(pid) not in (sid_surf, 'DESK', 'SURFACE', 'TABLE', 'WORLD'):
                    return ('NOT_ON_SURFACE', label)
                if current_grasper and current_grasper != a:
                    return ('CUSTODY_CONFLICT_HELD_BY_ANOTHER_ACTOR', label)
                self.props[pid] = a
                self.grasped_by[pid] = a
                return None

        if typ in ('SLIDE_PROP', 'PUSH_ON_SURFACE'):
            # Must be grasped by actor a, OR resting on surface in front of actor without other's grasp
            if current_grasper != a and self.props.get(pid) not in (sid_surf, 'DESK', 'SURFACE', 'TABLE', 'WORLD'):
                return ('SLIDE_WITHOUT_CONTACT', label)
            # Prop moves to the surface; custody does NOT pass automatically to recipient!
            self.props[pid] = sid_surf
            self.surfaces[pid] = sid_surf
            self.grasped_by[pid] = None
            return None

        if typ in ('PLACE_ON_SURFACE', 'RELEASE'):
            if self.props.get(pid) in (sid_surf, 'DESK', 'SURFACE', 'TABLE', 'WORLD') and not current_grasper:
                return None
            if current_grasper != a and self.props.get(pid) != a:
                return ('RELEASE_WITHOUT_CUSTODY', label)
            self.props[pid] = sid_surf or 'WORLD'
            self.grasped_by[pid] = None
            for k, v in list(self.hands.items()):
                if k[0] == a and v == pid:
                    self.hands[k] = None
            return None

        if typ in ('GRASP_PROP', 'PICKUP'):
            curr_holder = self.props.get(pid, 'WORLD')
            if current_grasper and current_grasper != a:
                return ('CUSTODY_CONFLICT_HELD_BY_ANOTHER_ACTOR', label)
            if curr_holder not in (sid_surf, 'DESK', 'SURFACE', 'TABLE', 'WORLD'):
                return ('CUSTODY_CONFLICT', label)
            if hand and hand not in ('LEFT', 'RIGHT', 'BOTH'):
                return ('HAND_UNKNOWN', label)
            if hand:
                hh = ['LEFT', 'RIGHT'] if hand == 'BOTH' else [hand]
                if any(self.hands.get((a, h)) not in (None, pid) for h in hh):
                    return ('HAND_OCCUPIED', label)
                for h in hh:
                    self.hands[(a, h)] = pid
            self.props[pid] = a
            self.grasped_by[pid] = a
            return None

        if typ in ('TRANSFER_HANDOFF', 'DIRECT_HANDOFF'):
            if self.props.get(pid) != a or current_grasper != a:
                return ('HANDOFF_WITHOUT_CUSTODY', label)
            if not dest or dest == a:
                return ('NO_RECIPIENT', label)
            self.props[pid] = dest
            self.grasped_by[pid] = dest
            return None

        if typ == 'TRANSFER_PROP':
            near = action_text[max(0, st - 35):min(len(action_text), en + 35)]
            if any(term in near or term in q for term in ('تدفع', 'يدفع', 'دفع', 'انزلاق', 'slide', 'push')):
                return ('SLIDE_CONFLATED_WITH_TRANSFER', label)
            if dest in ('WORLD', 'DESK', 'SURFACE', 'TABLE'):
                self.props[pid] = dest
                self.grasped_by[pid] = None
                return None
            if self.props.get(pid) != a or current_grasper != a:
                return ('HANDOFF_WITHOUT_CUSTODY', label)
            if not dest:
                return ('NO_RECIPIENT', label)
            self.props[pid] = dest
            self.grasped_by[pid] = dest
            return None

        if typ == 'ATTACH_PROP':
            target_p = e.get('target_prop_id')
            if not target_p:
                return ('MISSING_ATTACHMENT_TARGET', label)
            # DEFECT-02 Fix: Validate target is registered and active
            if self.registry is not None and target_p not in self.registry:
                return ('UNREGISTERED_ATTACHMENT_TARGET', f'{label}: Target prop {target_p} not registered')
            if target_p not in self.props:
                return ('UNINITIALIZED_ATTACHMENT_TARGET', f'{label}: Target prop {target_p} not in active props')
            if self.props.get(pid) != a and current_grasper != a:
                return ('ATTACH_WITHOUT_CUSTODY', label)
            target_holder = self.props.get(target_p)
            target_grasper = self.grasped_by.get(target_p)
            if target_holder != a and target_holder not in (sid_surf, 'DESK', 'SURFACE', 'TABLE', 'WORLD'):
                return ('ATTACH_TARGET_INACCESSIBLE', f'{label}: Target {target_p} not accessible to {a}')
            if target_grasper and target_grasper != a:
                return ('ATTACH_TARGET_HELD_BY_ANOTHER', f'{label}: Target {target_p} grasped by another actor')
            self.attached[pid] = target_p
            return None

        if typ == 'DETACH_PROP':
            target_p = e.get('target_prop_id')
            if pid not in self.attached:
                return ('DETACH_NOT_ATTACHED', f'{label}: Prop {pid} is not currently attached to any target')
            if target_p and self.attached[pid] != target_p:
                return ('DETACH_TARGET_MISMATCH', f'{label}: Prop {pid} attached to {self.attached[pid]}, not {target_p}')
            if self.props.get(pid) != a and current_grasper != a:
                return ('DETACH_WITHOUT_CUSTODY', label)
            del self.attached[pid]
            return None

        return ('UNRECOGNIZED_EVENT', label)

def check_props(beats, props=None, containers=None, prop_registry=None, terminal_reconciliation=None):
    """Enhanced state machine replay with surface states, container inversion, registry audits, and active terminal reconciliation."""
    sm = PropStateMachine(props, containers, prop_registry)
    fail = []
    uncertain = []

    for sid, b in beats:
        action = b.get('action_text', '')
        bid = b.get('beat_id')
        locators_in_beat = []

        # 1. Container Inversion Guard:
        for c in sm.initial_containers_declared_open:
            if any(v in action for v in CONTAINER_OPEN_VERBS):
                if c.lower() in action.lower() or 'حقيبة' in action or 'حافظة' in action or 'bag' in action.lower():
                    has_open_event = any(e.get('event_type') == 'OPEN_CONTAINER' and (e.get('container_id') == c or e.get('prop_id') == c) for e in b.get('prop_events', []))
                    if not has_open_event:
                        fail.append(('CONTAINER_STATE_INVERSION', f'{sid}/{bid}: Container {c} declared OPEN initially but opened in prose without event'))

        # 2. Replay declared prop events
        for n, e in enumerate(b.get('prop_events', [])):
            res = sm.step(e, sid, bid, n, action)
            if res:
                code, label = res
                if code in ('LOCATOR_NOT_GROUNDED', 'DOUBLE_INITIALIZE', 'CLOSED_CONTAINER',
                            'NOT_IN_CONTAINER', 'SLIDE_WITHOUT_CONTACT', 'RELEASE_WITHOUT_CUSTODY',
                            'CUSTODY_CONFLICT', 'CUSTODY_CONFLICT_HELD_BY_ANOTHER_ACTOR',
                            'HAND_OCCUPIED', 'HANDOFF_WITHOUT_CUSTODY',
                            'NO_RECIPIENT', 'SLIDE_CONFLATED_WITH_TRANSFER', 'UNREGISTERED_PROP',
                            'NOT_ON_SURFACE', 'ATTACH_WITHOUT_CUSTODY', 'MISSING_ATTACHMENT_TARGET',
                            'UNREGISTERED_ATTACHMENT_TARGET', 'UNINITIALIZED_ATTACHMENT_TARGET',
                            'ATTACH_TARGET_INACCESSIBLE', 'ATTACH_TARGET_HELD_BY_ANOTHER',
                            'DETACH_NOT_ATTACHED', 'DETACH_TARGET_MISMATCH', 'DETACH_WITHOUT_CUSTODY'):
                    fail.append((code, label))
                else:
                    uncertain.append((code, label))
            loc = e.get('text_locator') or {}
            if loc.get('quoted_text'):
                locators_in_beat.append(loc['quoted_text'])

        # 3. Linguistic Assistant: Scan for unmodeled physical nouns interacting with handling verbs
        has_handling = any(v in action for v in HANDLING_VERBS)
        if has_handling:
            for noun in PHYSICAL_NOUNS:
                if noun in action:
                    covered = any(noun in q for q in locators_in_beat)
                    if not covered:
                        uncertain.append(('UNMODELED_PROP_SUSPECTED', f'{sid}/{bid}: Physical noun "{noun}" in action text lacks event'))

    # 4. DEFECT-03 Fix: Active Final State Reconciliation
    if sm.registry:
        for pid in sm.registry:
            if pid not in sm.props:
                fail.append(('UNINITIALIZED_PROP_IN_REGISTRY', f'Prop {pid} in registry was never initialized'))

    # Active Terminal State Verification: each declared prop requires a final receipt.
    # A known last holder/location is NOT itself independently reconciled evidence.
    for pid in sm.props:
        current_grasper = sm.grasped_by.get(pid)
        current_loc = sm.props.get(pid)
        is_attached = pid in sm.attached

        if terminal_reconciliation and pid in terminal_reconciliation:
            expected = terminal_reconciliation[pid]
            exp_holder = expected.get('expected_holder')
            exp_attached = expected.get('expected_attached_to')
            exp_status = expected.get('status', 'UNVERIFIED')
            if exp_status not in ('SETTLED', 'UNRESOLVED'):
                uncertain.append(('TERMINAL_STATUS_UNVERIFIED', f'Prop {pid}: missing verified settlement status'))

            if exp_holder and current_loc != exp_holder:
                fail.append(('TERMINAL_STATE_DRIFT', f'Prop {pid} actual holder "{current_loc}" != declared "{exp_holder}"'))
            if exp_attached and sm.attached.get(pid) != exp_attached:
                fail.append(('TERMINAL_ATTACHMENT_DRIFT', f'Prop {pid} actual attached "{sm.attached.get(pid)}" != declared "{exp_attached}"'))
            if exp_status == 'UNRESOLVED':
                fail.append(('TERMINAL_STATE_UNRESOLVED', f'Prop {pid} declared with UNRESOLVED terminal status'))
        else:
            uncertain.append(('TERMINAL_RECONCILIATION_MISSING', f'Prop {pid}: observed final location {current_loc}, but no explicit terminal state evidence/receipt'))
            if current_grasper is not None:
                uncertain.append(('TERMINAL_PROP_UNSETTLED_IN_HAND', f'Prop {pid} remains active in grasp of {current_grasper} without explicit terminal reconciliation'))

    return fail, uncertain

def critical_path(nodes):
    d = {x.get('action_id'): x for x in nodes}
    if len(d) != len(nodes) or None in d:
        return None, ['INVALID_IDS']
    visiting = set()
    memo = {}
    def solve(k):
        if k in visiting: raise ValueError('CYCLE')
        if k not in d: raise ValueError('UNKNOWN_DEPENDENCY')
        if k in memo: return memo[k]
        visiting.add(k)
        n = d[k]
        seconds = n.get('estimated_duration_sec')
        if not numeric(seconds) or seconds < 0: raise ValueError('INVALID_DURATION')
        z = max([solve(v) for v in n.get('depends_on', [])], default=0) + seconds
        visiting.remove(k)
        memo[k] = z
        return z
    try:
        span = max([solve(k) for k in d], default=0)
    except ValueError as e:
        return None, [str(e)]
    issues = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            shared = set(a.get('required_resources', [])) & set(b.get('required_resources', []))
            if shared and b['action_id'] not in a.get('depends_on', []) and a['action_id'] not in b.get('depends_on', []):
                issues.append('RESOURCE_CONFLICT_UNSCHEDULED')
    return span, issues

def audit(p, contract, approved=None):
    r = []
    def add(*args):
        r.append(record(*args))

    if [x['id'] for x in contract.get('criteria', [])] != CRITERIA:
        add('TECH', 'FAIL', 'CONTRACT_CRITERIA_DRIFT', 'Definitions and ids of H01-H10 inconsistent')

    cfg = p.get('approved_configuration', {})
    beats = beats_of(p)
    if not beats:
        add('TECH', 'FAIL', 'MISSING_BEATS', 'No structured screenplay beats')

    # H01: Canon Lock
    if approved is None:
        add('H01', 'NOT_VERIFIED', 'APPROVED_LOCK_MISSING', 'Independent approved choices absent')
    else:
        keys = ['project_id', 'character_count_lock', 'target_duration_sec', 'aspect_ratio', 'dialogue_language', 'visual_style']
        bad = [k for k in keys if (p.get(k) if k == 'project_id' else cfg.get(k)) != approved.get(k)]
        add('H01', 'FAIL' if bad else 'PASS', 'APPROVED_CANON_DRIFT' if bad else 'APPROVED_CANON_MATCH', 'Comparison to independently approved P0-P5 fields', bad)

    # H02: Character Counts & Speaking Identities
    roster = p.get('approved_roster', [])
    speakers = [d.get('speaker') for _, b in beats for d in b.get('dialogue', [])]
    roles = set(p.get('approved_roster', []))
    ident = set(speakers)
    for s in p.get('screenplay_body', {}).get('scenes', []):
        ident.update(s.get('characters_present', []))
    for _, b in beats:
        ident.update(b.get('characters', []))
    lock = cfg.get('character_count_lock')
    bad = not isinstance(lock, int) or not roles or len(roles) != lock or not speakers or set(speakers) != roles or not ident.issubset(roles)
    add('H02', 'FAIL' if bad else 'PASS', 'CHARACTER_EXACT_COUNT' if bad else 'CHARACTER_COUNT_OK', 'Registered and speaking identities must match N exactly', [{'lock': lock, 'speakers': sorted(set(speakers), key=str), 'roster': sorted(roles, key=str), 'extras': sorted(ident - roles, key=str)}])

    # H03: Knowledge Ledger & Temporal Disclosure
    for ev in p.get('knowledge_events', []):
        if ev.get('assertion_time_sec', 1e9) < ev.get('disclosed_time_sec', 0):
            add('H03', 'FAIL', 'PREMATURE_KNOWLEDGE', 'Explicit registered knowledge time conflict', [ev])
    add('H03', 'NEEDS_REVIEW', 'KNOWLEDGE_SEMANTICS_UNVERIFIED', 'Full information ledger and semantic knowledge require human review')

    # H04: Sequential Interval Arithmetic & Timing
    t = 0
    timing_bad = False
    performance_review = False
    counts = []
    for sid, b in beats:
        start, end = b.get('start_sec'), b.get('end_sec')
        if not numeric(start) or not numeric(end) or start != t or end <= start:
            timing_bad = True
            break
        dur = end - start
        t = end
        if numeric(b.get('final_edit_duration_sec')) and not nearly(b['final_edit_duration_sec'], dur):
            timing_bad = True
        word_count = sum(len(d.get('text', '').split()) for d in b.get('dialogue', []))
        counts.append({'beat': b.get('beat_id'), 'words': word_count})
        rate = b.get('estimated_dialogue_wps')
        if not numeric(rate) or rate <= 0:
            performance_review = True
        elif word_count / rate > dur:
            add('H04', 'FAIL', 'DIALOGUE_OVERRUN', 'Calculated assumed spoken duration exceeds interval', [sid, b.get('beat_id')])
        graph = b.get('action_graph', [])
        if graph:
            span, issues = critical_path(graph)
            if span is None:
                add('H04', 'FAIL', 'INVALID_ACTION_GRAPH', 'DAG is invalid', issues)
            elif span > dur:
                add('H04', 'FAIL', 'ACTION_CRITICAL_PATH_OVERFLOW', 'Estimated critical path exceeds beat', [sid, b.get('beat_id')])
            if issues:
                performance_review = True
            if numeric(rate) and rate > 0 and span is not None and span + word_count / rate > dur:
                performance_review = True
        if b.get('action_text') and not graph:
            performance_review = True

    if not numeric(cfg.get('target_duration_sec')) or not nearly(t, cfg.get('target_duration_sec', -1)):
        timing_bad = True
    add('H04', 'FAIL' if timing_bad else 'PASS', 'INTERVAL_FAILURE' if timing_bad else 'INTERVAL_ARITHMETIC_OK', 'Sequential intervals from 0 to exact approved target', counts)
    if performance_review:
        add('H04', 'NEEDS_REVIEW', 'PERFORMANCE_ESTIMATE', 'Physical action timing and overlap are not independently measured')

    # H05: Enhanced Prop State Machine & Registry Auditing
    f, u = check_props(beats, p.get('initial_props'), p.get('initial_containers'), p.get('prop_registry'), p.get('terminal_props_reconciliation'))
    for code, loc in f:
        add('H05', 'FAIL', code, 'Detected physical/prop state transition violation', [loc])
    for code, loc in u:
        add('H05', 'NEEDS_REVIEW', code, 'Physical/prop event requires semantic review or assistance check', [loc])
    add('H05', 'NEEDS_REVIEW', 'PROP_EXTRACTION_COMPLETENESS', 'Text-to-event completeness and physical blocking remain semantic')

    # H06, H07, H08: Human Semantic Reviews
    for h, msg in [
        ('H06', 'Causality, procedural validity, and external legal/technical claims require human verification'),
        ('H07', 'Opening hook, conflict escalation, and earned dramatic payoff require human verification'),
        ('H08', 'Authentic dialogue dialect, pacing, and acting subtext require human verification')
    ]:
        add(h, 'NEEDS_REVIEW', 'SEMANTIC_REVIEW_REQUIRED', msg)

    # H09: Shot Plan Feasibility & Trim Arithmetic
    for sid, b in beats:
        shots = b.get('shot_plan', [])
        if shots:
            d = 0
            for shot in shots:
                raw, inn, out = shot.get('raw_generation_duration_sec'), shot.get('trim_in_sec'), shot.get('trim_out_sec')
                if raw not in GEN_BINS or not numeric(inn) or not numeric(out) or not 0 <= inn < out <= raw:
                    add('H09', 'FAIL', 'INVALID_GENERATION_BIN_OR_TRIM', 'Invalid generation bin or shot trim', [sid, b.get('beat_id')])
                else:
                    d += out - inn
            if not nearly(d, b['end_sec'] - b['start_sec']):
                add('H09', 'FAIL', 'EDIT_DURATION_MISMATCH', 'Trimmed shot durations do not sum to beat interval', [sid, b.get('beat_id')])
    add('H09', 'NEEDS_REVIEW', 'PRODUCTION_REALISM_UNVERIFIED', 'Generator compatibility requires media evidence and production review')

    # H10: Canonical Dialogue Packet & Cross-Artifact Reconciliation
    try:
        from core.canonical_source import reconcile_canonical_source
    except ImportError:
        try:
            from .canonical_source import reconcile_canonical_source
        except ImportError:
            import canonical_source as _cs
            reconcile_canonical_source = _cs.reconcile_canonical_source

    canon_issues = reconcile_canonical_source(p)
    deterministic_conflicts = [i for i in canon_issues if not str(i).startswith('PARTIAL_PROPEVENTS_SUSPECTED')]
    extraction_uncertainties = [i for i in canon_issues if str(i).startswith('PARTIAL_PROPEVENTS_SUSPECTED')]
    if deterministic_conflicts:
        add('H10', 'FAIL', 'CANONICAL_SOURCE_CONFLICT', 'Discrepancies found across canonical timeline, dialogue or prop artifacts', deterministic_conflicts)
    if extraction_uncertainties:
        add('H10', 'NEEDS_REVIEW', 'PARTIAL_EVENT_EXTRACTION_UNVERIFIED', 'Prose contains physical actions in beats without prop-event coverage', extraction_uncertainties)

    packet = p.get('canonical_dialogue_packet')
    actual = [{'speaker': d.get('speaker'), 'text': d.get('text')} for _, b in beats for d in b.get('dialogue', [])]
    if packet is None:
        add('H10', 'NOT_VERIFIED', 'DIALOGUE_PACKET_ABSENT', 'Canonical dialogue packet not supplied')
    elif not deterministic_conflicts:
        add('H10', 'FAIL' if packet != actual else 'PASS', 'DIALOGUE_PACKET_MISMATCH' if packet != actual else 'DIALOGUE_PACKET_MATCH', 'Compare actual spoken lines to canonical packet')
    add('H10', 'NEEDS_REVIEW', 'CROSS_ARTIFACTS_UNVERIFIED', 'All screenplay, story bible, state ledger and quality report have not been reconciled')

    # Explicit Gate
    add('GATE', 'NOT_VERIFIED', 'EXPLICIT_APPROVAL_REQUIRED', 'User approval necessary to advance after successful external review')
    return r

def verdict(records):
    if any(x['status'] == 'FAIL' for x in records):
        return 'NEEDS_FIX'
    if any(x['status'] in ('NOT_VERIFIED', 'NEEDS_REVIEW') for x in records):
        return 'BLOCKED_PENDING_EVIDENCE'
    return 'PASS_ELIGIBLE_PENDING_USER_APPROVAL'
