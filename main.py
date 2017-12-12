from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app, jsonify
from flask_oauthlib.client import OAuth, OAuthException
from user_definition import *
import time
import pickle
from random import randint

# VARIABLES
FEATURES_TO_PLOT = ['valence', 'energy']
FEATURES = ['valence', 'energy', 'danceability', "acousticness", "instrumentalness"]
FEATURES_TO_SHOW_ALTERNATIVE_SONGS_ON = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']
NUMBER_OF_TOP_TRACKS_TO_COLLECT = 400  # per 100

app = Flask(__name__)
app.debug = True
app.secret_key = 'development'

app.config.update(dict(
    DATABASE='example.db',
    SECRET_KEY='development key'
))

oauth = OAuth(app)

spotify = oauth.remote_app(
    'spotify',
    consumer_key='a833100236684147b8ae69e1439f571a',
    consumer_secret='9d979735d9fe40b38f6a0015275377ae',
    base_url='https://api.spotify.com/',
    request_token_url=None,
    access_token_url='https://accounts.spotify.com/api/token',
    authorize_url='https://accounts.spotify.com/authorize'
)


def get_similar_track():
    return 0


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login')
def login():
    callback = url_for(
        'spotify_authorized',
        next=request.args.get('next') or request.referrer or None,
        _external=True
    )
    return spotify.authorize(callback=callback,
                             scope="user-top-read user-read-playback-state user-modify-playback-state user-read-recently-played")


@app.route('/login/authorized')
def spotify_authorized():
    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    # declare global variables
    global gebruiker
    global song_display_dic

    resp = spotify.authorized_response()
    if resp is None:
        return 'Access denied: reason={0} error={1}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )
    if isinstance(resp, OAuthException):
        return 'Access denied: {0}'.format(resp.message)
    session['oauth_token'] = (resp['access_token'], '')

    # PAUSE PLAYER IF SONG IS PLAYING
    url = "https://api.spotify.com/v1/me/player/pause"
    spotify.put(url=url, format='json')

    # DEFINE THE USER

    me = spotify.request('/v1/me')  # LOAD USER PROFILE
    gebruiker = User(me)  # Initialize user

    gebruiker.load_questions() # Initialize questions

    # COLLECT THE MOST LISTENED TRACKS OF THE USER
    # THE FEATURES VARIABLE INDICATES WHICH FEATURE VALUE OF THE SONGS NEED TO BE ADDED TO THE DICTONARY
    # THE NUMBER OF TOP TRACKS INDICATE THE NUMBER OF TOP TRACKS THAT WE REQUEST FROM SPOTIFY, TOO MANY CAUSE
    # THE API TO TIME OUT

    gebruiker.get_top_tracks(FEATURES, NUMBER_OF_TOP_TRACKS_TO_COLLECT)  # Collect the top tracks of the user

    return render_template('select_seed.html', seed=list(gebruiker.top_tracks['id']), song_dic=gebruiker.most_listened_tracks)


@app.route('/calrec', methods=['GET', 'POST'])
def calrec():
    # IDENTIFY GLOBAL VARIABLES

    global gebruiker, seed_identifier
    global status

    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT

    if request.method == 'POST':
        seed_identifier = str(request.form['selected_song'])

    gebruiker.calculate_recommendations(seed_identifier, ['energy'])

    # THE FIRST LIST IS RANDOMLY CHOSEN, FORM THE SYSTEM THAT THIS IS THE CURRENT LIST

    gebruiker.current_list = gebruiker.first_list

    status = 'listeningList1'

    return redirect(url_for('play_song'))

@app.route('/getrec', methods=['GET', 'POST'])
def getrec():

    # IDENTIFY GLOBAL VARIABLES

    global gebruiker

    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT
    if request.method == 'GET':
        return jsonify(gebruiker.recommendations_to_user)

@app.route('/pause', methods=['GET', 'POST'])
def pause():
    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT
    if request.method == 'POST':
        url = "https://api.spotify.com/v1/me/player/pause"
        spotify.put(url=url, format='json')
        return 'true'

@app.route('/volume', methods=['POST'])
def volume():
    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT
    if request.method == 'POST':
        volume = request.json['volume']
        print(volume)
        url = "https://api.spotify.com/v1/me/player/volume?volume_percent=" + volume
        spotify.put(url=url, format='json')
        return 'true'


@app.route('/play_song', methods=['GET', 'POST'])
def play_song():
    return render_template('playing_song.html', gebruiker=gebruiker)


@app.route('/music_player', methods=['GET', 'POST'])
def music_player():

    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    global gebruiker

    if request.method == 'GET':

        status_playing = spotify.request('/v1/me/player/currently-playing')
        progress = 'null'
        trackid = 'null'
        name = 'null'
        artist = 'null'
        playing = 'null'

        if status_playing.status == 200:
            progress = status_playing.data['progress_ms']
            trackid = status_playing.data['item']['id']
            name = status_playing.data['item']['name']
            artist = status_playing.data['item']['artists'][0]['name']
            playing = status_playing.data['is_playing']

        if status_playing.status == 202:
            time.sleep(5)

        return jsonify({'status':status_playing.status,
                        'current_list': gebruiker.current_list,
                        'current_song': gebruiker.current_song,
                        'progress': progress,
                        'id': trackid,
                        'name': name,
                        'artist': artist,
                        'playing': playing,
                        'nomorequestions':gebruiker.no_more_questions})

    if request.method == 'POST':

        gebruiker.current_song = request.json['current_song']
        current_id = request.json['current_id']
        payload = {"uris": ["spotify:track:" + current_id]}
        url = "https://api.spotify.com/v1/me/player/play?device_id=" + str(gebruiker.active_device['id'])

        spotify.put(url=url, data=payload, format='json')
        gebruiker.no_more_questions = False
        gebruiker.load_questions()  # RELOAD QUESTIONS

        return 'true'

