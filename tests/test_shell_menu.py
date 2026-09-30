"""The app shell's window and menus (SPEC-shell 5, 14.1).

Two kinds of claim, as the repository's other shell tests make them: static
ones that read ``app/main.js`` and ``app/preload.js``, and ones that run the
real ``main.js`` under node against a stand-in for Electron whose menu,
windows and tracker child process are recorded. Skipped where node is not on
PATH (CI installs it).

This is the menu part (session S2). The renderer part (colour tokens, spacing,
the icons, the page's answers to the menu) is added on the renderer branch and
joined by S6.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import tracker.api as api

REPO = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _menu_words_in_main() -> dict[str, str]:
    block = read("app/main.js").split("const DEFAULT_MENU_WORDS = {", 1)[1].split("\n};", 1)[0]
    return dict(re.findall(r'^\s*(\w+): "([^"]*)",$', block, flags=re.M))


def _bar_ids_and_accelerators() -> tuple[list[str], list[str]]:
    """The menu bar's ids in order, and every accelerator, as main.js types them."""
    block = read("app/main.js").split("const BAR = [", 1)[1].split("\n];", 1)[0]
    ids = re.findall(r'\["([a-z_]+)"(?:, "[^"]+")?\]', block)
    return ids, re.findall(r'"((?:CmdOrCtrl\+[A-Za-z0-9]|F\d+)[^"]*)"', block)


def test_the_menus_default_words_are_the_apis_word_for_word():
    """main.js holds the menu's words so it is there from the first frame
    (SPEC-shell 5.1); the API's ``MENU`` is the source and they are equal."""
    assert _menu_words_in_main() == api.MENU
    assert api._vocab()["menu"] == api.MENU


def test_the_menu_has_no_reload_zoom_or_developer_tools():
    main_js = read("app/main.js")
    for role in ("reload", "forceReload", "toggleDevTools", "zoomIn", "zoomOut", "resetZoom",
                 "togglefullscreen", "viewMenu", "windowMenu", "appMenu"):
        assert not re.search(rf'role:\s*"{role}"', main_js, flags=re.I), role
    for accelerator in ("CmdOrCtrl+R", "CmdOrCtrl+Shift+R", "CmdOrCtrl+Shift+I", "F12", "Ctrl+R",
                        "CmdOrCtrl+Plus", "CmdOrCtrl+-", "CmdOrCtrl+0", "F11"):
        assert f'"{accelerator}"' not in main_js, accelerator
    assert "devTools: !app.isPackaged" in main_js
    # Edit is Windows' own by role; Exit is the quit role; nothing else is.
    assert re.findall(r'role:\s*"(\w+)"', main_js) == ["editMenu", "quit"]


def test_every_accelerator_is_named_once():
    ids, accelerators = _bar_ids_and_accelerators()
    assert sorted(accelerators) == sorted(
        ["CmdOrCtrl+N", "CmdOrCtrl+E", "CmdOrCtrl+1", "CmdOrCtrl+2", "CmdOrCtrl+3", "CmdOrCtrl+4",
         "CmdOrCtrl+F", "F5", "F9"])
    assert len(set(accelerators)) == len(accelerators)
    assert len(set(ids)) == len(ids)


def test_every_menu_id_is_in_the_apis_words_and_every_word_is_placed():
    """The template's ids are ``MENU`` keys, and each ``MENU`` key is a
    top-level label or an item of the bar or a right-click menu. (The page's
    half - it answers each id - is checked where ``shell.js`` is.)"""
    main_js = read("app/main.js")
    ids, _ = _bar_ids_and_accelerators()
    popups = read("app/main.js").split("const POPUPS = new Map([", 1)[1].split("\n]);", 1)[0]
    popup_ids = set(re.findall(r'"([a-z_]+)"', popups)) - {"household", "return", "file", "moved",
                                                          "request", "received"}
    labels = set(re.findall(r'\["(file|edit|client|view|tools|help)",', main_js))
    assert labels == {"file", "edit", "client", "view", "tools", "help"}
    placed = set(ids) | popup_ids | labels
    assert placed <= set(api.MENU), placed - set(api.MENU)
    assert set(api.MENU) <= placed, set(api.MENU) - placed
    # The six right-click menus of 5.2, by name.
    assert set(re.findall(r'^\s*\["([a-z]+)", \[', popups, flags=re.M)) == {
        "household", "return", "file", "moved", "request", "received"}


