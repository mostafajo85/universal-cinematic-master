"""Offline packaging, byte-integrity and optional six-source KB activation.

No network, licensing, DRM, provider IDs or media/approval authentication.
"""
from pathlib import Path, PurePosixPath
import hashlib, json, re, stat, zipfile

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def files(root):
    root = Path(root).resolve()
    result = {}
    for p in root.rglob('*'):
        if '__pycache__' in p.parts:
            continue
        if p.is_symlink():
            raise ValueError('SYMLINK_NOT_SUPPORTED')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = p
    return result

def validate_kb(root):
    """Validate the exact RC2 source identities; no guessed or rewritten KBs."""
    root = Path(root).resolve()
    spec = read_json(root/'resources/PRIVATE_KB_SOURCE_PINS_ONLY.json')['private_kb_sources']
    if set(spec) != {'CINE','PERF','REAL','TRANS','COMPAT','EXEC'}:
        raise ValueError('INVALID_KB_ROLE_SET')
    folder = root/'knowledge_base'
    if folder.is_symlink():
        raise ValueError('KB_SYMLINK_NOT_SUPPORTED')
    if not folder.exists():
        return {'status':'STANDARD_AVAILABLE','professional_available':False,'sources':{},'errors':[], 'production_approved':False}
    if not folder.is_dir():
        raise ValueError('KB_NOT_DIRECTORY')
    # A visible text placeholder survives ZIP import; it is NOT a KB source.
    # It may remain when the six actual private KB files are later added.
    entries = [p for p in folder.iterdir() if p.name != 'README.txt']
    if not entries:
        return {'status':'STANDARD_AVAILABLE','professional_available':False,'sources':{},'errors':[], 'production_approved':False}
    expected = {v['filename'] for v in spec.values()}
    if len(expected) != 6 or any(PurePosixPath(n).name != n or '\\' in n for n in expected):
        raise ValueError('INVALID_KB_FILENAMES')
    errors, observed = [], {}
    if {p.name for p in entries} != expected:
        errors.append('EXACT_SIX_KB_FILES_REQUIRED')
    for role, identity in spec.items():
        p = folder/identity['filename']
        if p.is_symlink() or not p.is_file():
            errors.append('KB_MISSING_OR_UNSAFE:'+role)
            continue
        raw = p.read_bytes()
        try:
            text = raw.decode('utf-8')
            if not text.strip() or '\x00' in text:
                raise ValueError('EMPTY_OR_BINARY_KB:'+role)
        except UnicodeError:
            errors.append('KB_UTF8_REQUIRED:'+role)
            continue
        if len(raw) != identity['bytes'] or sha(raw) != identity['source_sha256']:
            errors.append('KB_HASH_OR_SIZE_MISMATCH:'+role)
        observed[role] = {'filename':p.name,'bytes':len(raw),'sha256':sha(raw)}
    return {'status':'BLOCKED' if errors else 'PROFESSIONAL_AVAILABLE',
            'professional_available':not errors,'sources':observed,'errors':errors,
            'scope':'SOURCE_IDENTITY_ONLY_NOT_SEMANTIC_USE_OR_LICENSE', 'production_approved':False}

GUARD_START = '<!-- UCM_GUARD_LOCK_START -->'
GUARD_END = '<!-- UCM_GUARD_LOCK_END -->'
ADAPTIVE_NOTES = 'adaptive/OPERATIONAL_NOTES.md'


def guard_bytes(skill_text):
    if skill_text.count(GUARD_START) != 1 or skill_text.count(GUARD_END) != 1:
        raise ValueError('IMMUTABLE_SKILL_GUARD_MISSING_OR_DUPLICATED')
    start = skill_text.index(GUARD_START)
    end = skill_text.index(GUARD_END) + len(GUARD_END)
    if end <= start:
        raise ValueError('IMMUTABLE_SKILL_GUARD_INVALID')
    return skill_text[start:end].encode('utf-8')


