from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, current_app
from flask_oauthlib.client import OAuth, OAuthException
import matplotlib.pyplot as plt
import pandas as pd
import random
import pickle
import datetime
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


def center_point(points):
    if len(points[0]) > 0:
        x = [p[0] for p in points]
    if len(points[0]) > 1:
        y = [p[1] for p in points]
    if len(points[0]) > 2:
        z = [p[2] for p in points]

    if len(points[0]) == 1:
        centroid_middle_all_data = [sum(x) / len(x)]
    if len(points[0]) == 2:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y)]
    if len(points[0]) == 3:
        centroid_middle_all_data = [sum(x) / len(x), sum(y) / len(y), sum(z) / len(z)]

    return centroid_middle_all_data


class User(object):

    # Class to load the user and its top tracks

    def __init__(self, me):

        @spotify.tokengetter
        def get_spotify_oauth_token():
            return session.get('oauth_token')

        # Initialize name

        if not me.data['display_name']:
            self.name = str(me.data['id'])
        else:
            self.name = str(me.data['display_name'])

        # Initialize profile picture

        NO_PROFILE_REPLACEMENT = "http://blog.ramboll.com/fehmarnbelt/" \
                                 "wp-content/themes/ramboll2/images/profile-img.jpg"  # No profile photo link

        if len(me.data["images"]) == 0:
            self.profile_picture = NO_PROFILE_REPLACEMENT
        else:
            self.profile_picture = me.data["images"][0]["url"]

        # Intitialize other information
        self.most_listened_tracks = []
        self.seed_song = dict()
        self.first_list = random.choice(['list_1','list_2'])
        self.current_list = 0
        self.current_song = 0
        self.status = 0
        self.devices = dict()
        self.active_device = {"id": "noDevice",
                              "is_active": "noDevice",
                              "is_restricted": "noDevice",
                              "name": "noDevice",
                              "type": "noDevice",
                              "volume_percent": "noDevice"
                              }
        self.recommendations = []
        self.done = False
        self.no_more_questions = False
        self.top_tracks = None
        self.song_done = False

        itemlist = []

        # DUMP THE DATA IN THE FILE
        with open(str(self.name) + '_answers.txt', 'wb') as fp:
            pickle.dump(itemlist, fp)

    def get_top_tracks(self, features, NUMBER_OF_TOP_TRACKS_TO_COLLECT):

        # Initizalize tokengetter

        @spotify.tokengetter
        def get_spotify_oauth_token():
            return session.get('oauth_token')

        # Load the basic information to the user object

        top_track_link = 'v1/me/top/tracks?limit=100'

        while len(self.most_listened_tracks) < NUMBER_OF_TOP_TRACKS_TO_COLLECT:

            top_track_data = spotify.request(top_track_link)  # LOAD MOST PLAYED TRACKS

            self.most_listened_tracks.extend(top_track_data.data["items"])

            if top_track_data.data["next"] is not None:
                top_track_link = str(top_track_data.data["next"]).replace('https://api.spotify.com', '')
            else:
                break  # break when there is no next page

        DF_top_tracks = pd.DataFrame(self.most_listened_tracks)
        DF_top_tracks.to_csv('user_data/' + str(self.name) + '_toptracks.txt')  # write the top tracks to a file for later analysis
        self.most_listened_tracks = {x["id"]: x for x in self.most_listened_tracks}
        list_of_ID = list(DF_top_tracks['id'])

        # Get audio features

        while len(list_of_ID) > 0:
            track_ids_string = ''  # CREATE REQUEST LINK
            for ID in list_of_ID[:100]: # REQUEST THE AUDIO FEATURES PER 100
                track_ids_string += str(ID) + ','
            link = track_ids_string[:-1]
            features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(link))

            if self.top_tracks:
                self.top_tracks.append(pd.DataFrame(features_recommended_tracks.data['audio_features']))
            else:
                self.top_tracks = pd.DataFrame(features_recommended_tracks.data['audio_features'])

            for track in features_recommended_tracks.data['audio_features']:
                for F in features:
                    # Try to add the features to the dictonary. If this gives an error, the song is not in the dictionary
                    try:
                        self.most_listened_tracks[track['id']][F] = track[F]
                    except:
                        continue

            list_of_ID = list_of_ID[100:]

        number_of_tracks = len(list(self.top_tracks.index))
        number_to_remove = number_of_tracks * 0.40

        remove = self.top_tracks.nsmallest(int(number_to_remove), ['energy'])
        remove = remove.append(self.top_tracks.nlargest(int(number_to_remove), ['energy']))

        self.top_tracks = pd.concat([self.top_tracks, remove]).drop_duplicates(keep=False)

        if len(list(self.top_tracks.index)) > 15:
            self.top_tracks = self.top_tracks.sample(n=15)
        else:
            self.top_tracks = self.top_tracks.sample(n=len(list(self.top_tracks.index)))

        self.top_tracks.to_csv('user_data/' + str(self.name) + '_recommended_tracks.txt')  # write the top tracks to a file for later analysis

    '''
    
    Load the questions for the user
    
    '''

    def load_questions(self):
        self.questions = json.load(open('questions_during_listening.json'))

    '''
    
    Calculate experiment
    
    '''

    def calculate_recommendations(self, seed_id, features):

        @spotify.tokengetter
        def get_spotify_oauth_token():
            return session.get('oauth_token')

        # GET THE SET OF RECOMMENDATIONS

        recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(seed_id) + '&limit=100')

        self.recommendations = {x["id"]: x for x in recommendations.data['tracks']}

        track_ids_string = ''
        for identifier in set(self.recommendations.keys()):
            track_ids_string += str(identifier) + ','

        track_ids_string = track_ids_string[:-1]

        features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

        for track in features_recommended_tracks.data['audio_features']:
            for F in features:
                # Try to add the features to the dictionary. If this gives an error, the song is not in the dictionary
                self.recommendations[track['id']][F] = track[F]

        self.df_features = pd.DataFrame(features_recommended_tracks.data['audio_features'])
        self.df_features.set_index('id', inplace=True)

        # CREATE AN ARRAY THAT CONTAINS THE FEATURE VALUES
        array = []

        for identifier, data in self.recommendations.items():
            array.append([data[features[0]]])

        centroid_middle_all_data = center_point(array)

        array.append([0])
        array.append([1])

        # SPLIT THE SONGS IN TWO CONTAINERS
        nbrs = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(array)
        distances, indices = nbrs.kneighbors(array)

        # CALCULATE THE AVERAGE OF THE PEAK-END LIST
        points = [[array[indices[100][1]][0]], [array[indices[101][1]][0]], [array[indices[100][2]][0]],
                  [array[indices[100][3]][0]], [array[indices[101][9]][0]]]

        centroid_list1 = center_point(points)

        # CREATE AN ARRAY THAT CONTAINS THE POINTS MARKED AS PEAK AND END
        peak_end = [list(array[indices[101][1]]), list(array[indices[101][9]])]

        centroid_peak_end = center_point(peak_end)

        array.append(centroid_peak_end)
        array.append(centroid_middle_all_data)
        array.append(centroid_list1)

        nbrs = NearestNeighbors(n_neighbors=15, algorithm='ball_tree').fit(array)
        distances, indices = nbrs.kneighbors(array)

        low = []
        for song in indices[100][1:]:
            try:
                low.append(list(self.recommendations.keys())[song])
            except:
                continue

        high = []
        for song in indices[101][1:]:
            try:
                high.append(list(self.recommendations.keys())[song])
            except:
                continue

        end = []
        for song in indices[101][9:]:
            try:
                end.append(list(self.recommendations.keys())[song])
            except:
                continue

        peak_end_value = []
        for song in indices[102][1:]:
            try:
                peak_end_value.append(list(self.recommendations.keys())[song])
            except:
                continue

        middle = []
        for song in indices[103][1:]:
            try:
                middle.append(list(self.recommendations.keys())[song])
            except:
                continue

        average = []
        for song in indices[104][1:]:
            try:
                average.append(list(self.recommendations.keys())[song])
            except:
                continue

        self.recommendations_to_user = {'list_1': [], 'list_2': []}

        # LIST 1 - PEAK_END

        self.recommendations_to_user['list_1'].append(low[0])
        self.recommendations_to_user['list_1'].append(high[0])
        self.recommendations_to_user['list_1'].append(low[1])
        self.recommendations_to_user['list_1'].append(low[2])
        self.recommendations_to_user['list_1'].append(end[0])

        # LIST 2 - AVERAGE

        self.recommendations_to_user['list_2'].append(peak_end_value[0])
        self.recommendations_to_user['list_2'].append(peak_end_value[1])
        self.recommendations_to_user['list_2'].append(peak_end_value[2])
        self.recommendations_to_user['list_2'].append(peak_end_value[3])
        self.recommendations_to_user['list_2'].append(peak_end_value[4])

        self.feature_values = {'list_1': [], 'list_2': []}

        for l, items in self.recommendations_to_user.items():
            for identifier in items:
                self.feature_values[l].append(self.recommendations[identifier][features[0]])

        # row and column sharing
        x = [1, 2, 3, 4, 5]
        f, (ax1, ax2) = plt.subplots(1, 2)

        # SET TITLE
        axis_font = {'fontname': 'Arial', 'size': '14'}

        ax1.set_title('List 1')
        ax2.set_title('List 2')

        ax1.set_ylim([0, 1])
        ax2.set_ylim([0, 1])

        ax1.plot(x, self.feature_values['list_1'])
        ax2.plot(x, self.feature_values['list_2'])
        plt.savefig('Peak-End_plot of ' + str(self.name) + '.pdf')