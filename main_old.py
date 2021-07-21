import eventlet
eventlet.monkey_patch()

from flask import Flask, request, render_template
from flask_socketio import SocketIO
import requests, difflib, json, re
from bs4 import BeautifulSoup as bs

import logging, sys

logging.basicConfig(filename='search.log', format='%(asctime)s %(message)s')

SIMILARITY_THRESHOLD = 0.7

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gurdenwurdermaldehyde'
socketio = SocketIO(app, logger=True, engineio_logger=True) #, async_mode='eventlet')

@app.route('/')
def home():
    return render_template('index.html')

# input box & buttons navigates with query params
# use query param to send search event (if present)
@app.route('/mix-explorer', methods=['GET', 'POST'])
def dj_explorer():
    return render_template('search.html')

@socketio.on('search')
def handle_search_event(json_obj, methods=['GET', 'POST']):
    print('##################### received search:' + str(json_obj), 'from:', request.sid)
    query = json_obj['query']
    print(query)

    # validate and parse input
    if 'soundcloud.com/' not in query:
        html = f'''
                <div class='track not-found'>
                Please enter a SoundCloud URL.
                <br>Examples:
                <br>https://soundcloud.com/neosignal/misanthrop-synergy-slap-the-ghost
                <br>https://soundcloud.com/adambeyer/dcr207-drumcode-radio-live-adam-beyer-live-from-carl-cox-at-space-ibiza
                </div>
                '''
        socketio.emit('message', {'embed': html}, room=request.sid)
        print('$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ soundcloud.com/ not in query:', query)
        socketio.emit('done', room=request.sid)
        return

    if '?' in query:
        query = query.split('?')[0]
    if 'm.soundcloud' in query:
        query = ''.join(query.split('m.'))

    # get track page directly
    print('############################# now searching for:', query)
    response = requests.get(query)
    try:
        soup = bs(response.text)
        scripts = soup.find_all('script')
        s = str(scripts[16])
        m = re.search(r'\[\{.*\}\]', s)
        x = m.group(0)
        j = json.loads(x)
        item = j[6]['data'][0]
    except Exception as e:
        print('exception:', e)
        socketio.emit('message', {'embed': 'There was a problem getting the track.'}, room=request.sid)
        socketio.emit('done', room=request.sid)
        return

    # prepare search request
    headers = {
        'Connection': 'keep-alive',
        'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Authorization': 'OAuth 2-290059-4633058-ngCv8CgzZa3tPnLG',
        'sec-ch-ua-mobile': '?0',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        'Origin': 'https://soundcloud.com',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://soundcloud.com/',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    params = (
        ('q', query),
        ('sc_a_id', '64812b39e64dfff7b5a22878872c7c32e8f47670'),
        ('variant_ids', '2312,2318'),
        ('facet', 'genre'),
        ('user_id', '734990-318830-622789-676080'),
        ('client_id', 'alw48hna4lka90aa4'),
        ('limit', '20'),
        ('offset', '0'),
        ('linked_partitioning', '1'),
        ('app_version', '1624617819'),
        ('app_locale', 'en'),
    )

    duration = item['duration'] / 60_000
    match_count = 0
    if duration >= 20: # it's a mix, so search for tracks
        title = item['title']
        socketio.emit('message', {'embed': f'<p>Searching for tracks in "{title}". . .</p>'},
                    room=request.sid)

        params = list(params)
        params.append(('filter.duration', 'medium'))
        params = tuple(params)

        # search for line function
        def search_for_line(line, params):
            print(line)
            new_params = list(params)
            new_params[0] = ('q', line)
            params = tuple(new_params)
            
            response = requests.get('https://api-v2.soundcloud.com/search/tracks', headers=headers, params=params)
            j = json.loads(response.text)
            tracks = j['collection']
            if tracks:
                for track in tracks:
                    title = track['title']
                    track['similarity'] = difflib.SequenceMatcher(None, line, title).ratio()
                closest = max(tracks, key=lambda x: x['similarity'])
            else:
                closest = {'similarity': 0}
            return closest

        # valid line function 
        def valid_line(line):
            return 10 < len(line) < 100
            
        # search for tracks from lines in description and match title using difference
        description = item['description']
        
        lines = [line for line in description.split('\n') if valid_line(line)]
        for line in lines:
            original_line = line
            closest = search_for_line(line, params)
            
            # repeat search with smaller lines
            if closest['similarity'] < SIMILARITY_THRESHOLD:
                line = ' '.join(line.split(' ')[1:])
                closest = search_for_line(line, params)

            if closest['similarity'] < SIMILARITY_THRESHOLD:
                line = ' '.join(line.split(' ')[:-1])
                closest = search_for_line(line, params)

            if closest['similarity'] < SIMILARITY_THRESHOLD:
                line = ' '.join(line.split(' ')[:-1])
                closest = search_for_line(line, params)

            if closest['similarity'] >= SIMILARITY_THRESHOLD:
                match_count += 1
                number = int(closest['urn'].split(':')[-1])

                # tracks have "find mixes" button that searches for title
                iframe = f'''
                <div class="track">
                    <div class='track-title'>best match for "{original_line}":</div>
                    <iframe id="{match_count}" width="100%" height="150" scrolling="no" frameborder="no" allow="autoplay"
                        src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/{number}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true&visual=true">
                    </iframe>
                    <button class='find-mixes' onclick='searchButton("{closest['permalink_url']}");'>
                        Find Mixes
                    </button>
                </div>
                '''
                socketio.emit('track', {'embed': iframe, 'widget_id': match_count}, room=request.sid)
            else:
                html = f"<div class='track not-found'>Not found: {original_line}</div>"
                socketio.emit('message', {'embed': html}, room=request.sid)

    else: # it's a track, so search for mixes
        title = item['title']
        socketio.emit('message', {'embed': f'<p>Searching for mixes with "{title}". . .</p>'},
                    room=request.sid)

        new_params = list(params)
        new_params[0] = ('q', title)
        params = tuple(new_params)
        print('###################### params', params)
        response = requests.get('https://api-v2.soundcloud.com/search/tracks', headers=headers, params=params)
        j = json.loads(response.text)
        tracks = j['collection']
        print('#################### collection', [(x['title'],x['duration']/60_000) for x in tracks])
        for track in tracks:
            duration = track['duration'] / 60_000
            if duration >= 20:
                match_count += 1
                number = int(track['urn'].split(':')[-1])

                # mixes have "find tracks" button that searches for link
                iframe = f'''
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
                '''
                socketio.emit('track', {'embed': iframe, 'widget_id': match_count}, room=request.sid)
    if not match_count:
        socketio.emit('message', {'embed': f"<div class='track not-found'>No results.</div>"},
                    room=request.sid)
    socketio.emit('done', room=request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=False)
