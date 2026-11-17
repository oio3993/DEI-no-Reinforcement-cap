"""Negative input/pack checks using synthetic data; no game files or DLL execution."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_pack
from project import (ROOT, BUILD, DLL, BOOTSTRAP, FRONTEND_MEMBER, FRONTEND_BOOTSTRAP,
                     RUNTIME_MODULES, check_dll, decode_payload, make_payload, sha, write_report)
from pack_io import make_pack, read_pack
import verify_release
from verify_release import verify_pack


class BuildTools(unittest.TestCase):
    def test_roundtrip(self):
        values={'campaigns\\fixture\\scripting.lua':b'-- fixture\n','lua_scripts\\x.lua':b'return true\n'}
        self.assertEqual(read_pack(make_pack(values)),values)

    def test_truncated_header(self):
        with self.assertRaises(ValueError):read_pack(b'PFH4')

    def test_truncated_payload(self):
        with self.assertRaises(ValueError):read_pack(make_pack({'x.lua':b'abc'})[:-1])

    def test_trailing_bytes(self):
        with self.assertRaises(ValueError):read_pack(make_pack({'x.lua':b'abc'})+b'bad')

    def test_bad_index_bounds(self):
        value=bytearray(make_pack({'x.lua':b'abc'}));struct.pack_into('<I',value,20,0xffffffff)
        with self.assertRaises(ValueError):read_pack(bytes(value))

    def test_unsafe_paths(self):
        for name in ('..\\x.lua','/x.lua','D:\\x.lua','x\\..\\y.lua','x\\\\y.lua'):
            with self.subTest(name=name),self.assertRaises(ValueError):make_pack({name:b'a'})

    def test_case_duplicate(self):
        with self.assertRaises(ValueError):make_pack({'x.lua':b'a','X.lua':b'b'})

    def test_missing_campaigns(self):
        BUILD.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            with self.assertRaisesRegex(ValueError,'Missing campaign'):build_pack.load_campaigns(Path(temp))

    def test_changed_campaign_rejected(self):
        BUILD.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            root=Path(temp);(root/'fixture').mkdir();(root/'fixture/scripting.lua').write_bytes(b'changed')
            with patch.dict(build_pack.CAMPAIGN_SHA,{'fixture':sha(b'known')},clear=True):
                with self.assertRaisesRegex(ValueError,'Unverified DEI'):build_pack.load_campaigns(root)

    def test_duplicate_bootstrap_rejected(self):
        BUILD.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            root=Path(temp);(root/'fixture').mkdir();data=b'-- fixture\n'+BOOTSTRAP
            (root/'fixture/scripting.lua').write_bytes(data)
            with patch.dict(build_pack.CAMPAIGN_SHA,{'fixture':sha(data)},clear=True):
                with self.assertRaisesRegex(ValueError,'already exists'):build_pack.load_campaigns(root)

    def test_wrong_native_rejected(self):
        with self.assertRaises(ValueError):check_dll(b'MZwrong')

    def test_missing_frontend_rejected(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            with self.assertRaisesRegex(ValueError, 'Missing frontend'):
                build_pack.load_frontend(Path(temp)/'missing.lua')

    def test_valid_frontend_input(self):
        prefix=b'-- Synthetic frontend input.\n'
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            path=Path(temp)/'frontend.lua'
            path.write_bytes(prefix)
            with patch.object(build_pack, 'FRONTEND_SHA', sha(prefix)):
                self.assertEqual(build_pack.load_frontend(path), prefix+FRONTEND_BOOTSTRAP)

    def test_changed_frontend_input_rejected(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            path=Path(temp)/'frontend.lua'
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Unverified DEI frontend'):
                build_pack.load_frontend(path)

    def test_duplicate_frontend_bootstrap_rejected(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            path=Path(temp)/'frontend.lua'
            path.write_bytes(FRONTEND_BOOTSTRAP)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                build_pack.load_frontend(path)

    def test_oversized_frontend_rejected(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            path=Path(temp)/'frontend.lua'
            path.write_bytes(b' '*(1024*1024+1))
            with self.assertRaisesRegex(ValueError, 'oversized'):
                build_pack.load_frontend(path)

    def test_windows_overlay_includes_frontend_bootstrap(self):
        import gzip
        from build_native_windows import write_overlay
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            overlay=Path(temp)/'overlay.gz'
            write_overlay(overlay)
            raw=gzip.decompress(overlay.read_bytes())
            self.assertIn(b'work/repo/integration/frontend_bootstrap.lua\0', raw)
            self.assertIn(FRONTEND_BOOTSTRAP, raw)

    def test_frontend_input_cannot_be_overwritten_by_pack(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            output=Path(temp)/build_pack.PACK_NAME
            arguments=['build_pack.py', '--campaign-dir', str(Path(temp)/'campaigns'),
                       '--frontend-script', str(output)]
            with patch.object(build_pack, 'DIST', Path(temp)), patch.object(sys, 'argv', arguments):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    build_pack.main()
            self.assertEqual(raised.exception.code, 2)

    def test_linked_checks_are_not_silently_skipped(self):
        import verify_native
        BUILD.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as temp:
            with patch.object(verify_native,'root',Path(temp)):
                with self.assertRaisesRegex(ValueError,'Linked checks require'):verify_native.verify()

    def test_payload_range_rejected(self):
        with self.assertRaises(ValueError):decode_payload(b'return "\\999"')

    def fixture(self):
        # This is our own tiny campaign input, never a DEI entry or release pack.
        prefix=b'-- Synthetic campaign input for public CI.\n'
        native=check_dll(DLL.read_bytes())
        entries={'campaigns\\fixture\\scripting.lua':prefix+BOOTSTRAP,
                 'lua_scripts\\rdp_reinforcement_cap_v01_payload.lua':make_payload(native)}
        entries[FRONTEND_MEMBER]=self.frontend_prefix()+FRONTEND_BOOTSTRAP
        for name in RUNTIME_MODULES:
            entries['lua_scripts\\'+name]=(ROOT/'src/lua'/name).read_bytes()
        return prefix,native,entries

    def frontend_prefix(self):
        return b'-- Synthetic frontend input for public CI.\n'

    def verify_fixture(self,raw,prefix,native,expected_hash):
        # Scope fixture identities to this call. Production verification retains
        # all nine real input hashes and the exact supported pack hash.
        with patch.dict(verify_release.CAMPAIGN_SHA,{'fixture':sha(prefix)},clear=True), \
             patch.object(verify_release,'PACK_SHA',expected_hash), \
             patch.object(verify_release,'FRONTEND_SHA',sha(self.frontend_prefix())):
            return verify_pack(raw,native)

    def test_valid_synthetic_pack(self):
        prefix,native,entries=self.fixture();raw=make_pack(entries)
        self.assertEqual(self.verify_fixture(raw,prefix,native,sha(raw)),entries)

    def test_changed_campaign_prefix_rejected(self):
        prefix,native,entries=self.fixture()
        entries['campaigns\\fixture\\scripting.lua']=b'-- Changed prefix\n'+BOOTSTRAP
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError,'DEI prefix differs'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_changed_runtime_source_rejected(self):
        prefix,native,entries=self.fixture()
        entries['lua_scripts\\rdp_reinforcement_cap_v01_campaign.lua']+=b'\n'
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError,'Runtime source differs'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_changed_payload_rejected(self):
        prefix,native,entries=self.fixture()
        entries['lua_scripts\\rdp_reinforcement_cap_v01_payload.lua']+=b'\n'
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError,'Packed payload differs'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_changed_frontend_prefix_rejected(self):
        prefix,native,entries=self.fixture()
        entries[FRONTEND_MEMBER]=b'changed\n'+FRONTEND_BOOTSTRAP
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError, 'Frontend prefix differs'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_missing_frontend_bootstrap_rejected(self):
        prefix,native,entries=self.fixture()
        entries[FRONTEND_MEMBER]=self.frontend_prefix()
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError, 'Missing frontend bootstrap'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_changed_frontend_runtime_rejected(self):
        prefix,native,entries=self.fixture()
        entries['lua_scripts\\rdp_rrc_replay_frontend_test01.lua']+=b'\n'
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError, 'Runtime source differs'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_missing_pack_entry_rejected(self):
        prefix,native,entries=self.fixture()
        del entries['lua_scripts\\rdp_reinforcement_cap_v01_loader.lua']
        raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError,'Unexpected pack entries'):
            self.verify_fixture(raw,prefix,native,sha(raw))

    def test_final_pack_hash_guard_retained(self):
        prefix,native,entries=self.fixture();raw=make_pack(entries)
        with self.assertRaisesRegex(ValueError,'exact supported'):
            self.verify_fixture(raw,prefix,native,'0'*64)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(BuildTools)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    write_report('build_tools_tests.json',dict(passed=result.wasSuccessful(),test_count=result.testsRun,
                 synthetic_and_tamper_tests=True,release_pack_required=False,game_executed=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