@app.route('/update_device', methods=['GET', 'POST'])
def update_device():

    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    devices = spotify.request('/v1/me/player/devices')

    print('-------------------------------------------------------------')
    print('')
    print('Device Data, status = %s' % (str(devices.status)))
    print(devices.data)

    if devices.status == 202:
        time.sleep(5)

    elif devices.status == 200:

        device_filter = [x for x in devices.data['devices'] if x['is_active']]

        if device_filter == 1:
            gebruiker.active_device = device_filter[0]

        elif len(devices.data['devices']) > 0:
            gebruiker.active_device = devices.data['devices'][0]

        else:
            print('User: %s does currently have no devices' % (str(gebruiker.name)))
            gebruiker.active_device =   {"id": "noDevice",
                                         "is_active": "noDevice",
                                         "is_restricted": "noDevice",
                                         "name": "noDevice",
                                         "type": "noDevice",
                                         "volume_percent": "noDevice"
                                         }

        print('Active devices: %s' % str(gebruiker.active_device))

    print('')
    print('-------------------------------------------------------------')

    return jsonify(gebruiker.active_device)


@app.route('/question', methods=['GET', 'POST'])
def question():

    if request.method == 'GET':

        # WHEN THERE ARE QUESTIONS LEFT
        if gebruiker.questions:

            # SELECT A QUESTION
            question = random.choice(gebruiker.questions)

            # REMOVE IT FROM THE LIST
            gebruiker.questions.remove(question)

            return jsonify(question)

        else:

            gebruiker.no_more_questions = True

            return jsonify({'status' : 'empty'})

    if request.method == 'POST':

        # GET THE CURRENT SONG PROGRESS
        status_playing = spotify.request('/v1/me/player/currently-playing')

        if status_playing.status == 200 and status_playing.data:
            progress = status_playing.data['progress_ms']
        else:
            progress = 'noData'

        # ASSIGN THE VALUES
        answer = request.json['answer']
        question = request.json['question']
        trackid = request.json['id']
        list = gebruiker.current_list
        song = gebruiker.current_song

        # TRY TO OPEN AN EXISTING FILE

        try:
            with open('user_data/' + str(gebruiker.name) + '_answers.txt', 'rb') as fp:
                itemlist = pickle.load(fp)

            print('')
            print('----------------------------------')
            print('')

            print('What is currently in the file')
            print(itemlist)

            print('')
            print('----------------------------------')
            print('')


        # IF NO EXISTING FILE IS AVAILABLE, CREATE AN EMPTY LIST
        except:
            itemlist = []

            print('')
            print('----------------------------------')
            print('')

            print('Load empty list')

            print('')
            print('----------------------------------')
            print('')

        itemlist.append({'answer' : answer, 'question' : question, 'list' : list, 'song': song, 'progress':progress, 'trackid':trackid})

        print('')
        print('----------------------------------')
        print('')

        print('To save in the list')
        print(itemlist)

        print('')
        print('----------------------------------')
        print('')

        # DUMP THE DATA IN THE FILE
        with open('user_data/' + str(gebruiker.name) + '_answers.txt', 'wb') as fp:
            pickle.dump(itemlist, fp)

        return 'OK'

@app.route('/review_list', methods=['GET'])
def review_list():

    global gebruiker

    gebruiker.load_questions()
    gebruiker.no_more_questions = True
    gebruiker.current_song = 0



    if gebruiker.current_list != gebruiker.first_list:
        gebruiker.done = True
    else:
        if gebruiker.first_list == 'list_1':
            gebruiker.current_list = 'list_2'
        else:
            gebruiker.current_list = 'list_1'

    return render_template('question.html')


@app.route('/router', methods=['GET', 'POST'])
def router():

    global status

    if request.method == 'POST':
        valence = request.json['valence']
        energy = request.json['energy']
        danceability = request.json['danceability']
        rating = request.json['rating']
        ratingNoPreference = request.json['ratingNoPreference']

        try:
            with open('user_data/' + str(gebruiker.name) + '_answers.txt', 'rb') as fp:
                itemlist = pickle.load(fp)

        # IF NO EXISTING FILE IS AVAILABLE, CREATE AN EMPTY LIST
        except:
            itemlist = []

        itemlist.append({'question': 'overall', 'valence': valence, 'energy': energy, 'danceability': danceability, 'rating':rating, 'ratingNoPreference':ratingNoPreference})

        # DUMP THE DATA IN THE FILE
        with open('user_data/' + str(gebruiker.name) + '_answers.txt', 'wb') as fp:
            pickle.dump(itemlist, fp)

    # REDIRECT
    if gebruiker.done:
        return render_template('comparison.html')
    else:
        status = 'listeningList2'
        return redirect(url_for('play_song'))


@app.route('/end', methods=['GET'])
def end():

    return 'end of experiment'

if __name__ == '__main__':
     app.debug = True
     port = int(os.environ.get("PORT", 5000))
     app.run(host='0.0.0.0', port=port)