def test_the_preload_exposes_one_menu_channel():
    preload = read("app/preload.js")
    assert re.findall(r'ipcRenderer\.(\w+)\("menu"', preload) == ["on", "send"]
    assert "menu: {" in preload and "onCommand:" in preload and "send:" in preload
    # Nothing but the page's own message is passed across, and no command
    # reaches the tracker through it: it does not touch the tracker channels.
    menu = preload.split("menu: {", 1)[1].split("},", 1)[0]
    assert "tracker-cmd" not in menu and "invoke" not in menu


def test_the_window_colours_main_reads_are_the_pages():
    main_js = read("app/main.js")
    assert '"--window-dark" : "--window-light"' in main_js
    assert 'read("pilot-ui.css")' in main_js
    assert "backgroundColor: pageBackground()" in main_js
    assert "nativeTheme.themeSource = \"system\"" in main_js
    css = read("app/renderer/pilot-ui.css")
    if "--window-light" in css:     # the tokens arrive on the renderer branch (S3)
        light = re.search(r"--window-light:\s*(#[0-9a-fA-F]{3,8})", css)
        dark = re.search(r"--window-dark:\s*(#[0-9a-fA-F]{3,8})", css)
        assert light and dark
        assert re.search(r"--bg-page:\s*var\(--window-light\)", css)
        assert re.search(r"--bg-page:\s*var\(--window-dark\)", css)


# ------------------------------------------------ main.js run against a stand-in ----

