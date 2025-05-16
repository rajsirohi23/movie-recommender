import pickle
import requests
from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# Load movie data
try:
    # Try to load movies with TMDB IDs if available
    movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
    # Check if we have a DataFrame or dictionary
    if isinstance(movies_dict, dict):
        movies = pd.DataFrame(movies_dict)
    else:
        movies = movies_dict
    
    # Check if 'tmdb_id' column exists
    has_tmdb_ids = 'tmdb_id' in movies.columns
    
except:
    try:
        # Try alternative file path
        movies = pickle.load(open('movies.pkl', 'rb'))
        has_tmdb_ids = 'tmdb_id' in movies.columns
    except Exception as e:
        print(f"Error loading movie data: {e}")
        movies = pd.DataFrame({'title': ['Sample Movie']})  # Fallback
        has_tmdb_ids = False

# Load similarity matrix
similarity = pickle.load(open('similarity.pkl', 'rb'))

# TMDB API key
TMDB_API_KEY = 'ad70c8640bb8ccf4c5d28226fbb602b4'

def fetch_poster(movie_title, movie_id=None):
    """
    Fetch movie poster using multiple methods to ensure reliability
    """
    # Placeholder to return if all methods fail
    default_img = "https://via.placeholder.com/300x450?text=No+Image"
    
    try:
        # Common headers for all requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        # METHOD 1: Direct ID lookup if we have the ID
        if movie_id:
            try:
                print(f"Trying direct ID lookup for movie ID: {movie_id}")
                url = f"https://api.themoviedb.org/3/movie/{movie_id}"
                params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                        print(f"Success with method 1: {poster_url}")
                        return poster_url
                    else:
                        print("Movie found by ID, but no poster available")
                else:
                    print(f"ID lookup failed with status code: {response.status_code}")
            except Exception as e:
                print(f"Error with direct ID lookup: {e}")
        
        # METHOD 2: Search by exact title
        try:
            print(f"Trying search for exact title: '{movie_title}'")
            url = "https://api.themoviedb.org/3/search/movie"
            params = {'api_key': TMDB_API_KEY, 'query': movie_title, 'include_adult': 'false'}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    # Try to find an exact match first
                    for result in data['results']:
                        if result['title'].lower() == movie_title.lower() and result.get('poster_path'):
                            poster_url = f"https://image.tmdb.org/t/p/w500{result['poster_path']}"
                            print(f"Success with method 2 (exact match): {poster_url}")
                            return poster_url
                    
                    # If no exact match, take the first result with a poster
                    for result in data['results']:
                        if result.get('poster_path'):
                            poster_url = f"https://image.tmdb.org/t/p/w500{result['poster_path']}"
                            print(f"Success with method 2 (first result): {poster_url}")
                            return poster_url
                    
                print("No results found with posters")
            else:
                print(f"Search failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error with title search: {e}")
        
        # METHOD 3: Try with simplified title (remove year and special chars if present)
        try:
            # Clean up title if it has year or special characters
            import re
            simplified_title = re.sub(r'\([^)]*\)', '', movie_title).strip()  # Remove anything in parentheses
            simplified_title = re.sub(r'[^\w\s]', '', simplified_title).strip()  # Remove special chars
            
            if simplified_title != movie_title:
                print(f"Trying with simplified title: '{simplified_title}'")
                url = "https://api.themoviedb.org/3/search/movie"
                params = {'api_key': TMDB_API_KEY, 'query': simplified_title, 'include_adult': 'false'}
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('results') and len(data['results']) > 0:
                        for result in data['results']:
                            if result.get('poster_path'):
                                poster_url = f"https://image.tmdb.org/t/p/w500{result['poster_path']}"
                                print(f"Success with method 3: {poster_url}")
                                return poster_url
                else:
                    print(f"Simplified search failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error with simplified title search: {e}")

        # If all methods failed, return default image
        print(f"All poster fetch methods failed for '{movie_title}'")
        return default_img
    
    except Exception as e:
        print(f"Unexpected error in fetch_poster: {e}")
        return default_img

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            movie = request.form.get('movie')
            if not movie:
                return render_template('index.html', 
                                      movie_list=movies['title'].values,
                                      error="Please select a movie")
            
            # Find the selected movie in our dataset
            movie_indices = movies.index[movies['title'] == movie].tolist()
            if not movie_indices:
                return render_template('index.html', 
                                      movie_list=movies['title'].values,
                                      error=f"Movie '{movie}' not found in database")
                
            idx = movie_indices[0]
            
            # Get similarity scores
            distances = similarity[idx]
            movie_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
            
            recommended_movies = []
            recommended_posters = []
            
            for i in movie_list:
                movie_idx = i[0]
                title = movies.iloc[movie_idx]['title']
                
                # Use TMDB ID if available, otherwise use title
                tmdb_id = None
                if has_tmdb_ids:
                    tmdb_id = movies.iloc[movie_idx].get('tmdb_id')
                    if pd.isna(tmdb_id):  # Check if it's NaN
                        tmdb_id = None
                        
                print(f"Fetching poster for: {title}{' (with ID)' if tmdb_id else ''}")
                poster_url = fetch_poster(title, movie_id=tmdb_id)
                recommended_movies.append(title)
                recommended_posters.append(poster_url)
            
            # Zip the movies and posters together for template
            movie_recommendations = list(zip(recommended_movies, recommended_posters))
            
            return render_template('index.html',
                                  movie_list=movies['title'].values,
                                  selected_movie=movie,
                                  recommended_movies=movie_recommendations)
        
        except Exception as e:
            print(f"Error in recommendation: {e}")
            return render_template('index.html', 
                                  movie_list=movies['title'].values, 
                                  error=f"An error occurred: {str(e)}")
    
    # For GET requests, just show the form
    return render_template('index.html', movie_list=movies['title'].values)

if __name__ == '__main__':
    app.run(debug=True)