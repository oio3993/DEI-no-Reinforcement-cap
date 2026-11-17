"""Check replay frontend lifecycle and campaign handoff using synthetic events."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from project import ROOT, check_sources, write_report
from lua_host import run, HOST_RUNTIME

check_sources()


def lua_string(text):
    delimiter = '='
    while ']' + delimiter + ']' in text:
        delimiter += '='
    return '[' + delimiter + '[' + text + ']' + delimiter + ']'


SYNTHETIC_FRONTEND = r'''
events = require "data.lua_scripts.events"
function AddEventCallBack(name, fn)
    events[name][#events[name] + 1] = fn
end
require "lua_scripts.frontend_hbs"
eh:add_listener("existing_click", "ComponentLClickUp", true, function() end, true)
eh:add_listener("existing_transition", "FrontendScreenTransition", true, function() end, true)
'''
EXERCISE = r'''
local count = 0

local function fixture(config)
    local cfg = config or {}
    local state = {calls = {}, events = {}, logs = {}, opened = 0, closed = 0, prepared = 0}
    local env = setmetatable({}, {__index = _G})
    env.__lib_type_frontend = 2
    env.__game_mode = cfg.mode or 2
    env.os = {date = function() return "mock-time" end}
    env.io = {open = function(path, mode)
        assert(path == ".\\rdp_rrc_replay_frontend_test01.log" and mode == "ab")
        if cfg.log_open_fail then return nil end
        state.opened = state.opened + 1
        return {
            write = function(self, ...)
                if cfg.log_write_fail then error("log write failure") end
                state.logs[#state.logs + 1] = table.concat({...})
                return self
            end,
            close = function()
                state.closed = state.closed + 1
                if cfg.log_close_fail then error("log close failure") end
                return true
            end,
        }
    end}
    local loader = {
        prepare = function()
            state.prepared = state.prepared + 1
            return not cfg.prepare_fail
        end,
        load = function(symbol)
            assert(symbol == "rrc_install" or symbol == "rrc_disable")
            if cfg.loader_throw then error("loader unavailable") end
            if cfg.load_nil then return nil end
            return function()
                if cfg.native_throw then error("native exception") end
                state.calls[#state.calls + 1] = symbol
            end
        end,
    }
    env.require = function(name)
        assert(name == "lua_scripts.rdp_reinforcement_cap_v01_loader", name)
        return loader
    end
    local function compile(text)
        local fn
        if setfenv then
            fn = assert(loadstring(text))
            setfenv(fn, env)
        else
            fn = assert(load(text, "frontend fixture", "t", env))
        end
        return fn
    end
    local module = compile(source)()
    local function register(name, fn)
        if cfg.registration_fail == name then error("registration unavailable") end
        state.events[name] = state.events[name] or {}
        table.insert(state.events[name], fn)
    end
    state.register = register
    state.module = module
    state.env = env
    state.compile = compile
    state.loader = loader
    state.cfg = cfg
    function state:emit(event, name)
        for _, fn in ipairs(self.events[event] or {}) do fn({string = name}) end
    end
    function state:root()
        assert(module.start(register))
        self:emit("UICreated", "FrontEnd UI")
    end
    function state:assert_calls(expected)
        assert(table.concat(self.calls, ",") == expected, table.concat(self.calls, ","))
    end
    return state
end

local function test(name, run)
    run()
    count = count + 1
    print("PASS " .. name)
end

test("cold_frontend_preparation", function()
    local s = fixture()
    assert(s.module.start(s.register))
    assert(s.prepared == 1)
    s:assert_calls("")
    s:emit("UICreated", "FrontEnd UI")
    s:assert_calls("rrc_disable")
end)
test("replay_screen_installs_without_selection_or_type", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:assert_calls("rrc_disable,rrc_install")
end)
for _, button in ipairs({"button_watch", "button_fight"}) do
    test("launch_" .. button, function()
        local s = fixture()
        s:root()
        s:emit("FrontendScreenTransition", "sp_replays")
        s:emit("ComponentLClickUp", button)
        s:emit("UIDestroyed", "FrontEnd UI")
        s:emit("FrontendScreenTransition", "menu")
        s:emit("UICreated", "Battle UI")
        s:assert_calls("rrc_disable,rrc_install,rrc_install")
        s:emit("UICreated", "FrontEnd UI")
        s:assert_calls("rrc_disable,rrc_install,rrc_install,rrc_disable")
    end)
end
test("screen_transition_after_launch_retains_request", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("ComponentLClickUp", "button_watch")
    s:emit("FrontendScreenTransition", "loading")
    s:assert_calls("rrc_disable,rrc_install,rrc_install")
end)
test("screen_transition_before_watch_is_retried", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("FrontendScreenTransition", "loading")
    s:emit("ComponentLClickUp", "button_watch")
    s:assert_calls("rrc_disable,rrc_install,rrc_disable,rrc_install")
end)
test("queued_watch_after_frontend_destruction_is_retried", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("FrontendScreenTransition", "loading")
    s:emit("UIDestroyed", "FrontEnd UI")
    s:emit("ComponentLClickUp", "button_watch")
    s:emit("UICreated", "Battle UI")
    s:emit("ComponentLClickUp", "button_watch")
    s:assert_calls("rrc_disable,rrc_install,rrc_disable,rrc_install")
end)
test("navigation_clears_queued_replay_context", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("FrontendScreenTransition", "sp_grand_campaign")
    s:emit("ComponentLClickUp", "another_button")
    s:emit("ComponentLClickUp", "button_watch")
    s:assert_calls("rrc_disable,rrc_install,rrc_disable")
end)
test("plain_navigation_releases", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("FrontendScreenTransition", "menu")
    s:assert_calls("rrc_disable,rrc_install,rrc_disable")
end)
for _, button in ipairs({"button_back", "button_cancel", "button_home", "button_quick_battle", "button_multiplayer"}) do
    test("navigation_" .. button, function()
        local s = fixture()
        s:root()
        s:emit("FrontendScreenTransition", "sp_replays")
        s:emit("ComponentLClickUp", button)
        s:assert_calls("rrc_disable,rrc_install,rrc_disable")
    end)
end
test("multiplayer_transition_releases_after_launch", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("ComponentLClickUp", "button_watch")
    s:emit("FrontendScreenTransition", "mp_games_list")
    s:assert_calls("rrc_disable,rrc_install,rrc_install,rrc_disable")
end)
test("unrelated_frontend_buttons_do_not_install", function()
    local s = fixture()
    s:root()
    s:emit("ComponentLClickUp", "button_watch")
    s:emit("FrontendScreenTransition", "sp_grand_campaign")
    s:assert_calls("rrc_disable")
end)
test("campaign_handoff_has_no_frontend_native_request", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    local before = #s.calls
    s:emit("UICreated", "Campaign UI")
    s:emit("FrontendScreenTransition", "sp_replays")
    s:emit("ComponentLClickUp", "button_watch")
    assert(#s.calls == before)
end)
for _, reverse in ipairs({false, true}) do
    test("baseline_campaign_handoff_" .. tostring(reverse), function()
        local s = fixture()
        s:root()
        s:emit("FrontendScreenTransition", "sp_replays")
        local pb = {is_active = function() return true end,
                    has_attacker = function() return true end,
                    has_defender = function() return true end}
        local scripting = {
            game_interface = {model = function()
                return {is_multiplayer = function() return false end,
                        pending_battle = function() return pb end}
            end},
            AddEventCallBack = s.register,
        }
        s.env.require = function(name)
            if name == "lua_scripts.EpisodicScripting" then return scripting end
            assert(name == "lua_scripts.rdp_reinforcement_cap_v01_loader")
            return s.loader
        end
        assert(s.compile(campaign)())
        s.env.__game_mode = 1
        if reverse then
            local callbacks = s.events.UICreated
            callbacks[1], callbacks[2] = callbacks[2], callbacks[1]
        end
        s:emit("UICreated", "Campaign UI")
        s:assert_calls("rrc_disable,rrc_install,rrc_disable,rrc_disable,rrc_install")
        local before = #s.calls
        s:emit("FrontendScreenTransition", "sp_replays")
        s:emit("ComponentLClickUp", "button_watch")
        assert(#s.calls == before)
        for _, fn in ipairs(s.events.PendingBattle) do fn({pending_battle = function() return pb end}) end
        s:emit("BattleCompleted", "")
        s:assert_calls("rrc_disable,rrc_install,rrc_disable,rrc_disable,rrc_install,rrc_disable,rrc_install,rrc_disable")
    end)
end
test("missing_and_nonfrontend_modes_are_inert", function()
    local s = fixture({mode = 1})
    assert(not s.module.start(s.register))
    s.env.__game_mode, s.env.__lib_type_frontend = nil, nil
    assert(not s.module.start(s.register))
    s:assert_calls("")
end)
test("idempotent_registration", function()
    local s = fixture()
    assert(s.module.start(s.register))
    assert(s.module.start(s.register))
    assert(s.prepared == 1)
    for _, callbacks in pairs(s.events) do assert(#callbacks == 1) end
end)
test("new_registration_retires_previous_callbacks", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    local newer = {}
    assert(s.module.start(function(name, fn) newer[name] = fn end))
    s:emit("FrontendScreenTransition", "sp_replays")
    s:assert_calls("rrc_disable,rrc_install,rrc_disable")
    newer.UICreated({string = "FrontEnd UI"})
    newer.FrontendScreenTransition({string = "sp_replays"})
    s:assert_calls("rrc_disable,rrc_install,rrc_disable,rrc_disable,rrc_install")
end)
for _, failure in ipairs({"load_nil", "loader_throw", "native_throw"}) do
    test("native_failure_" .. failure, function()
        local cfg = {[failure] = true}
        local s = fixture(cfg)
        s:root()
        s:emit("FrontendScreenTransition", "sp_replays")
        s:assert_calls("")
        cfg[failure] = false
        s:emit("ComponentLClickUp", "button_watch")
        s:assert_calls("rrc_install")
    end)
end
for _, failure in ipairs({"log_open_fail", "log_write_fail", "log_close_fail"}) do
    test("logging_failure_" .. failure, function()
        local s = fixture({[failure] = true})
        s:root()
        s:emit("FrontendScreenTransition", "sp_replays")
        s:assert_calls("rrc_disable,rrc_install")
        assert(s.opened == s.closed)
    end)
end
test("partial_registration_remains_inert", function()
    local s = fixture({registration_fail = "ComponentLClickUp"})
    assert(not s.module.start(s.register))
    s:emit("UICreated", "FrontEnd UI")
    s:emit("FrontendScreenTransition", "sp_replays")
    s:assert_calls("")
end)
test("malformed_context_is_contained", function()
    local s = fixture()
    s:root()
    for _, callbacks in pairs(s.events) do
        for _, fn in ipairs(callbacks) do fn(nil) end
    end
    s:assert_calls("rrc_disable")
end)
test("bounded_log", function()
    local s = fixture()
    s:root()
    for _ = 1, 1000 do s:emit("FrontendScreenTransition", "menu") end
    assert(s.opened <= 256)
end)
test("log_describes_native_call_completion", function()
    local s = fixture()
    s:root()
    s:emit("FrontendScreenTransition", "sp_replays")
    local text = table.concat(s.logs)
    assert(text:find("native_call_returned", 1, true))
    assert(not text:find("APPLIED", 1, true))
end)

local function bootstrap_fixture(failure)
    local s = fixture()
    s.env.events = {UICreated = {}, UIDestroyed = {}, ComponentLClickUp = {}, FrontendScreenTransition = {}}
    s.events = s.env.events
    s.env.require = function(name)
        if name == "data.lua_scripts.events" then return s.env.events end
        if name == "lua_scripts.rdp_reinforcement_cap_v01_loader" then return s.loader end
        if name == "lua_scripts.rdp_rrc_replay_frontend_test01" then
            if failure == "require" then error("module unavailable") end
            if failure == "start" then return {start = function() error("start unavailable") end} end
            return s.module
        end
        if name == "lua_scripts.frontend_hbs" then
            s.env.eh = {add_listener = function(self, _, event, _, callback)
                s.env.AddEventCallBack(event, callback)
            end}
        end
        return {}
    end
    s.compile(frontend .. bootstrap)()
    return s
end
test("synthetic_frontend_callbacks_survive_append", function()
    local s = bootstrap_fixture()
    assert(#s.events.ComponentLClickUp == 2)
    assert(#s.events.FrontendScreenTransition == 2)
    s:emit("UICreated", "FrontEnd UI")
    s:emit("FrontendScreenTransition", "sp_replays")
    s:assert_calls("rrc_disable,rrc_install")
end)
for _, failure in ipairs({"require", "start"}) do
    test("bootstrap_failure_preserves_base_" .. failure, function()
        local s = bootstrap_fixture(failure)
        assert(#s.events.ComponentLClickUp == 1)
        assert(#s.events.FrontendScreenTransition == 1)
        s:assert_calls("")
    end)
end
print("FRONTEND_TEST_COUNT=" .. count)

assert(count == 35)
'''
inputs = {
    'source': (ROOT/'src/lua/rdp_rrc_replay_frontend_test01.lua').read_text(encoding='utf-8'),
    'bootstrap': (ROOT/'integration/frontend_bootstrap.lua').read_text(encoding='utf-8'),
    'campaign': (ROOT/'src/lua/rdp_reinforcement_cap_v01_campaign.lua').read_text(encoding='utf-8'),
    'frontend': SYNTHETIC_FRONTEND,
}
prelude = '\n'.join('local ' + name + ' = ' + lua_string(value) for name, value in inputs.items())
run('replay_frontend_lifecycle', prelude + '\n' + EXERCISE)
report = dict(passed=True, test_count=35, synthetic_events=True, native_exports_mocked=True,
              host_runtime=HOST_RUNTIME, game_executed=False)
write_report('frontend_tests.json', report)
print(json.dumps(report, indent=2))