#: The real main.js under node with Electron stood in for: the menu it sets and
#: the pop-ups it opens are recorded as plain data (a label, whether it is
#: enabled, its accelerator, its role), items are "clicked" by label, and the
#: tracker child process is a fake that answers ``list`` with a vocabulary. A
#: scenario is a list of steps; the harness prints what happened.
_HARNESS = r"""
const Module = require("module");
const EventEmitter = require("events");
const realFs = require("fs");
const [mainJs, scenarioJson] = process.argv.slice(2);
const sc = JSON.parse(scenarioJson);
// Off Windows the fallback is Electron's userData; "win32" is %LOCALAPPDATA%.
Object.defineProperty(process, "platform", { value: sc.platform || "linux" });
if (sc.localAppData !== undefined) process.env.LOCALAPPDATA = sc.localAppData;
process.resourcesPath = process.resourcesPath || "/resources";
const log = { menus: [], popups: [], sends: [], opened: [], revealed: [], answers: [], backgrounds: [], windowOptions: null };
let openHandler = null;
let menuHandler = null;
let trackerHandler = null;
let updated = null;
const theme = { shouldUseDarkColors: !!sc.dark, shouldUseHighContrastColors: !!sc.contrast,
                themeSource: "", on(name, fn) { if (name === "updated") updated = fn; } };
const snapshot = (items) => items.map((i) => ({
  label: i.label, type: i.type, role: i.role, enabled: i.enabled, accelerator: i.accelerator,
  submenu: i.submenu ? snapshot(i.submenu) : undefined }));
let live = { bar: null, popup: null };
const win = {
  isDestroyed: () => false,
  getContentBounds: () => ({ width: 1400, height: 900 }),
  setBackgroundColor: (c) => log.backgrounds.push(c),
  loadFile() {}, on() {}, isMinimized: () => false, focus() {},
  webContents: { setWindowOpenHandler() {}, on() {}, session: { flushStorageData() {} },
                 send: (channel, message) => log.sends.push({ channel, message }) },
};
class BrowserWindow {
  constructor(options) { log.windowOptions = options; return win; }
  static getAllWindows() { return [win]; }
}
const electron = {
  app: { isPackaged: !!sc.packaged, requestSingleInstanceLock: () => true, quit() {}, on() {},
         getPath: () => { if (!sc.userData) throw new Error("no such path"); return sc.userData; },
         whenReady: () => Promise.resolve() },
  BrowserWindow,
  Menu: {
    buildFromTemplate: (template) => ({ template, popup(options) {
      live.popup = template;
      log.popups.push({ items: snapshot(template), options });
    } }),
    setApplicationMenu(menu) {
      live.bar = menu.template;
      log.menus.push(snapshot(menu.template));
    },
  },
  ipcMain: { handle(name, fn) {
               if (name === "tracker-cmd") trackerHandler = fn;
               if (name === "open-path") openHandler = fn;
             },
             on(name, fn) { if (name === "menu") menuHandler = fn; } },
  nativeTheme: theme,
  shell: { openPath: async (p) => { log.opened.push(p); return ""; },
           showItemInFolder: (p) => { log.revealed.push(p); } },
  dialog: {},
};
const listReply = () => ({ vocab: { commands: ["list", "after-install"], menu: sc.vocabMenu,
                                    path_kinds: sc.pathKinds,
                                    shell: { error_log: sc.errorLog } }, paths: sc.paths });
const fakeSpawn = (cmd, args) => {
  const proc = new EventEmitter();
  proc.stdout = new EventEmitter();
  proc.stdout.setEncoding = () => {};
  proc.stderr = new EventEmitter();
  proc.stdin = { write() {}, end() {}, on() {} };
  proc.pid = 1;
  proc.kill = () => {};
  setImmediate(() => {
    if (args.includes("list")) proc.stdout.emit("data", JSON.stringify(listReply()) + "\n");
    proc.emit("close", 0);
  });
  return proc;
};
const load = Module._load;
Module._load = function (request, ...rest) {
  if (request === "electron") return electron;
  if (request === "child_process") return { spawn: fakeSpawn };
  if (request === "fs") {
    return { ...realFs, existsSync: () => true,
      readFileSync(p, ...more) {
        const base = String(p).split(/[\\/]/).pop();
        if (base in (sc.css || {})) {
          if (sc.css[base] === null) throw Object.assign(new Error("no such file"), { code: "ENOENT" });
          return sc.css[base];
        }
        return realFs.readFileSync(p, ...more);
      } };
  }
  return load.call(this, request, ...rest);
};
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const items = (list, label) => {
  for (const item of list) {
    if (item.label === label) return item;
    const inner = item.submenu && items(item.submenu, label);
    if (inner) return inner;
  }
  return null;
};
(async () => {
  require(mainJs);
  await wait(100);
  for (const step of sc.steps) {
    if (step.menu !== undefined) {
      menuHandler({ sender: step.stranger ? {} : win.webContents }, step.menu);
    } else if (step.tracker) {
      await trackerHandler({ sender: { isDestroyed: () => false, send() {} } }, step.tracker, undefined);
    } else if (step.open) {
      log.answers.push(await openHandler({}, ...step.open));
    } else if (step.clickBar) {
      const item = items(live.bar, step.clickBar);
      if (item && item.click) item.click();
    } else if (step.clickPopup) {
      const item = items(live.popup, step.clickPopup);
      if (item && item.click) item.click();
    } else if (step.theme) {
      Object.assign(theme, step.theme);
      updated();
    }
    await wait(60);
  }
  process.stdout.write(JSON.stringify(log));
})();
"""


def _node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it)")
    return node


