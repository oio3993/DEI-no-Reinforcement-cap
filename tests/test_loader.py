"""Exercise extraction failure scenarios with mocked I/O and mocked native loading."""
import hashlib,json,os,tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from project import PAYLOAD, check_sources, write_report
from lua_host import run, HOST_RUNTIME
check_sources()
root=Path(__file__).resolve().parents[1]
source=(root/'src/lua/rdp_reinforcement_cap_v01_loader.lua').read_text()
payload=PAYLOAD.read_text()
setup='''
local payload=(function()
'''+payload+'''
end)()
local target='.\\\\rdp_rrc_sp01_63d42188045383cf.dll'
local stage=target..'.rdp-tmp'
local marker='.\\\\Rome2.exe'
local files={[marker]='MZexe fixture'}
local cfg={};local writes=0;local renames=0;local closes=0;local loadcalls=0;local nativecalls=0
local function permitted(path)assert(path==target or path==stage or path==marker,path)end
io={open=function(path,mode)
    permitted(path)
    if cfg.open_throw then error('open error')end
    if mode=='rb' then
        if path==target and cfg.unreadable then return nil,'denied',13 end
        if not files[path] then return nil,'missing',cfg.unknown_errno and 13 or 2 end
    else
        assert(mode=='wb' and path==stage,'unexpected write')
        if cfg.stage_denied then return nil,'locked',13 end
        writes=writes+1;files[path]=''
    end
    return {
        read=function(self,n)
            assert(n<=#payload+1)
            if (path==target and cfg.read_throw) or (path==stage and cfg.stage_read_throw) then error('read failure')end
            if path==stage and cfg.stage_corrupt then return 'bad' end
            local data=files[path]:sub(1,n)
            if data=='' then return nil end
            return data
        end,
        write=function(self,data)
            assert(mode=='wb' and path==stage and data==payload)
            if cfg.write_throw then error('write failure')end
            files[path]=cfg.partial and data:sub(1,64) or data
            if cfg.target_appears then files[target]=cfg.target_appears=='same' and payload or 'different' end
            if cfg.write_nil then return nil,'disk full' end
            return self
        end,
        close=function(self)
            closes=closes+1
            if mode=='wb' and cfg.close_throw then error('close failure')end
            if (mode=='wb' and cfg.close_nil) or cfg.read_close_nil then return nil,'close failure' end
            return true
        end}
end}
os={remove=function(path)assert(path==stage);files[path]=nil;return true end,
    rename=function(from,to)
        assert(from==stage and to==target);renames=renames+1
        if cfg.rename_throw then error('rename error')end
        if cfg.rename_same then files[target]=payload;return nil,'exists' end
        if cfg.rename_different then files[target]='different';return nil,'exists' end
        if cfg.rename_fail or files[target] then return nil,'locked' end
        files[target]=files[stage];files[stage]=nil
        if cfg.after_rename_bad then files[target]='corrupt' end
        return true
    end}
require=function(name)
    assert(name=='lua_scripts.rdp_reinforcement_cap_v01_payload')
    if cfg.payload_throw then error('missing payload')end
    if cfg.payload_wrong_type then return {}end
    if cfg.payload_short then return payload:sub(1,-2)end
    if cfg.payload_bad_magic then return 'ZZ'..payload:sub(3)end
    return payload
end
package.loadlib=function(path,symbol)
    assert(path==target and files[target]==payload,'unverified DLL was loaded')
    assert(symbol=='rrc_install' or symbol=='rrc_disable')
    loadcalls=loadcalls+1
    if cfg.load_throw then error('loader error')end
    if cfg.load_nil then return nil,'load failure' end
    return function()nativecalls=nativecalls+1 end
end
'''
def exercise(name,before,after):
    run(name,setup+'\n'+before+'\nlocal loader=(function()\n'+source+'\nend)()\n'+after)

tests=[]
def case(name,before,after):exercise(name,before,after);tests.append(name)
case('fresh_extract_verify_commit_and_load','',"""
assert(loader.prepare());assert(files[target]==payload and files[stage]==nil)
assert(writes==1 and renames==1)
assert(loader.prepare());assert(writes==1)
local fn=assert(loader.load('rrc_install'));fn();assert(loadcalls==1 and nativecalls==1)
""")
case('existing_identical_dll_reused','files[target]=payload;cfg.stage_denied=true',
     "assert(loader.prepare());assert(writes==0 and renames==0);assert(loader.load('rrc_disable'))")
