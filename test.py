from __future__ import unicode_literals
import youtube_dl

ydl_opts = {}
with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download(['https://www.youtube.com/watch?v=BaW_jenozKc'])


import glob, os, asyncio
from soundscrape.soundscrape import get_client, process_soundcloud
from pydub import AudioSegment
from shazamio import Shazam

url = "https://soundcloud.com/kyle-watson/kyle-watson-the-red-bull-studio-live-stage-oppikoppi-odyssey"

try:
    base_url = 'https://soundcloud.com/'
    slug = url.split(base_url)[1]
    params = slug.split('/')
    artist = params[0]
    track = params[1]
    if '?' in track:
        track = track.split('?')[0]

    vargs = {
                'track': track, 
                'num_tracks': 1,
                'path': '', 
                'folders': False, 
                'group': False,  
                'bandcamp': False, 
                'downloadable': False, 
                'likes': False, 
                'open': False, 
                'artist_url': artist, 
                'keep': True
            }

    process_soundcloud(vargs)

    loop = asyncio.get_event_loop()
    async def recognize(filename):
        shazam = Shazam()
        out = await shazam.recognize_song(filename)
        return out

    files = glob.glob('*.mp3')
    filename = files[0]
    song = AudioSegment.from_mp3(filename)
    print("song length:", len(song))
    # os.remove(filename)

    minute_length = 60 * 1000
    skip_length = minute_length # // 2
    segment_length = minute_length # // 2
    segments = [song[i:i + segment_length] for i in range(0, len(song), skip_length)]
    print("num segments:", len(segments))

    for i in range(len(segments)):
        segment_file = f"segment_{i}.mp3"
        segments[i].export(f"segment_{i}.mp3", format="mp3")

        result = loop.run_until_complete(recognize(segment_file))
        track_found = 'track' in result

        track_title = "not found"
        if track_found:
            title = ' '.join(result['track']['urlparams']['{tracktitle}'].split('+'))
            artist = ' '.join(result['track']['urlparams']['{trackartist}'].split('+'))
            track_title = title + ' ' + artist

        print(i, "—", track_title)

        os.remove(segment_file)

        # how to get track from soundcloud?
        # results include spotify, Apple music, and shazam link
        # artist ID?

except Exception as e:
    raise e

finally:
    for sound_file in glob.glob('*.mp3'):
        os.remove(sound_file)