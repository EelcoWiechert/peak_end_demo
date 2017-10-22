from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app
from flask_oauthlib.client import OAuth, OAuthException
from create_plot import *
import sqlite3
import time
import os
import random
import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn import preprocessing
from scipy import spatial
from sklearn.neighbors import KDTree


# VARIABLES
NO_PROFILE_REPLACEMENT ="http://blog.ramboll.com/fehmarnbelt/wp-content/themes/ramboll2/images/profile-img.jpg"
NUMBER_OF_RECOMMENDED_SONGS = 10
NUMBER_OF_PLAYLISTS = 3
FEATURES_TO_PLOT = ['valence','energy', 'danceability'] #,"speechiness","acousticness","instrumentalness","liveness"]
POINT_SCALE = 5
peak_end = ['one', 'five', 'one', 'five','one', 'five', 'one', 'five','one', 'five', 'one', 'five']

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


    me = spotify.request('/v1/me') # LOAD USER PROFILE

    '''
    
    DEFINE THE USER
    
    '''

    user ={}

    if len(me.data["images"]) == 0:
        user['picture'] = NO_PROFILE_REPLACEMENT
    else:
        user['picture'] = me.data["images"][0]["url"]

    if not me.data['display_name']:
        user['name'] = str(me.data['id'])
    else:
        user['name'] = str(me.data['display_name'])

    # DEFINE RECOMMENDATIONS
    top_tracks = spotify.request('v1/me/top/tracks') # LOAD MOST PLAYED TRACKS

    # determine seed tracks
    recommendation_to_user = dict()
    recommended_items = {}
    for track in top_tracks.data["items"][:NUMBER_OF_PLAYLISTS]:
        time.sleep(0.01)
        recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(track['id']) + '&limit=100')

        # store info of recommended tracks
        rec_list = []
        for recommendation in recommendations.data['tracks']:
            rec_lib = {}
            rec_lib['id'] = recommendation['id']
            rec_lib['name'] = recommendation['name']
            rec_lib['artist'] = recommendation['artists'][0]['name']
            rec_lib['cover'] = recommendation['album']['images'][1]['url']
            rec_lib['preview'] = recommendation['preview_url']
            rec_list.append(rec_lib)
            recommended_items[track['id']] = {}
            recommended_items[track['id']]['cover'] = track['album']['images'][0]['url']
            recommended_items[track['id']]['recommendations'] = rec_list

    plot_dic = {}
    count=0
    for seed, recommendation_list in recommended_items.items():
        count+=1
        track_ids_string = ''
        for recommended_track in recommendation_list['recommendations']:
            track_ids_string += recommended_track['id'] + ','

        features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

        variables_to_plot = dict()
        for item in FEATURES_TO_PLOT:
            variables_to_plot[item] = []

        for feature, values in variables_to_plot.items():
            for track in features_recommended_tracks.data['audio_features']:
                values.append(track[feature])

        data = pd.DataFrame.from_dict(variables_to_plot)

        x = data.values
        # x_scaled = preprocessing.normalize(x)
        df = pd.DataFrame(x, columns=FEATURES_TO_PLOT)

        df2 = pd.DataFrame([[0,0,0],[1,1,1]], columns=FEATURES_TO_PLOT)

        df = df.append(df2, ignore_index=True)

        test_data_numpy = df.as_matrix()

        nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(test_data_numpy)

        distances, indices = nbrs.kneighbors(test_data_numpy)

        for test in indices[100]:
            print(test_data_numpy[test])

        for test in indices[101]:
            print(test_data_numpy[test])

        df.plot.scatter(x='valence', y='energy')
        plt.savefig(str(FEATURES_TO_PLOT[0]) + '_' + str(FEATURES_TO_PLOT[1]) + '_' + str(count) + 'test.png')

        nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.values)
        distances, indices = nbrs.kneighbors(df.values)

        good_indices = []

        one = []
        for song in indices[100][1:]:
            print(song)
            one.append({'id':recommendation_list['recommendations'][song]['id'],'title':recommendation_list['recommendations'][song]['name'],'artist':recommendation_list['recommendations'][song]['artist'], 'cover':recommendation_list['recommendations'][song]['cover'], 'preview':recommendation_list['recommendations'][song]['preview'],'indice':song, 'features':test_data_numpy[song]})
        five = []
        for song in indices[101][1:]:
            print(song)
            five.append({'id':recommendation_list['recommendations'][song]['id'],'title':recommendation_list['recommendations'][song]['name'],'artist':recommendation_list['recommendations'][song]['artist'],'cover':recommendation_list['recommendations'][song]['cover'],'preview':recommendation_list['recommendations'][song]['preview'],'indice':song, 'features':test_data_numpy[song]})

        recommendation_to_user[seed] = []
        for rat in peak_end:
            if rat == 'one':
                recommendation_to_user[seed].append(one[0])
                good_indices.append(one[0]['indice'])
                del one[0]
            elif rat == 'five':
                recommendation_to_user[seed].append(five[0])
                good_indices.append(one[0]['indice'])
                del five[0]

        plot_data = [features_recommended_tracks.data['audio_features'][i] for i in good_indices]
        plot_code = make_plot(plot_data, FEATURES_TO_PLOT)
        plot_dic[seed] = plot_code

        print(recommendation_to_user)

    return render_template('user_profile.html', user=user, top_user_tracks=top_tracks.data["items"][:NUMBER_OF_PLAYLISTS], recommendations=recommendation_to_user, plot=plot_dic)


@spotify.tokengetter
def get_spotify_oauth_token():
    return session.get('oauth_token')

from flask import request

@app.route('/mood_page', methods=['POST'])
def led_handler():
    test = str(request.form['fname']) + str(request.form['lname'])
    return test


if __name__ == '__main__':
    app.run(host='127.0.0.1')