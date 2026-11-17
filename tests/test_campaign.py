"""Check all battle-type and main-force combinations using mocked game APIs."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from project import check_sources, write_report
from lua_host import run, HOST_RUNTIME
check_sources()

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src/lua' / 'rdp_reinforcement_cap_v01_campaign.lua').read_text(encoding='utf-8')
BATTLE_TYPES = (
    'land_normal', 'land_ambush', 'land_bridge', 'fort_standard', 'fort_sally',
    'fort_relief', 'settlement_standard', 'settlement_sally', 'settlement_relief',
    'settlement_unfortified', 'town_normal', 'naval_normal', 'naval_blockade',
    'naval_breakout', 'port_assault', 'battle_arena', 'unspecified', 'coastal_battle',
    'unfortified_port',
)
ROLES = {
    'human_attacker': dict(ah=True, dh=False, human_reinforcement=False),
    'human_defender': dict(ah=False, dh=True, human_reinforcement=False),
    'human_reinforces_ai_main_forces': dict(ah=False, dh=False, human_reinforcement=True),
    'ai_only': dict(ah=False, dh=False, human_reinforcement=False),
}
SETUP = r'''
local calls, events, loads = {}, {}, {}
local prepared, type_queries, faction_queries = 0, 0, 0
local cfg = {typ='land_normal', mp=false, ah=true, dh=false, att=true, def=true}
local loader = {
    prepare=function() prepared=prepared+1; return true end,
    load=function(symbol)
        assert(symbol=='rrc_install' or symbol=='rrc_disable')
        loads[symbol]=(loads[symbol] or 0)+1
        if cfg.load_throw then error('loader unavailable') end
        if cfg.load_nil then return nil end
        return function() calls[#calls+1]=symbol end
    end
}
local function force(human)
    return {faction=function()
        faction_queries=faction_queries+1
        return {is_human=function() return human end}
    end}
end
local pb = {
    is_active=function() return cfg.active end,
    battle_type=function()
        type_queries=type_queries+1
        if cfg.type_api_throw then error('type unavailable') end
        return cfg.typ
    end,
    has_attacker=function()
        if cfg.attacker_api_error then error('attacker unavailable') end
        return cfg.att
    end,
    has_defender=function() return cfg.def end,
    attacker=function() return force(cfg.ah) end,
    defender=function() return force(cfg.dh) end
}
local model = {is_multiplayer=function() return cfg.mp end,
               pending_battle=function() return pb end}
local scripting = {
    game_interface={model=function() return model end},
    AddEventCallBack=function(key, fn) assert(not events[key]); events[key]=fn end
}
require=function(name)
    if name=='lua_scripts.EpisodicScripting' then return scripting end
    assert(name=='lua_scripts.rdp_reinforcement_cap_v01_loader')
    return loader
end
'''
EXERCISE = r'''
assert(prepared==1)
local event_count=0
for _ in pairs(events) do event_count=event_count+1 end
assert(event_count==3)
events.PendingBattle({pending_battle=function() return pb end})
cfg.active=false
events.UICreated()
cfg.active=true
events.UICreated()
events.BattleCompleted()
assert(type_queries==0, 'Battle type must not restrict installation')
assert(faction_queries==0, 'Main-force faction must not restrict installation')
if not cfg.load_nil and not cfg.load_throw then
    for _, count in pairs(loads) do assert(count==1) end
end
'''
ENABLED = 'rrc_disable,rrc_install,rrc_disable,rrc_disable,rrc_disable,rrc_install,rrc_disable'
DISABLED = 'rrc_disable,rrc_disable,rrc_disable,rrc_disable,rrc_disable'
tests = []


def case(name, config, expected):
    values = []
    for key, value in config.items():
        literal = str(value).lower() if isinstance(value, bool) else json.dumps(value)
        values.append('cfg.' + key + '=' + literal)
    code = SETUP + '\n' + '\n'.join(values)
    code += '\nassert((function()\n' + SOURCE + '\nend)())\n' + EXERCISE
    code += '\nassert(table.concat(calls,",")==' + json.dumps(expected) + ')\n'
    run(name, code)
    tests.append(name)


for battle_type in BATTLE_TYPES:
    for role, config in ROLES.items():
        case(battle_type + '_' + role, dict(config, typ=battle_type), ENABLED)
case('future_battle_type', dict(typ='future_mod_battle', ah=False, dh=False), ENABLED)
case('empty_type', dict(typ='', ah=False, dh=False), ENABLED)
case('type_api_not_needed', dict(type_api_throw=True, ah=False, dh=False), ENABLED)
for role, config in ROLES.items():
    case('multiplayer_' + role, dict(config, mp=True), DISABLED)
case('missing_attacker', dict(att=False), DISABLED)
case('missing_defender', dict(**{'def': False}), DISABLED)
case('missing_both', dict(att=False, **{'def': False}), DISABLED)
case('attacker_api_error', dict(attacker_api_error=True), DISABLED)
case('loader_returns_nil', dict(load_nil=True), '')
case('loader_throws', dict(load_throw=True), '')

report = dict(passed=True, test_count=len(tests), tests=tests,
              known_battle_types=len(BATTLE_TYPES), main_force_scenarios=list(ROLES),
              all_battle_types_allowed=True, main_force_human_gate_removed=True,
              multiplayer_excluded=True, host_runtime=HOST_RUNTIME,
              native_exports_mocked=True, game_executed=False)
write_report('campaign_tests.json', report)
print(json.dumps({key: value for key, value in report.items() if key != 'tests'}, indent=2))
