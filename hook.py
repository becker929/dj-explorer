from __future__ import unicode_literals

import asyncio
import glob
import os
import traceback
from urllib.parse import unquote

import youtube_dl
from pydub import AudioSegment
from shazamio import Shazam

short_url = "https://soundcloud.com/whatever/amen-break"
medium_url = "https://soundcloud.com/skrillex/benny-bennassi-cinema-skrillex"
long_url = "https://soundcloud.com/kyle-watson/kyle-watson-the-red-bull-studio-live-stage-oppikoppi-odyssey"

url = medium_url

search_length_seconds = 120
approximate_bit_rate = 16_000
min_segment_bytes = search_length_seconds * approximate_bit_rate

# need to use object otherwise the variables in the
# functions called by the callbacks are limited to the
# function scope. Using an object keeps everything scoped
# properly


class Context:
    def __init__(self):
        self.byte_index = 0


context = Context()


def get_byte_index():
    return context.byte_index


def set_index(index):
    context.byte_index = index


# custom Shazam subclass in order to pass bytes directly instead of file


class ShazamSearch(Shazam):
    async def recognize_song(self, audio: bytes):
        audio = self.normalize_audio_data(audio)
        signature_generator = self.create_signature_generator(audio)
        signature = signature_generator.get_next_signature()
        while not signature:
            signature = signature_generator.get_next_signature()
        results = await self.send_recognize_request(signature)
        return results


shazam = ShazamSearch()


async def recognize(audio_bytes):
    return await shazam.recognize_song(audio_bytes)


# For now we are just reading the whole file as it is written
# and then just indexing into the bytes to get the current
# segment. This may be very slow but it is the simplest solution.

# when audio_length - byte_index >= min_segment_bytes,
# process all_bytes[byte_index:] and set byte_index to audio_length
# NOTE: this will leave off the last segment if < min_segment_bytes


def shazam_search_hook(d):
    print(" ")
    if "tmpfilename" in d:
        file_name = d["tmpfilename"]
        audio_file = open(file_name, "rb")
        all_bytes = audio_file.read()

        audio_length = len(all_bytes)
        print("total length", audio_length)

        byte_index = get_byte_index()

        if audio_length - byte_index >= min_segment_bytes:
            current_bytes = all_bytes[byte_index:]
            print("segment length", len(current_bytes))

            byte_index = len(all_bytes)
            set_index(byte_index)
            print("new byte index", byte_index)

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(recognize(current_bytes))
            if "track" in result:
                title = " ".join(
                    result["track"]["urlparams"]["{tracktitle}"].split("+")
                )
                artist = " ".join(
                    result["track"]["urlparams"]["{trackartist}"].split("+")
                )
                track_title = unquote(title + " " + artist)
            else:
                track_title = "not found"

            print(track_title)

        audio_file.close()


try:
    ydl_opts = {"progress_hooks": [shazam_search_hook]}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

except Exception as e:
    traceback.print_exc()

finally:
    for sound_file in glob.glob("*.mp3"):
        os.remove(sound_file)
