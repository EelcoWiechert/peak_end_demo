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

    gebruiker.load_questions()

    # COLLECT THE MOST LISTENED TRACKS OF THE USER
    # THE FEATURES VARIABLE INDICATES WHICH FEATURE VALUE OF THE SONGS NEED TO BE ADDED TO THE DICTONARY
    # THE NUMBER OF TOP TRACKS INDICATE THE NUMBER OF TOP TRACKS THAT WE REQUEST FROM SPOTIFY, TOO MANY CAUSE
    # THE API TO TIME OUT

    gebruiker.get_top_tracks(FEATURES, NUMBER_OF_TOP_TRACKS_TO_COLLECT)  # Collect the top tracks of the user

    # CHOOSE A RANDOM SONG FROM THE TOP TRACKS TO SERVE AS INITIAL SEED SONG
    gebruiker.choose_seed_song()

    song_display_dic = gebruiker.most_listened_tracks

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
    global status

    # POST REQUEST MADE BY THE USER THAT SELECTS TO GO TO THE EXPERIMENT

    if request.method == 'POST':
        seed_identifier = str(request.form['selected_song'])

    gebruiker.calculate_recommendations(seed_identifier, ['energy'])

    # THE FIRST LIST IS RANDOMLY CHOSEN, FORM THE SYSTEM THAT THIS IS THE CURRENT LIST

    gebruiker.current_list = gebruiker.first_list

    status = 'listeningList1'

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
    global status

    name = 'noName'
    artist = 'noArtist'
    cover = 'noCover'
    progress = 'noProgress'
    timeout = 10000
    nexttrack = 0
    hold = 0


    print('status')
    print(status)
    print(gebruiker.no_more_questions)

    # CHECK CURRENTLY PLAYING TRACK
    status_playing = spotify.request('/v1/me/player/currently-playing')
    print('Status Player: %s' % str(status_playing.status))

    # NO SONG IS LOADED (204) CAN ONLY HAPPEN AT THE START OF THE EXPERIMENT
    if status_playing.status == 204:

        print('')
        print('-------------------------------------------------------------')
        print('')
        print('Player status, status = %s' % (str(status_playing.status)))

        # NO SONG IS PLAYING, PLAY SONG
        id_to_listen = gebruiker.recommendations_to_user['condition_' + str(gebruiker.condition)][
            'list_' + str(gebruiker.current_list)][gebruiker.current_song]
        print('Start playing: %s' % id_to_listen)

        # PLAY SONG
        payload = {"uris": ["spotify:track:" + id_to_listen]}
        url = "https://api.spotify.com/v1/me/player/play?device_id=" + str(gebruiker.active_device['id'])

        spotify.put(url=url, data=payload, format='json')
        gebruiker.no_more_questions = False
        gebruiker.load_questions()  # RELOAD QUESTIONS

        print('')
        print('-------------------------------------------------------------')
        print('')

    # SONG IS LOADED, AND PLAYING (200)
    if status_playing.status == 200:

        progress = status_playing.data['progress_ms']

        # IF THE SONG IS PLAYED
        if status_playing.data['is_playing']:

            print('')
            print('-------------------------------------------------------------')
            print('')

            print('Currently playing song %s of 5 [List %s]' % (str(gebruiker.current_song + 1),str(gebruiker.current_list)))

            name = status_playing.data['item']['name']
            artist = status_playing.data['item']['artists'][0]['name']
            cover = status_playing.data['item']['album']['images'][1]['url']

            # WHEN THE TRACK IS PLAYING, WE NEED TO CHECK IF IT IS OVER THE TIME LIMIT
            if status_playing.data['progress_ms'] > 25000 and gebruiker.no_more_questions:

                # AT END OF SONG, PAUSE THE SONG
                url = "https://api.spotify.com/v1/me/player/pause"
                spotify.put(url=url, format='json')
                gebruiker.current_song += 1

                # AT END OF LIST
                if gebruiker.current_song == 5:
                    gebruiker.current_song = 0

                    # IF THE USER IS AT ITS FIRST LIST
                    if gebruiker.first_list == gebruiker.current_list:
                        if gebruiker.current_list == 1:
                            gebruiker.current_list = 2
                        else:
                            gebruiker.current_list = 1

                        status = 'evaluateList1'
                    else:
                        gebruiker.done = True
                        status = 'evaluateList2'

            print('')
            print('-------------------------------------------------------------')
            print('')

        # IF THE SONG IS PAUSED (START OF THE EXPERIMENT, DURING QUESTION LIST, END OF EXPERIMENT
        # WE NEED TO MAKE SURE THAT WE ARE NOT PAUSED BECAUSE WE ARE EVALUATING THE LIST
        elif not (status == 'evaluateList1' or status == 'evaluateList2'):
            if gebruiker.no_more_questions:
                print('')
                print('-------------------------------------------------------------')
                print('')
                print('No more questions, start playing song from pause')
                print(gebruiker.no_more_questions)
                id_to_listen = gebruiker.recommendations_to_user['condition_' + str(gebruiker.condition)][
                    'list_' + str(gebruiker.current_list)][gebruiker.current_song]

                payload = {"uris": ["spotify:track:" + id_to_listen]}
                url = "https://api.spotify.com/v1/me/player/play"

                spotify.put(url=url, data=payload, format='json')
                gebruiker.no_more_questions = False
                gebruiker.load_questions()  # RELOAD QUESTIONS

                status_playing = spotify.request('/v1/me/player/currently-playing')

                name = status_playing.data['item']['name']
                artist = status_playing.data['item']['artists'][0]['name']
                cover = status_playing.data['item']['album']['images'][1]['url']
                nexttrack = 0

                print('')
                print('-------------------------------------------------------------')
                print('')

            else:
                print('')
                print('-------------------------------------------------------------')
                print('')
                print('Song is paused, waiting to play next song till all questions are answered')
                print('')
                print('-------------------------------------------------------------')
                print('')

        elif not (status == 'evaluateList1' or status == 'evaluateList2'):

            print('')
            print('-------------------------------------------------------------')
            print('')
            print('Evaluating list')
            print('')
            print('-------------------------------------------------------------')
            print('')

    # BAD CONNECTION
    if status_playing.status == 202:

        print('')
        print('-------------------------------------------------------------')
        print('')
        print('Error 202')
        print('')
        print('-------------------------------------------------------------')
        print('')

        time.sleep(5)

    return jsonify({'name': name,
                    'artist': artist,
                    'cover': cover,
                    'progress': progress,
                    'timeout': timeout,
                    'stage' : status,
                    'nexttrack': gebruiker.no_more_questions,
                    'hold': hold})


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
        list = gebruiker.current_list
        song = gebruiker.current_song

        # TRY TO OPEN AN EXISTING FILE

        try:
            with open(str(gebruiker.name) + '_answers.txt', 'rb') as fp:
                itemlist = pickle.load(fp)

        # IF NO EXISTING FILE IS AVAILABLE, CREATE AN EMPTY LIST
        except:
            itemlist = []

        itemlist.append({'answer' : answer, 'question' : question, 'list' : list, 'song': song, 'progress':progress})

        print(itemlist)

        # DUMP THE DATA IN THE FILE
        with open(str(gebruiker.name) + '_answers.txt', 'wb') as fp:
            pickle.dump(itemlist, fp)

        return 'OK'

@app.route('/review_list', methods=['GET'])
def review_list():

    gebruiker.load_questions()
    gebruiker.no_more_questions = True

    return render_template('question.html', questions=gebruiker.questions)


@app.route('/router', methods=['POST'])
def router():

    global status

    if request.method == 'POST':
        valenceLevel = request.form['valence']
        energyLevel = request.form['energy']

    print('Level of energy: %s, Level of valence: %s' % (str(energyLevel), str(valenceLevel)))
    print('Gebruiker done: %s' % gebruiker.done)

    try:
        with open(str(gebruiker.name) + '_answers.txt', 'rb') as fp:
            itemlist = pickle.load(fp)

    # IF NO EXISTING FILE IS AVAILABLE, CREATE AN EMPTY LIST
    except:
        itemlist = []

    itemlist.append({'question': 'overall', 'overallEnergy': energyLevel, 'overallValence': valenceLevel})

    # DUMP THE DATA IN THE FILE
    with open(str(gebruiker.name) + '_answers.txt', 'wb') as fp:
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
    app.run(host='127.0.0.1')
