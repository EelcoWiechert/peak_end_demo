from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app
from flask_oauthlib.client import OAuth, OAuthException
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import json
from sklearn.neighbors import NearestNeighbors
from scipy import ndimage

MAKE_PLOT = False

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

def define_user(me):

    @spotify.tokengetter
    def get_spotify_oauth_token():
        return session.get('oauth_token')

    # VARIABLES
    NO_PROFILE_REPLACEMENT ="http://blog.ramboll.com/fehmarnbelt/wp-content/themes/ramboll2/images/profile-img.jpg"

    user ={}

    # PROFILE PICTURE
    if len(me.data["images"]) == 0:
        user['picture'] = NO_PROFILE_REPLACEMENT
    else:
        user['picture'] = me.data["images"][0]["url"]

    # NAME
    if not me.data['display_name']:
        user['name'] = str(me.data['id'])
    else:
        user['name'] = str(me.data['display_name'])

    # MAKE POOL OF TOP TRACKS
    top_items =[]
    top_tracks = spotify.request('v1/me/top/tracks?limit=50')  # LOAD MOST PLAYED TRACKS
    for item in top_tracks.data["items"]:
        top_items.append(item)
    while top_tracks.data["next"] is not None:
        link = str(top_tracks.data["next"]).replace('https://api.spotify.com', '')
        top_tracks = spotify.request(link)  # LOAD MOST PLAYED TRACKS
        for item in top_tracks.data["items"]:
            top_items.append(item)

    user['top_tracks'] = top_items

    return user

def get_audio_features(list_of_ID, user, song_display_dic, features):

    songs_available = True
    while songs_available:
        # CREATE REQUEST LINK
        track_ids_string = ''
        n=0
        for ID in list_of_ID:
            n+=1
            track_ids_string += str(ID) + ','
            if n == 100:
                break

        link = track_ids_string[:-1]
        features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(link))

        for track in features_recommended_tracks.data['audio_features']:
            for F in features:
                if track['id'] not in song_display_dic:
                    song_display_dic[track['id']] = {}
                song_display_dic[track['id']][F] = track[F]

        list_of_ID = list_of_ID[100:]

        if len(list_of_ID) < 1:
            songs_available = False

    if MAKE_PLOT:
        # create plot
        features_of_interest = ['valence','energy', 'danceability', "speechiness", "acousticness", "instrumentalness", "liveness"]
        datalists = {}

        for feature in features_of_interest:
            datalists[feature] = []

        for track, features in song_display_dic.items():
            for f in features_of_interest:
                datalists[f].append(features[f])

        # Two subplots, unpack the axes array immediately
        n_bins = 20
        plt.rcParams.update({'font.size': 6})
        f, (ax1,ax2,ax3,ax4,ax5,ax6,ax7) = plt.subplots(1, len(features_of_interest), sharey=True)
        ax1.hist(datalists[features_of_interest[0]], n_bins, normed=1, histtype='bar', stacked=True)
        ax2.hist(datalists[features_of_interest[1]], n_bins, normed=1, histtype='bar', stacked=True)
        ax3.hist(datalists[features_of_interest[2]], n_bins, normed=1, histtype='bar', stacked=True)
        ax4.hist(datalists[features_of_interest[3]], n_bins, normed=1, histtype='bar', stacked=True)
        ax5.hist(datalists[features_of_interest[4]], n_bins, normed=1, histtype='bar', stacked=True)
        ax6.hist(datalists[features_of_interest[5]], n_bins, normed=1, histtype='bar', stacked=True)
        ax7.hist(datalists[features_of_interest[6]], n_bins, normed=1, histtype='bar', stacked=True)

        ax1.set_title(features_of_interest[0], fontsize=6)
        ax2.set_title(features_of_interest[1], fontsize=6)
        ax3.set_title(features_of_interest[2], fontsize=6)
        ax4.set_title(features_of_interest[3], fontsize=6)
        ax5.set_title(features_of_interest[4], fontsize=6)
        ax6.set_title(features_of_interest[5], fontsize=6)
        ax7.set_title(features_of_interest[6], fontsize=6)

        ax1.set_xlim(0, 1)
        ax2.set_xlim(0, 1)
        ax3.set_xlim(0, 1)
        ax4.set_xlim(0, 1)
        ax5.set_xlim(0, 1)
        ax6.set_xlim(0, 1)
        ax7.set_xlim(0, 1)

        with open('user_data.json') as data_file:
            data = json.load(data_file)

        data[user['name']] = datalists

        with open('user_data.json', 'w') as file:
            file.write(json.dumps(data))

        plt.savefig('figure_map/user_profile_' + user['name'] + '.png', dpi=1000)

    return song_display_dic

