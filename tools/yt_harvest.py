"""Harvest a YouTube channel for research: transcripts + deduplicated key frames.

Usage: <venv-with-yt-dlp,imageio-ffmpeg,pillow>/bin/python -I tools/yt_harvest.py <out_dir> <url> [<url>...] [--subs-only ID,ID]
Per video writes <out_dir>/<id>/: meta.json, transcript.txt (timestamped, deduped auto-captions),
frames/<id>_<mmss>.jpg (scene changes + every 45 s, near-duplicates removed), frames.json. The video file is deleted
after extraction. Idempotent: skips videos whose frames.json (or transcript for subs-only) already exists."""
import json, os, re, subprocess, sys, pathlib, shutil
import yt_dlp, imageio_ffmpeg
from PIL import Image

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

def ahash(path, n=16):
    im = Image.open(path).convert("L").resize((n, n))
    px = list(im.getdata()); avg = sum(px) / len(px)
    return [p > avg for p in px]

def vtt_to_text(vtt):
    out, prev = [], ""
    ts = None
    for line in vtt.splitlines():
        m = re.match(r"(\d\d):(\d\d):(\d\d)\.\d+ -->", line)
        if m:
            ts = f"{int(m[1])*60+int(m[2]):02d}:{m[3]}"; continue
        t = re.sub(r"<[^>]+>", "", line).strip()
        if not t or t.startswith(("WEBVTT", "Kind:", "Language:")) or t == prev:
            continue
        out.append(f"[{ts}] {t}"); prev = t
    return "\n".join(out)

def harvest(out, url, subs_only=False):
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    vid = info["id"]; d = out / vid; d.mkdir(parents=True, exist_ok=True)
    done_marker = d / ("transcript.txt" if subs_only else "frames.json")
    if done_marker.exists():
        print("skip", vid); return
    meta = {k: info.get(k) for k in ("id", "title", "channel", "upload_date", "duration", "description", "webpage_url")}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    opts = {"quiet": True, "outtmpl": str(d / "v.%(ext)s"), "writeautomaticsub": True, "writesubtitles": True,
            "subtitleslangs": ["en", "en-orig", "en.*"], "subtitlesformat": "vtt", "ffmpeg_location": FFMPEG,
            "sleep_interval_subtitles": 8, "sleep_interval": 6, "max_sleep_interval": 15, "retries": 10, "extractor_retries": 5}
    if subs_only:
        opts["skip_download"] = True
    else:
        opts["format"] = "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/b"  # video only: frames need no audio
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    vtts = sorted(d.glob("v*.vtt"))
    if vtts:
        (d / "transcript.txt").write_text(vtt_to_text(vtts[0].read_text()))
        for v in vtts: v.unlink()
    else:
        (d / "transcript.txt").write_text("NO CAPTIONS AVAILABLE")
    if subs_only:
        print("subs", vid); return
    video = next((p for p in d.glob("v.*") if p.suffix in (".mp4", ".mkv", ".webm")), None)
    if not video:
        print("no video", vid); return
    fdir = d / "frames"; tmp = d / "tmp"; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    vf = "select='gt(scene,0.22)+isnan(prev_selected_t)+gte(t-prev_selected_t,45)',showinfo,scale=1280:-2"
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(video), "-vf", vf, "-vsync", "vfr", "-q:v", "3",
                        str(tmp / "f%05d.jpg")], capture_output=True, text=True)
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    files = sorted(tmp.glob("f*.jpg"))
    fdir.mkdir(exist_ok=True); kept, last = [], None
    for f, t in zip(files, times):
        h = ahash(f)
        if last is not None and sum(a != b for a, b in zip(h, last)) < 18:
            continue
        last = h
        name = f"{vid}_{int(t)//60:02d}{int(t)%60:02d}.jpg"
        shutil.move(str(f), fdir / name); kept.append({"file": name, "t": round(t, 1)})
    shutil.rmtree(tmp); video.unlink()
    (d / "frames.json").write_text(json.dumps(kept, indent=1))
    print("done", vid, len(kept), "frames", flush=True)

if __name__ == "__main__":
    args = sys.argv[1:]; out = pathlib.Path(args.pop(0))
    subs = set()
    if "--subs-only" in args:
        i = args.index("--subs-only"); subs = set(args[i + 1].split(",")); del args[i:i + 2]
    urls = []
    for a in args:
        if "/@" in a:
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as y:
                urls += [e["url"] for e in y.extract_info(a, download=False)["entries"]]
        else:
            urls.append(a)
    for u in urls:
        for attempt in range(3):
            try:
                harvest(out, u, subs_only=any(s in u for s in subs)); break
            except Exception as e:
                print("ERROR", u, f"attempt {attempt+1}", repr(e)[:300], flush=True)
                import time; time.sleep(90 * (attempt + 1))