def _run(tmp_path, steps, **scenario) -> dict:
    harness = tmp_path / "menu_harness.js"
    harness.write_text(_HARNESS, encoding="utf-8", newline="\n")
    done = subprocess.run(
        [_node(), str(harness), str(REPO / "app" / "main.js"),
         json.dumps({"steps": steps, **scenario})],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _word(key: str) -> str:
    return api.MENU[key]


def _flat(menu: list[dict]) -> dict[str, dict]:
    found = {}
    for top in menu:
        for item in top.get("submenu") or []:
            if item.get("label"):
                found[item["label"]] = item
    return found


def test_the_menu_is_set_before_the_first_frame_from_the_apis_words_in_both_builds(tmp_path):
    for packaged in (False, True):
        ran = _run(tmp_path, [], packaged=packaged)
        [menu] = ran["menus"]
        assert [top["label"] for top in menu] == [
            _word(k) for k in ("file", "edit", "client", "view", "tools", "help")]
        assert menu[1]["role"] == "editMenu"
        file_items = [i.get("label") or "-" for i in menu[0]["submenu"]]
        assert file_items == [_word("new_household"), _word("change_root"), _word("open_root"), "-",
                              _word("exit")]
        exit_item = _flat(menu)[_word("exit")]
        assert exit_item["role"] == "quit" and not exit_item.get("accelerator")


def test_the_template_carries_the_accelerators_of_the_spec_and_no_others(tmp_path):
    [menu] = _run(tmp_path, [])["menus"]
    found = {label: item["accelerator"] for label, item in _flat(menu).items()
             if item.get("accelerator")}
    assert found == {
        _word("new_household"): "CmdOrCtrl+N", _word("edit_list"): "CmdOrCtrl+E",
        _word("overview"): "CmdOrCtrl+1", _word("needs_review"): "CmdOrCtrl+2",
        _word("reminders"): "CmdOrCtrl+3", _word("clients"): "CmdOrCtrl+4",
        _word("find"): "CmdOrCtrl+F", _word("refresh"): "F5", _word("sort_now"): "F9"}


def test_only_the_items_that_need_nothing_are_enabled_until_the_page_speaks(tmp_path):
    [menu] = _run(tmp_path, [])["menus"]
    enabled = {label for label, item in _flat(menu).items() if item.get("enabled")}
    # Exit is a role: Electron enables it itself.
    assert enabled == {_word(k) for k in ("change_root", "refresh", "tour", "safeguards", "terms",
                                          "error_log", "about")}


def test_the_page_enables_the_items_whose_rule_holds_and_the_menu_follows(tmp_path):
    ran = _run(tmp_path, [{"menu": {"enable": ["new_household", "overview", "sort_now", "no_such_id"]}}])
    now = _flat(ran["menus"][-1])
    assert now[_word("new_household")]["enabled"] and now[_word("overview")]["enabled"]
    assert now[_word("sort_now")]["enabled"]
    assert not now[_word("edit_list")]["enabled"] and not now[_word("stop_sorting")]["enabled"]
    # The same list again rebuilds nothing.
    again = _run(tmp_path, [{"menu": {"enable": ["overview"]}}, {"menu": {"enable": ["overview"]}}])
    assert len(again["menus"]) == 2


def test_the_menu_channel_drops_what_it_does_not_know(tmp_path):
    steps = [
        {"menu": {"enable": ["overview", 7, None, "constructor", "__proto__", "check"]}},   # ids not in the bar
        {"menu": {"enable": ["overview"]}},   # the same list once the strays are dropped: no rebuild
        {"menu": {"enable": "overview"}},                    # not an array
        {"menu": "overview"}, {"menu": None}, {"menu": [["enable"]]},
        {"menu": {"popup": "nowhere", "enable": [], "token": "row"}},          # not one of the six
        {"menu": {"popup": "constructor", "enable": [], "token": "row"}},
        {"menu": {"popup": ["household"], "token": "row"}},
        {"menu": {"popup": "household", "enable": [], "token": "t" * 65}},     # a long token
        {"menu": {"popup": "household", "enable": [], "token": 5}},
        {"menu": {"popup": "household", "enable": ["overview"]}, "stranger": True},   # not our window
    ]
    ran = _run(tmp_path, steps)
    assert ran["popups"] == [] and ran["sends"] == []
    # Only the one known bar id was taken, from the first message; the unknown ids were dropped,
    # or the second message, naming the same one id, would have rebuilt the menu.
    assert len(ran["menus"]) == 2
    now = _flat(ran["menus"][-1])
    assert now[_word("overview")]["enabled"] and not now[_word("clients")]["enabled"]
    assert _word("check") not in now


def test_a_right_click_menu_is_native_holds_only_its_templates_items_and_echoes_the_token(tmp_path):
    steps = [
        {"menu": {"popup": "household", "token": "row-7", "x": 10.4, "y": 20,
                  "enable": ["edit_household", "open_inbox", "edit_list", "no_such_id"]}},
        {"clickPopup": _word("edit_household")},
        {"clickPopup": _word("add_return")},     # disabled by the page's list: still an item
        {"menu": {"popup": "received", "enable": ["unfile"], "x": 5000, "y": 5}},
        {"menu": {"popup": "return", "enable": [], "token": "r" * 64}},
    ]
    ran = _run(tmp_path, steps)
    household, received, ret = ran["popups"]
    assert [i.get("label") or "-" for i in household["items"]] == [
        _word("edit_household"), _word("add_return"), _word("roll_forward"), _word("mark_shared"), "-",
        _word("open_client_folder"), _word("open_inbox")]
    assert {i["label"]: i["enabled"] for i in household["items"] if i.get("label")} == {
        _word("edit_household"): True, _word("add_return"): False, _word("roll_forward"): False,
        _word("mark_shared"): False, _word("open_client_folder"): False, _word("open_inbox"): True}
    assert household["options"]["x"] == 10 and household["options"]["y"] == 20
    # A click sends {id, token} to the window that asked; a click on a greyed item does the same
    # in this stand-in (Electron itself never delivers one).
    assert ran["sends"][0] == {"channel": "menu", "message": {"id": "edit_household", "token": "row-7"}}
    # An x outside the window opens the menu at the pointer.
    assert "x" not in received["options"] and "y" not in received["options"]
    assert [i["label"] for i in received["items"]] == [_word("unfile"), _word("mark_missing")]
    assert [i["label"] for i in ret["items"] if i.get("label")] == [
        _word("edit_list"), _word("draft_reminder"), _word("open_working"),
        _word("open_client_folder"), _word("open_inbox")]


def test_the_six_right_click_menus_hold_the_items_of_the_spec(tmp_path):
    names = {
        "household": ["edit_household", "add_return", "roll_forward", "mark_shared", "-",
                      "open_client_folder", "open_inbox"],
        "return": ["edit_list", "draft_reminder", "-", "open_working", "open_client_folder", "open_inbox"],
        "file": ["check", "not_requested", "another_return"],
        "moved": ["check", "put_back", "keep_here"],
        "request": ["edit_request"],
        "received": ["unfile", "mark_missing"],
    }
    ran = _run(tmp_path, [{"menu": {"popup": name, "enable": [], "token": name}} for name in names])
    for popup, (name, ids) in zip(ran["popups"], names.items(), strict=True):
        assert [i.get("label") or "-" for i in popup["items"]] == [
            "-" if i == "-" else _word(i) for i in ids], name


def test_a_chosen_bar_item_is_sent_to_the_page_except_exit_and_the_error_log(tmp_path):
    ran = _run(tmp_path, [{"menu": {"enable": ["find"]}}, {"clickBar": _word("find")},
                          {"clickBar": _word("tour")}, {"clickBar": _word("exit")}])
    assert ran["sends"] == [{"channel": "menu", "message": {"id": "find", "token": ""}},
                            {"channel": "menu", "message": {"id": "tour", "token": ""}}]


def _learn(errorlog, **scenario):
    return [{"tracker": ["list"]}, {"clickBar": _word("error_log")}], {"errorLog": str(errorlog), **scenario}


def test_open_error_log_opens_the_named_file_and_says_so_when_there_is_none(tmp_path):
    log = tmp_path / "tracker-errors.log"
    log.write_text("kept\n", encoding="utf-8")
    steps, scenario = _learn(log)
    ran = _run(tmp_path, steps, **scenario)
    assert ran["opened"] == [str(log)] and ran["sends"] == []
    # Not yet named by the API: nothing is opened, the page is told.
    ran = _run(tmp_path, [{"clickBar": _word("error_log")}])
    assert ran["opened"] == []
    assert ran["sends"] == [{"channel": "menu", "message": {"id": "error_log", "missing": True}}]
    # Named, but not there.
    steps, scenario = _learn(tmp_path / "gone.log")
    ran = _run(tmp_path, steps, **scenario)
    assert ran["opened"] == []
    assert ran["sends"] == [{"channel": "menu", "message": {"id": "error_log", "missing": True}}]
    # Named, and a folder is not a file.
    steps, scenario = _learn(tmp_path)
    ran = _run(tmp_path, steps, **scenario)
    assert ran["opened"] == [] and ran["sends"][0]["message"]["missing"] is True


def test_open_error_log_falls_back_to_the_shells_own_log_when_the_api_named_none(tmp_path):
    """Jason, 2026-09-29: with no data folder the failure is saved in the
    fallback log (error.log in the per-user folder), and Open error log opens it
    through the same lstat check; the named log wins when there is one."""
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    fallback = userdata / "error.log"
    steps = [{"clickBar": _word("error_log")}]
    # Nothing named, nothing saved yet: the page is told.
    ran = _run(tmp_path, steps, userData=str(userdata))
    assert ran["opened"] == [] and ran["sends"][0]["message"] == {"id": "error_log", "missing": True}
    # Saved: it opens.
    fallback.write_text("kept\n", encoding="utf-8")
    ran = _run(tmp_path, steps, userData=str(userdata))
    assert ran["opened"] == [str(fallback)] and ran["sends"] == []
    # A named log is the one opened, never the fallback.
    named = tmp_path / "tracker-errors.log"
    named.write_text("named\n", encoding="utf-8")
    learn_steps, scenario = _learn(named, userData=str(userdata))
    ran = _run(tmp_path, learn_steps, **scenario)
    assert ran["opened"] == [str(named)]


def test_open_error_log_opens_the_local_non_roaming_fallback_on_windows(tmp_path):
    """Jason's ruling (2026-09-29): on Windows the fallback is
    %LOCALAPPDATA%\\Tax Document Tracker Pilot\\error.log, never userData
    (which is under the roaming %APPDATA%)."""
    local = tmp_path / "local"
    fallback = local / "Tax Document Tracker Pilot" / "error.log"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("kept\n", encoding="utf-8")
    roaming = tmp_path / "roaming"
    roaming.mkdir()
    (roaming / "error.log").write_text("wrong place\n", encoding="utf-8")
    steps = [{"clickBar": _word("error_log")}]
    ran = _run(tmp_path, steps, platform="win32", localAppData=str(local), userData=str(roaming))
    assert ran["opened"] == [str(fallback)] and ran["sends"] == []


def test_open_error_log_refuses_a_fallback_that_is_a_link_or_a_folder(tmp_path):
    userdata = tmp_path / "userdata"
    (userdata / "error.log").mkdir(parents=True)          # a folder is not a file
    steps = [{"clickBar": _word("error_log")}]
    ran = _run(tmp_path, steps, userData=str(userdata))
    assert ran["opened"] == [] and ran["sends"][0]["message"]["missing"] is True
    # A link is not a file either: the fallback is never opened through one.
    linked = tmp_path / "linked"
    linked.mkdir()
    real = tmp_path / "real.log"
    real.write_text("x\n", encoding="utf-8")
    try:
        (linked / "error.log").symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("this machine cannot make a symbolic link")
    ran = _run(tmp_path, steps, userData=str(linked))
    assert ran["opened"] == [] and ran["sends"][0]["message"]["missing"] is True


def test_open_error_log_refuses_a_symbolic_link(tmp_path):
    real = tmp_path / "real.log"
    real.write_text("x\n", encoding="utf-8")
    link = tmp_path / "linked.log"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("this machine cannot make a symbolic link")
    steps, scenario = _learn(link)
    ran = _run(tmp_path, steps, **scenario)
    assert ran["opened"] == []
    assert ran["sends"] == [{"channel": "menu", "message": {"id": "error_log", "missing": True}}]


def test_a_word_from_the_api_rebuilds_the_menu_only_when_it_differs(tmp_path):
    same = _run(tmp_path, [{"tracker": ["list"]}], vocabMenu=dict(api.MENU))
    assert len(same["menus"]) == 1
    changed = {**api.MENU, "sort_now": "Sort here", "file": "&Files", "not_a_key": "x", "find": 5}
    ran = _run(tmp_path, [{"tracker": ["list"]}], vocabMenu=changed)
    assert len(ran["menus"]) == 2
    menu = ran["menus"][-1]
    assert menu[0]["label"] == "&Files"
    now = _flat(menu)
    assert "Sort here" in now and _word("sort_now") not in now
    assert _word("find") in now                       # a word that is not a string is ignored


def test_the_window_paints_the_pages_colour_for_the_systems_theme(tmp_path):
    css = {"pilot-ui.css": ":root { --window-light: #ffffff; }\n:root { --window-dark: #1b1e24; }\n",
           "style.css": ":root { --bg: #f5f5f5; }"}
    assert _run(tmp_path, [], css=css)["windowOptions"].get("backgroundColor") == "#ffffff"
    assert _run(tmp_path, [], css=css, dark=True)["windowOptions"].get("backgroundColor") == "#1b1e24"
    # A contrast theme paints its own.
    assert _run(tmp_path, [], css=css, contrast=True)["windowOptions"].get("backgroundColor") is None


def test_the_window_colour_is_read_defensively(tmp_path):
    # Without the names (the stylesheet before they exist) or without the file: never a thrown error.
    older = {"pilot-ui.css": ":root { --other: #123456; }", "style.css": ":root { --bg: #f5f5f5; }"}
    assert _run(tmp_path, [], css=older)["windowOptions"].get("backgroundColor") == "#f5f5f5"
    none = {"pilot-ui.css": None, "style.css": None}
    ran = _run(tmp_path, [], css=none)
    assert ran["windowOptions"].get("backgroundColor") is None and len(ran["menus"]) == 1


def test_a_switch_between_light_and_dark_sets_the_window_colour_again(tmp_path):
    css = {"pilot-ui.css": ":root { --window-light: #ffffff; --window-dark: #1b1e24; }"}
    ran = _run(tmp_path, [{"theme": {"shouldUseDarkColors": True}},
                          {"theme": {"shouldUseDarkColors": False}},
                          {"theme": {"shouldUseHighContrastColors": True}}], css=css)
    assert ran["backgrounds"] == ["#1b1e24", "#ffffff"]      # a contrast theme paints its own


# ------------------------------- a file name on the page is a live link (S8a) ----

# The kinds as the API reports them: only a marked review copy is "file" (it
# opens, decision 190); a filed, moved or shown working copy is "reveal".
_KINDS = {"engagement": "folder", "review_copy": "file", "filed_copy": "reveal",
          "moved_copy": "reveal", "shown_copy": "reveal"}
NOT_REPORTED = "That path is not one the tracker reported; nothing was opened."
NOT_OPENED = "Not Opened; It Has Changed"


def _reveal_scenario(tmp_path):
    working = tmp_path / "Prepared"
    working.mkdir()
    copy = working / "A01 - W-2 - TY2025.pdf"
    copy.write_bytes(b"%PDF-1.4\n")
    moved = working / "wandered.pdf"
    moved.write_bytes(b"%PDF-1.4\n")
    paths = {"engagement": str(tmp_path), "filed_copy K1 0": str(copy), "moved_copy K2": str(moved)}
    return copy, moved, {"pathKinds": _KINDS, "paths": paths}


def test_a_moved_workbook_is_shown_with_reveal_and_refused_without_it(tmp_path):
    """F1: a moved-by-hand .xlsm carries no Protected View mark, so a plain
    open (the default program) is refused; only reveal shows it."""
    _copy, _moved, scenario = _reveal_scenario(tmp_path)
    macro = tmp_path / "Prepared" / "budget.xlsm"
    macro.write_bytes(b"PK\x03\x04")
    scenario["paths"]["moved_copy K3"] = str(macro)
    plain = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(macro)]}], **scenario)
    assert plain["opened"] == [] and plain["revealed"] == []
    assert plain["answers"] == [NOT_OPENED]
    shown = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(macro), "reveal"]}], **scenario)
    assert shown["revealed"] == [str(macro)] and shown["opened"] == [] and shown["answers"] == [""]


