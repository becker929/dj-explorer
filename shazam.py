import asyncio
import sys

from pydub import AudioSegment
from shazamio import Shazam


class ShazamSearch(Shazam):
    async def recognize_song(self, audio: bytes):
        audio = self.normalize_audio_data(audio)
        signature_generator = self.create_signature_generator(audio)
        signature = signature_generator.get_next_signature()
        while not signature:
            signature = signature_generator.get_next_signature()
        results = await self.send_recognize_request(signature)
        return results

if not sys.argv[1]:
    print("usage: python3 shazam.py filename")

else:
    filename = sys.argv[1]
    print("shazaming", filename)
    
    loop = asyncio.get_event_loop()
    async def recognize(filename):
        shazam = ShazamSearch()
        with open(filename, 'rb') as file:
            audio = file.read()
            out = await shazam.recognize_song(audio)
        return out

    result = loop.run_until_complete(recognize(filename))
    track_found = 'track' in result

    track_title = "not found"
    if track_found:
        title = ' '.join(result['track']['urlparams']['{tracktitle}'].split('+'))
        artist = ' '.join(result['track']['urlparams']['{trackartist}'].split('+'))
        track_title = title + ' ' + artist

    print(track_title)

# async def load_file(file: Union[str, pathlib.Path], binary: bool = False):
#     mode = "r" if not binary else "rb"
#     async with aiofiles.open(file, mode=mode) as f:
#         return await f.read()

# def normalize_audio_data(song_data: bytes) -> AudioSegment:
        # audio = AudioSegment.from_file(BytesIO(song_data))

# file = await load_file(file_path, True)
# audio = self.normalize_audio_data(file)