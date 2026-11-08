"""Read Kuku-style timestamped screenplays. Uses only Python's standard library."""
from __future__ import annotations
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path

TIME = r"(\d{2}:\d{2}\.\d{2})"
TIMING = re.compile(r"^Start:\s*\(" + TIME + r"\)\s*\|\s*End:\s*\(" + TIME + r"\)\s*$")
TITLE = re.compile(r"^\*\*(.+?):\*\*\s*$")
SCENE = re.compile(r"^SCENE\s+(\d+)", re.IGNORECASE)
EPISODE = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.IGNORECASE)


def seconds(t: str) -> float:
    m, s = t.split(':')
    return round(int(m) * 60 + float(s), 2)


def stamp(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 6000:02d}:{(cs % 6000) / 100:05.2f}"


@dataclass
class Event:
    category: str
    speaker: str
    scene: int
    start: float
    end: float
    text: str


@dataclass
class Episode:
    number: int
    filename: str
    logline: str
    continuity: str
    duration: float
    events: list[Event]


def parse_script(source: str, filename: str = 'episode.txt') -> Episode:
    lines = source.replace('\r\n', '\n').splitlines()
    head = '\n'.join(lines[:8])
    match = EPISODE.search(head)
    if not match:
        name_match = re.search(r'episode-(\d+)', filename, re.IGNORECASE)
        if not name_match:
            raise ValueError(f"Cannot determine episode number: {filename}")
        number = int(name_match.group(1))
    else:
        number = int(match.group(1))
    logline = next((x.split(':', 1)[1].strip() for x in lines if x.startswith('EPISODE LOGLINE:')), '')
    continuity = next((x.split(':', 1)[1].strip() for x in lines if x.startswith('CONTINUITY NOTES:')), '')
    events: list[Event] = []
    active_header = ''
    scene_number = 1
    highest_scene_end = 0.0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        scene_match = SCENE.match(line)
        if scene_match:
            scene_number = int(scene_match.group(1))
        if line.lower().startswith('scene end:'):
            raw = line.split(':', 1)[1].strip()
            try: highest_scene_end = max(highest_scene_end, seconds(raw))
            except (ValueError, IndexError): pass
        header = TITLE.match(line)
        if header:
            active_header = header.group(1)
            i += 1
            continue
        timing = TIMING.match(line)
        if timing and active_header:
            start, end = map(seconds, timing.groups())
            j = i + 1
            body = []
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or TITLE.match(nxt) or TIMING.match(nxt) or SCENE.match(nxt) or nxt.startswith('--- SCRIPT'):
                    break
                body.append(nxt)
                j += 1
            if end > start and body:
                category = active_header if active_header in {'CAMERA', 'ACTION', 'SOUND FX'} else 'DIALOGUE'
                speaker = '' if category != 'DIALOGUE' else active_header.split(' (')[0]
                events.append(Event(category, speaker, scene_number, start, end, ' '.join(body)))
            i = j
            continue
        i += 1
    if not events:
        raise ValueError(f"No timestamped screenplay events in {filename}")
    events.sort(key=lambda e: (e.start, e.end, e.category))
    duration = max(highest_scene_end, max(e.end for e in events))
    return Episode(number, Path(filename).name, logline, continuity, duration, events)


def load_episodes(path: str | Path) -> list[Episode]:
    path = Path(path)
    results = []
    if path.is_dir():
        entries = ((p.name, p.read_bytes()) for p in sorted(path.rglob('*.txt')))
    elif path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            # Consume the bytes directly; we never extract untrusted archive paths.
            entries = [(Path(name).name, z.read(name)) for name in sorted(z.namelist()) if name.lower().endswith('.txt') and not name.endswith('/')]
    else:
        entries = [(path.name, path.read_bytes())]
    for name, raw in entries:
        results.append(parse_script(raw.decode('utf-8-sig'), name))
    if not results:
        raise ValueError('No .txt screenplay files found in input.')
    by_number = {}
    for ep in results:
        if ep.number in by_number:
            raise ValueError(f'Duplicate episode {ep.number}')
        by_number[ep.number] = ep
    return sorted(results, key=lambda x: x.number)
