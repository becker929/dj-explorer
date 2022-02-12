import asyncio

from flask import Flask, request
from shazamio import Shazam

loop = asyncio.get_event_loop()

# Shazam search setup DUPLICATED IN APP.PY
search_length_seconds = 120
approximate_bit_rate = 16_000
min_segment_bytes = search_length_seconds * approximate_bit_rate

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

# Flask app
app = Flask(__name__)

@app.route('/')
def recognize():
    file_name = request.args.get('file-name')
    start_byte = int(request.args.get('start-byte'))
    end_byte = int(request.args.get('end-byte'))

    audio_file = open(file_name, 'rb')
    all_bytes = audio_file.read()
    current_bytes = all_bytes[start_byte:end_byte]

    result = loop.run_until_complete(shazam.recognize_song(current_bytes))
    return result

if __name__ == '__main__':
    Flask.run(app, host='127.0.0.1', port=8081, debug=False)

