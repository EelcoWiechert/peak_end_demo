from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app
from flask_oauthlib.client import OAuth, OAuthException
from seed_song_determine import *
from user_definition import *

import time
from create_plot import *
import pandas as pd

import random

# VARIABLES
FEATURES_TO_PLOT = ['valence','energy']#, 'danceability', 'popularity'] #,"speechiness","acousticness","instrumentalness","liveness"]

FEATURES = ['valence','energy', 'danceability',"acousticness","instrumentalness"]

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
    return spotify.authorize(callback=callback, scope="user-top-read user-read-playback-state user-modify-playback-state user-read-recently-played")

@app.route('/login/authorized')
def spotify_authorized():
    resp = spotify.authorized_response()
    if resp is None:
        return 'Access denied: reason={0} error={1}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )
    if isinstance(resp, OAuthException):
        return 'Access denied: {0}'.format(resp.message)
    session['oauth_token'] = (resp['access_token'], '')


    # SPOTIFY REQUESTS
    me = spotify.request('/v1/me') # LOAD USER PROFILE
    global user
    user = define_user(me)

    global song_display_dic
    song_display_dic = {}
    song_ids = []
    for song in user['top_tracks']:
        try:
            song_ids.append(song['id'])
            song_display_dic[song['id']] = {"title": song['name'], "artist": song['artists'][0]['name'],
                                            "cover": song['album']['images'][1]['url'], "preview": song['preview_url']}
        except:
            continue

    song_display_dic = get_audio_features(song_ids, user, song_display_dic, FEATURES)

    # DETERMINE A SEED SONG
    seed = random.choice(user['top_tracks'])

    return redirect(url_for('find_alternative_songs', seed=seed['id'], seed_url=seed['album']['images'][0]['url'], seed_title=seed['name'], seed_artist=seed['artists'][0]['name']))

@app.route('/find_alternative_songs', methods=['GET', 'POST'])
def find_alternative_songs():
    if request.method == 'GET':
        seed = request.args.get('seed')
        seed_url = request.args.get('seed_url')
        seed_title = request.args.get('seed_title')
        seed_artist = request.args.get('seed_artist')

    if request.method == 'POST':
        test = str(request.form['song'])
        a = test.split(',')
        seed = a[0]
        seed_url = a[3].strip()
        seed_title = a[1]
        seed_artist = a[2]

    # GET CHARACTERISTICS
    global song_display_dic
    seed_characteristcs = song_display_dic[seed]

    # DETERMINE POINT
    features_of_interest = ['valence', 'energy', 'danceability', 'acousticness','instrumentalness']

    alternative_song_dic = {}

    for feature in features_of_interest:
        alternative_song_dic[feature] = {'lower': [], 'higher': []}

    for i in range(50):
        seed_id, t_features = random.choice(list(song_display_dic.items()))
        for feature, lists in alternative_song_dic.items():
            if t_features[feature] > seed_characteristcs[feature]:
                lists['higher'].append(seed_id)
            else:
                lists['lower'].append(seed_id)

    for feature, lists in alternative_song_dic.items():
        if len(lists['higher']) > 0:
            random.shuffle(lists['higher'])
            lists['higher'] = lists['higher'][:6]
        if len(lists['lower']) > 0:
            random.shuffle(lists['lower'])
            lists['lower'] = lists['lower'][:6]

    return render_template('user_seed_selection.html', seed_id=seed, image = seed_url, title=seed_title, artist=seed_artist,
                           alternatives=alternative_song_dic, song_dic=song_display_dic)

@app.route('/recommendations1', methods=['GET', 'POST'])
def recommendations1():

    if request.method == 'POST':
        seed_id = str(request.form['selected_song'])

    VAR_FEATURE = 'valence,energy'
    peak_end = 'low,peak,low,low,end'

    return redirect(url_for('condition1', seed_id=seed_id, VAR_FEATURE=VAR_FEATURE, peak_end=peak_end))


@app.route('/condition1', methods=['GET', 'POST'])
def condition1():
    if request.method == 'GET':
        global seed_id
        seed_id = request.args.get('seed_id')
        global VAR_FEATURE
        VAR_FEATURE = request.args.get('VAR_FEATURE').split(',')
        global peak_end
        peak_end = request.args.get('peak_end').split(',')


    if request.method == 'POST':
        valence = request.form.get('valence')
        energy = request.form.get('energy')
        danceability = request.form.get('danceability')
        acousticness = request.form.get('acousticness')
        instrumentalness = request.form.get('instrumentalness')

        VAR_FEATURE =[]
        FEATURES_TEMP = [valence, energy, danceability, acousticness, instrumentalness]

        for f in FEATURES_TEMP:
            if f is not None:
                VAR_FEATURE.append(str(f))

    global song_display_dic
    print(seed_id)

    song_display_dic, good_indices = get_recommendations_con1(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end)

    stat_dic = create_stats_dic(VAR_FEATURE, good_indices, song_display_dic)

    return render_template('condition_1.html', seed=seed_id, song_dic=song_display_dic, features=FEATURES,
                           recom=good_indices, stats=stat_dic)

@app.route('/condition2', methods=['GET', 'POST'])
def condition2():
    if request.method == 'GET':
        print('ok')


    if request.method == 'POST':
        valence = request.form.get('valence')
        energy = request.form.get('energy')
        danceability = request.form.get('danceability')
        acousticness = request.form.get('acousticness')
        instrumentalness = request.form.get('instrumentalness')

        VAR_FEATURE =[]
        FEATURES_TEMP = [valence, energy, danceability, acousticness, instrumentalness]

        for f in FEATURES_TEMP:
            if f is not None:
                VAR_FEATURE.append(str(f))

    global song_display_dic
    VAR_FEATURE = ['valence','energy']

    song_display_dic, good_indices = get_recommendations_con2(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end)

    stat_dic = create_stats_dic(VAR_FEATURE, good_indices, song_display_dic)

    return render_template('condition_2.html', seed=seed_id, song_dic=song_display_dic, features=FEATURES,
                           recom=good_indices, stats=stat_dic)

@app.route('/condition3', methods=['GET', 'POST'])
def condition3():
    if request.method == 'GET':
        print('ok')


    if request.method == 'POST':
        valence = request.form.get('valence')
        energy = request.form.get('energy')
        danceability = request.form.get('danceability')
        acousticness = request.form.get('acousticness')
        instrumentalness = request.form.get('instrumentalness')

        VAR_FEATURE =[]
        FEATURES_TEMP = [valence, energy, danceability, acousticness, instrumentalness]

        for f in FEATURES_TEMP:
            if f is not None:
                VAR_FEATURE.append(str(f))

    global song_display_dic
    VAR_FEATURE = ['valence','energy']

    song_display_dic, good_indices = get_recommendations_con3(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end)

    stat_dic = create_stats_dic(VAR_FEATURE, good_indices, song_display_dic)

    return render_template('condition_3.html', seed=seed_id, song_dic=song_display_dic, features=FEATURES,
                           recom=good_indices, stats=stat_dic)

@spotify.tokengetter
def get_spotify_oauth_token():
    return session.get('oauth_token')

if __name__ == '__main__':
    app.run(host='127.0.0.1')