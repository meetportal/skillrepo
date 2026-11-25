import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run(script, *args, cwd=None):
    done = subprocess.run([sys.executable, "-I", "-B", str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    return done.returncode, done.stdout, done.stderr


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return path


def three(composition):
    return {"src": "3d/x.mov", "fit": "full", "three": {"composition": composition, "props": {}}}


def cues(duration, cuts, cover=()):
    words = [{"i": i, "text": f"w{i}", "start": round(0.1 + i * 0.3, 2), "end": round(0.35 + i * 0.3, 2)} for i in range(int((duration - 1) / 0.3))]
    return {"duration": duration, "fps": 25, "cuts": list(cuts), "words": words, "cover": [{"start": a, "end": b, "reason": "mock"} for a, b in cover]}


def findings(stdout):
    return [line for line in stdout.splitlines() if line[:4] in ("FAIL", "WARN")]


def test_audit_exact_findings(tmp):
    beats = [
        {"id": "hook", "component": "HookHeadline", "mode": "talk", "from": 0.0, "to": 1.2, "props": {}},
        {"id": "early3d", "component": "VideoInsert", "mode": "card", "from": 0.5, "to": 1.7, "props": three("DomainBurn3D")},
        {"id": "spamA", "component": "VideoInsert", "mode": "takeover", "from": 6.0, "to": 7.2, "props": three("EnvelopeToSpam3D")},
        {"id": "spamB", "component": "VideoInsert", "mode": "takeover", "from": 16.0, "to": 17.2, "props": three("EnvelopeToSpam3D")},
        {"id": "end", "component": "EndCard", "mode": "takeover", "from": 30.0, "to": 32.5, "props": {}},
    ]
    write(tmp / "beatmap.json", {"beats": beats})
    write(tmp / "cues.json", cues(30.0, range(2, 30, 2), cover=[(20.0, 20.4)]))
    code, out, _ = run("beat_audit.py", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json")
    lines = findings(out)
    assert code == 1, out
    assert len(lines) == 3, out
    assert any(l.startswith("FAIL 3d") and "early3d starts at 0.50s" in l for l in lines), out
    assert any(l.startswith("WARN 3d") and "spamA at 6.00s" in l and "spamB at 16.00s" in l for l in lines), out
    assert any(l.startswith("FAIL cover") and "20.00-20.40" in l for l in lines), out
    return out


def test_audit_clean_and_covered(tmp):
    beats = [
        {"id": "hook", "component": "HookHeadline", "mode": "talk", "from": 0.0, "to": 1.2, "props": {}},
        {"id": "spam", "component": "VideoInsert", "mode": "takeover", "from": 6.0, "to": 7.2, "props": three("EnvelopeToSpam3D")},
        {"id": "hide", "component": "TitleSlam", "mode": "hidden", "from": 19.9, "to": 20.6, "props": {}},
        {"id": "shield", "component": "VideoInsert", "mode": "card", "from": 22.0, "to": 23.4, "props": three("AuthShield3D")},
        {"id": "end", "component": "EndCard", "mode": "takeover", "from": 30.0, "to": 32.5, "props": {}},
    ]
    write(tmp / "beatmap.json", {"beats": beats})
    write(tmp / "cues.json", cues(30.0, range(2, 30, 2), cover=[(20.0, 20.4)]))
    code, out, _ = run("beat_audit.py", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json")
    assert code == 0 and not findings(out), out


def test_audit_cta_kicks_density(tmp):
    beats = [
        {"id": "hook", "component": "HookHeadline", "mode": "talk", "from": 0.0, "to": 1.2, "props": {}},
        {"id": "late3d", "component": "VideoInsert", "mode": "card", "from": 18.5, "to": 19.6, "props": three("AuthShield3D")},
        {"id": "long3d", "component": "VideoInsert", "mode": "takeover", "from": 5.0, "to": 6.8, "props": three("EnvelopeToSpam3D")},
        {"id": "logo", "component": "VideoInsert", "mode": "takeover", "from": 20.0, "to": 20.9, "props": three("LogoExtrude3D")},
        {"id": "end", "component": "EndCard", "mode": "takeover", "from": 20.9, "to": 23.0, "props": {}},
    ]
    camera = {"keys": [{"t": 0.0, "scale": 1.1, "tx": 0, "ty": 0, "ease": "cut"},
                       {"t": 9.0, "scale": 1.1, "tx": 0, "ty": 0, "ease": "kick", "px": 4.5, "frames": 7},
                       {"t": 10.5, "scale": 1.1, "tx": 0, "ty": 0, "ease": "kick", "px": 4.5, "frames": 7}]}
    write(tmp / "beatmap.json", {"beats": beats})
    write(tmp / "cues.json", cues(20.0, [3.5, 7.4, 11.0, 14.5, 17.0]))
    write(tmp / "camera.json", camera)
    code, out, _ = run("beat_audit.py", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json", "--camera", tmp / "camera.json", "--takeover-max", "2.0")
    lines = findings(out)
    assert code == 1, out
    assert any("late3d" in l and "CTA window 17.00-20.00" in l for l in lines), out
    assert not any("logo" in l and "CTA" in l for l in lines), out
    assert any(l.startswith("WARN kick") for l in lines), out
    assert any(l.startswith("WARN 3d") and "long3d lasts 1.80s" in l for l in lines), out
    assert any(l.startswith("WARN 3d") and "per 60s" in l for l in lines), out


def test_audit_median_gap(tmp):
    beats = [
        {"id": "hook", "component": "HookHeadline", "mode": "talk", "from": 0.0, "to": 1.0, "props": {}},
        {"id": "end", "component": "EndCard", "mode": "takeover", "from": 12.0, "to": 14.5, "props": {}},
    ]
    write(tmp / "beatmap.json", {"beats": beats})
    write(tmp / "cues.json", cues(12.0, [3.0, 6.0, 9.0]))
    code, out, _ = run("beat_audit.py", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json")
    lines = findings(out)
    assert code == 0 and len(lines) == 1 and lines[0].startswith("WARN rhythm") and "median gap" in lines[0], out


def test_beat_sheet(tmp):
    words = [{"text": f" w{i}" + ("." if i == 5 else ""), "startMs": 200 + i * 330, "endMs": 460 + i * 330, "timestampMs": 0, "confidence": None} for i in range(12)]
    write(tmp / "words.json", words)
    write(tmp / "beatmap.json", {"beats": [{"id": "hook", "from": 0.0, "to": 1.0}]})
    code, out, _ = run("beat_sheet.py", tmp / "words.json", "--beatmap", tmp / "beatmap.json")
    assert code == 0, out
    assert "words/s" in out.splitlines()[0], out
    assert "GAP" in out, out


def test_event_counts_agree(tmp):
    beats = [
        {"id": "hook", "component": "HookHeadline", "mode": "talk", "from": 0.0, "to": 1.2, "props": {}},
        {"id": "card", "component": "AuthTiles", "mode": "card", "from": 3.5, "to": 5.0, "props": {}},
        {"id": "end", "component": "EndCard", "mode": "takeover", "from": 9.0, "to": 11.0, "props": {}},
    ]
    write(tmp / "beatmap.json", {"beats": beats})
    write(tmp / "cues.json", cues(9.0, [3.0, 6.0]))
    words = [{"text": f" w{i}", "startMs": 200 + i * 300, "endMs": 450 + i * 300, "timestampMs": 0, "confidence": None} for i in range(26)]
    write(tmp / "words.json", words)
    _, audit_out, _ = run("beat_audit.py", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json")
    _, sheet_out, _ = run("beat_sheet.py", tmp / "words.json", "--beatmap", tmp / "beatmap.json", "--cues", tmp / "cues.json")
    audit_count = int(audit_out.split(" visual events")[0].rsplit(" ", 1)[1])
    sheet_count = int(sheet_out.split(" planned visual events")[0].rsplit(" ", 1)[1])
    assert audit_count == sheet_count == 6, (audit_out, sheet_out)


def test_doc_lint_help_failed(tmp):
    scripts = tmp / "skills" / "demo" / "scripts"
    write(scripts / "broken.py", "import module_that_is_not_installed\n")
    write(scripts / "fine.py", "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--out')\nparser.parse_args()\n")
    write(tmp / "skills" / "demo" / "SKILL.md", "```bash\npython scripts/broken.py --a --b --c\npython scripts/broken.py --d\nfine.py --out x --nope\n```\n")
    code, out, _ = run("doc_lint.py", "--root", tmp, "--python", sys.executable)
    lines = out.splitlines()
    assert code == 1, out
    assert len(lines) == 2, out
    assert lines[0].startswith("skills/demo/SKILL.md:2 help-failed demo/scripts/broken.py: exit 1: ModuleNotFoundError"), out
    assert lines[1] == "skills/demo/SKILL.md:4 --nope demo/scripts/fine.py", out


def test_status(tmp):
    work = tmp / "reel"
    for name in ("edl.json", "config/grade.json"):
        write(work / name, {})
    write(work / "aroll.mp4", "mock")
    write(work / "voice_cut.wav", "mock")
    write(work / "out/gfx.mp4", "mock")
    write(work / "out/gfx.mp4.aroll.md5", "0" * 32 + "  aroll.mp4\n")
    write(work / "props.json", {"fps": 25, "durationSec": 14.5})
    write(work / "beatmap.json", {"beats": [{"id": "spam3d", "component": "VideoInsert", "mode": "takeover", "from": 1.0, "to": 2.2,
                                            "props": {"src": "3d/spam3d.mov", "three": {"composition": "EnvelopeToSpam3D", "props": {"landAt": 1.8}}}}]})
    write(work / "3d/spam3d.mov", "mock")
    write(work / "3d/spam3d.json", {"beat": "spam3d", "composition": "EnvelopeToSpam3D", "from": 1.0, "to": 2.4, "fps": 25, "frames": 35, "hash": "abc"})
    old = 1_700_000_000
    for path in work.rglob("*"):
        if path.is_file():
            os.utime(path, (old, old))
    os.utime(work / "config/grade.json", (old + 10, old + 10))
    code, out, _ = run("status.py", "--work", work, "--json")
    assert code == 0, out
    data = json.loads(out)
    state = {row["output"]: row for row in data["outputs"]}
    assert state["aroll.mp4"]["state"] == "STALE" and "config/grade.json" in state["aroll.mp4"]["reason"], state["aroll.mp4"]
    assert state["out/gfx.mp4"]["state"] == "STALE", state["out/gfx.mp4"]
    assert state["3d/spam3d.json"]["state"] == "STALE" and "to 2.4" in state["3d/spam3d.json"]["reason"], state["3d/spam3d.json"]
    assert state["camera_plan.json"]["state"] == "MISSING"
    assert state["props.json"]["state"] == "STALE" and "upstream stale: aroll.mp4" in state["props.json"]["reason"], state["props.json"]
    assert data["next"]["step"] == "render_aroll", data["next"]

    write(work / "3d/spam3d.json", {"beat": "spam3d", "composition": "EnvelopeToSpam3D", "from": 1.0, "to": 2.2, "fps": 25, "frames": 30, "hash": "abc"})
    for path in work.rglob("*"):
        if path.is_file():
            os.utime(path, (old, old))
    code, out, _ = run("status.py", "--work", work, "--json")
    state = {row["output"]: row for row in json.loads(out)["outputs"]}
    three_state = state["3d/spam3d.json"]
    assert three_state["state"] in ("STALE", "UNKNOWN"), three_state
    assert three_state["state"] == "UNKNOWN" or "hash abc" in three_state["reason"], three_state
    assert state["3d/spam3d.mov"]["state"] == three_state["state"], state["3d/spam3d.mov"]


def main():
    tests = [test_audit_exact_findings, test_audit_clean_and_covered, test_audit_cta_kicks_density, test_audit_median_gap, test_beat_sheet, test_event_counts_agree,
             test_doc_lint_help_failed, test_status]
    failed = 0
    for test in tests:
        with tempfile.TemporaryDirectory() as folder:
            try:
                test(Path(folder))
                print(f"ok   {test.__name__}")
            except AssertionError as error:
                failed += 1
                print(f"FAIL {test.__name__}\n{error}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
