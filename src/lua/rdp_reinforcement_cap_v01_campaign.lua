local loader = require "lua_scripts.rdp_reinforcement_cap_v01_loader"
-- Apply the reinforcement-cap patch to every single-player pending battle.
local scripting = require "lua_scripts.EpisodicScripting"
local loaded = {}

local function native(symbol)
    local ok, result = pcall(function()
        local fn = loaded[symbol]
        if not fn then
            fn = loader.load(symbol)
            if type(fn) ~= "function" then return false end
            loaded[symbol] = fn
        end
        fn()
        return true
    end)
    return ok and result
end

local function pending(context)
    pcall(function()
        native("rrc_disable")
        local model = scripting.game_interface:model()
        if model:is_multiplayer() then return end
        local pb = context:pending_battle()
        if not pb:has_attacker() or not pb:has_defender() then return end
        native("rrc_install")
    end)
end

scripting.AddEventCallBack("PendingBattle", pending)
scripting.AddEventCallBack("UICreated", function()
    pcall(function()
        native("rrc_disable")
        local pb = scripting.game_interface:model():pending_battle()
        if pb:is_active() then pending({pending_battle = function() return pb end}) end
    end)
end)
scripting.AddEventCallBack("BattleCompleted", function()
    native("rrc_disable")
end)
-- Prepare on campaign load; native calls retry if preparation fails.
loader.prepare()
return true