def get_recommendations_con1(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end):
    recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(seed_id) + '&limit=100')

    rec_ids = []

    for recommendation in recommendations.data['tracks']:
        song_display_dic[recommendation['id']] = {"title": recommendation['name'],
                                                      "artist": recommendation['artists'][0]['name'],
                                                      "cover": recommendation['album']['images'][1]['url'],
                                                      "preview": recommendation['preview_url']}
        rec_ids.append(recommendation['id'])

    track_ids_string = ''
    for id in rec_ids:
        track_ids_string += str(id) + ','

    track_ids_string = track_ids_string[:-1]

    features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

    # Add info to general dic
    for track in features_recommended_tracks.data['audio_features']:
        if track['id'] not in song_display_dic:
            song_display_dic[track['id']] = {}
        for F in FEATURES:
            song_display_dic[track['id']][F] = track[F]

    variables_to_plot2 = dict()
    for FEAT in FEATURES:
        variables_to_plot2[FEAT] = []

    # Add features
    for F, V in variables_to_plot2.items():
        for track in features_recommended_tracks.data['audio_features']:
            V.append(track[F])

    data2 = pd.DataFrame.from_dict(variables_to_plot2)

    low_point = []
    high_point = []

    for VAR in VAR_FEATURE:
        low_point.append(0)
        high_point.append(1)

    data_filtered = data2.filter(items=VAR_FEATURE)


    df2 = pd.DataFrame([low_point, high_point], columns=VAR_FEATURE)
    df = data_filtered.append(df2, ignore_index=True)

    # SPLIT THE SONGS IN TWO CONTAINERS
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())
    points = []
    points.append(list(df.iloc[indices[101][1]])) # PEAK
    points.append(list(df.iloc[indices[101][9]])) # END

    print(points)

    if len(VAR_FEATURE) > 0:
        x = [p[0] for p in points]
    if len(VAR_FEATURE) > 1:
        y = [p[1] for p in points]
    if len(VAR_FEATURE) > 2:
        z = [p[2] for p in points]

    if len(VAR_FEATURE) == 1:
        centroid_middle_all_data = [sum(x) / len(x)]
    if len(VAR_FEATURE) == 2:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y)]
    if len(VAR_FEATURE) == 3:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y), sum(z) / len(z)]

    df3 = pd.DataFrame([centroid_middle_all_data], columns=VAR_FEATURE)
    df = df.append(df3, ignore_index=True)
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())

    good_indices = {'cond_1':[], 'cond_2':[]}

    #df.plot.scatter(x='valence', y='energy')
    #df.plot.scatter(x=centroid_middle_all_data[0], y=centroid_middle_all_data[1], color='red')
    #plt.savefig(str(VAR_FEATURE[0]) + '_' + str(VAR_FEATURE[1]) + 'test.png')

    low = []
    for song in indices[100][1:]:
        try:
            low.append(rec_ids[song])
        except:
            continue

    high = []
    for song in indices[101][1:]:
        try:
            high.append(rec_ids[song])
        except:
            continue

    end = []
    for song in indices[101][6:]:
        try:
            end.append(rec_ids[song])
        except:
            continue

    middle = []
    for song in indices[102][1:]:
        try:
            middle.append(rec_ids[song])
        except:
            continue

    # MAKE LIST WITH SONGS TO RECOMMEND
    for rat in peak_end:
        if rat == 'low':
            good_indices['cond_1'].append(low[0])
            del low[0]
        elif rat == 'peak':
            good_indices['cond_1'].append(high[0])
            del high[0]
        elif rat == 'end':
            good_indices['cond_1'].append(end[0])
            del end[0]
        good_indices['cond_2'].append(middle[0])
        del middle[0]

    return song_display_dic, good_indices