def check_adaptive(root, actual, pin):
    if 'SKILL.md' not in actual:
        raise ValueError('REQUIRED_SKILL_MISSING')
    skill_path = actual['SKILL.md']
    raw = skill_path.read_bytes()
    if len(raw) > 200_000: raise ValueError('SKILL_TOO_LARGE_TO_AUDIT')
    try:
        skill = raw.decode('utf-8')
    except UnicodeError:
        raise ValueError('SKILL_UTF8_REQUIRED')
    front = re.match(r'\A---\nname: ([a-z0-9-]{1,64})\ndescription: [^\n]+\n---\n',skill)
    if not front or front.group(1) != pin['skill_name']:
        raise ValueError('SKILL_FRONTMATTER_OR_NAME_DRIFT')
    if sha(guard_bytes(skill)) != pin['protected_skill_guard_sha256']:
        raise ValueError('IMMUTABLE_SKILL_GUARD_CHANGED')
    changes = []
    baseline = pin.get('adaptive_baselines', {})
    for n in ('SKILL.md', ADAPTIVE_NOTES):
        if n in actual:
            current = sha(actual[n].read_bytes())
            if current != baseline.get(n):
                changes.append({'file':n,'baseline_sha256':baseline.get(n),'observed_sha256':current})
    # Strictly non-executable notes: mutations to scripts and other executable content NEVER adaptive.
    for n,p in actual.items():
        if not n.startswith('adaptive/') or n == ADAPTIVE_NOTES:
            continue
        if p.suffix not in {'.md','.txt','.json','.jsonl'}:
            raise ValueError('ADAPTIVE_EXECUTABLE_OR_UNSUPPORTED_RESOURCE:'+n)
        if p.stat().st_size > 200_000:
            raise ValueError('ADAPTIVE_RESOURCE_TOO_LARGE:'+n)
        changes.append({'file':n,'baseline_sha256':None,'observed_sha256':sha(p.read_bytes())})
    # This check detects protected-text changes and byte drift; NOT contradictory natural-language additions.
    return {'status':'ADAPTIVE_MODIFIED' if changes else 'ADAPTIVE_BASELINE',
            'changes':changes,
            'requires_semantic_review':bool(changes),
            'guard_verified':True,
            'semantic_safety':'NOT_PROVEN_BY_HASHES_OR_TEXT_SCAN'}


def verify(root, trusted_pin):
    root = Path(root).resolve()
    pinfile = root/'release_pin.json'
    if pinfile.is_symlink():
        raise ValueError('UNSAFE_RELEASE_PIN')
    raw = pinfile.read_bytes()
    if sha(raw) != trusted_pin:
        raise ValueError('RELEASE_PIN_NOT_INDEPENDENTLY_TRUSTED')
    pin = json.loads(raw)
    if pin.get('integrity_schema') != 'ucm.core-immutable-adaptive-skill.v1':
        raise ValueError('UNSUPPORTED_INTEGRITY_SCHEMA')
    actual = files(root)
    mutable = {'SKILL.md',ADAPTIVE_NOTES}
    # Private knowledge is checked separately, never bundled in public release.
    observed_protected = {n for n in actual if n not in mutable and n != 'release_pin.json'
                          and not n.startswith('knowledge_base/') and not n.startswith('adaptive/')}
    # The public KB placeholder is immutable but private KB data isn't.
    if 'knowledge_base/README.txt' in actual:
        observed_protected.add('knowledge_base/README.txt')
    if observed_protected != set(pin['members']):
        raise ValueError('RELEASE_MEMBER_SET_MISMATCH')
    for name, expected in pin['members'].items():
        if sha(actual[name].read_bytes()) != expected:
            raise ValueError('RELEASE_MEMBER_HASH_MISMATCH:'+name)
    if pin['master_sha256'] != sha((root/'resources/MASTER.md').read_bytes()):
        raise ValueError('MASTER_PIN_DRIFT')
    contract = root/'scripts/vendor_p6/contracts/P6_H01_H10_MASTER.json'
    if pin['p6_contract_sha256'] != sha(contract.read_bytes()):
        raise ValueError('P6_CONTRACT_PIN_DRIFT')
    if read_json(contract)['origin_master_sha256'] != pin['master_sha256']:
        raise ValueError('MASTER_CONTRACT_DRIFT')
    adaptive = check_adaptive(root,actual,pin)
    kb = validate_kb(root)
    if kb['errors']:
        raise ValueError(';'.join(kb['errors']))
    return {'status':'LOCAL_CORE_VERIFIED_WITH_ADAPTIVE_DRIFT' if adaptive['changes'] else 'LOCAL_RELEASE_VERIFIED',
            'protected_members':len(pin['members']),'files':len(actual),
            'master_sha256':pin['master_sha256'],'adaptive':adaptive,'knowledge':kb,
            'gemini_runtime':'NOT_TESTED_LIVE','hermes_runtime':'NOT_TESTED_LIVE',
            'production_approved':False}

