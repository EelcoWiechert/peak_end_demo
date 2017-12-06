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
        # self.condition = random.choice([1,2,3])
        self.condition = 3
        # self.first_list = random.choice([1,2])
        self.first_list = 1
        self.current_list = 0
        self.current_song = 0
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
        self.no_more_questions = True
        self.top_tracks = None

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

        self.most_listened_tracks = {x["id"]: x for x in self.most_listened_tracks}

        list_of_ID = list(self.most_listened_tracks.keys())

        #with open(str(self.name) + '_toptracks.txt', 'w') as fp:
            #fp.write(list_of_ID)

        # Get audio features

        while len(list_of_ID) > 0:

            # CREATE REQUEST LINK
            track_ids_string = ''

            for ID in list_of_ID[:100]:
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

            remove = self.top_tracks.nsmallest(40, 'energy')
            remove.append(self.top_tracks.nlargest(40, 'energy'))

            for track in list(remove.index):
                remove.drop([track])

            self.top_tracks = remove.sample(n=5)

            print(self.top_tracks)

    '''
    
    Load the questions for the user
    
    '''

    def load_questions(self):

        self.questions = json.load(open('questions.json'))

    '''
    
    Choose the seed song random from the users' top tracks
    
    '''

    def choose_seed_song(self):

        # CHOOSE A SEED SONG
        self.seed_song['id'] = random.choice(list(self.most_listened_tracks.keys()))
        self.seed_song['data'] = self.most_listened_tracks[self.seed_song['id']]

    '''

    Select a random set of 50 songs and postion them relative to the seed song.
    The alternative songs are presented in containers as given in the discriminating features

    '''

    def select_alternative_songs(self, seed, discriminating_features):

        # GET CHARACTERISTICS
        seed_characteristics = self.most_listened_tracks[seed]

        alternative_song_dic = {}

        for feature in discriminating_features:
            alternative_song_dic[feature] = {'lower': [], 'higher': []}

        for i in range(50):
            seed_id, t_features = random.choice(list(self.most_listened_tracks.items()))

            for feature, lists in alternative_song_dic.items():
                if t_features[feature] > seed_characteristics[feature]:
                    lists['higher'].append(seed_id)
                else:
                    lists['lower'].append(seed_id)

        # Shuffle the list to avoid that the same albums are shown to the user

        for feature, lists in alternative_song_dic.items():
            if len(lists['higher']) > 0:
                random.shuffle(lists['higher'])
                lists['higher'] = lists['higher'][:6]
            if len(lists['lower']) > 0:
                random.shuffle(lists['lower'])
                lists['lower'] = lists['lower'][:6]

        return alternative_song_dic

    '''
    
    Calculate experiment
    
    '''

    def calculate_recommendations(self, seed_id, features):

        # Initizalize tokengetter

        @spotify.tokengetter
        def get_spotify_oauth_token():
            return session.get('oauth_token')

        # GET THE SET OF RECOMMENDATIONS

        recommendations = spotify.request(
            '/v1/recommendations?market=NL&seed_tracks=' + str(seed_id) + '&limit=100')

        self.recommendations = {x["id"]: x for x in recommendations.data['tracks']}

        track_ids_string = ''
        for identifier in list(self.recommendations.keys()):
            track_ids_string += str(identifier) + ','

        track_ids_string = track_ids_string[:-1]

        features_recommended_tracks = spotify.request('/v1/audio-features/?ids=' + str(track_ids_string))

        for track in features_recommended_tracks.data['audio_features']:
            for F in features:
                # Try to add the features to the dictionary. If this gives an error, the song is not in the dictionary
                self.recommendations[track['id']][F] = track[F]

        self.df_features = pd.DataFrame(features_recommended_tracks.data['audio_features'])
        self.df_features.set_index('id', inplace=True)
        print(self.df_features.head())

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

        self.recommendations_to_user = {'condition_1': {'list_1': [], 'list_2': []},
                                        'condition_2': {'list_1': [], 'list_2': []},
                                        'condition_3': {'list_1': [], 'list_2': []}}

        '''
        
        CREATE CONDITION 1
        
        '''

        # LIST 1 - PEAK_END

        self.recommendations_to_user['condition_1']['list_1'].append(low[0])
        self.recommendations_to_user['condition_1']['list_1'].append(high[0])
        self.recommendations_to_user['condition_1']['list_1'].append(low[1])
        self.recommendations_to_user['condition_1']['list_1'].append(low[2])
        self.recommendations_to_user['condition_1']['list_1'].append(end[0])

        # LIST 2 - AVERAGE

        self.recommendations_to_user['condition_1']['list_2'].append(peak_end_value[0])
        self.recommendations_to_user['condition_1']['list_2'].append(peak_end_value[1])
        self.recommendations_to_user['condition_1']['list_2'].append(peak_end_value[2])
        self.recommendations_to_user['condition_1']['list_2'].append(peak_end_value[3])
        self.recommendations_to_user['condition_1']['list_2'].append(peak_end_value[4])

        '''

        CREATE CONDITION 2

        '''

        # LIST 1 - PEAK_END

        self.recommendations_to_user['condition_2']['list_1'].append(low[0])
        self.recommendations_to_user['condition_2']['list_1'].append(high[0])
        self.recommendations_to_user['condition_2']['list_1'].append(low[1])
        self.recommendations_to_user['condition_2']['list_1'].append(low[2])
        self.recommendations_to_user['condition_2']['list_1'].append(end[0])

        # LIST 2 - PEAK_END

        self.recommendations_to_user['condition_2']['list_2'].append(middle[0])
        self.recommendations_to_user['condition_2']['list_2'].append(middle[1])
        self.recommendations_to_user['condition_2']['list_2'].append(middle[2])
        self.recommendations_to_user['condition_2']['list_2'].append(middle[3])
        self.recommendations_to_user['condition_2']['list_2'].append(middle[4])

        '''

        CREATE CONDITION 3

        '''

        # LIST 1 - PEAK_END

        self.recommendations_to_user['condition_3']['list_1'].append(low[0])
        self.recommendations_to_user['condition_3']['list_1'].append(high[0])
        self.recommendations_to_user['condition_3']['list_1'].append(low[1])
        self.recommendations_to_user['condition_3']['list_1'].append(low[2])
        self.recommendations_to_user['condition_3']['list_1'].append(end[0])

        # LIST 2 - PEAK_END

        self.recommendations_to_user['condition_3']['list_2'].append(average[0])
        self.recommendations_to_user['condition_3']['list_2'].append(average[1])
        self.recommendations_to_user['condition_3']['list_2'].append(average[2])
        self.recommendations_to_user['condition_3']['list_2'].append(average[3])
        self.recommendations_to_user['condition_3']['list_2'].append(average[4])

        self.feature_values = {'condition_1': {'list_1': [], 'list_2': []},
                               'condition_2': {'list_1': [], 'list_2': []},
                               'condition_3': {'list_1': [], 'list_2': []}}

        for condition, lists in self.recommendations_to_user.items():
            for l, i in lists.items():
                for identifier in i:
                    self.feature_values[condition][l].append(self.recommendations[identifier][features[0]])

        # row and column sharing
        x = [1, 2, 3, 4, 5]
        f, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2)

        # SET TITLE
        axis_font = {'fontname': 'Arial', 'size': '14'}

        ax1.set_title('List 1')
        ax2.set_title('List 2')

        ax1.set_ylim([0, 1])
        ax2.set_ylim([0, 1])
        ax3.set_ylim([0, 1])
        ax4.set_ylim([0, 1])
        ax5.set_ylim([0, 1])
        ax6.set_ylim([0, 1])

        ax1.plot(x, self.feature_values['condition_1']['list_1'])
        ax2.plot(x, self.feature_values['condition_1']['list_2'])
        ax3.plot(x, self.feature_values['condition_2']['list_1'])
        ax4.plot(x, self.feature_values['condition_2']['list_2'])
        ax5.plot(x, self.feature_values['condition_3']['list_1'])
        ax6.plot(x, self.feature_values['condition_3']['list_2'])
        plt.savefig('Peak-End_plot of ' + str(self.name) + '.pdf')