def test_a_filed_copy_and_a_shown_copy_are_reveal_only_and_a_review_copy_still_opens(tmp_path):
    copy, _moved, scenario = _reveal_scenario(tmp_path)
    parked = tmp_path / "Prepared" / "parked.docx"
    parked.write_bytes(b"PK")
    review = tmp_path / "Prepared" / "review.pdf"
    review.write_bytes(b"%PDF-1.4\n")
    scenario["paths"]["shown_copy K4"] = str(parked)
    scenario["paths"]["review_copy K5"] = str(review)
    ran = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(copy)]}, {"open": [str(parked)]},
                          {"open": [str(parked), "reveal"]}, {"open": [str(review)]}], **scenario)
    assert ran["opened"] == [str(review)], "only a marked review copy opens (decision 190)"
    assert ran["revealed"] == [str(parked)]
    assert ran["answers"] == [NOT_OPENED, NOT_OPENED, "", ""]


def test_reveal_shows_a_reported_file_in_file_explorer_and_a_plain_open_still_opens_it(tmp_path):
    copy, moved, scenario = _reveal_scenario(tmp_path)
    ran = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(copy), "reveal"]},
                          {"open": [str(moved), "reveal"]}, {"open": [str(copy)]}], **scenario)
    assert ran["revealed"] == [str(copy), str(moved)], "the row's kind came from the word before the space"
    assert ran["opened"] == [], "a filed copy is reveal-only: the plain open is refused"
    assert ran["answers"] == ["", "", NOT_OPENED]