for name,before in [
 ('wrong_existing_dll',"files[target]='different'"),
 ('oversized_existing_dll','files[target]=payload..string.rep("x",100000)'),
 ('truncated_existing_dll','files[target]=payload:sub(1,64)'),
 ('empty_existing_dll',"files[target]=''"),
 ('unreadable_existing_dll','files[target]=payload;cfg.unreadable=true')]:
 case(name,before,"local previous=files[target];assert(not loader.prepare());assert(not loader.load('rrc_install'));assert(files[target]==previous and writes==0 and loadcalls==0)")
for name,before in [
 ('missing_game_marker','files[marker]=nil'),('wrong_game_marker',"files[marker]='ZZ'"),
 ('io_open_throws','cfg.open_throw=true'),('ambiguous_open_error','cfg.unknown_errno=true'),
 ('missing_io_library','io=nil'),('payload_unavailable','cfg.payload_throw=true'),
 ('payload_wrong_type','cfg.payload_wrong_type=true'),('payload_wrong_length','cfg.payload_short=true'),
 ('payload_bad_magic','cfg.payload_bad_magic=true'),('rename_api_missing','os.rename=nil'),
 ('remove_api_missing','os.remove=nil')]:
 case(name,before,"assert(not loader.prepare());assert(not loader.load('rrc_install'));assert(writes==0 and loadcalls==0)")
for name,key in [
 ('staging_open_denied','stage_denied'),('write_returns_nil','write_nil'),('write_throws','write_throw'),
 ('short_write_reported_as_success','partial'),('close_returns_nil','close_nil'),('close_throws','close_throw'),
 ('staging_read_throws','stage_read_throw'),('staging_verification_mismatch','stage_corrupt'),
 ('rename_returns_nil','rename_fail'),('rename_throws','rename_throw')]:
 case(name,'cfg.'+key+'=true',"assert(not loader.prepare());assert(not loader.load('rrc_install'));assert(files[target]==nil and files[stage]==nil and loadcalls==0)")
case('read_failure_closes_handle','files[target]=payload;cfg.read_throw=true',
     "assert(not loader.prepare());assert(closes==2 and writes==0 and loadcalls==0)")
case('read_close_failure_refuses_load','files[target]=payload;cfg.read_close_nil=true',
     "assert(not loader.prepare());assert(writes==0 and loadcalls==0)")
case('retry_after_write_failure','cfg.write_nil=true',
     "assert(not loader.prepare());cfg.write_nil=false;assert(loader.prepare());assert(loader.load('rrc_install'))")
case('matching_target_appears_before_commit',"cfg.target_appears='same'",
     "assert(loader.prepare());assert(files[target]==payload and files[stage]==nil and renames==0)")
case('different_target_appears_before_commit',"cfg.target_appears='different'",
     "assert(not loader.prepare());assert(files[target]=='different' and files[stage]==nil and renames==0)")
case('failed_rename_but_matching_target_appears','cfg.rename_same=true',
     "assert(loader.prepare());assert(files[target]==payload and files[stage]==nil)")
case('failed_rename_and_different_target_appears','cfg.rename_different=true',
     "assert(not loader.prepare());assert(files[target]=='different' and files[stage]==nil)")
case('final_verification_mismatch','cfg.after_rename_bad=true',
     "assert(not loader.prepare());assert(not loader.load('rrc_install'));assert(loadcalls==0)")
for name,key in [('native_loader_returns_nil','load_nil'),('native_loader_throws','load_throw')]:
 case(name,'cfg.'+key+'=true',"assert(not loader.load('rrc_install'));assert(files[target]==payload and nativecalls==0)")
case('unexpected_export_rejected','',"assert(not loader.load('other'));assert(writes==0 and loadcalls==0)")
case('reverify_before_native_load','',
     "assert(loader.prepare());files[target]='changed';assert(not loader.load('rrc_install'));assert(loadcalls==0)")


report=dict(passed=True,tests=tests,test_count=len(tests),
    host_runtime=HOST_RUNTIME,mocked_file_io=True,mocked_native_loading=True,
    windows_rename_executed=False,native_dll_executed=False,game_executed=False)
write_report('loader_tests.json', report)
print(json.dumps(report,indent=2))
