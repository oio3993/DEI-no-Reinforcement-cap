"""Paths and fingerprints for the Reinforcement Cap AllBattles01 release."""
from pathlib import Path
import hashlib
import json
import re

if not __debug__:
    raise RuntimeError('Run the verification tools without Python -O.')

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
REPORTS = BUILD / 'reports'
GENERATED = BUILD / 'generated'
DIST = ROOT / 'dist'
DLL = BUILD / 'rdp_reinforcement_cap_v01.dll'
PAYLOAD = GENERATED / 'rdp_reinforcement_cap_v01_payload.lua'
PACK_NAME = 'rdp_reinforcement_cap_v01_singlepack_all_battles01.pack'
DLL_SHA = '63d42188045383cfa615f2165662902be92049dee70b0712176076456c41fcd2'
DLL_SIZE = 8142
PACK_SHA = 'f0a24b9ee8cc11ac256fde0926ce7415caf4fc8b815fdc65aa31e7b6a1cc8f7a'
BOOTSTRAP = b'\n-- Reinforcement capacity runtime\nrequire "lua_scripts.rdp_reinforcement_cap_v01_campaign";\n'
SOURCE_SHA = {
    'src/native/patch.c': '40f08ef18ea755dd35df4c9441baa8230022d24ed06842d75ba959e6f1ff4a6d',
    'src/native/patch_bytes.h': 'd711ee1ba999ac51238056961fb26746891ccd788af9ed978de0fded72ede1fd',
    'src/native/patch.def': 'd8462fef3a6e44a317f6389cff830e3e2a441c80c0ecbb04c4fc3aaedf2a5b3a',
    'src/lua/rdp_reinforcement_cap_v01_campaign.lua': '143b8dc3506380b475f10754f927e0eac4715990b2ba4021cac56b713f3ce960',
    'src/lua/rdp_reinforcement_cap_v01_loader.lua': '7538b6de7c946a340184c31502ad0206c371c1758552ccb795d4bd2142888168',
}
CAMPAIGN_SHA = {
    'main_3c': '0841007a67acda50fc265be2282432bbe526dffc6021ab7faeda48f3b7a3b9be',
    'main_emperor': '83e7c6760f0e91783ce31a65defe9236b79b3f700f9e666e4d49c1744074fdb0',
    'main_gaul': 'a8a9a4b1fb1eb947694141b3a7125e67b76783d965212ab98dad22934a7b3255',
    'main_greek': '2a267b4213516e2e59f95d07a78c5b37d51c64d96a93ff3d355afd6cbaa2beca',
    'main_invasion': '2050de995a7a77038ecd74c584c8ff25a7d2ccaa5c60d3959043071cb13a5cb3',
    'main_punic': '4d2716a2a2dba02e9dd5620aa17782aab819a21c1e52792cafde48c1eb4756fd',
    'main_rome': '1c2d47bc57c0d261a172266a5c1d5805f2925799163bcfee9bf2537a525c5911',
    'prologue_01': 'b94785440b0e3476ba648a624adde6342188bac70ba2ebdebead914462b9062e',
    'prologue_02': 'a027dc0c6f6a1c687fee9a586b8ef58fd27157571453562426c67ad5786ed770',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_report(name, report):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')


def check_sources():
    for name, digest in SOURCE_SHA.items():
        require(sha((ROOT / name).read_bytes()) == digest,
                'Baseline source differs: ' + name + '. Review a version change explicitly.')
    require((ROOT / 'integration/dei_bootstrap.lua').read_bytes() == BOOTSTRAP,
            'Bootstrap differs from the supported release.')


def check_dll(raw):
    require(len(raw) == DLL_SIZE and sha(raw) == DLL_SHA,
            'DLL does not match AllBattles01. Do not update the loader silently.')
    return raw


def make_payload(raw):
    check_dll(raw)
    chunks = ['    "' + ''.join('\\' + f'{byte:03d}' for byte in raw[i:i+128]) + '"'
              for i in range(0, len(raw), 128)]
    return ('-- Generated DLL bytes; SHA256: ' + DLL_SHA +
            '\nreturn table.concat({\n' + ',\n'.join(chunks) + '\n})\n').encode('ascii')


def decode_payload(raw):
    numbers = re.findall(rb'\\([0-9]{3})', raw)
    require(all(int(value) <= 255 for value in numbers), 'Invalid payload byte.')
    native = check_dll(bytes(int(value) for value in numbers))
    require(raw == make_payload(native), 'Payload is not the exact generated module.')
    return native