def test_reveal_of_a_path_the_api_did_not_report_is_refused(tmp_path):
    copy, _moved, scenario = _reveal_scenario(tmp_path)
    stranger = tmp_path / "not-reported.pdf"
    stranger.write_bytes(b"x")
    steps = [{"tracker": ["list"]}]
    steps += [{"open": [p, "reveal"]} for p in (str(stranger), str(tmp_path / ".." / "x"), "", None, 7)]
    ran = _run(tmp_path, steps, **scenario)
    assert ran["revealed"] == [] and ran["opened"] == []
    # The exact sentence: it is the allow-list's own (the kind check says something else).
    assert ran["answers"] == [NOT_REPORTED] * 5
    # Before the API has reported anything, even the file that would be reported is refused.
    early = _run(tmp_path, [{"open": [str(copy), "reveal"]}], **scenario)
    assert early["revealed"] == [] and early["answers"] == [NOT_REPORTED]


def test_a_reported_key_whose_word_has_no_kind_is_refused_by_the_kind_check_alone(tmp_path):
    """The second lock, pinned separately: the path is on the allow-list (the
    API reported it) but its word names no kind, so it fails closed - with the
    kind check's sentence, not the allow-list's."""
    _copy, _moved, scenario = _reveal_scenario(tmp_path)
    odd = tmp_path / "Prepared" / "odd.pdf"
    odd.write_bytes(b"x")
    scenario["paths"]["mystery K9"] = str(odd)
    ran = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(odd), "reveal"]}, {"open": [str(odd)]}],
               **scenario)
    assert ran["opened"] == [] and ran["revealed"] == []
    assert ran["answers"] == [NOT_OPENED, NOT_OPENED] and NOT_OPENED != NOT_REPORTED