def check_zip(path):
    """Inspect bytes without extraction. Intentionally stricter than generic ZIP."""
    errors, names, seen = [], [], set()
    total = 0
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            n = i.filename
            if i.is_dir():
                continue
            names.append(n)
            parts = PurePosixPath(n).parts
            if (not parts or n.startswith('/') or '\\' in n or ':' in n or
                any(p in {'.','..',''} for p in n.split('/')) or len(parts)>10):
                errors.append('UNSAFE_ARCHIVE_PATH:'+n)
            if n.casefold() in seen:
                errors.append('DUPLICATE_ARCHIVE_PATH:'+n)
            seen.add(n.casefold())
            if stat.S_ISLNK(i.external_attr >> 16):
                errors.append('ARCHIVE_SYMLINK:'+n)
            total += i.file_size
            if i.file_size>100_000_000 or total>100_000_000:
                raise ValueError('ARCHIVE_TOO_LARGE')
            raw = z.read(i)
            if not raw:
                errors.append('EMPTY_RESOURCE:'+n)
            try:
                if '\x00' in raw.decode('utf-8'):
                    errors.append('BINARY_RESOURCE:'+n)
            except UnicodeError:
                errors.append('NON_UTF8_RESOURCE:'+n)
            if PurePosixPath(n).suffix not in {'.md','.py','.json','.txt'}:
                errors.append('UNEXPECTED_RESOURCE_TYPE:'+n)
        if names.count('SKILL.md') != 1 or sum(PurePosixPath(n).name=='SKILL.md' for n in names)!=1:
            errors.append('ONE_ROOT_SKILL_REQUIRED')
        if 'SKILL.md' in names:
            skill = z.read('SKILL.md').decode('utf8')
            if not re.match(r'\A---\nname: [a-z0-9-]{1,64}\ndescription: [^\n]+\n---\n',skill):
                errors.append('INVALID_SKILL_FRONTMATTER')
        if len(names)>100 or Path(path).stat().st_size>100_000_000:
            errors.append('ARCHIVE_LIMIT')
    return {'status':'BLOCKED' if errors else 'LOCAL_PACKAGE_PASS', 'errors':errors,
            'files':len(names),'uncompressed_bytes':total,'zip_sha256':sha(Path(path).read_bytes()),
            'gemini_runtime':'NOT_TESTED_LIVE','production_approved':False}

def build_zip(root, out, trusted_pin, profile):
    root, out = Path(root).resolve(), Path(out).resolve()
    if out.is_relative_to(root):
        raise ValueError('OUTPUT_MUST_BE_OUTSIDE_SKILL_ROOT')
    if out.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    state = verify(root, trusted_pin)
    ready = state['knowledge']['professional_available']
    if profile=='professional' and not ready:
        raise ValueError('ALL_SIX_VALIDATED_KB_REQUIRED')
    selected = files(root)
    if profile=='public':
        selected = {n:p for n,p in selected.items() if not n.startswith('knowledge_base/') or n == 'knowledge_base/README.txt'}
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for n,p in sorted(selected.items()):
            info = zipfile.ZipInfo(n, date_time=(2026,10,24,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info,p.read_bytes())
    result = check_zip(out)
    if result['errors']:
        raise ValueError('BUILT_PACKAGE_INVALID:'+','.join(result['errors']))
    result['profile'] = profile
    return result

def preflight(root, trusted_pin, mode, workspace=None):
    if mode not in {'STANDARD','PRO'}:
        raise ValueError('ONLY_TWO_MODES_STANDARD_AND_PRO')
    result = verify(root,trusted_pin)
    if mode == 'PRO':
        if not workspace:
            raise ValueError('PRO_WORKSPACE_REQUIRED')
        from .knowledge_gate import verify_private
        state=verify_private(root,workspace)
        if not state['verified']:
            raise ValueError('PRO_SIX_KB_NOT_VERIFIED:'+','.join(state['errors']))
        result['workspace_kb_state']=state
    # H01-H10 executable in BOTH modes; actual screenplay acceptance is a separate check.
    import subprocess,sys
    proc=subprocess.run([sys.executable,str(Path(root)/'scripts/vendor_p6/run_validator.py'),'--help'],
                       capture_output=True,text=True,timeout=20)
    if proc.returncode:
        raise ValueError('MANDATORY_P6_CHECKER_NOT_EXECUTABLE')
    result.update(status='LOCAL_PREFLIGHT_PASS',mode=mode,
                  mandatory_p6_checker='EXECUTABLE_NOT_ACTUAL_SCREENPLAY_VALIDATION',
                  runtime_attachments='ACTUAL_GEMINI_AVAILABILITY_NOT_TESTED_LIVE')
    return result
