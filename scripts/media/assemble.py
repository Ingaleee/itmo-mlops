"""Assemble captioned screen walkthroughs and validate the published media.

Screenshots are captured through the browser UI. This script encodes those actual
captures without altering their displayed results. Requires Pillow and FFmpeg
(or imageio-ffmpeg); these are documentation tools, not runtime dependencies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs/media"
WALKTHROUGHS = [
    {"lab": "lab1", "slug": "api-demo", "title": "Iris: readiness, три класса и валидация",
     "pages": ["health", "setosa", "versicolor", "virginica", "invalid-size", "invalid-type"]},
    {"lab": "lab1", "slug": "delivery-demo", "title": "Iris: модель, тесты, pipeline и Kubernetes",
     "pages": ["model", "tests", "pipeline", "kubernetes", "security", "registry"]},
    {"lab": "lab2", "slug": "retrieval-demo", "title": "Search: индекс, поиск, рекомендации и метрики",
     "pages": ["ready", "search", "recommendations", "invalid", "metrics", "reproducibility"]},
    {"lab": "lab2", "slug": "release-demo", "title": "Search: quality gate, promotion и rollback",
     "pages": ["tests", "quality-normal", "quality-reverse", "kubernetes", "promotion", "rollback"]},
]


def main():
    from PIL import Image
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--duration", type=float, default=5,
                        help="Seconds per captured evidence screen")
    parser.add_argument("--video-frames", type=Path,
                        help="Optional directory with uniform viewport captures, one subdirectory per lab")
    args = parser.parse_args()
    executable = str(args.ffmpeg) if args.ffmpeg else shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    pages = json.loads((MEDIA / "sources/pages.json").read_text(encoding="utf-8"))
    manifest = {"format": "Browser screenshots and screen walkthroughs", "images": [], "videos": []}
    for page in pages:
        path = MEDIA / page["lab"] / (page["slug"] + ".jpg")
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            width, height = im.size
        manifest["images"].append({"file": path.relative_to(MEDIA).as_posix(), "title": page["title"],
                                   "width": width, "height": height, "origin": page["origin"],
                                   "sources": ["sources/" + f for f in page["sources"]],
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for file, title, origin, sources in (
        ("lab1/openapi.jpg", "Iris OpenAPI", "Swagger UI локального Iris API", ["sources/iris-openapi.json"]),
        ("lab2/openapi.jpg", "Search OpenAPI", "Swagger UI локального Search API", ["sources/search-openapi.json"]),
        ("shared/github-actions.jpg", "GitHub Actions", "GitHub · run #37905104404", ["sources/teaching-pipeline.json"])):
        path = MEDIA / file
        with Image.open(path) as im:
            width, height = im.size
            im.verify()
        manifest["images"].append({"file": file, "title": title, "origin": origin, "sources": sources,
                                   "width": width, "height": height,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    scratch = ROOT / ".course-access/media-encoding"
    scratch.mkdir(parents=True, exist_ok=True)
    for video in WALKTHROUGHS:
        frame_root = (args.video_frames or MEDIA).resolve()
        files = [frame_root / video["lab"] / (name + ".jpg") for name in video["pages"]]
        frames = []
        for path in files:
            with Image.open(path) as im:
                frame = im.convert("RGB")
                frame.thumbnail((960, 960))
                frames.append(frame.quantize(colors=128))
        gif = MEDIA / video["lab"] / (video["slug"] + ".gif")
        frames[0].save(gif, save_all=True, append_images=frames[1:], duration=int(args.duration*1000),
                       loop=0, optimize=True, disposal=2)
        # ffmpeg concat input uses forward slashes and quoted paths on Windows.
        listing = scratch / (video["lab"] + "-" + video["slug"] + ".txt")
        listing.write_text("".join(f"file '{p.as_posix()}'\nduration {args.duration}\n" for p in files)
                           + f"file '{files[-1].as_posix()}'\n", encoding="utf-8")
        mp4 = MEDIA / video["lab"] / (video["slug"] + ".mp4")
        subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2,fps=12",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", "-t", str(len(files)*args.duration), str(mp4)], check=True, timeout=120)
        # Decode the complete video to catch truncated or corrupt files.
        subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-f", "null", "-"],
                       check=True, timeout=60)
        with Image.open(gif) as preview:
            if preview.n_frames != len(files):
                raise RuntimeError("GIF frame count differs from walkthrough")
        manifest["videos"].append({**video, "mp4": mp4.relative_to(MEDIA).as_posix(),
                                    "preview": gif.relative_to(MEDIA).as_posix(),
                                    "duration_seconds": len(files)*args.duration,
                                    "recording": "Sequence of browser screenshots; each screen shows captured real results",
                                    "sha256": hashlib.sha256(mp4.read_bytes()).hexdigest()})
        print(f"Encoded and decoded {mp4.relative_to(ROOT)}", flush=True)
    (MEDIA / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"images": len(manifest["images"]), "videos": len(manifest["videos"]),
                      "total_bytes": sum(p.stat().st_size for p in MEDIA.rglob("*") if p.is_file())}))


if __name__ == "__main__":
    main()
