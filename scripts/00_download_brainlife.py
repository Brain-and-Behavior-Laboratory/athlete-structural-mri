from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import analysis_paths, command_output, load_config, require_commands, run_command, save_json


def datatype_name(obj: dict) -> str:
    dt = obj.get("datatype")
    if isinstance(dt, dict):
        return str(dt.get("name") or dt.get("id") or "")
    return str(dt or obj.get("datatype_name") or "")


def normalize_subject(value: str) -> str:
    value = str(value).strip()
    return value[4:] if value.startswith("sub-") else value


def subject_id(obj: dict) -> str:
    meta = obj.get("meta") or {}
    value = meta.get("subject") if isinstance(meta, dict) else None
    if value is None:
        value = obj.get("subject")
    return normalize_subject(value or "")


def sanitize_tag(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9_+-]+", "_", str(tag).strip())


def object_dir_name(obj: dict, what: str) -> str:
    oid = str(obj["_id"])
    tags = [sanitize_tag(x) for x in (obj.get("tags") or []) if str(x).strip()]
    if what == "anat":
        base = "dt-neuro-anat-t1w"
    else:
        base = "dt-neuro-freesurfer"
    tag_text = "".join(f".tag-{tag}" for tag in tags)
    return f"{base}{tag_text}.id-{oid}"


def resolve_release(cfg: dict) -> str:
    explicit = str(cfg["brainlife"].get("release_id") or "").strip()
    if explicit:
        return explicit
    query = cfg["brainlife"]["publication_query"]
    pubs = json.loads(command_output(["bl", "pub", "query", "-q", query, "--json"]))
    if not pubs:
        raise RuntimeError(f"No brainlife publication matched: {query}")
    chosen = pubs[0]
    releases = [r for r in chosen.get("releases", []) if not r.get("removed", False)]
    if not releases:
        raise RuntimeError("No active publication release found. Set brainlife.release_id manually.")
    releases.sort(key=lambda r: str(r.get("create_date") or ""))
    return str(releases[-1]["_id"])


def matches(obj: dict, what: str) -> bool:
    name = datatype_name(obj).lower()
    if what == "anat":
        return "anat/t1w" in name or "neuro/anat/t1w" in name
    return "freesurfer" in name


def main():
    parser = argparse.ArgumentParser(
        description="Download public brainlife anatomical T1w or FreeSurfer data objects."
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--what", choices=["anat", "freesurfer"], default="anat")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    require_commands(["bl"])
    release = resolve_release(cfg)
    print(f"brainlife release: {release}")

    objects = json.loads(
        command_output(["bl", "data", "query", "--limit", "10000", "--pub", release, "--json"])
    )
    selected = [obj for obj in objects if matches(obj, args.what) and subject_id(obj)]
    selected.sort(key=lambda o: (subject_id(o), object_dir_name(o, args.what)))

    destination = paths["anat_t1w_root"] if args.what == "anat" else paths["freesurfer_root"]
    destination.mkdir(parents=True, exist_ok=True)
    save_json(selected, destination / f"brainlife_{args.what}_objects.json")

    print(f"Matched {len(selected)} {args.what} data objects")
    if args.dry_run:
        for obj in selected:
            print(f"sub-{subject_id(obj)}/{object_dir_name(obj, args.what)}")
        return

    for i, obj in enumerate(selected, 1):
        subject = subject_id(obj)
        oid = str(obj["_id"])
        outdir = destination / f"sub-{subject}" / object_dir_name(obj, args.what)
        outdir.mkdir(parents=True, exist_ok=True)
        save_json(obj, outdir / "_brainlife_object.json")
        existing = [p for p in outdir.iterdir() if p.name != "_brainlife_object.json"]
        if existing:
            print(f"[{i}/{len(selected)}] skip existing sub-{subject}: {outdir.name}")
            continue
        print(f"[{i}/{len(selected)}] download sub-{subject}: {outdir.name}")
        run_command(
            ["bl", "data", "download", "-i", oid, "--directory", str(outdir)],
            log_path=paths["logs"] / f"brainlife_download_{args.what}.log",
        )

    print(f"Download completed under: {destination}")


if __name__ == "__main__":
    main()
