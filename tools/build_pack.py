"""Generate native payload and build the known pack from user-supplied campaign scripts."""
import argparse
import json
from pathlib import Path
from project import (ROOT, BUILD, GENERATED, DIST, DLL, PAYLOAD, PACK_NAME, PACK_SHA,
                     CAMPAIGN_SHA, BOOTSTRAP, FRONTEND_MEMBER, FRONTEND_SHA,
                     FRONTEND_BOOTSTRAP, check_sources, check_dll, make_payload,
                     sha, require, write_report)
from pack_io import make_pack


def generate_payload():
    check_sources()
    native = check_dll(DLL.read_bytes())
    GENERATED.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_bytes(make_payload(native))
    write_report('payload.json', dict(passed=True, size=len(native), dll_sha256=sha(native),
                                    payload_sha256=sha(PAYLOAD.read_bytes()), generated=True))
    return native


def load_campaigns(folder):
    entries = {}
    resolved = folder.resolve()
    require(resolved.is_dir(), 'Campaign directory does not exist.')
    for name, digest in CAMPAIGN_SHA.items():
        path = resolved/name/'scripting.lua'
        require(path.resolve().is_relative_to(resolved), 'Campaign path escapes input directory.')
        require(path.is_file(), 'Missing campaign input: ' + name + '/scripting.lua')
        require(path.stat().st_size <= 10 * 1024 * 1024, 'Campaign input is oversized: ' + name)
        raw = path.read_bytes()
        require(b'lua_scripts.rdp_reinforcement_cap_v01_campaign' not in raw, 'Bootstrap already exists: ' + name)
        require(sha(raw) == digest, 'Unverified DEI input: ' + name + '. This release requires its recorded baseline input.')
        entries['campaigns\\' + name + '\\scripting.lua'] = raw + BOOTSTRAP
    return entries


def load_frontend(path):
    require(path.is_file(), 'Missing frontend input file.')
    require(path.stat().st_size <= 1024 * 1024, 'Frontend input is oversized.')
    original = path.read_bytes()
    require(b'lua_scripts.rdp_rrc_replay_frontend_test01' not in original,
            'Frontend bootstrap already exists.')
    require(sha(original) == FRONTEND_SHA, 'Unverified DEI frontend input.')
    return original + FRONTEND_BOOTSTRAP


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload-only', action='store_true', help='No DEI inputs needed; prepare Lua tests')
    parser.add_argument('--campaign-dir', type=Path, help='Directory containing main_rome/scripting.lua etc.')
    parser.add_argument('--frontend-script', type=Path, help='Matching original DEI lua_scripts/frontend_scripted.lua')
    args = parser.parse_args()
    if not args.payload_only and (args.campaign_dir is None or args.frontend_script is None):
        parser.error('--campaign-dir and --frontend-script are required for a pack build; use --payload-only for tests.')
    if args.payload_only and (args.campaign_dir is not None or args.frontend_script is not None):
        parser.error('--payload-only and DEI input options are mutually exclusive.')
    output = DIST/PACK_NAME
    if not args.payload_only and args.frontend_script.resolve() == output.resolve():
        parser.error('Frontend input must differ from the output pack.')
    campaigns = None if args.payload_only else load_campaigns(args.campaign_dir)
    frontend = None if args.payload_only else load_frontend(args.frontend_script)
    native = generate_payload()
    if args.payload_only:
        print(json.dumps(dict(passed=True, payload_generated=True, native_sha256=sha(native))))
        return
    entries = campaigns
    # Retain the tested pack's original member order.
    for name in ('rdp_reinforcement_cap_v01_campaign.lua', 'rdp_reinforcement_cap_v01_loader.lua'):
        entries['lua_scripts\\' + name] = (ROOT/'src/lua'/name).read_bytes()
    entries['lua_scripts\\rdp_reinforcement_cap_v01_payload.lua'] = PAYLOAD.read_bytes()
    entries[FRONTEND_MEMBER] = frontend
    entries['lua_scripts\\rdp_rrc_replay_frontend_test01.lua'] = (ROOT/'src/lua/rdp_rrc_replay_frontend_test01.lua').read_bytes()
    raw = make_pack(entries)
    require(sha(raw) == PACK_SHA, 'Pack differs from the exact supported release.')
    DIST.mkdir(exist_ok=True)
    if args.campaign_dir.resolve().is_relative_to(DIST.resolve()):
        parser.error('Keep campaign inputs outside dist/.')
    output.write_bytes(raw)
    report = dict(passed=True, pack_file=PACK_NAME, pack_sha256=sha(raw), size=len(raw),
                  campaign_count=len(CAMPAIGN_SHA), entry_count=len(entries),
                  exact_release_pack=True, native_sha256=sha(native), frontend_sha256=FRONTEND_SHA,
                  original_input_sha256=CAMPAIGN_SHA, game_executed=False)
    write_report('pack_build.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
