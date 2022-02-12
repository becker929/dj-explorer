import glob
import json
import logging
import os
import re
import time
import traceback
from urllib.parse import unquote

import requests
import youtube_dl
from bs4 import BeautifulSoup as bs
from flask import Flask, redirect, render_template, request, url_for
from flask_socketio import SocketIO
from pydub import AudioSegment

import test_email

logging.basicConfig(filename="search.log", format="%(asctime)s %(message)s")

# Flask app
app = Flask(__name__)
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
socketio = SocketIO(app, logger=True, engineio_logger=True)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/mix-explorer/example")
def example():
    query = "https://soundcloud.com/adambeyer/dcr207-drumcode-radio-live-adam-beyer-live-from-carl-cox-at-space-ibiza"
    return redirect(url_for("dj_explorer") + "?q=" + query)


# # input box & buttons navigates with query params
# # use query param to send search event (if present)
@app.route("/mix-explorer", methods=["GET", "POST"])
def dj_explorer():
    return render_template("search.html")


@socketio.on("search")
def handle_search_event(json_obj, methods=["GET", "POST"]):
    print(
        "##################### received search:" + str(json_obj), "from:", request.sid
    )
    query = json_obj["query"]
    print(query)
    test_email.send_email("Mix Explorer search initiated", query)

    # validate and parse input
    if "soundcloud.com/" not in query:
        print(
            "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ soundcloud.com/ not in query:", query
        )
        error_html = f"""
                <div class='track not-found'>
                Please enter a SoundCloud URL.
                <br>Examples:
                <br>https://soundcloud.com/neosignal/misanthrop-synergy-slap-the-ghost
                <br>https://soundcloud.com/adambeyer/dcr207-drumcode-radio-live-adam-beyer-live-from-carl-cox-at-space-ibiza
                </div>
                """
        socketio.emit("message", {"embed": error_html}, room=request.sid)
        socketio.emit("done", room=request.sid)
        return

    if "?" in query:
        query = query.split("?")[0]
    if "m.soundcloud" in query:
        query = "".join(query.split("m."))

    # get track page directly
    print("############################# now searching for:", query)
    response = requests.get(query)
    try:
        soup = bs(response.text)
        scripts = soup.find_all("script")
        s = str(scripts[16])
        m = re.search(r"\[\{.*\}\]", s)
        x = m.group(0)
        j = json.loads(x)
        item = j[6]["data"][0]
    except Exception as e:
        print("exception:", e)
        socketio.emit(
            "message",
            {"embed": "There was a problem getting the track."},
            room=request.sid,
        )
        socketio.emit("done", room=request.sid)
        return

    # prepare search request
    headers = {
        "Connection": "keep-alive",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Authorization": "OAuth 2-290059-4633058-ngCv8CgzZa3tPnLG",
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Origin": "https://soundcloud.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://soundcloud.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    params = (
        ("q", query),
        ("sc_a_id", "64812b39e64dfff7b5a22878872c7c32e8f47670"),
        ("variant_ids", "2312,2318"),
        ("facet", "genre"),
        ("user_id", "734990-318830-622789-676080"),
        ("client_id", "alw48hna4lka90aa4"),
        ("limit", "20"),
        ("offset", "0"),
        ("linked_partitioning", "1"),
        ("app_version", "1624617819"),
        ("app_locale", "en"),
    )

    duration = item["duration"] / 60_000
    match_count = 0
    if duration >= 20:  # it's a mix, so search for tracks
        title = item["title"]
        socketio.emit(
            "message",
            {"embed": f'<p>Searching for tracks in "{title}". . .</p>'},
            room=request.sid,
        )

        params = list(params)
        params.append(("filter.duration", "medium"))
        params = tuple(params)

        # search for line function
        def search_soundcloud(track_search, params=params):
            print("searching soundcloud for", track_search)
            new_params = list(params)
            new_params[0] = ("q", track_search)
            params = tuple(new_params)

            response = requests.get(
                "https://api-v2.soundcloud.com/search/tracks",
                headers=headers,
                params=params,
            )
            j = json.loads(response.text)
            tracks = j["collection"]

            return tracks[0] if tracks else None

        # Shazam search setup DUPLICATED IN SHAZAM_SERVER.PY
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
                self.match_count = 0

        context = Context()

        def get_byte_index():
            return context.byte_index

        def set_index(index):
            context.byte_index = index

        def get_match_count():
            return context.match_count

        def increment_match_count():
            context.match_count += 1

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
                    # request: recognize(file_name, byte_index, len(all_bytes))
                    # sometimes the temp file might not be available or did not grow as expected,
                    # it might even shrink at the end of the download process
                    shazam_url = f"http://127.0.0.1:8081/?file-name={file_name}"
                    shazam_url += f"&start-byte={byte_index}&end-byte={audio_length}"
                    response = requests.get(shazam_url)
                    result = json.loads(response.content)

                    current_bytes = all_bytes[byte_index:]
                    print("segment length", len(current_bytes))

                    byte_index = len(all_bytes)
                    set_index(byte_index)
                    print("new byte index", byte_index)

                    if "track" in result:
                        title = unquote(
                            " ".join(
                                result["track"]["urlparams"]["{tracktitle}"].split("+")
                            )
                        )
                        artist = unquote(
                            " ".join(
                                result["track"]["urlparams"]["{trackartist}"].split("+")
                            )
                        )
                        num_seconds = byte_index // approximate_bit_rate
                        timestamp = time.strftime("%H:%M:%S", time.gmtime(num_seconds))

                        # EMIT TITLE & ARTIST, TIMESTAMP
                        track_html = f"""
                        <div class="track">
                            <div class='track-title'>{timestamp} — {title} by {artist}</div>
                        </div>
                        """
                        increment_match_count()

                        shazam_result = title + " " + artist
                        soundcloud_track = search_soundcloud(shazam_result)
                        if soundcloud_track:
                            track_urn = int(soundcloud_track["urn"].split(":")[-1])
                            track_url = soundcloud_track["permalink_url"]

                            # tracks have "find mixes" button that searches for title
                            iframe = f"""
                            <div class="track">
                                <div class='track-title'>best match for "{shazam_result}":</div>
                                <iframe id="{context.match_count}" width="100%" height="150" scrolling="no" frameborder="no" allow="autoplay"
                                    src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/{track_urn}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true&visual=true">
                                </iframe>
                                <button class='find-mixes' onclick='searchButton("{track_url}");'>
                                    Find Mixes
                                </button>
                            </div>
                            """
                            socketio.emit(
                                "track",
                                {"embed": iframe, "widget_id": context.match_count},
                                room=request.sid,
                            )
                        else:
                            html = f"<div class='track not-found'>Not found on SoundCloud: {shazam_result}</div>"
                            socketio.emit("message", {"embed": html}, room=request.sid)

                    else:
                        shazam_result = "not found"

                        # EMIT NOTHING
                    print("Shazam result:", shazam_result)

                audio_file.close()

        # perform audio search then search soundcloud for artist + track title
        try:
            ydl_opts = {"progress_hooks": [shazam_search_hook]}
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([query])

        except Exception as e:
            traceback.print_exc()

        finally:
            match_count = context.match_count
            for sound_file in glob.glob("*.mp3"):
                os.remove(sound_file)

    else:  # it's a track, so search for mixes
        title = item["title"]
        socketio.emit(
            "message",
            {"embed": f'<p>Searching for mixes with "{title}". . .</p>'},
            room=request.sid,
        )

        new_params = list(params)
        new_params[0] = ("q", title)
        params = tuple(new_params)
        print("###################### params", params)
        response = requests.get(
            "https://api-v2.soundcloud.com/search/tracks",
            headers=headers,
            params=params,
        )
        j = json.loads(response.text)
        tracks = j["collection"]
        print(
            "#################### collection",
            [(x["title"], x["duration"] / 60_000) for x in tracks],
        )
        for track in tracks:
            duration = track["duration"] / 60_000
            if duration >= 20:
                match_count += 1
                number = int(track["urn"].split(":")[-1])

                # mixes have "find tracks" button that searches for link
                iframe = f"""
                <div class="track">
                    <div class='player'>
                        <iframe id="{match_count}" style="display: inline-block" width="100%" height="150" 
                            scrolling="no" frameborder="no" allow="autoplay"
                            src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/{number}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true&visual=true">
                        </iframe>
                    </div>
                    <button class='find-mixes' onclick='searchButton("{track['permalink_url']}");'>
                        Find Tracks
                    </button>
                </div>
                """
                socketio.emit(
                    "track",
                    {"embed": iframe, "widget_id": match_count},
                    room=request.sid,
                )
    if not match_count:
        socketio.emit(
            "message",
            {"embed": f"<div class='track not-found'>No results.</div>"},
            room=request.sid,
        )
    socketio.emit("done", room=request.sid)

    message_text = f"""
        url: {query}
        match_count: {match_count}
    """
    test_email.send_email("Mix Explorer search results", message_text)


if __name__ == "__main__":
    # debug must == False when using monkey_patch
    socketio.run(app, host="127.0.0.1", port=8080, debug=False)
    # socketio.run(app, host='127.0.0.1', port=8080, debug=True)
    # socketio.run(app, host='0.0.0.0', port=80, debug=False)