def test_reveal_is_refused_when_the_file_is_no_longer_a_file_or_is_a_link(tmp_path):
    copy, moved, scenario = _reveal_scenario(tmp_path)
    copy.unlink()
    copy.mkdir()                                   # a folder where the file was
    moved.unlink()
    moved.symlink_to(tmp_path / "Prepared" / "elsewhere.pdf")
    ran = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(copy), "reveal"]},
                          {"open": [str(moved), "reveal"]}], **scenario)
    assert ran["revealed"] == [] and ran["opened"] == []
    assert all(ran["answers"])


def test_a_word_that_is_not_reveal_opens_the_default_way_and_a_folder_is_never_revealed(tmp_path):
    copy, _moved, scenario = _reveal_scenario(tmp_path)
    ran = _run(tmp_path, [{"tracker": ["list"]}, {"open": [str(copy), "anything"]},
                          {"open": [str(tmp_path), "reveal"]}], **scenario)
    assert ran["opened"] == [str(tmp_path)] and ran["revealed"] == []
    assert ran["answers"] == [NOT_OPENED, ""], "a reveal-only copy is not opened by any other word"


def test_the_preload_passes_the_optional_second_argument_on_the_same_open_and_adds_no_channel():
    preload = read("app/preload.js")
    assert 'open: (p, how) => ipcRenderer.invoke("open-path", p, how),' in preload
    assert re.findall(r'ipcRenderer\.(?:invoke|send|on)\("([a-z-]+)"', preload) == [
        "tracker-cmd", "open-path", "pick-folder", "log-error", "tracker-progress", "after-install-done",
        "menu", "menu"]
    main_js = read("app/main.js")
    assert main_js.count('ipcMain.handle("open-path"') == 1
    assert main_js.count("shell.showItemInFolder(") == 1 and main_js.count("shell.openPath(") == 1


def test_the_menus_default_words_carry_the_capital_the_section_is_written_with():
    assert _menu_words_in_main()["needs_review"] == "Needs Review"