def get_recommendations_con2(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end):
    recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(seed_id) + '&limit=100')

    rec_ids = []

    for recommendation in recommendations.data['tracks']:
        song_display_dic[recommendation['id']] = {"title": recommendation['name'],
                                                      "artist": recommendation['artists'][0]['name'],
                                                      "cover": recommendation['album']['images'][1]['url'],
                                                      "preview": recommendation['preview_url']}
        rec_ids.append(recommendation['id'])

    track_ids_string = ''
    for id in rec_ids:
        track_ids_string += str(id) + ','

    track_ids_string = track_ids_string[:-1]

    features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

    # Add info to general dic
    for track in features_recommended_tracks.data['audio_features']:
        if track['id'] not in song_display_dic:
            song_display_dic[track['id']] = {}
        for F in FEATURES:
            song_display_dic[track['id']][F] = track[F]

    variables_to_plot2 = dict()
    for FEAT in FEATURES:
        variables_to_plot2[FEAT] = []

    # Add features
    for F, V in variables_to_plot2.items():
        for track in features_recommended_tracks.data['audio_features']:
            V.append(track[F])

    data2 = pd.DataFrame.from_dict(variables_to_plot2)

    low_point = []
    high_point = []

    for VAR in VAR_FEATURE:
        low_point.append(0)
        high_point.append(1)

    data_filtered = data2.filter(items=VAR_FEATURE)


    df2 = pd.DataFrame([low_point, high_point], columns=VAR_FEATURE)
    df = data_filtered.append(df2, ignore_index=True)

    # SPLIT THE SONGS IN TWO CONTAINERS
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())

    points = []
    points.append(list(df.iloc[indices[100][1]])) # PEAK
    points.append(list(df.iloc[indices[101][1]])) # END

    if len(VAR_FEATURE) > 0:
        x = [p[0] for p in points]
    if len(VAR_FEATURE) > 1:
        y = [p[1] for p in points]
    if len(VAR_FEATURE) > 2:
        z = [p[2] for p in points]

    if len(VAR_FEATURE) == 1:
        centroid_middle_all_data = [sum(x) / len(x)]
    if len(VAR_FEATURE) == 2:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y)]
    if len(VAR_FEATURE) == 3:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y), sum(z) / len(z)]

    df3 = pd.DataFrame([centroid_middle_all_data], columns=VAR_FEATURE)
    df = df.append(df3, ignore_index=True)
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())

    good_indices = {'cond_1':[], 'cond_2':[]}
    low = []
    for song in indices[100][1:]:
        try:
            low.append(rec_ids[song])
        except:
            continue

    high = []
    for song in indices[101][1:]:
        try:
            high.append(rec_ids[song])
        except:
            continue

    end = []
    for song in indices[101][6:]:
        try:
            end.append(rec_ids[song])
        except:
            continue

    middle = []
    for song in indices[102][1:]:
        try:
            middle.append(rec_ids[song])
        except:
            continue

    # MAKE LIST WITH SONGS TO RECOMMEND
    for rat in peak_end:
        if rat == 'low':
            good_indices['cond_1'].append(low[0])
            del low[0]
        elif rat == 'peak':
            good_indices['cond_1'].append(high[0])
            del high[0]
        elif rat == 'end':
            good_indices['cond_1'].append(end[0])
            del end[0]
        good_indices['cond_2'].append(middle[0])
        del middle[0]

    return song_display_dic, good_indices

