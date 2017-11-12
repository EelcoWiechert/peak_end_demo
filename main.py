from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app, jsonify
from flask_oauthlib.client import OAuth, OAuthException
from user_definition import *
import time

# VARIABLES
FEATURES_TO_PLOT = ['valence', 'energy']
FEATURES = ['valence', 'energy', 'danceability', "acousticness", "instrumentalness"]
FEATURES_TO_SHOW_ALTERNATIVE_SONGS_ON = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']
NUMBER_OF_TOP_TRACKS_TO_COLLECT = 100  # per 100

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

    # DEFINE THE USER

    me = spotify.request('/v1/me')  # LOAD USER PROFILE
    gebruiker = User(me)  # Initialize user

    # COLLECT THE MOST LISTENED TRACKS OF THE USER
    # THE FEATURES VARIABLE INDICATES WHICH FEATURE VALUE OF THE SONGS NEED TO BE ADDED TO THE DICTONARY
    # THE NUMBER OF TOP TRACKS INDICATE THE NUMBER OF TOP TRACKS THAT WE REQUEST FROM SPOTIFY, TOO MANY CAUSE
    # THE API TO TIME OUT

    gebruiker.get_top_tracks(FEATURES, NUMBER_OF_TOP_TRACKS_TO_COLLECT)  # Collect the top tracks of the user

    # CHOOSE A RANDOM SONG FROM THE TOP TRACKS TO SERVE AS INITIAL SEED SONG
    gebruiker.choose_seed_song()

    song_display_dic = gebruiker.most_listened_tracks

    gebruiker.get_devices()

    return redirect(url_for('find_alternative_songs', seed=gebruiker.seed_song['id']))


@app.route('/find_alternative_songs', methods=['GET', 'POST'])
def find_alternative_songs():

    global seed
    global alternative_song_dic
    global gebruiker

    # A GET REQUEST IS MADE WHEN THE SEED SONG IS INITIALLY CHOSEN

    if request.method == 'GET':
        seed = request.args.get('seed')

    # A POST REQUEST IS MADE WHEN THE USER SELECTS AN ALTERNATIVE SEED SONG

    if request.method == 'POST':
        seed = str(request.form['song'])

    # GET RECOMMENDATIONS BASED ON THE RANDOMLY SELECTED SEED SONG
    # ALSO SORT THESE ALTERNATIVE SONGS BASED ON THE FEATURES GIVEN
    # IN FEATURES_TO_SHOW_ALTERNATIVE_SONGS_ON

    alternative_song_dic = gebruiker.select_alternative_songs(seed, FEATURES_TO_SHOW_ALTERNATIVE_SONGS_ON)

    return render_template('user_seed_selection.html', seed_id=seed, alternatives=alternative_song_dic,
                           song_dic=gebruiker.most_listened_tracks)


@app.route('/calrec', methods=['GET', 'POST'])
def calrec():
    # IDENTIFY GLOBAL VARIABLES

    global gebruiker, seed_identifier

    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT

    if request.method == 'POST':
        seed_identifier = str(request.form['selected_song'])

    gebruiker.calculate_recommendations(seed_identifier, ['valence'])

    # THE FIRST LIST IS RANDOMLY CHOSEN, IFORM THE SYSTEM THAT THIS IS THE CURRENT LIST

    gebruiker.current_list = gebruiker.first_list

    return redirect(url_for('play_song', gebruiker=gebruiker))


@app.route('/play_song', methods=['GET', 'POST'])
def play_song():
    return render_template('playing_song.html')


