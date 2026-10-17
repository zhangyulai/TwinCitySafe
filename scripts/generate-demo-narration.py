"""Generate standard Chinese synthetic narration and its service-provided word timing."""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ('docs/video/seven' if '--seven' in sys.argv else 'docs/video')
OUT = DATA / 'voice'
VOICE = 'zh-CN-XiaoxiaoNeural'

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = json.loads((DATA / 'narration-cn.json').read_text())
    semaphore = asyncio.Semaphore(3)
    async def generate(entry):
        async with semaphore:
            audio = OUT / (entry['id'] + '.mp3')
            timing = OUT / (entry['id'] + '.json')
            if timing.exists() and audio.exists():
                old = json.loads(timing.read_text())
                if old['text'] == entry['text']:
                    print('Cached', entry['id'], flush=True)
                    return old
            for attempt in range(3):
                try:
                    boundaries = []
                    speech = edge_tts.Communicate(entry['text'], VOICE, rate='+8%', boundary='WordBoundary')
                    with audio.open('wb') as stream:
                        async for chunk in speech.stream():
                            if chunk['type'] == 'audio':
                                stream.write(chunk['data'])
                            elif chunk['type'] == 'WordBoundary':
                                boundaries.append({k: chunk[k] for k in ('text','offset','duration')})
                    assert boundaries and audio.stat().st_size > 1000
                    duration = float(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(audio)], text=True))
                    record = {**entry, 'voice': VOICE, 'rate': '+8%', 'audio': str(audio), 'duration': duration, 'boundaries': boundaries}
                    timing.write_text(json.dumps(record, ensure_ascii=False, indent=2))
                    print('Generated', entry['id'], round(duration,2), 'seconds', flush=True)
                    return record
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 + attempt)
    records = await asyncio.gather(*(generate(e) for e in entries))
    (OUT / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print('Narration and word-level timings ready', flush=True)

if __name__ == '__main__':
    asyncio.run(main())
