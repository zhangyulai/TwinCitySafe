"""Align speech and exact subtitles to recorded UI events; encode the narrated MP4."""
import array
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND_CENTER = '--command-center' in sys.argv
FULL_WALKTHROUGH = '--full-walkthrough' in sys.argv
SEVEN = '--seven' in sys.argv or COMMAND_CENTER or FULL_WALKTHROUGH
DATA = ROOT / ('docs/video/seven' if SEVEN else 'docs/video')
RATE = 24000
SECONDS = 420 if SEVEN else 300
STEM = ('TwinCitySafe-全功能中文讲解演示' if FULL_WALKTHROUGH
        else 'TwinCitySafe-指挥大屏全模块讲解' if COMMAND_CENTER
        else 'TwinCitySafe-7min-all-modules-demo' if SEVEN
        else 'TwinCitySafe-5min-final-demo')

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def subtitle_chunks(entry):
    text = entry['text']
    words = entry['boundaries']
    locations = []
    cursor = 0
    for word in words:
        start = text.find(word['text'], cursor)
        assert start >= cursor, (entry['id'], word['text'], cursor)
        locations.append(start)
        cursor = start + len(word['text'])
    locations.append(len(text))
    result, current, first, last = [], '', None, None
    for i, word in enumerate(words):
        piece = text[locations[i]:locations[i + 1]]
        if current and len(current + piece) > 27:
            result.append((first, last, current))
            current, first = '', None
        if first is None:
            first = word['offset'] / 10_000_000
        current += piece
        last = (word['offset'] + word['duration']) / 10_000_000
        if re.search('[。！？；]$', piece) or (re.search('[，、]$', piece) and len(current) >= 8):
            result.append((first, last, current))
            current, first = '', None
    if current:
        result.append((first, last, current))
    assert ''.join(row[2] for row in result) == text, entry['id'] + ': subtitles must exactly match spoken text'
    return result

def stamp(seconds, ass=False):
    ticks = round(seconds * (100 if ass else 1000))
    unit = 100 if ass else 1000
    h, rest = divmod(ticks, 3600 * unit)
    m, rest = divmod(rest, 60 * unit)
    s, fraction = divmod(rest, unit)
    return f'{h}:{m:02}:{s:02}.{fraction:02}' if ass else f'{h:02}:{m:02}:{s:02},{fraction:03}'

def main():
    recording = json.loads((DATA / 'narrated-recording.json').read_text())
    assert recording['success'] and not recording['errors']
    assert recording['pointerChecks'] and all(x['visible'] for x in recording['pointerChecks'])
    manifest = {e['id']: e for e in json.loads((DATA / 'voice/manifest.json').read_text())}
    cues = recording['speechCues']
    assert len(cues) == len(manifest) and {c['id'] for c in cues} == set(manifest)
    track = array.array('h', [0]) * (RATE * SECONDS)
    subtitles, audit = [], []
    for i, cue in enumerate(cues):
        entry = manifest[cue['id']]
        start = cue['t']
        deadline = min(SECONDS, cues[i + 1]['t'] if i + 1 < len(cues) else SECONDS)
        available = deadline - start - .18
        assert available > 1, ('Insufficient time for narration', cue)
        tempo = max(1., entry['duration'] / available)
        assert tempo <= 1.5, ('Shorten this narration instead of rushing it', cue['id'], tempo)
        pcm = subprocess.check_output(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-i',str(DATA/'voice'/(cue['id']+'.mp3')),'-af',f'atempo={tempo:.8f}','-f','s16le','-ar',str(RATE),'-ac','1','pipe:1'])
        samples = array.array('h'); samples.frombytes(pcm)
        begin = round(start * RATE)
        assert begin + len(samples) <= round(deadline * RATE), (cue['id'],'overlapping speech')
        track[begin:begin + len(samples)] = samples
        local = subtitle_chunks(entry)
        for j, (first, last, text) in enumerate(local):
            end = min(last + .10, local[j + 1][0] - .02 if j + 1 < len(local) else entry['duration'])
            subtitles.append({'start':start + first / tempo, 'end':start + end / tempo, 'text':text, 'cue':cue['id']})
        audit.append({'id':cue['id'],'start':start,'end':start + len(samples)/RATE,'tempo':tempo,'text':entry['text'],'subtitlesExactlyMatch':True})
        print(cue['id'],f'{start:.2f}s',f'tempo {tempo:.3f}',flush=True)
    for previous, following in zip(subtitles, subtitles[1:]):
        assert previous['end'] <= following['start'] + .02
    with wave.open(str(DATA / 'narration.wav'),'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(RATE); stream.writeframes(track.tobytes())
    srt = '\n\n'.join(f'{i+1}\n{stamp(row["start"])} --> {stamp(row["end"])}\n{row["text"]}' for i,row in enumerate(subtitles))+'\n'
    # Keep editing subtitles away from the MP4 so players cannot auto-load
    # a second copy over the already burned-in captions.
    subtitle_dir = DATA / 'subtitles'
    subtitle_dir.mkdir(exist_ok=True)
    (subtitle_dir / f'{STEM}.srt').write_text(srt)
    ass = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Narration,Noto Sans CJK SC,30,&H00FFFFFF,&H00FFFFFF,&H00100A04,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0,2,65,65,36,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    for row in subtitles:
        ass += f'Dialogue: 0,{stamp(row["start"],True)},{stamp(row["end"],True)},Narration,,0,0,0,,{row["text"]}\n'
    (DATA / 'narrated.ass').write_text(ass)
    (DATA / 'narration-sync.json').write_text(json.dumps({'voice':'zh-CN-XiaoxiaoNeural (standard synthetic voice)','timing':'TTS word boundaries aligned to actual recorded UI events','subtitleCount':len(subtitles),'cues':audit,'pointerSamples':len(recording['pointerChecks']),'allPointerSamplesVisible':True},ensure_ascii=False,indent=2))
    subtitle_filter = f"drawbox=x=0:y=976:w=iw:h=104:color=0x040f19:t=fill,ass={DATA.relative_to(ROOT)}/narrated.ass:fontsdir=/usr/share/fonts/opentype/noto"
    # The command-center delivery keeps the same 1080p source and subtitle
    # quality, while using a faster local encode so recording can complete
    # reliably in constrained demo environments.
    video_encode = (['-c:v','libx264','-preset','ultrafast','-crf','20']
                    if COMMAND_CENTER or FULL_WALKTHROUGH else ['-c:v','libx264','-preset','fast','-crf','18'])
    run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(DATA/'narrated-capture.mp4'),'-i',str(DATA/'narration.wav'),'-vf',subtitle_filter,'-af','loudnorm=I=-17:TP=-2:LRA=7','-map','0:v:0','-map','1:a:0','-t',str(SECONDS),*video_encode,'-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-movflags','+faststart',str(ROOT/f'{STEM}.mp4')],cwd=ROOT)
    print('Delivered', ROOT/f'{STEM}.mp4',flush=True)

if __name__ == '__main__':
    main()
