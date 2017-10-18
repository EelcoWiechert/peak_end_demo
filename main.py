from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app
from flask_oauthlib.client import OAuth, OAuthException
from create_plot import *
import sqlite3
import time
import os
import random


# VARIABLES
NO_PROFILE_REPLACEMENT ="http://blog.ramboll.com/fehmarnbelt/wp-content/themes/ramboll2/images/profile-img.jpg"


# os.remove('example.db')
# conn = sqlite3.connect('example.db')
# c = conn.cursor()
# c.execute('''CREATE TABLE users (id text, name text, pic text)''')
# c.execute('''CREATE TABLE recommendations (artist text, trackname text, url text, id text, user text)''')
# conn.commit()

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

    # DEFINE THE USER

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

    recommended_items ={}
    for track in top_tracks.data["items"][:3]:
        time.sleep(0.1)
        recommendations = spotify.request('/v1/recommendations?seed_tracks=' + str(track['id']) + '&limit=5')
        rec_list = []
        for recommendation in recommendations.data['tracks']:
            rec_lib = {}
            rec_lib['id'] = recommendation['id']
            rec_lib['name'] = recommendation['name']
            rec_lib['artist'] = recommendation['artists'][0]['name']
            rec_list.append(rec_lib)
            recommended_items[track['id']] = rec_list

    plot_dic={}
    for original, recommendation in recommended_items.items():
        plot_code = make_plot()
        plot_dic[original] = plot_code

    return render_template('user_profile.html', user=user, top_tracks=top_tracks.data["items"][:3], recommendations=recommended_items, plot=plot_dic)


@spotify.tokengetter
def get_spotify_oauth_token():
    return session.get('oauth_token')

if __name__ == '__main__':
    app.run(host='127.0.0.1')