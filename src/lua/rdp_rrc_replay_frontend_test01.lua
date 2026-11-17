-- Frontend replay experiment using the unchanged reinforcement-cap DLL.
local M = {}
local loader
local loaded = {}
local last_registration
local last_state
local log_count = 0
local log_path = ".\\rdp_rrc_replay_frontend_test01.log"

local function log(event, detail)
    if log_count >= 256 then return end
    log_count = log_count + 1
    pcall(function()
        local stamp = os.date("%Y-%m-%d %H:%M:%S")
        local text = tostring(detail or ""):gsub("[\r\n\t]", " ")
        local file = io.open(log_path, "ab")
        if not file then return end
        pcall(file.write, file, stamp, " #", tostring(log_count), " ", event, " ", text, "\n")
        pcall(file.close, file)
    end)
end

local function get_loader()
    if not loader then
        loader = require "lua_scripts.rdp_reinforcement_cap_v01_loader"
    end
    return loader
end

local function native(symbol, reason)
    local ok, returned = pcall(function()
        local fn = loaded[symbol]
        if not fn then
            fn = get_loader().load(symbol)
            if type(fn) ~= "function" then return false end
            loaded[symbol] = fn
        end
        fn()
        return true
    end)
    -- The existing exports return zero Lua values. A returned call establishes
    -- invocation only. It does not report the engine patch's actual state.
    if ok and returned then
        log("native_call_returned", symbol .. " reason=" .. reason)
        return true
    end
    log("native_call_failed", symbol .. " reason=" .. reason .. " error=" .. tostring(returned))
    return false
end

local function request_install(state, reason)
    if native("rrc_install", reason) then state.install_requested = true end
end

local function request_release(state, reason, reset_frontend)
    if state.install_requested or reset_frontend then
        if not native("rrc_disable", reason) then return end
    end
    state.install_requested = false
    state.launch_requested = false
end

local function event_string(context)
    local ok, value = pcall(function() return context.string end)
    if ok and type(value) == "string" then return value end
    return ""
end

local function multiplayer_screen(name)
    return name == "multiplayer" or name == "mp_frame" or name:sub(1, 3) == "mp_"
end

local leave_buttons = {
    button_back = true,
    button_cancel = true,
    button_exit = true,
    button_home = true,
    button_quit = true,
    button_multiplayer = true,
    button_multiplayer_campaign = true,
    button_quick_battle = true,
}

function M.start(add_callback)
    if type(add_callback) ~= "function" then return false end
    if __lib_type_frontend == nil or __game_mode ~= __lib_type_frontend then return false end
    if last_registration == add_callback and last_state and last_state.ready then return true end
    if last_state then
        last_state.ready = false
        request_release(last_state, "frontend_registration_restart")
    end

    local state = {
        ready = false,
        frontend_alive = false,
        screen = "",
        replay_visit = false,
        install_requested = false,
        launch_requested = false,
    }
    last_registration = add_callback
    last_state = state

    local function register(name, callback)
        add_callback(name, function(context)
            if not state.ready then return end
            local ok, message = pcall(callback, context)
            if not ok then log("callback_error", name .. " " .. tostring(message)) end
        end)
    end

    local ok, message = pcall(function()
        register("UICreated", function(context)
            local name = event_string(context)
            log("UICreated", name)
            if name == "FrontEnd UI" then
                state.frontend_alive = true
                state.screen = ""
                state.replay_visit = false
                -- This also cleans up a previous replay when Lua modules were
                -- reloaded but the pinned native DLL retained its state.
                request_release(state, "frontend_root", true)
            elseif name == "Campaign UI" then
                state.frontend_alive = false
                state.replay_visit = false
                state.install_requested = false
                state.launch_requested = false
                log("campaign_handoff", "baseline campaign callbacks own subsequent requests")
            elseif name == "Battle UI" then
                state.frontend_alive = false
                state.replay_visit = false
            end
        end)

        register("FrontendScreenTransition", function(context)
            if not state.frontend_alive then return end
            local name = event_string(context)
            log("FrontendScreenTransition", name)
            state.screen = name
            if name == "sp_replays" then
                state.replay_visit = true
                state.launch_requested = false
                request_install(state, "replay_screen")
            elseif multiplayer_screen(name) then
                state.replay_visit = false
                request_release(state, "multiplayer_screen")
            elseif name ~= "" and not state.launch_requested then
                request_release(state, "other_frontend_screen")
            end
        end)

        register("ComponentLClickUp", function(context)
            local name = event_string(context)
            local replay_context = state.replay_visit or
                (state.frontend_alive and state.screen == "sp_replays")
            if replay_context and (name == "button_watch" or name == "button_fight") then
                state.launch_requested = true
                log("replay_launch_requested", name)
                request_install(state, name)
            elseif not state.frontend_alive then
                return
            elseif leave_buttons[name] then
                request_release(state, name)
                state.replay_visit = false
            elseif state.replay_visit and state.screen ~= "sp_replays" then
                request_release(state, "frontend_navigation_after_launch")
                state.replay_visit = false
            end
        end)

        register("UIDestroyed", function(context)
            local name = event_string(context)
            log("UIDestroyed", name)
            if name == "FrontEnd UI" then
                state.frontend_alive = false
                -- Preserve the request while entering the replay battle.
            end
        end)
    end)
    if not ok then
        log("registration_failed", message)
        return false
    end

    state.ready = true
    log("frontend_module_ready", "ReplayFrontendTest01 records call completion, engine byte verification unavailable")
    local prepared, result = pcall(function() return get_loader().prepare() end)
    log("loader_prepare", "returned=" .. tostring(prepared and result == true))
    return true
end

return M
