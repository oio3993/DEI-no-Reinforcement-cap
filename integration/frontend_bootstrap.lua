
-- Reinforcement-cap replay frontend experiment.
do
    local ok, replay = pcall(require, "lua_scripts.rdp_rrc_replay_frontend_test01")
    if ok and type(replay) == "table" and type(replay.start) == "function" then
        pcall(replay.start, AddEventCallBack)
    end
end