class Analytics(object):

    def __init__(self):
        self.features_of_interest = ['valence', 'energy', 'danceability', "speechiness", "acousticness",
                                     "instrumentalness", "liveness"]

    def user_characteristics_plot(self, user, song_display_dic):

        datalists = {}

        for feature in self.features_of_interest:
            datalists[feature] = []

        for track, features in song_display_dic.items():
            for f in self.features_of_interest:
                datalists[f].append(features[f])

        # Two subplots, unpack the axes array immediately
        n_bins = 20
        plt.rcParams.update({'font.size': 6})
        f, (ax1, ax2, ax3, ax4, ax5, ax6, ax7) = plt.subplots(1, len(self.features_of_interest), sharey=True)
        ax1.hist(datalists[self.features_of_interest[0]], n_bins, normed=1, histtype='bar', stacked=True)
        ax2.hist(datalists[self.features_of_interest[1]], n_bins, normed=1, histtype='bar', stacked=True)
        ax3.hist(datalists[self.features_of_interest[2]], n_bins, normed=1, histtype='bar', stacked=True)
        ax4.hist(datalists[self.features_of_interest[3]], n_bins, normed=1, histtype='bar', stacked=True)
        ax5.hist(datalists[self.features_of_interest[4]], n_bins, normed=1, histtype='bar', stacked=True)
        ax6.hist(datalists[self.features_of_interest[5]], n_bins, normed=1, histtype='bar', stacked=True)
        ax7.hist(datalists[self.features_of_interest[6]], n_bins, normed=1, histtype='bar', stacked=True)

        ax1.set_title(self.features_of_interest[0], fontsize=6)
        ax2.set_title(self.features_of_interest[1], fontsize=6)
        ax3.set_title(self.features_of_interest[2], fontsize=6)
        ax4.set_title(self.features_of_interest[3], fontsize=6)
        ax5.set_title(self.features_of_interest[4], fontsize=6)
        ax6.set_title(self.features_of_interest[5], fontsize=6)
        ax7.set_title(self.features_of_interest[6], fontsize=6)

        ax1.set_xlim(0, 1)
        ax2.set_xlim(0, 1)
        ax3.set_xlim(0, 1)
        ax4.set_xlim(0, 1)
        ax5.set_xlim(0, 1)
        ax6.set_xlim(0, 1)
        ax7.set_xlim(0, 1)

        with open('user_data.json') as data_file:
            data = json.load(data_file)

        data[user] = datalists

        with open('user_data.json', 'w') as file:
            file.write(json.dumps(data))

        plt.savefig('figure_map/user_profile_' + user + '.png', dpi=1000)