@app.route('/music_player', methods=['GET', 'POST'])
def music_player():
    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    global gebruiker

    name = 'noName'
    artist = 'noArtist'
    cover = 'noCover'
    progress = 'noProgress'
    timeout = 10000
    nexttrack = 0

    # CHECK CURRENTLY PLAYING TRACK
    status_playing = spotify.request('/v1/me/player/currently-playing')

    # NO SONG IS LOADED (204)
    if status_playing.status == 204:
        # NO SONG IS PLAYING, PLAY SONG

        id_to_listen = gebruiker.recommendations_to_user['condition_' + str(str(gebruiker.condition))][
            'list_' + str(gebruiker.current_list)][gebruiker.current_song]

        payload = {"uris": ["spotify:track:" + id_to_listen]}
        url = "https://api.spotify.com/v1/me/player/play"

        spotify.put(url=url, data=payload, format='json')

        time.sleep(1)

        status_playing = spotify.request('/v1/me/player/currently-playing')

        name = status_playing.data['item']['name']
        artist = status_playing.data['item']['artists'][0]['name']
        cover = status_playing.data['item']['album']['images'][1]['url']

    # SONG IS LOADED, AND PLAYING (200)
    if status_playing.status == 200:

        # IF DEVICE IS AVAILABLE
        if status_playing.data:

            # IF THE SONG IS PLAYED
            if status_playing.data['is_playing']:

                name = status_playing.data['item']['name']
                artist = status_playing.data['item']['artists'][0]['name']
                cover = status_playing.data['item']['album']['images'][1]['url']

                # WHEN THE TRACK IS PLAYING, WE NEED TO CHECK IF IT IS ALREADY OVER THE TIME LIMIT
                if status_playing.data['progress_ms'] < 25000:

                    nexttrack = 0

                else:

                    # PAUSE THE SONG
                    url = "https://api.spotify.com/v1/me/player/pause"
                    spotify.put(url=url, format='json')

                    # UPDATE PARAMETERS
                    gebruiker.current_song += 1

                    if gebruiker.current_song == 5:
                        gebruiker.current_song = 0
                        if gebruiker.first_list != gebruiker.current_list:
                            return 'experiment done'

                        elif gebruiker.first_list == gebruiker.current_list:
                            if gebruiker.current_list == 1:
                                gebruiker.current_list = 2
                            elif gebruiker.current_list == 2:
                                gebruiker.current_list = 1
                            else:
                                return 'error in list'

                        else:
                            return ' error in current list'

                    print('Next list: %s, Next song: %s' % (str(gebruiker.current_list), str(gebruiker.current_song)))

                    nexttrack = 1

            # IF THE SONG IS PAUSED, START OF THE EXPERIMENT
            else:

                print(print('I will play: Next list: %s, Next song: %s' % (
                str(gebruiker.current_list), str(gebruiker.current_song))))

                id_to_listen = gebruiker.recommendations_to_user['condition_' + str(str(gebruiker.condition))][
                    'list_' + str(gebruiker.current_list)][gebruiker.current_song]

                payload = {"uris": ["spotify:track:" + id_to_listen]}
                url = "https://api.spotify.com/v1/me/player/play"

                spotify.put(url=url, data=payload, format='json')

                time.sleep(1)

                status_playing = spotify.request('/v1/me/player/currently-playing')

                name = status_playing.data['item']['name']
                artist = status_playing.data['item']['artists'][0]['name']
                cover = status_playing.data['item']['album']['images'][1]['url']
                nexttrack = 0

    # SONG IS LOADED, AND PAUSED (200)

    # NO DEVICES AVAILABLE (200)

    # COULD NOT GET INTO (202)

    if status_playing.status == 202:
        time.sleep(5)

    return jsonify({'name': name,
                    'artist': artist,
                    'cover': cover,
                    'progress': progress,
                    'timeout': timeout,
                    'nexttrack': nexttrack,
                    'url': url_for('question')})


@app.route('/question', methods=['GET', 'POST'])
def question():
    return render_template('question.html', gebruiker=gebruiker)


@app.route('/update_device', methods=['GET', 'POST'])
def update_device():
    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    data = {'device': 'noDevice', 'name': 'noDevice', 'type': 'noDevice'}

    devices = spotify.request('/v1/me/player/devices')

    if devices.status == 202:
        time.sleep(5)

    elif devices.status == 200:
        print(devices.status)
        print(devices.data['devices'])
        active_device = list(filter(lambda x: x['is_active'] == True, devices.data['devices']))
        if active_device:
            print(active_device)
            data = {'device': active_device[0]['id'], 'name': active_device[0]['name'],
                    'type': active_device[0]['type']}

    return jsonify(data)


if __name__ == '__main__':
    app.run(host='127.0.0.1')
