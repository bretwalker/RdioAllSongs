import cPickle as pickle
import re
import urllib
import unicodedata

from credentials import *

from Rdio.rdio import Rdio
from BeautifulSoup import BeautifulSoup

token = USER_OAUTH_CREDENTIALS
rdio = Rdio(API_CREDENTIALS, token)
word_pattern = re.compile('[\W_]+')
missing_song_pattern = re.compile(r'^(.*)  by  (.*)$', re.MULTILINE)

def search(song, artist):
    song = song.strip()
    artist = artist.strip()
    search_results = rdio.call('search', {'query':' '.join((song, artist)), 'types':'Track', 'count':'100'})
    
    artist_clean = word_pattern.sub('', artist.lower().replace('the', ''))
    song_clean = word_pattern.sub('', song.lower().replace('the', ''))
    song_set = set(song.lower().replace('the', '').split())
    
    if search_results['status'] == 'ok':
        for search_result in search_results['result']['results']:            
            artist_search_clean = word_pattern.sub('', search_result['artist'].lower().replace('the', ''))
            song_search_clean = word_pattern.sub(' ', search_result['name'].lower().replace('the', ''))
            song_search_set = set(search_result['name'].lower().replace('the', '').split())

            # if 30% of the words are the same, it's probably the same song. Probably.
            if (artist_clean == artist_search_clean or artist_clean.replace('and', '') == artist_search_clean.replace('and', '')) and len(list(song_set & song_search_set))  / float(max(len(song_set), len(song_search_set))) > .3:
                return search_result['key']
    
    return None
    
def update_existing_playlists():
    playlists = rdio.call('getUserPlaylists', {'user':'s6312938', 'type':'owned', 'extras':'description,tracks', 'count': '1000'})

    if playlists['status'] == 'ok':
        for playlist in playlists['result']:
            missing_song_count = 0
            found_song_count = 0
            description = ''
            
            for song in missing_song_pattern.findall(playlist['description']):
                missing_song_count = missing_song_count + 1
                search_result = search(song[0], song[1])

                if search_result:
                    found_song_count = found_song_count + 1
                    updated_playlist = rdio.call('addToPlaylist', {'playlist': playlist['key'], 
                                                           'tracks': search_result,
                                                           'extras':'description,tracks'})
                                                           
                    if updated_playlist['status'] == 'ok' and any(t['key'] == search_result for t in updated_playlist['result']['tracks']):
                        if description == '':
                            description = updated_playlist['result']['description']

                        description = description.replace(song[0] + '  by  ' + song[1] + '\n', '')
                            
                        rdio.call('setPlaylistFields', {'playlist': updated_playlist['result']['key'], 
                                                        'name': updated_playlist['result']['name'],
                                                        'description': description})
                
                # If there are no more missing songs, remove the "Songs not found on Rdio:" text
                if missing_song_count > 0 and found_song_count == missing_song_count:                                        
                    rdio.call('setPlaylistFields', {'playlist': updated_playlist['result']['key'], 
                                                    'name': updated_playlist['result']['name'],
                                                    'description': description.replace('Songs not found on Rdio:\n', '')})
    
def load_new_episodes():
    try:
        loaded_urls = pickle.load( open( 'loaded_urls.p', 'rb' ) )
    except IOError:
        loaded_urls = []
        pickle.dump( loaded_urls, open( 'loaded_urls.p', 'wb' ) )    

    f = urllib.urlopen('http://www.npr.org/blogs/allsongs/163479981/our-show') 
    soup = BeautifulSoup(f)

    stories = soup.findAll('article', {'class':'story story-blogpost clearfix'})
    stories.reverse()

    for story in stories:
        url = story.div.h1.a['href']
        if url not in loaded_urls:
            f = urllib.urlopen(url) 
            soup = BeautifulSoup(f)

            song_keys = []
            songs_not_found = []

            description = 'Songs from All Songs Considered '
            date = soup.findAll('div', {'class':'dateblock'})[0].time.span.contents[0]
            description = description + date

            title = soup.findAll('div', {'class': 'storytitle'})[0].h1.contents[0]

            songs = soup.findAll('div', {'class': re.compile(r".*\bplaylistitem\b.*")})
            for song_data in songs:
                try:
                    artist = song_data.div.h4.contents[0].strip()
                except TypeError:
                    artist = song_data.div.h4.a.contents[0].strip()

                song = song_data.div.ul.li.findNextSibling('li').contents[1].strip()
                search_result = search(unicodedata.normalize('NFKD', song).encode('ascii','ignore'),
                                       unicodedata.normalize('NFKD', artist).encode('ascii','ignore'))
            
                if search_result:  
                    song_keys.append(search_result)
                else:
                    songs_not_found.append(song + '  by  ' + artist)

            if len(songs_not_found) > 0:
                description = description + '\nSongs not found on Rdio:\n' +'\n'.join(songs_not_found)
            
            description = description + '\n' + url + '\n'

            playlist = None
            if len(song_keys) > 0:
                playlist = rdio.call('createPlaylist', {'name': title, 
                                                        'description': unicodedata.normalize('NFKD', description).encode('ascii','ignore'), 
                                                        'tracks':','.join(song_keys)})

            if playlist:
                loaded_urls.append(url)
                pickle.dump( loaded_urls, open( 'loaded_urls.p', 'wb' ) )
            
            
if __name__ == "__main__":
    update_existing_playlists()
    #load_new_episodes()