def get_recommendations_con3(FEATURES, VAR_FEATURE, song_display_dic, seed_id, peak_end):
    recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(seed_id) + '&limit=100')

    rec_ids = []

    for recommendation in recommendations.data['tracks']:
        song_display_dic[recommendation['id']] = {"title": recommendation['name'],
                                                      "artist": recommendation['artists'][0]['name'],
                                                      "cover": recommendation['album']['images'][1]['url'],
                                                      "preview": recommendation['preview_url']}
        rec_ids.append(recommendation['id'])

    track_ids_string = ''
    for id in rec_ids:
        track_ids_string += str(id) + ','

    track_ids_string = track_ids_string[:-1]

    features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

    # Add info to general dic
    for track in features_recommended_tracks.data['audio_features']:
        if track['id'] not in song_display_dic:
            song_display_dic[track['id']] = {}
        for F in FEATURES:
            song_display_dic[track['id']][F] = track[F]

    variables_to_plot2 = dict()
    for FEAT in FEATURES:
        variables_to_plot2[FEAT] = []

    # Add features
    for F, V in variables_to_plot2.items():
        for track in features_recommended_tracks.data['audio_features']:
            V.append(track[F])

    data2 = pd.DataFrame.from_dict(variables_to_plot2)

    low_point = []
    high_point = []

    for VAR in VAR_FEATURE:
        low_point.append(0)
        high_point.append(1)

    data_filtered = data2.filter(items=VAR_FEATURE)


    df2 = pd.DataFrame([low_point, high_point], columns=VAR_FEATURE)
    df = data_filtered.append(df2, ignore_index=True)

    # SPLIT THE SONGS IN TWO CONTAINERS
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())

    low = []
    for song in indices[100][1:]:
        try:
            low.append(song)
        except:
            continue

    high = []
    for song in indices[101][1:]:
        try:
            high.append(song)
        except:
            continue

    end = []
    for song in indices[101][6:]:
        try:
            end.append(song)
        except:
            continue

    temp_list = []

    for rat in peak_end:
        if rat == 'low':
            temp_list.append(low[0])
            del low[0]
        elif rat == 'peak':
            temp_list.append(high[0])
            del high[0]
        elif rat == 'end':
            temp_list.append(end[0])
            del end[0]

    l_dic = {}
    for VAR in VAR_FEATURE:
        l_dic[VAR] = []

    for item in temp_list:
        for VAR in VAR_FEATURE:
            l_dic[VAR].append(df.iloc[item][VAR])

    for VAR in VAR_FEATURE:
        l_dic[VAR] = sum(l_dic[VAR]) / len(l_dic[VAR])

    centroid_middle_all_data = []

    for feature, value in l_dic.items():
        centroid_middle_all_data.append(value)


    df3 = pd.DataFrame([centroid_middle_all_data], columns=VAR_FEATURE)
    df = df.append(df3, ignore_index=True)
    nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df.as_matrix())
    distances, indices = nbrs.kneighbors(df.as_matrix())

    good_indices = {'cond_1':[], 'cond_2':[]}

    low = []
    for song in indices[100][1:]:
        try:
            low.append(rec_ids[song])
        except:
            continue

    high = []
    for song in indices[101][1:]:
        try:
            high.append(rec_ids[song])
        except:
            continue

    end = []
    for song in indices[101][6:]:
        try:
            end.append(rec_ids[song])
        except:
            continue

    middle = []
    for song in indices[102][1:]:
        try:
            middle.append(rec_ids[song])
        except:
            continue

    # MAKE LIST WITH SONGS TO RECOMMEND
    for rat in peak_end:
        if rat == 'low':
            good_indices['cond_1'].append(low[0])
            del low[0]
        elif rat == 'peak':
            good_indices['cond_1'].append(high[0])
            del high[0]
        elif rat == 'end':
            good_indices['cond_1'].append(end[0])
            del end[0]
        good_indices['cond_2'].append(middle[0])
        del middle[0]

    return song_display_dic, good_indices

def create_stats_dic(VAR_FEATURE, good_indices, song_display_dic):
    stat_dic = {'cond_1':{}, 'cond_2':{}}
    for condition, stats in stat_dic.items():

        for F in VAR_FEATURE:
            stats[F] = {'raw': [], 'average': 0, 'peak_end': 0}

        for song in good_indices[condition]:
            for F in VAR_FEATURE:
                stats[F]['raw'].append(song_display_dic[song][F])

        for F in VAR_FEATURE:
            stats[F]['average'] = sum(stats[F]['raw']) / len(stats[F]['raw'])
            stats[F]['peak_end'] = (max(stats[F]['raw'][:-1]) + stats[F]['raw'][-1]) / 2

    return stat_dic

